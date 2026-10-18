"""Leakage checks, label-free selection, and region-level evaluation."""
from __future__ import annotations
from collections import defaultdict
import numpy as np


def check_splits(records, splits):
    """Require mutually exclusive region sets; no image can cross partitions."""
    names = ("train", "validation", "test")
    if set(splits) != set(names):
        raise ValueError("Expected train, validation and test region lists")
    for i, a in enumerate(names):
        if not splits[a] or len(splits[a]) != len(set(splits[a])):
            raise ValueError(f"Empty or duplicate regions: {a}")
        for b in names[i + 1:]:
            if set(splits[a]) & set(splits[b]):
                raise ValueError(f"Region leakage between {a} and {b}")
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate original-image identifiers")
    known = {r["region"] for r in records}
    if set().union(*(set(v) for v in splits.values())) - known:
        raise ValueError("A split refers to a region absent from the manifest")


def select(features, regions, budget, strategy, seed):
    """Selection consumes RGB-derived features and source-region names only."""
    x = np.asarray(features, dtype=np.float64)
    regions = np.asarray(regions)
    if x.ndim != 2 or len(x) != len(regions) or not np.isfinite(x).all():
        raise ValueError("Invalid feature matrix")
    if not 0 < budget <= len(x):
        raise ValueError("Budget must fit the candidate pool")
    valid = {"random", "kcenter", "region_random", "region_kcenter", "permuted_region_kcenter"}
    if strategy not in valid:
        raise ValueError(f"Strategy must be one of {sorted(valid)}")
    rng = np.random.default_rng(seed)
    if strategy == "permuted_region_kcenter":
        # Negative control: preserve group sizes but break real geography.
        regions = regions[np.random.default_rng(seed + 20261018).permutation(len(regions))]
        strategy = "region_kcenter"
    if strategy == "random":
        return rng.choice(len(x), budget, replace=False).tolist()
    # Cosine-distance k-center on normalized image descriptors.
    x = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)
    selected = []
    min_distance = np.full(len(x), np.inf)
    remaining = np.ones(len(x), dtype=bool)
    unique_regions = np.unique(regions)
    region_counts = {r: 0 for r in unique_regions}
    # A random fixed tie order prevents alphabetical advantages.
    tie_order = rng.permutation(len(x))
    for _ in range(budget):
        eligible = remaining.copy()
        if strategy.startswith("region_"):
            available = [r for r in unique_regions if np.any(remaining & (regions == r))]
            minimum = min(region_counts[r] for r in available)
            balanced = [r for r in available if region_counts[r] == minimum]
            eligible &= np.isin(regions, balanced)
        candidates = tie_order[eligible[tie_order]]
        if strategy.endswith("random") or not selected:
            index = int(rng.choice(candidates))
        else:
            index = int(candidates[np.argmax(min_distance[candidates])])
        selected.append(index)
        remaining[index] = False
        region_counts[regions[index]] += 1
        distance = np.maximum(0.0, 1.0 - x @ x[index])
        min_distance = np.minimum(min_distance, distance)
    return selected


def candidate_pool(records, source_regions, profile="all", seed=20261018):
    """Select candidate IDs without labels, with equal total counts across profiles.

    For the 5-per-region pilot, balanced3 and skewed5_1 both use 3R images
    when the number of source regions R is even. Heavy regions are selected
    by an independent fixed random permutation, not by their outcomes.
    """
    source_regions = sorted(source_regions)
    rng = np.random.default_rng(seed)
    heavy = set(rng.permutation(source_regions)[:len(source_regions) // 2])
    if profile not in {"all", "balanced3", "skewed5_1"}:
        raise ValueError("Unknown candidate-pool profile")
    if profile == "skewed5_1" and len(source_regions) % 2:
        raise ValueError("Skewed5_1 requires an even number of source regions")
    result = []
    for region in source_regions:
        group = sorted([r for r in records if r["region"] == region], key=lambda r: r["id"])
        count = len(group) if profile == "all" else (3 if profile == "balanced3" else (5 if region in heavy else 1))
        if len(group) < count:
            raise ValueError(f"Not enough candidates in {region} for {profile}")
        region_rng = np.random.default_rng(seed + sum((i+1)*ord(c) for i, c in enumerate(region)))
        result.extend(group[i] for i in sorted(region_rng.choice(len(group), count, replace=False)))
    return result


def confusion(truth, prediction, classes=8, ignore=-1):
    y, p = np.asarray(truth), np.asarray(prediction)
    if y.shape != p.shape:
        raise ValueError("Prediction and ground truth must have the same shape")
    keep = y != ignore
    if np.any((y[keep] < 0) | (y[keep] >= classes)):
        raise ValueError("Unexpected ground-truth class index")
    if np.any((p[keep] < 0) | (p[keep] >= classes)):
        raise ValueError("Unexpected predicted class index")
    return np.bincount(
        classes * y[keep].astype(np.int64) + p[keep].astype(np.int64),
        minlength=classes * classes,
    ).reshape(classes, classes)


def scores(matrix):
    cm = np.asarray(matrix, dtype=np.int64)
    denominator = cm.sum(0) + cm.sum(1) - np.diag(cm)
    iou = np.divide(np.diag(cm), denominator, out=np.full(len(cm), np.nan), where=denominator > 0)
    present = cm.sum(1) > 0
    return {
        "miou": float(np.mean(iou[present])) if np.any(present) else None,
        "union_class_miou": float(np.nanmean(iou)) if np.any(denominator > 0) else None,
        "class_iou": [None if not np.isfinite(a) else float(a) for a in iou],
        "valid_classes": int(np.sum(present)),
        "union_valid_classes": int(np.sum(denominator > 0)),
        "primary_class_set": "classes present in ground truth; fixed across strategies",
        "pixel_accuracy": float(np.trace(cm) / cm.sum()) if cm.sum() else None,
        "evaluated_pixels": int(cm.sum()),
    }


def aggregate(image_results):
    by_region = defaultdict(lambda: np.zeros((8, 8), dtype=np.int64))
    for r in image_results:
        by_region[r["region"]] += np.asarray(r["confusion"], dtype=np.int64)
    if not by_region:
        raise ValueError("No evaluation images")
    region_results = {k: scores(v) for k, v in sorted(by_region.items())}
    region_miou = [v["miou"] for v in region_results.values() if v["miou"] is not None]
    return {
        "regions": region_results,
        "equal_region_miou": float(np.mean(region_miou)),
        "worst_region_miou": float(np.min(region_miou)),
        "pooled_pixel_scores": scores(sum(by_region.values())),
    }


def paired_region_interval(a, b, seed=20261018, repetitions=10000):
    """Bootstrap matched region differences after the caller averages seeds."""
    if set(a) != set(b) or len(a) < 3:
        raise ValueError("At least three exactly matched regions are required")
    regions = sorted(a)
    differences = np.array([a[r] - b[r] for r in regions], dtype=float)
    if not np.isfinite(differences).all():
        raise ValueError("Nonfinite paired differences")
    rng = np.random.default_rng(seed)
    samples = differences[rng.integers(0, len(regions), (repetitions, len(regions)))].mean(1)
    return {"difference": float(differences.mean()),
            "lower": float(np.quantile(samples, .025)),
            "upper": float(np.quantile(samples, .975)),
            "regions": regions, "repetitions": repetitions,
            "unit": "held-out region", "seed": seed}

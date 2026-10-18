"""Source-image selection using descriptors, identifiers and source groups only.

No selector accepts masks, classes, validation data or target data. See
docs/v2_selection_methods.md for objective definitions and adaptation boundaries.
"""
from __future__ import annotations

import numpy as np

try:  # Support both ``import v2_selection`` and ``import code.v2_selection``.
    from .core import select as _legacy_select
except ImportError:
    from core import select as _legacy_select


LEGACY_STRATEGIES = frozenset({
    "random", "kcenter", "region_random", "region_kcenter",
    "permuted_region_kcenter",
})
STRATEGIES = LEGACY_STRATEGIES | {"kmeanspp", "facility_location", "fd_roundrobin"}


def _unit_rows(x: np.ndarray) -> np.ndarray:
    # Scaling first avoids overflow for large but finite descriptor values.
    scale = np.max(np.abs(x), axis=1, keepdims=True)
    if np.any(scale == 0):
        raise ValueError("Cosine-based new strategies require nonzero descriptors")
    scaled = x / scale
    return scaled / np.linalg.norm(scaled, axis=1, keepdims=True)


def _kmeanspp_indices(x: np.ndarray, budget: int, rng) -> list[int]:
    """D-squared seeding on unit rows; returned centers are actual pool items."""
    selected = [int(rng.choice(len(x)))]
    remaining = np.ones(len(x), dtype=bool)
    remaining[selected[0]] = False
    nearest_sq = np.full(len(x), np.inf)
    while len(selected) < budget:
        delta = x - x[selected[-1]]
        squared = np.einsum("ij,ij->i", delta, delta)
        nearest_sq = np.minimum(nearest_sq, squared)
        candidates = np.flatnonzero(remaining)
        weights = nearest_sq[candidates]
        total = float(weights.sum())
        if total == 0.0:
            index = int(rng.choice(candidates))
        else:
            index = int(rng.choice(candidates, p=weights / total))
        selected.append(index)
        remaining[index] = False
    return selected


def _facility_location_indices(x: np.ndarray, budget: int, rng) -> list[int]:
    """Greedy maximization of sum_i max_{j in S} clip((cos(i,j)+1)/2)."""
    similarity = np.clip((x @ x.T + 1.0) / 2.0, 0.0, 1.0)
    covered = np.zeros(len(x), dtype=np.float64)
    remaining = np.ones(len(x), dtype=bool)
    tie_order = rng.permutation(len(x))
    selected = []
    for _ in range(budget):
        candidates = tie_order[remaining[tie_order]]
        gains = np.maximum(similarity[:, candidates] - covered[:, None], 0).sum(axis=0)
        index = int(candidates[np.argmax(gains)])
        selected.append(index)
        remaining[index] = False
        covered = np.maximum(covered, similarity[:, index])
    return selected


def _fd_labels(x: np.ndarray, rng, n_clusters: int = 12,
               max_iter: int = 100) -> np.ndarray:
    """Euclidean Lloyd partition with explicit, disjoint empty-cluster repair."""
    k = min(n_clusters, len(x))
    centers = x[_kmeanspp_indices(x, k, rng)].copy()
    tie_order = rng.permutation(len(x))
    previous = None
    for _ in range(max_iter):
        distances = np.empty((len(x), k), dtype=np.float64)
        for cluster in range(k):
            delta = x - centers[cluster]
            distances[:, cluster] = np.einsum("ij,ij->i", delta, delta)
        labels = np.argmin(distances, axis=1)
        counts = np.bincount(labels, minlength=k)
        errors = distances[np.arange(len(x)), labels]
        for empty in np.flatnonzero(counts == 0):
            # A donor must retain at least one member. Recompute eligibility
            # after every move; a point always has exactly one cluster label.
            eligible = tie_order[counts[labels[tie_order]] > 1]
            donor = int(eligible[np.argmax(errors[eligible])])
            counts[labels[donor]] -= 1
            labels[donor] = empty
            counts[empty] += 1
            errors[donor] = 0.0
        centers = np.stack([x[labels == cluster].mean(axis=0) for cluster in range(k)])
        if previous is not None and np.array_equal(labels, previous):
            break
        previous = labels.copy()
    return labels


def _fd_roundrobin_indices(x: np.ndarray, budget: int, rng) -> list[int]:
    labels = _fd_labels(x, rng)
    groups = [rng.permutation(np.flatnonzero(labels == c)).tolist()
              for c in range(int(labels.max()) + 1)]
    order = rng.permutation(len(groups))
    selected = []
    position = 0
    while len(selected) < budget:
        for cluster in order:
            if position < len(groups[cluster]):
                selected.append(int(groups[cluster][position]))
                if len(selected) == budget:
                    return selected
        position += 1
    return selected


def select_images(ids: list[str], descriptors: np.ndarray, regions: list[str],
                  budget: int, strategy: str, seed: int) -> list[str]:
    """Return exactly ``budget`` unique IDs, without modifying caller inputs.

    Descriptors must be a finite real N-by-D matrix, D >= 1. New cosine-based
    strategies reject zero rows. Legacy strategies preserve core.select's
    behavior, including its zero-row normalization and seeded tie handling.
    """
    if (not isinstance(budget, (int, np.integer)) or isinstance(budget, (bool, np.bool_))
            or not 0 < budget <= len(ids)):
        raise ValueError("Budget must be a positive integer within the candidate pool")
    if (not isinstance(seed, (int, np.integer)) or isinstance(seed, (bool, np.bool_))
            or seed < 0):
        raise ValueError("Seed must be a nonnegative integer")
    if not isinstance(strategy, str) or strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy; expected one of {sorted(STRATEGIES)}")
    if (any(not isinstance(i, str) or not i for i in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("Image identifiers must be unique nonempty strings")
    if (len(regions) != len(ids)
            or any(not isinstance(r, str) or not r for r in regions)):
        raise ValueError("Each candidate requires a nonempty source-region string")
    try:
        raw = np.asarray(descriptors)
        if np.iscomplexobj(raw):
            raise ValueError("Descriptors must be real")
        x = np.array(raw, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("Descriptors must be a real numeric matrix") from exc
    if (x.ndim != 2 or x.shape[0] != len(ids) or x.shape[1] < 1
            or not np.isfinite(x).all()):
        raise ValueError("Descriptors must be a finite N-by-D matrix with D >= 1")
    budget, seed = int(budget), int(seed)
    if strategy in LEGACY_STRATEGIES:
        indices = _legacy_select(x, list(regions), budget, strategy, seed)
    else:
        x = _unit_rows(x)
        rng = np.random.default_rng(seed)
        selector = {
            "kmeanspp": _kmeanspp_indices,
            "facility_location": _facility_location_indices,
            "fd_roundrobin": _fd_roundrobin_indices,
        }[strategy]
        indices = selector(x, budget, rng)
    return [ids[index] for index in indices]

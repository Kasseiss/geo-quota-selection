"""Add source-group mean coverage controls without changing v2_selection.

Weights apply to represented candidate rows, not selected representative columns.
The original eight policies delegate unchanged to the original selector.
"""
from __future__ import annotations

import numpy as np

try:
    from . import v2_selection as base
except ImportError:
    import v2_selection as base


REGION_WEIGHTED = "region_weighted_facility_location"
PERMUTED_WEIGHTED = "permuted_region_weighted_facility_location"
WEIGHTED_STRATEGIES = frozenset({REGION_WEIGHTED, PERMUTED_WEIGHTED})
STRATEGIES = base.STRATEGIES | WEIGHTED_STRATEGIES
PERMUTATION_SEED_OFFSET = 20261018


def _group_memberships(regions, seed, permuted=False):
    groups = np.asarray(regions).copy()
    if permuted:
        # Separate RNG: exactly the legacy negative-control membership rule,
        # without consuming any randomness from facility-location tie ordering.
        groups = groups[np.random.default_rng(seed + PERMUTATION_SEED_OFFSET).permutation(len(groups))]
    return groups


def _group_weights(regions, seed, permuted=False):
    groups = _group_memberships(regions, seed, permuted)
    _, inverse, counts = np.unique(groups, return_inverse=True, return_counts=True)
    return 1.0 / (len(counts) * counts[inverse])


def _validate_inputs(ids, descriptors, regions, budget, seed):
    """Mirror the established input contract without calling or altering a policy."""
    if (not isinstance(budget, (int, np.integer)) or isinstance(budget, (bool, np.bool_))
            or not 0 < budget <= len(ids)):
        raise ValueError("Budget must be a positive integer within the candidate pool")
    if (not isinstance(seed, (int, np.integer)) or isinstance(seed, (bool, np.bool_)) or seed < 0):
        raise ValueError("Seed must be a nonnegative integer")
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Image identifiers must be unique nonempty strings")
    if len(regions) != len(ids) or any(not isinstance(r, str) or not r for r in regions):
        raise ValueError("Each candidate requires a nonempty source-region string")
    try:
        raw = np.asarray(descriptors)
        if np.iscomplexobj(raw):
            raise ValueError("Descriptors must be real")
        x = np.array(raw, dtype=np.float64, copy=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Descriptors must be a real numeric matrix") from exc
    if (x.ndim != 2 or x.shape[0] != len(ids) or x.shape[1] < 1
            or not np.isfinite(x).all()):
        raise ValueError("Descriptors must be a finite N-by-D matrix with D >= 1")
    return x


def _weighted_facility_indices(x, weights, budget, seed):
    # This normalization/similarity/tie sequence is identical to the base FL.
    x = base._unit_rows(x)
    similarity = np.clip((x @ x.T + 1.0) / 2.0, 0.0, 1.0)
    covered = np.zeros(len(x), dtype=np.float64)
    remaining = np.ones(len(x), dtype=bool)
    tie_order = np.random.default_rng(seed).permutation(len(x))
    selected = []
    for _ in range(budget):
        candidates = tie_order[remaining[tie_order]]
        # Candidate i's coverage utility receives w_i; the weight is outside
        # max_j. Multiplying columns instead would be a different objective.
        gains = (weights[:, None] * np.maximum(
            similarity[:, candidates] - covered[:, None], 0.0)).sum(axis=0)
        index = int(candidates[np.argmax(gains)])
        selected.append(index)
        remaining[index] = False
        covered = np.maximum(covered, similarity[:, index])
    return selected


def select_images(ids: list[str], descriptors: np.ndarray, regions: list[str],
                  budget: int, strategy: str, seed: int) -> list[str]:
    """Select unique source IDs using only fixed descriptors and group metadata.

    Balanced group sizes delegate directly to the base facility_location policy,
    preserving its sequence exactly, including floating-point tie behavior.
    """
    if not isinstance(strategy, str) or strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy; expected one of {sorted(STRATEGIES)}")
    if strategy in base.STRATEGIES:
        return base.select_images(ids, descriptors, regions, budget, strategy, seed)
    x = _validate_inputs(ids, descriptors, regions, budget, seed)
    budget, seed = int(budget), int(seed)
    weights = _group_weights(regions, seed, strategy == PERMUTED_WEIGHTED)
    if np.all(weights == weights[0]):
        return base.select_images(ids, descriptors, regions, budget, "facility_location", seed)
    indices = _weighted_facility_indices(x, weights, budget, seed)
    return [ids[i] for i in indices]

"""Small local algorithm checks; no downloads, model training or formal runs."""
from collections import Counter
import unittest

import numpy as np

from core import select as legacy_select
from v2_selection import STRATEGIES, _fd_labels, _kmeanspp_indices, select_images


class ChoiceProbe:
    """Expose the distribution requested by the selector, without sampling it."""
    def __init__(self):
        self.calls = []

    def choice(self, candidates, p=None):
        self.calls.append((np.asarray(candidates).copy(), None if p is None else p.copy()))
        return 0 if np.isscalar(candidates) else candidates[0]


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.x = np.random.default_rng(23).normal(size=(29, 5))
        self.ids = [f"image-{i}" for i in range(len(self.x))]
        self.regions = ["a"] * 3 + ["b"] * 9 + ["c"] * 17

    def test_budget_reproducibility_and_input_preservation(self):
        before_x, before_ids, before_regions = self.x.copy(), self.ids.copy(), self.regions.copy()
        for strategy in STRATEGIES:
            for budget in (1, 12, len(self.ids)):
                with self.subTest(strategy=strategy, budget=budget):
                    result = select_images(self.ids, self.x, self.regions, budget, strategy, 91)
                    self.assertEqual(len(result), budget)
                    self.assertEqual(len(set(result)), budget)
                    self.assertTrue(set(result) <= set(self.ids))
                    self.assertEqual(result, select_images(
                        self.ids, self.x, self.regions, budget, strategy, 91))
        np.testing.assert_array_equal(self.x, before_x)
        self.assertEqual(self.ids, before_ids)
        self.assertEqual(self.regions, before_regions)

    def test_legacy_exact_sequences_and_permuted_group_sizes(self):
        for seed in (0, 7, 20261018):
            for strategy in ("random", "kcenter", "region_random", "region_kcenter",
                             "permuted_region_kcenter"):
                expected = [self.ids[i] for i in legacy_select(
                    self.x, self.regions, len(self.ids), strategy, seed)]
                self.assertEqual(select_images(self.ids, self.x, self.regions,
                                              len(self.ids), strategy, seed), expected)
            permuted = np.asarray(self.regions)[
                np.random.default_rng(seed + 20261018).permutation(len(self.ids))]
            self.assertEqual(Counter(permuted), Counter(self.regions))
            # The documented negative control must equal ordinary region-kcenter
            # with permuted memberships, including the unmodified selection seed.
            result = select_images(self.ids, self.x, self.regions, 20,
                                   "permuted_region_kcenter", seed)
            expected = select_images(self.ids, self.x, permuted.tolist(), 20,
                                     "region_kcenter", seed)
            self.assertEqual(result, expected)

    def test_region_constraint_until_exhaustion(self):
        for strategy in ("region_random", "region_kcenter"):
            selected = select_images(self.ids, self.x, self.regions,
                                     len(self.ids), strategy, 5)
            assigned = dict(zip(self.ids, self.regions))
            sizes, used = Counter(self.regions), Counter()
            for image in selected:
                available = [r for r in sizes if used[r] < sizes[r]]
                self.assertEqual(used[assigned[image]], min(used[r] for r in available))
                used[assigned[image]] += 1

    def test_kmeanspp_d_squared_probabilities(self):
        # With first center (1,0), squared Euclidean distances are 0,2,4,0.
        # Squaring cosine distance again would instead give the wrong 1:4 odds.
        x = np.array([[1., 0.], [0., 1.], [-1., 0.], [1., 0.]])
        probe = ChoiceProbe()
        self.assertEqual(_kmeanspp_indices(x, 2, probe), [0, 1])
        np.testing.assert_array_equal(probe.calls[1][0], [1, 2, 3])
        np.testing.assert_allclose(probe.calls[1][1], [1 / 3, 2 / 3, 0], atol=1e-15)

    def test_kmeanspp_degenerate_uniform_remaining(self):
        probe = ChoiceProbe()
        result = _kmeanspp_indices(np.tile([1., 0.], (4, 1)), 4, probe)
        self.assertEqual(result, [0, 1, 2, 3])
        for candidates, probabilities in probe.calls[1:]:
            self.assertIsNone(probabilities)  # NumPy choice defaults to uniform.
        np.testing.assert_array_equal(probe.calls[-1][0], [3])

    def test_facility_location_known_marginal_gains(self):
        # Hand-derived similarity matrix:
        # [[1,.5,0], [.5,1,.5], [0,.5,1]]. First point must be the middle;
        # then either endpoint, then the other. Objective increments: 2,.5,.5.
        x = np.array([[1., 0.], [0., 1.], [-1., 0.]])
        ids, regions = ["east", "north", "west"], ["r"] * 3
        similarity = np.array([[1., .5, 0.], [.5, 1., .5], [0., .5, 1.]])
        for seed in range(5):
            sequence = select_images(ids, x, regions, 3, "facility_location", seed)
            self.assertEqual(sequence[0], "north")
            previous = 0.
            for budget, expected_gain in enumerate([2., .5, .5], 1):
                prefix = select_images(ids, x, regions, budget, "facility_location", seed)
                self.assertEqual(prefix, sequence[:budget])
                objective = similarity[:, [ids.index(i) for i in prefix]].max(axis=1).sum()
                self.assertAlmostEqual(objective - previous, expected_gain)
                previous = objective

    def test_facility_location_seed_only_breaks_ties(self):
        # Every item covers everyone equally. The full sequence is tie order.
        ids, x, regions = ["a", "b", "c"], np.ones((3, 2)), ["r"] * 3
        for seed in (2, 9):
            expected = [ids[i] for i in np.random.default_rng(seed).permutation(3)]
            self.assertEqual(select_images(ids, x, regions, 3, "facility_location", seed),
                             expected)

    def test_fd_empty_repair_unique_members_and_full_coverage(self):
        # Identical rows force all but one Lloyd cluster to be empty before repair.
        x = np.tile([1., 0.], (19, 1))
        labels = _fd_labels(x, np.random.default_rng(4))
        self.assertEqual(labels.shape, (19,))
        self.assertEqual(set(labels), set(range(12)))
        self.assertEqual(sorted(Counter(labels).values()), [1] * 11 + [8])
        ids, regions = [str(i) for i in range(19)], ["r"] * 19
        result = select_images(ids, x, regions, 19, "fd_roundrobin", 4)
        self.assertEqual(set(result), set(ids))
        first_round = [labels[int(i)] for i in result[:12]]
        self.assertEqual(len(set(first_round)), 12)
        for budget in (1, 12, 15):
            self.assertEqual(select_images(ids, x, regions, budget, "fd_roundrobin", 4),
                             result[:budget])
        # A pool smaller than K must remain fully covered, without phantom clusters.
        for n in (1, 4, 11):
            small = select_images(ids[:n], x[:n], regions[:n], n, "fd_roundrobin", 4)
            self.assertEqual(set(small), set(ids[:n]))

    def test_new_strategies_use_unit_rows(self):
        for strategy in ("kmeanspp", "facility_location", "fd_roundrobin"):
            scaled = self.x * np.arange(1, len(self.x) + 1)[:, None]
            self.assertEqual(select_images(self.ids, self.x, self.regions, 14, strategy, 3),
                             select_images(self.ids, scaled, self.regions, 14, strategy, 3))

    def test_invalid_inputs(self):
        cases = [
            {"budget": 0}, {"budget": 30}, {"budget": 1.5}, {"budget": True},
            {"seed": -1}, {"seed": .5}, {"seed": True}, {"strategy": "unknown"},
            {"ids": ["duplicate"] * 29}, {"regions": ["r"] * 28},
            {"descriptors": np.ones(29)}, {"descriptors": np.ones((29, 0))},
            {"descriptors": np.full((29, 5), np.nan)},
            {"descriptors": np.full((29, 5), np.inf)},
            {"descriptors": np.ones((29, 5), dtype=complex)},
            {"descriptors": np.zeros((29, 5))},
        ]
        for replacement in cases:
            values = dict(ids=self.ids, descriptors=self.x, regions=self.regions,
                          budget=3, strategy="kmeanspp", seed=1)
            values.update(replacement)
            with self.subTest(replacement=list(replacement)):
                with self.assertRaises(ValueError):
                    select_images(**values)


if __name__ == "__main__":
    unittest.main()

"""Synthetic algorithm checks only: no panel data, models or scientific runs."""
from collections import Counter
from fractions import Fraction
import itertools
import unittest

import numpy as np
import v2_selection as base
from v2_weighted_selection import (PERMUTED_WEIGHTED, REGION_WEIGHTED, WEIGHTED_STRATEGIES,
                                    _group_memberships, _group_weights, select_images)


class WeightedSelectionTests(unittest.TestCase):
    @staticmethod
    def geometry():
        # Directions0,0,60,120 degrees: similarities have exact rational values.
        x = np.array([[1., 0.], [1., 0.], [.5, np.sqrt(3) / 2], [-.5, np.sqrt(3) / 2]])
        similarity = [[Fraction(1), Fraction(1), Fraction(3, 4), Fraction(1, 4)],
                      [Fraction(1), Fraction(1), Fraction(3, 4), Fraction(1, 4)],
                      [Fraction(3, 4), Fraction(3, 4), Fraction(1), Fraction(3, 4)],
                      [Fraction(1, 4), Fraction(1, 4), Fraction(3, 4), Fraction(1)]]
        return x, similarity

    def test_greedy_steps_against_exhaustive_rational_objectives(self):
        x, similarity = self.geometry()
        weights = [Fraction(1, 6)] * 3 + [Fraction(1, 2)]
        def value(subset):
            return sum(weights[i] * max(similarity[i][j] for j in subset) for i in range(4))
        for seed in (0, 1, 9):
            result = select_images(list("abcd"), x, ["A", "A", "A", "B"], 4, REGION_WEIGHTED, seed)
            selected = []
            objective_values = []
            for identifier in result:
                # Enumerate every allowable extension and compare absolute
                # rational objective values, independently of marginal-gain code.
                choices = {j: value(selected + [j]) for j in range(4) if j not in selected}
                chosen = "abcd".index(identifier)
                self.assertEqual(choices[chosen], max(choices.values()))
                selected.append(chosen)
                objective_values.append(value(selected))
            self.assertEqual(objective_values, [Fraction(19, 24), Fraction(11, 12), Fraction(1), Fraction(1)])
            # Greedy is not exhaustive global optimization: size2 has a better
            # global subset here. This protects the claimed algorithm boundary.
            optimum_two = max(value(s) for s in itertools.combinations(range(4), 2))
            self.assertEqual(optimum_two, Fraction(23, 24))
            self.assertLess(objective_values[1], optimum_two)

    def test_row_weighting_differs_from_weighted_representative_columns(self):
        x, similarity = self.geometry()
        weights = [Fraction(1, 6)] * 3 + [Fraction(1, 2)]
        row_values = [sum(weights[i] * similarity[i][j] for i in range(4)) for j in range(4)]
        wrong_column_values = [weights[j] * sum(similarity[i][j] for i in range(4)) for j in range(4)]
        self.assertEqual(row_values.index(max(row_values)), 2)
        self.assertEqual(wrong_column_values.index(max(wrong_column_values)), 3)
        result = select_images(list("abcd"), x, ["A"] * 3 + ["B"], 1, REGION_WEIGHTED, 0)
        self.assertEqual(result, ["c"])

    def test_balanced_and_single_group_delegate_exactly(self):
        random_x = np.random.default_rng(6).normal(size=(12, 5))
        for x in (random_x, np.ones((12, 5))):
            for regions in (["a"] * 4 + ["b"] * 4 + ["c"] * 4, ["only"] * 12):
                for seed in (0, 2, 11):
                    for budget in (1, 6, 12):
                        expected = base.select_images([str(i) for i in range(12)], x, regions,
                                                      budget, "facility_location", seed)
                        for strategy in WEIGHTED_STRATEGIES:
                            self.assertEqual(select_images([str(i) for i in range(12)], x, regions,
                                                           budget, strategy, seed), expected)

    def test_permutation_sizes_weight_multiset_and_independent_tie_rng(self):
        regions = ["a"] * 3 + ["b"] + ["c"] * 2
        ids = [str(i) for i in range(6)]
        x = np.random.default_rng(5).normal(size=(6, 4))
        for seed in (0, 1, 12):
            permutation = np.random.default_rng(seed + 20261018).permutation(6)
            expected_groups = np.asarray(regions)[permutation]
            groups = _group_memberships(regions, seed, True)
            np.testing.assert_array_equal(groups, expected_groups)
            self.assertEqual(Counter(groups), Counter(regions))
            real_w, fake_w = _group_weights(regions, seed), _group_weights(regions, seed, True)
            np.testing.assert_array_equal(np.sort(real_w), np.sort(fake_w))
            self.assertAlmostEqual(float(fake_w.sum()), 1.)
            for group in set(groups):
                self.assertAlmostEqual(float(fake_w[groups == group].sum()), 1 / 3)
            expected = select_images(ids, x, groups.tolist(), 6, REGION_WEIGHTED, seed)
            self.assertEqual(select_images(ids, x, regions, 6, PERMUTED_WEIGHTED, seed), expected)
            # All similarities equal: both policies must use the untouched base
            # tie RNG sequence, irrespective of the membership permutation.
            tie_expected = [ids[i] for i in np.random.default_rng(seed).permutation(6)]
            for strategy in WEIGHTED_STRATEGIES:
                self.assertEqual(select_images(ids, np.ones((6, 2)), regions, 6, strategy, seed), tie_expected)

    def test_proxy_all_original_policies(self):
        x = np.random.default_rng(21).normal(size=(17, 6))
        ids, regions = [str(i) for i in range(17)], ["a"] * 3 + ["b"] * 14
        for strategy in base.STRATEGIES:
            for budget in (1, 8, 17):
                self.assertEqual(select_images(ids, x, regions, budget, strategy, 3),
                                 base.select_images(ids, x, regions, budget, strategy, 3))

    def test_budget_determinism_prefix_and_no_mutation(self):
        x = np.random.default_rng(43).normal(size=(23, 5))
        ids, regions = [f"id{i}" for i in range(23)], ["a"] * 3 + ["b"] * 20
        original_x, original_ids, original_regions = x.copy(), ids.copy(), regions.copy()
        for strategy in WEIGHTED_STRATEGIES:
            full = select_images(ids, x, regions, 23, strategy, 5)
            self.assertEqual(set(full), set(ids))
            for budget in (1, 9, 23):
                selected = select_images(ids, x, regions, budget, strategy, 5)
                self.assertEqual(len(selected), len(set(selected)))
                self.assertEqual(len(selected), budget)
                self.assertEqual(selected, full[:budget])
                self.assertEqual(selected, select_images(ids, x, regions, budget, strategy, 5))
                self.assertEqual(selected, select_images(ids, x * np.arange(1, 24)[:, None], regions,
                                                         budget, strategy, 5))
        np.testing.assert_array_equal(x, original_x)
        self.assertEqual(ids, original_ids); self.assertEqual(regions, original_regions)

    def test_invalid_inputs(self):
        cases = [{"budget": 0}, {"budget": 5}, {"budget": True}, {"budget": 1.5},
                 {"seed": -1}, {"seed": True}, {"strategy": "unknown"},
                 {"ids": ["same"] * 4}, {"regions": ["r"] * 3},
                 {"descriptors": np.zeros((4, 2))}, {"descriptors": np.full((4, 2), np.nan)},
                 {"descriptors": np.full((4, 2), np.inf)}, {"descriptors": np.ones((4, 2), complex)},
                 {"descriptors": np.ones(4)}, {"descriptors": np.ones((4, 0))}]
        for strategy in WEIGHTED_STRATEGIES:
            for case in cases:
                arguments = dict(ids=list("abcd"), descriptors=np.ones((4, 2)), regions=["a"] * 3 + ["b"],
                                 budget=2, strategy=strategy, seed=0)
                arguments.update(case)
                with self.subTest(strategy=strategy, case=list(case)), self.assertRaises(ValueError):
                    select_images(**arguments)


if __name__ == "__main__":
    unittest.main()

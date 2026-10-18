# Secondary source-group weighted facility-location controls

This module adds two explanatory policies before the first new-panel model
scoring, while leaving `code/v2_selection.py`, its eight existing policies and the
original primary comparison unchanged. It is an application of standard weighted
facility location, not a claim of a new optimization algorithm or demonstrated
segmentation improvement.

## Interface and policies

```python
from v2_weighted_selection import select_images
select_images(ids, descriptors, regions, budget, strategy, seed)
```

All eight strategies from `v2_selection` delegate directly to that module. The
additional names are:

- `region_weighted_facility_location`
- `permuted_region_weighted_facility_location`

The input contract matches the original selector: unique image IDs, finite real
N-by-D descriptors, one source-region string per image, an integer budget in
1..N and a nonnegative integer seed. Zero descriptor rows are invalid for these
cosine-based policies. Only fixed source RGB descriptors and source metadata
enter selection; no mask, class label, trained task model, validation score or
new-target information is accepted. Input arrays/lists are not modified.

## Objective

Let V be the fixed source candidate pool, R its number of nonempty source groups,
and n_r the number of candidates in group r. Normalize each descriptor to L2 unit
length using the same routine as the existing FL baseline. Define

```text
s(i,j) = clip((cos(i,j)+1)/2, 0, 1)
w_i = 1 / (R * n_group(i))
F(S) = sum_i w_i * max_{j in S} s(i,j), with F(empty)=0.
```

At each step, choose the remaining candidate j with greatest exact greedy
marginal gain `sum_i w_i * max(s(i,j)-coverage_i, 0)`. The weights multiply the
**represented rows i**, outside the maximum over chosen representatives j.
Multiplying representative columns instead would define another method.
Each source group has total weight1/R; weights remain fixed throughout selection
and do not depend on how many of its images have already been chosen.

The seed creates exactly the original FL's fixed candidate tie order,
`default_rng(seed).permutation(N)`. It does not change similarities or weights in
the real-group policy. Dense float64 similarity storage remains about8N squared
bytes, and no new dependency beyond NumPy is introduced.

This is mean source-group representativeness. It is not a hard selection quota,
does not require selecting an image from every group and does not optimize or
guarantee the worst group's coverage. Equal weighting is a prespecified policy
assumption, not evidence that all source groups are equally predictive of every
unseen target region. No additional tuning parameter is introduced.

## Permuted control and balanced degeneration

The permuted policy uses exactly the membership permutation rule of the existing
`permuted_region_kcenter`: apply
`default_rng(seed + 20261018).permutation(N)` to the group-label vector while
keeping IDs/descriptors in place. This preserves group sizes and the weight
multiset while breaking their original image assignments. Its generator is
separate from the FL tie generator, so permutation consumes no tie randomness.
Conditional on permuted groups, it is the same algorithm as real-group weighting.

When all group sizes are equal (including balanced3 and single-group pools), all
weights are constant. Both new policies **directly return the original
`facility_location` result**, ensuring exact equality even at floating-point ties.
Balanced pools therefore provide a degeneration check without new distinct
training fits. The implementation itself accepts any valid pool; the experimental
runner is responsible for restricting new scientific fits to skewed5_1.

## Prespecified explanatory amendment and interpretation

The original504 fits and primary full-model skewed5_1 B12 comparison,
`region_kcenter minus kcenter`, remain the base design. The amendment adds only
skewed5_1 conditions for the two new policies:18 full-model fits and54 frozen-model
fits, for72 additional fits and576 distinct fits overall. A separate, source-only
randomization amendment pairs each selection seed0/1/2 with optimization seed0/1/2
for all policies, avoiding identical deterministic-subset fits under fixed init0;
the selection module itself does not control model initialization. This module does not
alter a runner, freeze record, audit matrix or analysis gate; those must explicitly
record and bind the separate amendment. It does not create balanced duplicate
run files or represent reused fits as new observations.

Real weighted-FL versus ordinary FL tests source-group weighting within one
coverage objective; real versus permuted weighted-FL additionally holds the
weight multiset fixed. These are secondary explanatory comparisons, not new
primary comparisons. They remain informative if improvements are absent.

Comparing weighted-FL directly to region-kcenter changes both the coverage
objective and the use of group information. Even if weighted-FL helps, this alone
cannot establish that hard quota rigidity caused region-kcenter's failure. A
hard-quota FL counterpart would be needed to isolate that factor on the same
objective. Neither the formula nor this experimental amendment proves novelty;
the possible contribution is controlled evidence about when source-group metadata
affects whole-image selection and held-out-region segmentation.

## Original public sources

- Yanhao Wang, Yuchen Li, Francesco Bonchi and Ying Wang, *Balancing Utility and
  Fairness in Submodular Maximization*, EDBT2024,
  [DOI10.48786/edbt.2024.01](https://doi.org/10.48786/edbt.2024.01),
  [official paper, Sections2–3](https://openproceedings.org/2024/conf/edbt/paper-7.pdf).
  It defines group-average utilities and distinguishes selected-item group quotas
  from utilities delivered to groups. Its bicriteria/maximin formulation is not
  the identical group-average-sum objective used here.
- Akbar Rafiey, *Decomposable Submodular Maximization in Federated Setting*,
  ICML2024, PMLR235:41841–41866,
  [formal publication](https://proceedings.mlr.press/v235/rafiey24a.html),
  [author manuscript Eq.1 and Section5](https://arxiv.org/html/2402.00138v2).
  Predetermined weighted sums of monotone submodular functions, including
  facility-location instances, are an established framework.
- Shiqi Zhang and Tuomas Virtanen, *Cover First, Disagree Softly: Rethinking
  Mismatch-First Active Learning for Frame-Level Audio Classification*,
  [arXiv2607.13571v2,2026](https://arxiv.org/abs/2607.13571v2),
  [Section3.1 Eq.2 and Section4.3](https://arxiv.org/html/2607.13571v2),
  [author code](https://github.com/TioSisai/mismatch-weighted-facility-location).
  The author arXiv record states acceptance at DCASE Workshop2026; a separate
  proceedings version is not asserted here. It weights coverage rows using
  classifier/label-neighbor disagreement and compares hard gating with soft
  weighting, unlike the source-count-only weights here. This is a close precedent
  for the hard-versus-soft explanatory narrative, not a source of observed results
  for our experiment.

## Synthetic validation

`code/test_v2_weighted_selection.py` uses small synthetic descriptors only. It
checks greedy steps against exhaustive candidate extensions with exact rational
objectives, a counterexample separating row from column weighting, exact balanced
degeneration, size/weight-multiset preservation, isolated tie randomness,
delegation of every original policy, budgets/prefixes/reproducibility, normalization,
input preservation and invalid inputs. The small example explicitly distinguishes
greedy selection from exact global subset optimization. No real panel scoring or
scientific performance test is performed by these checks.

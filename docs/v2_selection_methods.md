# V2 image-selection methods

This document specifies the implementation in `code/v2_selection.py`. These are
selection baselines and adaptations, not proposed algorithms. Implementing them
does not establish a segmentation benefit or research novelty.

## Interface and information boundary

```python
select_images(ids: list[str], descriptors: np.ndarray, regions: list[str],
              budget: int, strategy: str, seed: int) -> list[str]
```

Only candidate source-image IDs, RGB-derived descriptors and source-region names
are accepted. The interface has no mask, class, validation or target/test argument.
The caller must construct a source-only candidate pool and must not derive input
descriptors or regions from forbidden labels. The function cannot independently
verify that provenance. All strategies return exactly `budget` distinct IDs.

IDs must be unique nonempty strings; regions must supply one nonempty string per
ID. Descriptors must be a finite real N-by-D matrix with D at least one. Budgets
must be positive integers no greater than N; seeds must be nonnegative integers.
Invalid values raise `ValueError`. Inputs are copied or read without mutation.
The three new methods normalize descriptor rows to L2 unit length; zero rows are
rejected because their cosine direction is undefined. The five old methods keep
the old normalization, including its zero-row handling, by calling `core.select`.
No new dependency beyond NumPy is introduced.

For the planned experiment, all methods use the same frozen DINO image
descriptors. The new methods need neither candidate masks nor a trained task head
nor feedback about class performance. Existing labels are used only by the caller
after selection for the downstream training/evaluation protocol.

## Preserved strategies

`random`, `kcenter`, `region_random`, `region_kcenter` and
`permuted_region_kcenter` delegate directly to the unchanged `code/core.py`.
The wrapper maps the returned indices to image IDs without reordering them.

The old k-center uses cosine distance and its seeded first point/tie order.
Region strategies restrict every next choice to the nonexhausted groups with the
fewest selections so far. Thus small groups can exhaust and remaining groups
continue; this is not a fixed floor/ceiling quota chosen in advance. The permuted
control permutes region memberships with `default_rng(seed + 20261018)`, preserving
the exact multiset of group sizes, and runs the same region-kcenter procedure with
the original selection seed. IDs and descriptors are not permuted.

## kmeanspp

This is D-squared **seeding**, without Lloyd refinement or centroid-to-image
matching. A seeded uniform first candidate is followed by sampling each remaining
candidate in proportion to its minimum squared Euclidean distance to the selected
unit vectors. For unit vectors, squared Euclidean distance equals twice cosine
distance; cosine distance must not be squared again. Selected candidates are
excluded. If every remaining weight is zero, sampling is uniform over remaining
candidates. Coincident descriptors therefore still yield a full unique ranking.

Source: David Arthur and Sergei Vassilvitskii, *k-means++: The Advantages of Careful
Seeding*, SODA 2007, pp. 1027–1035.
[Author-hosted original paper](https://theory.stanford.edu/~sergei/papers/kMeansPP-soda.pdf).
Its clustering guarantee is not a guarantee of downstream segmentation accuracy.

## facility_location

For unit descriptor rows define `s(i,j) = clip((cos(i,j)+1)/2, 0, 1)` and
`F(S) = sum_i max_{j in S} s(i,j)`, with empty-set coverage zero. At each step,
choose the remaining image with the largest exact increase in F over the entire
candidate pool. The seed only creates a fixed tie order; it does not subsample or
change objective weights. The implementation uses a dense float64 similarity
matrix (approximately `8*N*N` bytes), suitable for the current small source pool.
If pool size grows substantially, this storage requirement must be reviewed.

This is generic similarity-based facility location, not the class-conditioned
objective or uncertainty-filtered active-learning variants in Kai Wei, Rishabh
Iyer and Jeff Bilmes, *Submodularity in Data Subset Selection and Active Learning*,
ICML 2015, PMLR 37, pp. 1954–1963.
[Official paper and PDF](https://proceedings.mlr.press/v37/wei15.html).
No class partition or trained classifier is used here.

## fd_roundrobin: fixed-K FD adaptation

This adapts Feature Diversity (FD) from Nogueira et al., *Core-Set Selection for
Data-efficient Land Cover Segmentation*, IEEE Access, 2026,
[DOI 10.1109/ACCESS.2026.3659734](https://doi.org/10.1109/ACCESS.2026.3659734).
[Author institutional record](https://www.microsoft.com/en-us/research/publication/core-set-selection-for-data-efficient-land-cover-segmentation/),
[public method manuscript, Section III-B](https://arxiv.org/html/2505.01225v2),
[author repository](https://github.com/keillernogueira/data-centric-rs-classification).
The method manuscript is a preprint version; it must not be used to silently
substitute experimental results for the formal article.

Implementation:

1. Use `K=12`, reduced to N only when the entire pool has fewer than 12 images.
2. Initialize centers with the D-squared seeding above. Run at most 100 Euclidean
   Lloyd assignment/update iterations on unit input vectors. Centroids are
   arithmetic means and are not renormalized: this is ordinary Euclidean k-means,
   not spherical k-means.
3. Following every assignment, repair each empty cluster by moving the point
   with greatest current squared assignment error from a cluster with more than
   one member. A fixed seeded order resolves ties. Update memberships/counts
   after each move so a donor cannot empty its original cluster. Each point has
   one integer membership throughout; no point belongs to two clusters.
4. Stop early when the repaired partition repeats unchanged. Shuffle members
   within each cluster and shuffle cluster order using the same seeded generator.
   Take one available member per cluster per round, skip exhausted clusters and
   stop at the requested image budget.

**Adaptation boundary:** the original FD uses ResNet18 representations and an
adaptive K procedure involving Vendi scores. This implementation uses the common
DINO descriptors and fixed K=12. It does not implement Vendi-based K selection and
is not a full reproduction of the original FD. It uses original image IDs as the
budget unit and does not reproduce the paper's entire patch/training protocol.
Fixed K is independent of budget, so rerunning the same pool/seed with a larger
budget extends the same ranking. Region names do not affect this baseline.

## Local validation scope

`code/test_v2_selection.py` contains only small synthetic checks: exact legacy
sequences, smallest-count group eligibility and size-preserving permuted groups;
hand-derived D-squared probabilities and zero-weight fallback; facility-location
objective increments on known geometry; seed-only tie handling; FD empty-cluster
repair, disjoint membership, full coverage and prefix consistency; reproducibility,
normalization, input preservation and rejected invalid inputs. They download no
data, train no model and provide no new scientific performance result.

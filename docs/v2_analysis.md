# V2 evidence audit and analysis

The two tools operate after the planned runs exist. Neither imports a model,
loads feature NPZ arrays, trains a network, or changes a selected subset. No
scientific outcomes are encoded in the analysis implementation.

## Commands

Run the evidence gate first, then reanalyse only when it passes:

```text
python code/v2_audit_runs.py
python code/v2_statistics.py
```

`--root PATH` can point to the project root. `--self-test` on either command runs
only small synthetic checks in memory; it does not open real new-panel results or
write artificial run/result files. Running self-tests does not constitute a
completed scientific evidence audit or a newly observed model result.

## Audit scope

`evidence/v2/run_completeness.json` has `passed=true` only after exactly 90 full
and 486 frozen fits occupy the design and prospective supplement's unique conditions, with no
missing, extra or duplicate identities, and every fit passes all checks.
Prerequisite failures are recorded as failures; planned identities then remain
explicitly unaudited rather than being claimed to be missing scientific runs.

The original `configs/v2_design.json` and its calibration binding stay unchanged.
The pre-evaluation `configs/v2_extension.json` adds
`region_weighted_facility_location` and
`permuted_region_weighted_facility_location` only for `skewed5_1`.
The original condition count remains full72 + frozen432 =504. The supplement adds
3 sources ×3 paired fit seeds ×2 strategies =18 full fits, plus
3 sources ×3 paired fit seeds ×3 budgets ×2 strategies =54 frozen fits.
The exact combined matrix therefore contains 576 fits; no balanced-pool fit
of either new strategy is planned or synthesized by the analysis.

Before the first new-panel score, a source-only subset diagnostic found identical
ordered selections across seeds for some facility-location conditions. The
prospective supplement therefore pairs selection seeds0/1/2 with optimization
initialization seeds0/1/2, respectively, for **every base and additional fit**.
These are three paired fit seeds, not a Cartesian selection-by-initialization
factorial. Counts stay576; the primary contrast, metric, budget and averaging
order do not change. Calibration retains initialization0 and its original SHA
bindings. `expected_matrix(design, None)` deliberately preserves the historical
504 initialization0 identities; `expected_matrix(design, extension)` returns the
576 amended identities and rejects missing/wrong pairing or duplicate keys.
The extension explicitly records this randomization amendment before panel scores.

The audit binds the pre-evaluation freeze and all its file hashes, the current
passed data audit, calibration choices and execution code. It recalculates the
candidate/selected ID lists and coverage metadata from the old descriptor index,
`candidate_pool` and the `v2_weighted_selection.select_images` dispatcher, which
delegates the original eight strategies to the unchanged original selector.
The new extension configuration and dispatcher must both appear in the required
freeze hashes and every run's execution identity. It never opens a complete feature NPZ.
Coverage checks include ordinary image-mean cosine distance, the equally weighted
mean of source-region distances, each source-region's mean distance, and selected
counts per source region. The condition tables retain both image-mean and
equal-region mean coverage as descriptive metrics; neither is a target score.
Every test fit must contain the same unique 72 panel IDs with their correct
regions. Full-model validation must match only that source allocation's old
validation IDs; frozen fits must have `validation=null`.

Every confusion matrix must be a nonnegative integer 8-by-8 array, with a positive
valid-pixel total no greater than 448 squared. All stored aggregates are
recomputed, including both the truth-present and union-class conventions.
Actual processed raw0..8 class counts in the SHA-bound data audit are compared
to the matrix truth margins (raw0 is void, raw1..8 become classes0..7). The field
is `processed_png_availability.pairs[*].processed_mask_class_counts_raw_0_to_8`;
it contains nine integers summing to448², computed by the data audit from each
actual448 PNG mask. Manifest/sidecar processed counts, if present, must agree.
**Original TIFF counts are never substituted for processed448 counts.** When
processed counts are absent, the audit checks identical truth margins per image
across all fits and requires the current passed data audit. This fallback cannot
independently prove the absolute valid-pixel total by decoding the mask; the
report states that limitation. PNG/sidecar byte hashes remain verified without
raster decoding.

The full recipe must match its source-only calibration's chosen steps and rates;
the frozen recipe is 600 steps at 0.001. Embedded and external SHA-bound logs
must agree and contain step1/every50/final step with finite losses and monotone
nonnegative elapsed times. Exactly one predetermined full-model checkpoint must
exist: source0, selection0, initialization0, region_kcenter. Its file SHA is
verified without deserializing the model. Other reported or unreported checkpoint
files inside the v2 runs tree fail the audit.

## Statistical outputs

The analysis first requires a passed 576-run audit. It checks the current result
inventory and rehashes every audited result, input and artifact before reading
confusion matrices. Any stale hash stops table creation. The emitted
`tables/v2/analysis_identity.json` binds the audit, all result identities, both
analysis/audit code and the output hashes.

| Output | Definition |
|---|---|
| `conditions_by_source.csv` | 192 model/pool/budget/strategy/source conditions; each contains three paired-seed fits |
| `conditions.csv` | 64 conditions: original56 + full-model2 + frozen-model6; each averages three source allocations by three paired-seed fits |
| `regions.csv` | 64 by24 =1536 region rows, retaining both metric conventions and all nine raw fit values |
| `classes.csv` | 64 by8 =512 class rows, retaining pooled and region-averaged class IoUs and defined-fit counts |
| `contrasts.json` | Original28 contrasts across seven families, plus eight weighted-FL contrasts across the four planned skewed-pool families; all with descriptive source-allocation sensitivities |
| `primary.json` | Full-model skewed5_1 B12, region_kcenter minus kcenter; primary union-class metric plus truth-present convention sensitivity |

Raw fit values in CSV are ordered by source_split, selection_seed and
initialization_seed; condition/region rows retain the fit identities. Condition
rows also retain seed counts and the explicit pairs(0,0), (1,1), (2,2). Sample SD
uses the raw fits and describes joint selection, optimization and source
variability. Their separate variance components are not identified by this paired
design; identical selected subsets are not counted as new independent annotation
choices. This SD is **not** a
geographic confidence interval. Class results are computed within each fit before
averaging fits; undefined class unions are excluded with defined-fit counts
reported. The class table does not collapse all replicated predictions into a
single confusion matrix.

For the primary contrast, first average each strategy's regional score over the
nine fits (three source allocations by three paired selection/optimization seeds),
then difference the two strategies for each of the 24 held-out regions.
The percentile paired region bootstrap uses 10,000 resamples with seed2026101805.
The raw regional differences and leave-one-region-out estimates are retained.
Both union-class and truth-present conventions follow this same order. Only the
union-class result is designated the prespecified primary metric.

`configs/v2_geographic_sensitivity.json` is a required freeze/audit input and its
SHA is also retained in the analysis identity. It prospectively specifies an
additional **descriptive** primary-condition sensitivity excluding the entire
Monrovia region, because the available coordinate metadata is outside the
declared CRS applicability range. Within each region, the same nine paired fits
are averaged first; Monrovia is then removed from both matched regional
dictionaries. The retained23 regions use the same10,000-resample percentile
bootstrap seed2026101805. Both union-class and truth-present versions, raw regional
differences and leave-one-region-out summaries are written under
`primary.json.geographic_sensitivity`. The24-region primary and all original
contrast fields remain intact. This is not a new confirmatory test, a sample
substitution, or an additional secondary-significance search. The existing
per-source-allocation sensitivities separately retain source0 for the Aachen
metadata caution; they do not change the formal source allocations.

Real-minus-fake, real-minus-facility-location and real-minus-FD comparisons, all
other budget families, and per-source-allocation contrasts are descriptive. No
extra confirmatory intervals or p-value screening are introduced for these
families. The supplemental contrasts are region-weighted FL minus ordinary FL,
and region-weighted FL minus permuted-region-weighted FL. These two contrasts
exist only for full-model B12 and frozen-model B6/B12/B24 under `skewed5_1`,
giving eight additional descriptive contrasts. The primary specification and
its bootstrap procedure remain unchanged. Source allocations and seeds are not counted as independent geographic
replicates. The tools make no publication, acceptance or equivalence judgment;
an interval crossing zero does not establish equivalence.

CSV and JSON preserve floating-point precision without formatting scientific
outcomes to display-rounded values. Full evidence interpretation must retain the
data audit's geographical cautions and the processed-pixel fallback limitation.

The synthetic tests cover the exact576 sparse matrix, rejection of altered
supplement counts/pools/seed mapping,64 aggregate conditions and192 source conditions,
absence of balanced weighted-FL rows,36 contrasts, and byte-for-byte equal
primary-result structures before and after adding synthetic weighted-FL fits
to the **same amended paired-seed base**, not the historical initialization0 base.
The synthetic outcomes deliberately depend on initialization, so using the old
base would fail this comparison. Every one of576 unique identities must have
`initialization_seed == selection_seed`; no Cartesian expansion is permitted.
The geographic-filter test verifies whole-region exclusion, correct matched
support and unchanged primary dictionaries. The full synthetic comparison also
checks that the primary retains24 regions while its appended geographic
sensitivity contains23, with byte-for-byte equal primary structures when only
weighted-FL fits are added to the same paired-fit base.
The existing per-class CM-margin, data-histogram, aggregate and log checks remain
in place. No test reads actual held-out outcomes or writes scientific results.

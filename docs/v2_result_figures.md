# V2 results plotting engine

`code/v2_plot_results.py` renders existing audited statistics with matplotlib. It does not train, evaluate, alter numerical tables, calculate tests, derive new confidence intervals, or write scientific conclusions. Formal execution must wait for all 576 runs. The implementation task used synthetic temporary objects only; no real result figure or formal figure evidence was generated during development.

## Execution and evidence gate

Use a Python environment with matplotlib. `--help` uses only the standard library. `--self-test` validates invented in-memory summaries and writes the twelve image-format checks into a system temporary directory that is removed on exit. It neither reads project score files nor writes a formal manifest. Normal execution accepts `--root PROJECT_ROOT`; outputs are fixed below that project root.

Before opening numerical table values, the normal entry point requires:

- `evidence/v2/run_completeness.json` passed with exactly 576 expected, observed, validated and inventoried result files; no missing, extra, duplicate or error entries.
- A current `configs/v2_freeze.json` with the frozen-before-evaluation status, bound identically by the audit and analysis.
- `tables/v2/analysis_identity.json` binding the current audit file SHA, all current audited input, artifact and result maps, and the exact six numerical output SHAs.
- The current physical `result.json` file set equal to the audited inventory, with every audited input, artifact and result rehashed. The current audit and statistics script SHAs must also match their recorded identities. Result files are hashed as bytes; this plotting engine does not parse predictions or per-image results.
- The design, extension and geographic-sensitivity configurations present in the audited input map.

The six checked numerical files are `conditions_by_source.csv`, `conditions.csv`, `regions.csv`, `classes.csv`, `contrasts.json`, and `primary.json`, all under `tables/v2`. Only `conditions.csv`, `primary.json`, and `contrasts.json` supply visible values. Their expected 64 condition families, nine-fit counts, raw-fit means, primary specification, fixed regional support, source supports and paired differences are checked before plotting. The balanced pool must contain exactly the eight actual strategies; the skewed pool contains ten. A weighted balanced duplicate is rejected, not imputed.

The complete evidence freshness gate runs again after rendering. A changed input prevents a new valid manifest. Formal outputs are four named figures, each in SVG, PDF and 300-dpi PNG, in `figures/v2/results`. `evidence/v2/result_figures.json` records current audit/analysis/freeze/configuration/numerical-file SHAs, the plotter SHA, the stable sorted-result-inventory digest, and all twelve output SHAs. Audit and analysis whole-file SHAs are execution observations; the scientific inventory digest itself excludes report timestamps. A failed render can leave incomplete assets but does not issue a new manifest: downstream use must validate the current manifest and each asset SHA. The manifest status explicitly requires visual review.

## Figures and statistical units

| Basename | Content and dependencies | Statistical unit and limits |
|---|---|---|
| `primary_union` | Fixed full-model skewed-pool budget-12 region-k-center minus visual-k-center comparison, union-class metric. `primary.json`, its matched `contrasts.json` entry, and design region order. All 24 individual region differences, overall mean with the stored 95% region-bootstrap interval, and all three source-allocation differences are shown. | Each primary region first averages three source allocations × three paired fit seeds. The 24 regions are the bootstrap units; the nine fits are not geographic replicates. Source means average three fitting pairs then 24 regions and receive no invented interval. Regions retain the fixed design order, never effect-size order. |
| `primary_truth_present` | Same fixed comparison and support under the truth-present metric. | A metric-convention sensitivity, not a second independent confirmatory outcome. The same averaging and unit apply. |
| `models_skewed_b12` | Both models, all ten strategies, same skewed pool and budget 12; both metric conventions. Uses all matching `conditions.csv` rows. | Every dot is the mean of nine fit-level equal-region means. No uncertainty interval is inferred from their SD. The two model pipelines differ in encoder, pretraining, decoder, grid and augmentation; this panel cannot isolate the causal effect of fine-tuning. |
| `frozen_pools_budgets` | Frozen model, both pools, budgets 6/12/24, all actually fitted policies; two metric rows × two pool columns. | Each point is a nine-fit descriptive mean. Lines connect the three specified budgets; they are not fitted response curves or independent replications. Balanced has eight series and skewed has ten. No extra balanced weighted-FL series are created because those policies degenerate to ordinary FL. |

When the fixed geographic-sensitivity object is present, both primary figures also show the stored 23-region sensitivity mean and stored interval, labelled descriptive. The excluded whole region must match the fixed configuration. This never substitutes for the original 24-region primary. Omission of a sensitivity object is visibly reflected by its absent row, not by fabricated numbers. If a stored bootstrap interval is absent, the point remains and its label says `CI unavailable`; means or fit SDs cannot supply replacement bounds. Source-allocation rows intentionally have no intervals.

Union-class mIoU includes classes present in the regional truth **or prediction**; prediction-only false-positive classes therefore contribute. Truth-present mIoU averages classes present in regional truth. Void pixels are excluded by the upstream audited statistics. The plotter displays existing IoU fractions as percentages, and paired differences as percentage points. It does not average the class conventions together. It uses no significance stars, interval-sign interpretation, favourable-condition selection, equivalence assertion, or submission-readiness claim.

## Rendering and validation boundaries

All visible text is at least 9 pt on the saved physical canvas. Text bounding boxes must remain inside that canvas (a two-pixel numerical tolerance is allowed); oversized labels cause a failure rather than silent clipping. SVG retains editable text; PDF embeds TrueType fonts. The palette uses colour-blind-friendly core colours together with marker/line-style differences; longer strategy labels appear on separate categorical rows or in a two-column legend. All condition means share the 0–100% scale. Signed paired effects have zero reference lines, without automatic positive/negative interpretation.

`--self-test` checks the 64-condition synthetic schema, missing/duplicate/nonfinite/extra-balanced-policy rejection, twelve temporary SVG/PDF/PNG file signatures, the text-size floor and canvas bounds, missing-CI labels, stable inventory sensitivity to a result SHA change, and rejection of an incomplete audit. It is a mechanical check, not an image-quality or scientific validation. It deliberately does not create a fake 576-run directory or bypass the formal evidence gate. Actual figure generation, full-size visual inspection, caption checking and downstream manuscript binding remain to be performed after complete audited evidence is available.

Development verification: Python 3.12 with matplotlib 3.10.8 passed `--help`, AST syntax parsing and `--self-test`. The bundled artifact Python lacked matplotlib; it was not modified or used to generate figures. No partial panel score or formal numerical output was opened for those checks.

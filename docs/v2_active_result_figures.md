# Active GPU result figures

The existing `code/v2_plot_results.py` retains its four figure families and all
64 designed conditions. When `configs/v2_active_gpu_amendment.json` exists, the
evidence gate calls the target root's `code/v2_active_gpu_results.py`
`validate_bundle(root)` interface. It requires a passed exact active 576-fit
inventory: GPU full-model 90 plus frozen-head 486. The separately retained CPU
72 reference fits are not part of these figure means or intervals. An absent or
failed active audit never falls back to the legacy CPU audit.

The adapter checks the active audit and six canonical numerical file bindings,
current analysis/audit code, frozen statistical reference code, configuration
hashes, 576-fit/64-condition counts and post-exposure descriptive scope. The
active validator supplies the complete current result/artifact/input inventory
checks and quiescence checks. Result files are hash-checked by that gate; the
plotter reads numerical tables only after it passes. The same gate runs after
rendering before a figure manifest can be issued.

The active main-comparison figures say “fixed main comparison (descriptive)”.
The figure manifest records the post-exposure role and the separate GPU/frozen
counts. This backend amendment creates no confirmatory evidence and no new
independent holdout. The original freeze and CPU reference evidence remain
available separately.

Figures remain: union-class main comparison; truth-present metric sensitivity;
full/frozen skewed-pool budget-12 means; and every planned frozen pool/budget
condition. Region points retain fixed region order. Fractions are multiplied by
100 for display only. All means average three source allocations and three
paired fitting seeds; geographic intervals use stored paired-region bootstrap
bounds, never fit standard deviations. The fixed 23-region sensitivity and
three source means remain descriptive. Missing stored intervals are labeled.
Balanced weighted-FL duplicates remain absent. Printing uses the existing
DejaVu Sans settings, minimum 9 pt, fixed physical canvases and SVG/PDF/300-dpi
PNG output, with canvas-bound checks. Four figure families produce 12 assets.

`python -B code/v2_plot_results.py --self-test` uses temporary synthetic values
only. It validates 64-condition support, invalid schema rejection, four rendered
families and formats, fonts/canvas bounds, missing intervals, active dispatch,
stale SHA/code rejection and descriptive-role enforcement. Its synthetic active
validator is an adapter fixture, not a substitute for the separately tested
scientific active auditor. No real figure render is authorized by these tests.
Actual rendering awaits the parent's passed active audit and requires later
visual review. Existing plotter provenance and validation history are retained
in `evidence/v2/software/active_result_figures_validation.json`.

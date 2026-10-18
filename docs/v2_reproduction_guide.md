# Reproducing the completed v2 delivery

The reproduction entry point is `code/v2_reproduce.py`. Use it only after the complete576-fit delivery and all six baseline numerical outputs exist. The wrapper does not fit models, download data, install dependencies, copy datasets or change the frozen experiment. It is an additional delivery tool; the experiment's frozen execution files remain unchanged.

## Tables: default path, no GPU

Use a prepared Python environment with NumPy. Run from the delivered project or provide an independent delivery copy explicitly:

```text
python -B code/v2_reproduce.py
python -B code/v2_reproduce.py --root PATH_TO_COMPLETE_DELIVERY
```

The current interpreter runs **that target root's** `code/v2_audit_runs.py --root ROOT`, then **that target root's** `code/v2_statistics.py --root ROOT`, with the target root as working directory. It does not import analysis code from the wrapper's source checkout. A target copy therefore uses its own frozen code, inputs and results. No Torch, CUDA, CuPy, Pillow or feature NPZ arrays are needed for this tables path; NumPy is needed by the frozen audit/analysis and selection dispatcher.

Before either script starts, the wrapper requires all six existing baseline files:

- `tables/v2/conditions_by_source.csv`
- `tables/v2/conditions.csv`
- `tables/v2/regions.csv`
- `tables/v2/classes.csv`
- `tables/v2/contrasts.json`
- `tables/v2/primary.json`

It records their SHA256 values, verifies the target freeze and every frozen input hash, and requires576 existing result files. The target audit must pass before statistics starts. After recomputation it verifies the audit/analysis code bindings, input/artifact/result SHA maps, the unchanged result inventory, expected576 fits/192 source conditions/64 aggregate conditions/1536 regional rows/512 class rows, and the analysis output-hash map. The six numerical files must be byte-identical to the delivered baseline. Audit and `analysis_identity.json` timestamps may change, so their full-file SHA values need not equal an earlier run.

The wrapper writes `evidence/v2/reproduction_check.json` in the target copy, including commands, before/after numerical hashes, frozen and result identities, and errors. `passed: true` requires all checks; process exit1 means a failure. Missing baseline files are not silently generated. A differing recomputed table is reported as a failure rather than accepted or restored automatically. Keep the original delivered package if a separate byte-for-byte reference is needed. Run one reproduction at a time, after fitting and any prior analysis have stopped.

The wrapper's own direct writes are restricted to the target `evidence/v2/` check report. Its two explicitly requested frozen subprocesses regenerate their normal audit/table/analysis-identity outputs. It hashes inputs and completed results before and after these operations; it does not overwrite scientific run results or frozen inputs.

## Optional checkpoint reload

```text
python -B code/v2_reproduce.py --root PATH_TO_COMPLETE_DELIVERY --mode reload
```

Reload mode first repeats and passes the entire tables gate. It then requires Torch, torchvision and Pillow in the current environment and runs the target's frozen `code/v2_reload_checkpoint.py`. This predetermined complete spatial checkpoint is source0, selection0, initialization0, `region_kcenter`. The verifier reconstructs `ResNet18UNet(pretrained=False)` and loads its saved state on CPU, so it needs neither an official pretrained file nor a GPU. This is inference from a saved trained state, not refitting.

The target verifier writes `evidence/v2/checkpoint_reload.json`. The wrapper requires exact integer confusion-matrix and aggregate matches for all72 images/24 regions, the predetermined result/checkpoint, matching code/data/freeze hashes, no refitting, and unchanged numerical outputs and run results. The fresh-panel PNGs are needed for this optional inference. It does not run the other575 fits again or validate arbitrary checkpoint choices.

## Required delivery evidence and interpretation

Retain the complete576 run-result/log files and predetermined checkpoint; the freeze and its listed files; original DINO index metadata; source-only calibration records/logs; new-panel index metadata; compact PNGs and SHA-bound provenance sidecars; the retained original formal manifest required by the data-audit inputs; the data/run audits; designs; source software; and six numerical tables. Follow the freeze and audit dependency maps when assembling the delivery. Feature NPZ arrays and original RGB TIFFs are not needed for tables reproduction. The processed PNG/sidecar byte hashes and the data audit's actual448-mask counts bind each image's confusion-matrix truth margins without reopening raster pixels during table reproduction.

The revised packaging plan also retains the exact192 existing DINO NPZ caches referenced by the two frozen indexes:120 source caches with native-mask-derived soft targets under `cache/dinov2-formal120/`, and72 panel evaluation-feature caches under `v2/cache/new_panel_dinov2/`. Final assembly will MOVE these SHA-verified files with unchanged relative paths after every writer has stopped, preserving the original source targets without making duplicate cache copies. This is a planned inventory rule until the final assembly/manifest proves actual delivery. Other caches, raw TIFFs and runtime trees remain outside the package. Tables reproduction remains NumPy-only and does not inspect these NPZ arrays.

The experiment comprises90 full spatial-model fits on CPU with8 threads and486 frozen-DINO feature-head fits on the local RTX4060. This is not GPU training or fine-tuning of DINO. Old24 regions are development/source data; new24 regions form the permanent panel. Three source allocations and paired selection/optimization seeds0/1/2 are averaged within each held-out region before geographic inference; the paired seeds are not independent factorial crosses or extra geographic replicates.

The primary comparison and24-region analysis remain fixed. `primary.json` also retains the prespecified descriptive23-region sensitivity excluding the entire Monrovia region because one image's declared CRS/operation lies outside its area of use. The Aachen source caution, unknown operation precision and source-mosaic independence limits remain applicable. Read `docs/v2_data_audit.md`, `docs/v2_analysis.md`, the geographic sensitivity configuration/disposition and `docs/v2_data_attribution.md`. Successful technical reproduction does not prove physical mosaic independence, equivalence, scientific novelty or journal acceptance.

RGB and label permissions remain source-specific. The label fallback license does not automatically authorize the RGB imagery. Public redistribution requires the corresponding attribution and applicable source conditions; this wrapper grants no new license or upload authorization.

## Full refitting is a separate task

There is intentionally no automatic training/download/install mode, and no actual576-fit refitting validation is claimed. The planned retained caches avoid regeneration for a separately arranged frozen-head refit. That path still needs the frozen runner and dependencies: NumPy, PyTorch for output interpolation, Pillow for compact labels, and compatible CuPy/CUDA/NVIDIA execution with the recorded settings. DINOv2 remains frozen. It needs no official DINO weights when consuming the already extracted caches, but caches and index SHAs must first be verified and a refit must use a separate workspace rather than overwrite delivered results.

Regenerating the original source caches is a different task: it requires the original native source masks/RGB, official SHA-bound DINOv2 weights, the frozen feature extractor and its recorded environment/specification. The nearest-resampled448 masks cannot replace native-resolution soft targets. Full spatial-model refitting additionally requires the official SHA-bound pretrained ResNet18 weights and the recorded CPU PyTorch environment with8 threads; the optional saved-checkpoint reload above needs no pretrained weight file. Do not silently change seeds, recipes, targets or weight versions and call it the frozen run. The retained files make a future refit better specified, but no refit or dependency installation is performed by the reproduction wrapper or packager.

Keep the project under2,000,000,000 logical bytes. The wrapper searches the target and its ancestors for the nearest `project_storage_budget.json` with `schema: "mdpi-resource-budget-1"`, `cap_bytes: 2000000000`, `scope: "this directory and descendants"`. If found, that directory and all descendants are the budget scope, including sibling V1 deliveries and runtime trees; the delivery subdirectory alone cannot hide their storage. The source policy is intentionally not copied into the delivery. An independent copy moved outside that policy tree falls back to its own target root.

An optional `--budget-root PATH` must name a target ancestor and cannot narrow an existing ancestor-policy scope. Reports describe the budget root by ancestor depth and target-relative path, not an absolute local path. The wrapper checks the whole chosen scope before and after execution, before each subprocess, and around its report write. It reserves the largest numerical table size plus4MB for atomic table/audit/identity/report work. It neither deletes evidence nor copies cached features or raw data to make room. A policy or quota failure stops the command; this tool does not choose what to delete.

## Software-only checks

```text
python -B code/v2_reproduce.py --help
python -B code/v2_reproduce.py --self-test
```

The small self-tests create an isolated OS temporary target with explicitly synthetic marker files and stub frozen scripts, then remove it. They verify target-scoped subprocess invocation, provenance/identity gates, matching six output hashes, refusal of changed frozen code, rejection of a changed numerical file even when its freshly emitted analysis hash matches it, missing baseline rejection and unsafe-path rejection. They do not read actual partial scores, execute real experiment code, produce scientific fits or run a real checkpoint reload. They are software checks, not evidence that the ongoing experiment has completed.

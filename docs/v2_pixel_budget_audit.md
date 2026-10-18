# Independent audit of the27 pixel-budget supplemental fits

`code/v2_audit_pixel_budget.py` never fits, downloads, changes original masks or modifies the original576 primary/CUDA90 execution. Its scientific path uses NumPy, Pillow and existing pure numerical validators; Torch/CuPy are not imported. The separate `validate_bundle(root)` gate uses only the standard library and the existing standard-library path/PID helper.

The fixed pixel plan SHA is `3e776a5517286d634eb29968ab3a7cafa3912e166f47d84137e8d16ef03d58e9`. It binds the source CUDA plan, original53-file freeze, runner/helper, protocol, diagnostic/rationale, software checks and implementation/test documentation. All `supplemental_input_sha256` entries are current-SHA verified. The exact ordered27 specs must equal the original CUDA90's three policies across three sources and three paired seeds; runtime, source-calibrated recipe, selection and panel are unchanged.

```text
python -B code/v2_audit_pixel_budget.py --root PROJECT_ROOT
python -B code/v2_audit_pixel_budget.py --root PROJECT_ROOT --audit-only
python -B code/v2_audit_pixel_budget.py --root PROJECT_ROOT --validate-bundle
```

No result CM is accessed until both CUDA90 and pixel writers/children are terminal, all27 paths exist without extras, and every27 result's completion/identity/provenance/recipe/log/attempt/lease/supervision metadata passes. A late corrupt or noncomplete record must leave `score_fields_opened: false`. The baseline requires a passed, hash-current CUDA90 audit and exact90 original result files. Missing/extra/live/unknown evidence fails closed; no partial analysis is produced.

The auditor independently decodes each selected original448 mask from its SHA-bound PNG and maps raw0 to255 and raw1..8 to0..7. In selected-image then row-major-valid order it builds a global keep vector, hides the uniform PCG64 sample of `N-2300000` positions using seed2026101811 plus selection seed, and reconstructs each uint8 target. This implementation does not call the runner's mask function. Every original/retained count, eight-class count, removed-class list, full mask SHA, little-endian packed keep-bitmap SHA, concatenated bitmap SHA and source RGB/label hash is checked. All fits must retain exactly2,300,000 valid source pixels. Original void remains ignored. Nothing is written to a raster or thinned evaluation mask.

The saved NumPy version must match the locked training runtime. Audit reconstruction records its own version and accepts only exact mask/bitmap SHA equality, even across library versions; if reconstruction differs, rerun using the recorded NumPy2.3.5 environment without importing Torch. Do not reinterpret a mismatching random mask as equivalent.

Existing CUDA pure validators check the unchanged recipe/runtime, selected-record/model/pretrained hashes, finite/state-hash declarations and complete sampled loss logs. Raw logs and start attempts are SHA-bound. Logs contain step1/every50/final, so unrecorded optimizer steps cannot be individually proved; CUDA learned states were not saved, so finite/state hash declarations cannot be independently reloaded. Original-crop eligibility, independent mask RNG and restoration before evaluation are bound through runner code/software proof and explicit restoration fields, not replay of unlogged crop draws.

Both72 panel and20 source-validation CMs require their original data-audit truth margins, never retained-training counts. Original aggregate metrics are recomputed. Each pixel fit has the same identity and ordered selection as its full-label CUDA90 reference.

The audit is `evidence/v2/pixel_budget_audit.json`, format `v2-pixel-budget-audit-1`, with passed/expected/observed/validated27, errors/missing/extra/duplicates, result_files, artifact_sha256, code_sha256, inputs, source_cuda_result_files and source_cuda_artifact_sha256. All recognized execution history is retained and hash-bound: exact planned run result/attempt/training/failure/closed-claim names and generation execution, closed lease, worker/supervisor summaries, worker leases, start/stop, budget and raw stdout. Historical logs may be valid sampled prefixes, not completed fits. Unknown names or conflicting identities fail; arbitrary files are not silently added. Only exact one-byte OS guard markers at their known guard paths are excluded, and exclusions are listed.

After audit passes, `tables/v2_pixel_budget/descriptive_analysis.json` has format `v2-pixel-budget-descriptive-1`, scope `DESCRIPTIVE_POST_EXPOSURE_PIXEL_BUDGET`, audit SHA and identical file maps. It reports only geographic k-center minus ordinary k-center and geographic k-center minus permuted geographic k-center, each with thinned contrast, matching full-label contrast and their paired change. Within each region the same nine source/seed fits are averaged first; source strata use their three paired seeds. Paired change is `(thinned A-B)-(full-label A-B)` in each matched region, not a comparison of two interval signs. All summaries use the original24 regions,10,000 region-bootstrap resamples and seed2026101805. They are post-exposure descriptive outputs, not a new margin, test family, independent holdout or replacement primary.

`validate_bundle(root)` is read-only and does not recompute science. It verifies terminal state, exact inventories, all file maps/counts/scope, current plan/protocol/runner/supplemental inputs and analysis-to-audit binding. It returns at least `{passed, validated_count, audit_sha256, analysis_sha256, file_sha256, read_only, scientific_analysis_recomputed}`. `file_sha256` unions input/code/result/artifact and both CUDA90 reference maps plus audit/analysis themselves. It includes the runner, tests, software proof, protocol/plan/rationale and these four audit support files. Existing data/cache/CUDA90 files are references for the parent packager to reuse rather than duplicate. A package must provide every mapped path unchanged.

```text
python -B code/v2_audit_pixel_budget.py --self-test
```

Synthetic tests use temporary real448 label PNGs, known CMs and fake fit records, never the ongoing scientific results or a GPU. They exercise independent masks,27 completeness/late metadata gating, altered masks/CM/log/provenance/history refusal, full-label paired-change arithmetic and a fresh-process standard-library-only bundle check. Software evidence is `evidence/v2/software/pixel_budget_audit_validation.json`. A successful software check does not establish completion or an empirical result for the real27 fits.

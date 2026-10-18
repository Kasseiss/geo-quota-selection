# Equal available processed-label implementation

This is an implementation record for a separate, post-panel-exposure descriptive ablation. It does not amend the original 53-file experiment freeze, the original primary analysis, or the locked CUDA90 execution plan. No actual fit was run during implementation validation.

## Fixed inputs and plan contract

`code/v2_pixel_budget.py` requires an explicit `--run`. `--self-test` runs temporary synthetic fixtures only. The real entry point reads `configs/v2_pixel_budget_plan.json`, which the parent creates only after this runner is stable. The following fields are mandatory:

- `format: v2-pixel-budget-plan-1`, `status: LOCKED_BEFORE_PIXEL_BUDGET_FITS_AFTER_PANEL_EXPOSURE`, `prior_target_exposure: true`, and `expected_runs: 27`.
- `runner_code_sha256`: the exact bytes of this runner; `helper_code_sha256`: a one-entry map binding `code/v2_cuda_parallel_v2.py`. The helper supplies path checks, process identity, OS mutexes, serialization, memory checks and byte counting. Its constants, storage class and scientific backend are not modified or used.
- `protocol_sha256`: the exact `docs/v2_pixel_budget_protocol.md` bytes.
- `source_cuda_plan: configs/v2_cuda_execution_plan.json` and `source_cuda_plan_sha256: 15d586fd03389d495dfc2b7d9cdea35b2b3089461ccb49cc37e5f8bd39ff1545`.
- `original_freeze_sha256`, `original_frozen_file_sha256`, `runtime`, and `new_panel_image_ids`: unchanged copies from the source CUDA90 plan. All 53 original frozen files must still match.
- `runs`: exactly the source plan's ordered entries filtered to `kcenter`, `region_kcenter`, and `permuted_region_kcenter`. Each full entry, including selection metadata, ordered selected IDs, paired initialization seed, CPU-calibrated learning rate and steps, must match. This produces three allocations × three paired seeds × three policies = 27 fits.
- `supervision` is exactly `processed_grid: [448,448]`, `available_valid_pixel_budget: 2300000`, `mask_seed_base: 2026101811`, `mask_order: ordered_selected_ids_then_row_major_original_valid_positions`, `sampling: uniform_remove_without_replacement`, and `original_void_remains_ignored: true`.

Optional scheduling fields, if supplied, must be `workers: 2`, `external_growth_reserve_bytes: 55000000`, and `per_worker_output_reserve_bytes: 4000000`. The runtime's `python` records source-plan preparation; `cuda_python` is the version required for actual execution. Runtime checking uses `cuda_python`.

## Mask construction and unchanged crop randomness

For each fit, original masks are loaded and checked through the frozen loader. Only internal class values 0–7 are valid; 255 is ignored. The 12 masks remain in the plan's selected-ID order. Valid positions are enumerated row-major within each image and concatenated conceptually by image. An independent `numpy.default_rng(2026101811 + selection_seed)` draws exactly `N - 2300000` distinct global valid-position indices with `choice(N, size, replace=False)`. Sorting the drawn indices only supports mapping back to images; it does not change the sampled set. Those labels become 255 in copied in-memory masks. RGB, original mask bytes, selection IDs and source records remain unchanged. No class value is consulted when sampling; class counts are computed afterward. A rare class may disappear and is recorded without resampling.

The training context temporarily wraps both `segmentation.load_pair` and `segmentation.make_batch`, without editing either source file. The batch wrapper reproduces the frozen image draw, up-to-16 crop attempts, two flip draws, quarter rotation and ImageNet normalization. Crop eligibility and retries always inspect the original full mask, while the loss receives the thinned mask at identical coordinates and transformations. This prevents removed labels from altering subsequent optimization RNG draws. A crop eligible under the original mask but entirely ignored after thinning fails closed after the same augmentation draws; it does not trigger another crop, add labels or change the seed. Synthetic tests compare RGB batches, retained class identities and generator state against the frozen sampler, including an explicit sparse-label retry case.

Both wrappers are restored in `finally` before any panel or source-validation evaluation, including a training failure. Validation uses all 20 original processed masks; panel evaluation uses all 72 original processed masks. Fitting calls the frozen `fit` with batch size 2, crop 224, the same seed/LR/steps and CUDA warn-only determinism. The existing official pretrained weight SHA must match before fitting; there is no download or CPU fallback. No new trained checkpoint is saved.

## Supervision evidence and hashes

Each result contains `pixel_supervision` with the mask seed, NumPy version, original and retained valid totals, deleted count, ordered IDs and per-image evidence. Per-image records include original/retained eight-class counts, classes removed entirely, original/retained valid counts and two SHA256 values:

- `training_mask_uint8_row_major_sha256`: all 448×448 internal labels encoded as uint8, row-major, with values 0–7/255.
- `keep_bitmap_sha256`: `numpy.packbits((mask != 255).ravel(order='C'), bitorder='little')` bytes. `combined_keep_bitmap_sha256` hashes these separately packed image buffers concatenated in selected-ID order.

`source_processed_file_sha256` binds each selected image's original processed RGB and label SHA. `pixel_supervision_sha256` hashes the complete metadata serialized as `json.dumps(indent=2, ensure_ascii=True, allow_nan=False) + '\n'`, UTF-8. Full masks are not written to disk. Results additionally bind runner, helper, plan, protocol, original freeze and its 53-file map, selected IDs, training state hashes, training logs and panel/validation confusion matrices. The frozen training identity still describes the original source records; the added supervision evidence identifies the actual masked targets supplied to this ablation.

## Two-worker admission, storage and recovery

All new outputs are under `evidence/v2/pixel_budget_execution/`. Two separate OS Python processes execute fixed plan indices modulo two, one fit at a time per process. A parent writer lease records PID plus creation identity, plan/code SHA, generation and registered children; per-worker leases record reserved/initializing/ready/terminal states; per-fit claims prevent duplicate writes. Children require registration by the live parent and wait at a launch barrier until both are ready. Failed workers request a cooperative stop between fits; the supervisor does not kill another fit and retains the global lease until all launched children have exited. Unknown launches preserve the lease for manual inspection.

Startup refuses any live or unknown CUDA90 writer/worker, any stale CUDA90 writer lease not recovered through its own supervisor, missing/extra CUDA90 result files, or mismatched terminal result identity/log SHA. It holds the existing CUDA supervisor's admission mutex for the whole ablation, preventing a concurrent supervisor restart. The scalar CUDA runner does not participate in that mutex, so the parent must also keep all CUDA90 launch paths stopped. The parent's independent complete CUDA audit remains a separate prerequisite; this runner's terminal check is not a scientific audit.

An initial and per-fit whole-project size scan retains the 2,000,000,000-byte cap, 55 MB for other writers and 4 MB per active pixel worker. Serialized byte charges use a monotone maximum of fresh observations and prior reservations, plus conservative metadata overhead. Every result and raw log must fit its 4 MB per-fit bound. Existing result files are never overwritten; resume requires matching plan/code/selection/training/masking identity and an unchanged referenced log. Missing or malformed referenced evidence stops the worker. Result writes use exclusive creation; a crash can leave an incomplete file, which must be preserved and inspected rather than automatically replaced. Stale global/per-fit claims are likewise not silently discarded.

After the parent locks the plan and verifies the CUDA90 audit and terminal processes, it may explicitly launch the existing GPU interpreter:

```text
C:\Users\china\AppData\Local\Programs\Python\Python312\python.exe -B code/v2_pixel_budget.py --run --workers 2
```

## Interpretation and validation limits

The equalized quantity is unique available valid supervision pixels on the processed 448 grid. Crop reuse, realized supervised pixel consumption across steps, class composition, native-resolution labeled area, human annotation effort and annotation time are not equalized. Thin-empty crop failures must remain visible. All 27 comparisons are post-panel-exposure descriptive analyses on the same panel; they cannot replace the original primary or establish a new independent holdout. Backend/software variation and warn-only CUDA determinism remain disclosed.

Validation uses synthetic arrays/files and mock fit/evaluation objects. The two-process smoke check performs only synthetic mask construction and shared storage accounting. It does not run two real scientific fits, validate CUDA convergence, prove the full 27-result audit, or authorize release. The separate audit must independently reconstruct mask identities and verify complete result/log/CM evidence before any scientific interpretation.

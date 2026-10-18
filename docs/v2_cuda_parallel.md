# Scheduling the existing CUDA replication concurrently

`code/v2_cuda_parallel.py` supervises2,3 or4 independent CUDA worker processes. It changes scheduling only. The locked90-fit CUDA execution plan, original scalar reference, original53-file freeze and original576-fit primary remain unchanged. This scheduling amendment follows the user's request to improve RTX4060 utilization after earlier panel scores already existed; it is not a new holdout, model or confirmatory analysis.

The executor pins `configs/v2_cuda_execution_plan.json` to SHA256 `15d586fd03389d495dfc2b7d9cdea35b2b3089461ccb49cc37e5f8bd39ff1545`. It verifies the scalar code, CUDA preflight, original freeze and every frozen dependency before worker execution. Every process must match the plan's exact CUDA Python/Torch/NumPy/build/device identity. The same frozen segmentation functions receive the same source-selected12 images, CPU-calibrated LR/steps, batch2, crop224 and optimization seed. CPU threads remain2 per worker. Deterministic algorithms remain enabled with `warn_only=True`, as in the scalar CUDA runner. CUDA is mandatory, existing official SHA-bound ResNet weights are required, and neither downloads nor CPU fallback are implemented. Concurrency does not promise bitwise training equivalence.

## Maintainer launch sequence

Use the existing CUDA interpreter that matches the locked plan, not the CPU-only research interpreter. Stop the original scalar CUDA process safely and verify that it is terminal before launching this tool. The original CPU experiment can continue; this scheduler does not stop or reconfigure it. Do not run a scalar and parallel CUDA writer together.

```text
CUDA_PYTHON -B code/v2_cuda_parallel.py --workers 2 --limit-per-worker 2
CUDA_PYTHON -B code/v2_cuda_parallel.py --workers 3 --limit-per-worker 2
CUDA_PYTHON -B code/v2_cuda_parallel.py --workers 4 --limit-per-worker 2
```

Each command is a separate scheduling generation and consumes only still-missing original identities. Choose the feasible faster configuration using recorded wall time, successful fitting steps, memory and worker status, without examining scores. Then omit `--limit-per-worker` to execute the remaining assigned identities. These commands are instructions for an explicit future launch, not evidence that concurrency has been benchmarked or validated on real fits.

Plan index modulo worker count fixes disjoint ownership; each worker executes its own partition serially. Before skipping an existing complete record, the worker checks identity, exact plan and source-selection binding, CUDA training recipe/runtime, finite-parameter flag, actual raw-log SHA and scoped path. Scalar records retain their scalar code identity. New records use the same per-run paths and result format, but `code_sha256` and `executor_code_sha256` identify this actual executor; `scalar_reference_code_sha256` identifies the unchanged reference. Parallel records additionally bind the generation's scheduling amendment and its SHA. The caller must update any secondary CUDA auditor to recognize this explicit provenance rather than relabeling new execution as the original scalar.

No training or checkpoint is added beyond the original missing identities. Each successful result retains raw training logs, the frozen fit's state hash, all72 panel and20 source-validation per-image confusion matrices, CUDA peak allocated/reserved memory and warn-only warnings. No extra learned checkpoint is saved.

## Writer protection and recovery

The supervisor exclusively owns the same `evidence/v2/cuda_execution/writer.lock` used by the scalar. A live old scalar, live supervisor, live child recorded by a stale supervisor, or live/unknown per-worker lease refuses a new generation. A kernel-held admission mutex serializes supervisors, including stale recovery. PID creation tokens prevent treating an unrelated reused PID as the original child when the OS supplies that identity; unavailable process identity is treated conservatively.

Under `evidence/v2/cuda_execution/parallel/GENERATION/`, each worker has a reserved then PID-bound lease and a disjoint index list. The supervisor records each spawned PID and authorizes its worker number; another process cannot claim that number through worker mode. All children initialize before the start barrier. A crash between reserving and registering a launch leaves an unknown lease that blocks automatic recovery. Do not delete it on assumption: inspect process status and retained evidence. The scalar itself does not inspect child leases, so retain the global writer lock until recovery is resolved.

If the old global lease is proven dead, `--recover-stale` archives it before a new exclusive lease is created. This flag never ignores live/unknown children or a live scalar. Dead per-fit claims from an older generation are archived before retry; their old attempts/logs/failures are retained. Same-generation/live claims and existing output files cannot be overwritten. A per-fit failure retains evidence, records failure and requests cooperative stop; other in-progress fits finish, then no further fit starts. A dead supervisor similarly prevents workers from beginning another fit.

The startup message gives this generation's `stop.request.json` relative path. Creating that file requests stop between fits. A supervisor interrupt also requests cooperative stop and waits for launched children. It never kills workers or frees the global lease while known children remain alive. Hard-kill interruptions, ambiguous launches or capacity failures can leave locks and partial evidence for manual inspection; there is no destructive automatic rollback.

## RAM, storage and throughput evidence

Initial physical-memory admission reserves at least512MiB per pending worker plus256MiB. Workers initialize sequentially behind the barrier; each observed reduction in available RAM can raise the forecast used for remaining workers. Low RAM refuses/backoffs the generation, without silently reducing worker count. This is an admission heuristic, not a guarantee against paging or an OOM during fitting. Try2 first and inspect actual memory before3/4. Current CPU work, shared DLL pages and changing external memory demand affect admission.

Each worker lease/summary records PID creation identity and, on Windows when available, working-set and peak working-set bytes. The supervisor records physical RAM before/after initialization and at completion. It reports child exit/status, successful fitting steps,600-step units, total wall seconds and normalized total seconds per600 steps. It also reports fitting-phase wall/normalized seconds separately from startup. Only successfully saved fits contribute steps; existing skips do not. These are timing and scheduling records, not comparisons of model outcomes.

All writes remain under the selected project root. Whole-root logical bytes include sibling V1 deliveries and runtimes; hard-linked paths count separately. The executor keeps the scalar's55,000,000-byte reserve plus2,000,000 bytes per parallel worker. Workers share a kernel-locked conservative write ledger; a fresh whole-root scan precedes every fit, and each attempt's log/result payload must remain below its2MB allowance. Existing CPU writers do not share this mutex, so the55MB reserve protects against modest intervening external growth, not unlimited concurrent writes. A cap/reserve refusal stops further work and preserves evidence. No data or caches are copied/moved to make room.

## Software validation

```text
python -B code/v2_cuda_parallel.py --help
python -B code/v2_cuda_parallel.py --self-test
```

The helper uses synthetic temporary plans and mock fit/evaluation functions without importing Torch or opening real raster/results. Tests launch real helper processes for disjoint partition execution and exclusive output creation; check2/3/4 partition coverage; demonstrate2-worker then4-worker limits consume only new identities; reject resume identity/plan/log/provenance drift; refuse a live scalar, stale-parent live child, unknown launch and mismatched generation; retain failed attempt/raw log/failure without a result; and reject RAM/storage shortages. These fixtures do not prove real GPU speedup, available VRAM or successful completion of the90-fit CUDA replication. Their hash-bound report is `evidence/v2/software/cuda_parallel_validation.json`.

# CUDA parallel executor V2: shorter budget-lock scope

`code/v2_cuda_parallel_v2.py` is a separate version of the tested V1 scheduler. V1 code, documentation and evidence remain unchanged, including any live V1 generation. This version changes one scheduling hotspot: fresh whole-project directory traversal occurs outside the shared budget mutex. Inside the mutex, the newest charged total is merged with that observation using `max(previous_accounted, observed) + requested_bytes + 4096`. A snapshot that becomes stale while another writer reserves space therefore cannot erase its reservation. A missing/uninitialized state without a fresh observation fails closed.

Every fit still requests a fresh whole-root scan. There is no cached snapshot, freshness interval or relaxation of the2,000,000,000-byte cap,55,000,000-byte external-writer reserve,2,000,000 bytes per worker or per-attempt output bounds. Scans can overlap other scans and small log/result reservations instead of holding their mutex for directory traversal. Filesystem traversal errors still stop the affected operation; this version does not silently ignore disappearing files or reduce reserve. Scientific work and external filesystem writers can affect actual performance, so no speedup is asserted before a real timing benchmark.

All other scheduling and scientific settings are inherited unchanged:2/3/4 workers, fixed plan-index-modulo partitioning, serial independent fits per worker, CPU threads2, exact locked CUDA runtime, source-selected IDs, original CPU-calibrated LR/steps, seeds, batch2, crop224, warn-only deterministic policy,72 panel plus20 source-validation confusion matrices, raw training logs, memory records and no extra checkpoint. The original plan SHA remains `15d586fd03389d495dfc2b7d9cdea35b2b3089461ccb49cc37e5f8bd39ff1545`. The scalar and original53 frozen dependencies must still match it. No fitting, download or plan alteration is part of this software validation.

Use the same CUDA interpreter only after the current scalar/V1 generation and all its children are terminal:

```text
CUDA_PYTHON -B code/v2_cuda_parallel_v2.py --workers 2 --limit-per-worker 2
CUDA_PYTHON -B code/v2_cuda_parallel_v2.py --workers 3 --limit-per-worker 2
CUDA_PYTHON -B code/v2_cuda_parallel_v2.py --workers 4 --limit-per-worker 2
```

Choose feasible concurrency from full timing/memory summaries, then omit the limit for the remaining original identities. The shared global writer lease, PID creation identity, authorized child leases, launch barrier, cooperative stop and conservative stale-recovery policy are unchanged. This tool cannot coexist with an active V1/scalar writer. Read `docs/v2_cuda_parallel.md` for operational detail; `--recover-stale` still refuses live or unknown children.

New result `code_sha256` and `executor_code_sha256` identify this V2 file. The scalar reference remains explicitly separate. Completed scalar, V1 and V2 records can coexist at the original per-run paths. Resume checks their identity/plan/selection/runtime/recipe/log SHA and, for parallel records, the original generation amendment and its recorded executor SHA. It does not require old V1 records to pretend they used the current V2 code and does not rewrite completed records. A later CUDA audit must preserve this mixed provenance.

The V2 self-test imports `test_v2_cuda_parallel_v2` and that helper imports this V2 module, so the inherited five scheduler tests actually exercise the new implementation. Additional tests hold one refresh observation in flight while another reservation completes, then prove monotone accounting and cap refusal when the stale observation is merged. A synthetic mixed-provenance test validates scalar/V1/V2 resume without relabeling. Tests use only temporary synthetic byte/CM records and mock fit/evaluate functions, not real results, masks, model scores or CUDA work.

```text
python -B code/v2_cuda_parallel_v2.py --self-test
```

Validation is recorded in `evidence/v2/software/cuda_parallel_v2_validation.json`. It does not certify actual GPU throughput, absence of paging/OOM, or completion of the90-fit CUDA replication. V1 proof files remain separate.

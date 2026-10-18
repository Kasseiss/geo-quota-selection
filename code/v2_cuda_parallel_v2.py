"""V2 scheduling-only CUDA supervisor: per-fit root scan outside budget mutex.

Real execution is explicit. --self-test uses synthetic temporary fixtures only.
The existing scalar writer must have stopped before a supervisor can acquire
its writer.lock. --recover-stale never ignores a live or unknown child.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import time
import uuid
import warnings

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
ROOT = Path(__file__).resolve().parents[1]
PLAN = "configs/v2_cuda_execution_plan.json"
PLAN_SHA = "15d586fd03389d495dfc2b7d9cdea35b2b3089461ccb49cc37e5f8bd39ff1545"
SCALAR = "code/v2_cuda_execution.py"
OUT = "evidence/v2/cuda_execution"
CAP = 2_000_000_000
RESERVE = 55_000_000
PER_WORKER_RESERVE = 2_000_000
MIB = 1024 * 1024


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def raw(value):
    return (json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe(root, relative):
    require(isinstance(relative, str) and relative and ":" not in relative and "\\" not in relative,
            "Expected project-relative POSIX path")
    p = Path(relative)
    require(not p.is_absolute() and ".." not in p.parts, "Escaping relative path")
    root = Path(root).absolute()
    path = root / p
    for item in (path, *path.parents):
        try:
            info = os.lstat(item)
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_reparse_tag", 0) & 0x20000000,
                "Symlink/junction/name-surrogate path refused")
    require(path.resolve().is_relative_to(root.resolve()), "Path outside project")
    return path


def process_info(pid=None):
    """PID plus creation identity, conservative alive when access is unknown."""
    pid = os.getpid() if pid is None else int(pid)
    result = {"pid": pid, "alive": True, "creation_token": None,
              "working_set_bytes": None, "peak_working_set_bytes": None}
    if os.name == "nt":
        import ctypes as c
        from ctypes import wintypes as w
        kernel = c.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; kernel.OpenProcess.restype = w.HANDLE
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.GetProcessTimes.argtypes = [w.HANDLE, c.POINTER(w.FILETIME), c.POINTER(w.FILETIME),
                                          c.POINTER(w.FILETIME), c.POINTER(w.FILETIME)]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            result["alive"] = c.get_last_error() not in (87, 1168)
            return result
        try:
            creation, exit_time, krn, user = [w.FILETIME() for _ in range(4)]
            if kernel.GetProcessTimes(handle, c.byref(creation), c.byref(exit_time), c.byref(krn), c.byref(user)):
                result["creation_token"] = str((creation.dwHighDateTime << 32) | creation.dwLowDateTime)
                if exit_time.dwHighDateTime or exit_time.dwLowDateTime:
                    result["alive"] = False
            class Counters(c.Structure):
                _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD)] + [
                    (name, c.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
            psapi = c.WinDLL("psapi", use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, c.POINTER(Counters), w.DWORD]
            counters = Counters(); counters.cb = c.sizeof(counters)
            if psapi.GetProcessMemoryInfo(handle, c.byref(counters), counters.cb):
                result.update(working_set_bytes=counters.WorkingSetSize, peak_working_set_bytes=counters.PeakWorkingSetSize)
        finally:
            kernel.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            proc = Path(f"/proc/{pid}/stat")
            if proc.exists():
                fields = proc.read_text().rsplit(")", 1)[1].split()
                result["creation_token"] = fields[19]
                if fields[0] == "Z": result["alive"] = False
        except ProcessLookupError:
            result["alive"] = False
        except PermissionError:
            pass
    return result


def same_live_process(record):
    if not record.get("pid"):
        return False
    current = process_info(record["pid"])
    return current["alive"] and (not record.get("creation_token") or not current["creation_token"] or
                                 record["creation_token"] == current["creation_token"])


def free_physical_bytes():
    if os.name == "nt":
        import ctypes as c
        class Memory(c.Structure):
            _fields_ = [("length", c.c_ulong), ("load", c.c_ulong)] + [(name, c.c_ulonglong) for name in
                ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
        memory = Memory(); memory.length = c.sizeof(memory)
        require(c.windll.kernel32.GlobalMemoryStatusEx(c.byref(memory)), "Cannot query physical RAM")
        return memory.available
    return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")


def check_memory(pending_workers, per_worker_bytes=512*MIB):
    free = free_physical_bytes(); required = 256*MIB + per_worker_bytes * pending_workers
    require(free >= required, f"RAM backoff: free{free} below required{required} for{pending_workers} pending workers")
    return {"free_physical_bytes": free, "required_bytes": required, "pending_workers": pending_workers,
            "per_worker_forecast_bytes": per_worker_bytes, "utc": utc()}


def logical_bytes(root):
    return sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file())


def bare_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw(value)); stream.flush(); os.fsync(stream.fileno())


def bare_replace(path, value):
    tmp = path.with_name(path.name + ".tmp." + uuid.uuid4().hex)
    bare_new(tmp, value)
    tmp.replace(path)


@contextmanager
def os_guard(path, timeout=30):
    """Kernel-released one-byte mutex; dead-process recovery has no PID race."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    if path.stat().st_size == 0: stream.write(b"0"); stream.flush()
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                require(time.monotonic() < deadline, "Scheduler OS mutex remained active")
                time.sleep(.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()


class Storage:
    """Serialized conservative byte charges; whole-root refresh before each fit.

    Existing CPU writers do not share this mutex. The original55MB reserve is
    retained in addition to2MB per parallel worker; their bytes enter the next
    whole-root snapshot. Charges include conservative metadata overhead.
    """
    def __init__(self, root, generation, workers):
        self.root = Path(root); self.generation = generation; self.workers = workers
        self.base = safe(root, OUT + "/parallel/" + generation)
        self.lock = self.base / "budget.lock"; self.state = self.base / "budget.json"

    @contextmanager
    def mutex(self):
        with os_guard(self.lock):
            yield

    def charge(self, count, refresh=False):
        # Keep every per-fit fresh scan, but never block other reservations/logs
        # during directory traversal. Its observation may age while waiting for
        # the mutex: merge with the latest charged total, never replace it.
        observed = logical_bytes(self.root) if refresh or not self.state.exists() else 0
        with self.mutex():
            prior = read(self.state).get("accounted_bytes", 0) if self.state.exists() else 0
            require(prior or observed, "Uninitialized budget state requires a fresh root scan")
            estimate = max(prior, observed) + count + 4096
            require(estimate + RESERVE + self.workers * PER_WORKER_RESERVE < CAP,
                    "Whole-root2GB cap/reserve refused parallel write")
            bare_replace(self.state, {"accounted_bytes": estimate, "last_observed_bytes": observed,
                                     "generation": self.generation, "workers": self.workers, "utc": utc()})

    def new(self, path, value):
        self.charge(len(raw(value))); bare_new(path, value)

    def replace(self, path, value):
        self.charge(len(raw(value))); bare_replace(path, value)

    def append(self, path, value):
        data = (json.dumps(value, allow_nan=False) + "\n").encode()
        self.charge(len(data)); path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())


def run_key(identity):
    key = "_".join(str(identity[k]) for k in ("source_split", "pool", "budget", "selection_seed", "initialization_seed", "strategy"))
    require(all(c.isalnum() or c in "_-" for c in key), "Unsafe run identity")
    return key


def load_plan(root, expected_sha=PLAN_SHA):
    planpath = safe(root, PLAN); require(sha(planpath) == expected_sha, "Locked CUDA plan SHA differs")
    plan = read(planpath)
    require(plan["expected_runs"] == len(plan["runs"]) == 90 and len({run_key(s["identity"]) for s in plan["runs"]}) == 90,
            "CUDA plan must have90 unique fixed identities")
    require(plan["code_sha256"] == sha(safe(root, SCALAR)), "Reference scalar code differs from CUDA plan")
    require(plan["cuda_preflight_sha256"] == sha(safe(root, "evidence/v2/software/cuda_preflight.json")),
            "Locked CUDA preflight changed")
    require(plan["original_freeze_sha256"] == sha(safe(root, "configs/v2_freeze.json")), "Original freeze changed")
    for relative, checksum in plan["original_frozen_file_sha256"].items():
        require(sha(safe(root, relative)) == checksum, "Original frozen file changed: " + relative)
    require(plan["runtime"]["threads"] == 2, "Original CUDA recipe threads must remain2 per worker")
    return plan


def partitions(plan, workers):
    require(workers in (2, 3, 4), "Only2,3 or4 workers allowed")
    groups = [[i for i in range(len(plan["runs"])) if i % workers == worker] for worker in range(workers)]
    require(sorted(i for group in groups for i in group) == list(range(len(plan["runs"]))), "Partition omission/duplication")
    return groups


def outstanding_children(root):
    children = []
    base = safe(root, OUT + "/parallel")
    if base.exists():
        for path in base.glob("*/worker_*.lease.json"):
            record = read(path)
            # A reserved launch with no registered PID is intentionally unknown.
            if not record.get("pid") and record.get("state") == "reserved":
                children.append({"lease": path.relative_to(root).as_posix(), "unknown_launch": True})
            elif same_live_process(record):
                children.append({"lease": path.relative_to(root).as_posix(), "pid": record["pid"]})
    return children


def acquire_global(root, generation, workers, plan_sha, executor_sha, recover=False):
    out = safe(root, OUT); out.mkdir(parents=True, exist_ok=True)
    with os_guard(out / "parallel_admission.guard"):
        return acquire_global_guarded(root, generation, workers, plan_sha, executor_sha, recover)


def acquire_global_guarded(root, generation, workers, plan_sha, executor_sha, recover):
    out = safe(root, OUT)
    lease = out / "writer.lock"
    children = outstanding_children(root)
    require(not children, "Live/unknown child leases block all new generations: " + str(children))
    if lease.exists():
        old = read(lease)
        require(not same_live_process(old), "Active scalar/supervisor writer lease blocks parallel execution")
        for child in old.get("children", []):
            require(not same_live_process(child), "Live child in stale supervisor lease blocks recovery")
        require(recover, "Stale global lease preserved; inspect and explicitly use --recover-stale")
        archive = out / ("stale_writer_" + uuid.uuid4().hex + ".json")
        lease.rename(archive)
    value = {**process_info(), "format": "v2-cuda-parallel-writer-1", "generation": generation,
             "workers": workers, "plan_sha256": plan_sha, "executor_sha256": executor_sha, "children": [], "utc": utc()}
    bare_new(lease, value)
    return lease, value


def check_generation(root, generation, require_parent=True):
    lease = read(safe(root, OUT + "/writer.lock"))
    require(lease.get("generation") == generation and lease.get("plan_sha256") == PLAN_SHA and
            lease.get("executor_sha256") == sha(Path(__file__)), "Mismatched active scheduling generation")
    if require_parent:
        require(same_live_process(lease), "Supervisor is no longer alive; no new fits allowed")
    return lease


def validate_existing(root, spec, plan, plan_sha):
    folder = safe(root, OUT + "/" + run_key(spec["identity"]))
    path = folder / "result.json"
    if not path.exists(): return False
    result = read(path)
    require(result.get("status") == "complete" and result.get("identity") == spec["identity"] and
            result.get("plan_sha256") == plan_sha and result.get("selection") == spec["selection"],
            "Existing result identity/plan/selection mismatch")
    log = safe(root, result["log_file"])
    require(log.parent == folder and sha(log) == result["log_sha256"], "Existing result log SHA/path mismatch")
    train = result["training"]
    require(train["steps"] == spec["steps"] and train["encoder_lr"] == spec["encoder_lr"] and
            train["seed"] == spec["identity"]["initialization_seed"] and train["device"] == "cuda:0" and
            train["batch_size"] == 2 and train["crop"] == 224 and result.get("deterministic_warn_only") is True,
            "Existing result training recipe differs")
    runtime = plan["runtime"]; train_identity = train["identity"]
    require(all(train_identity.get(field) == runtime[expected] for field, expected in (
                ("torch", "torch"), ("numpy", "numpy"), ("python", "cuda_python"),
                ("threads", "threads"), ("device_name", "device"))) and
            train_identity.get("selected_ids") == spec["selection"]["selected_ids"] and
            train.get("all_final_parameters_finite") is True, "Existing result CUDA/selected training identity differs")
    if result.get("code_sha256") != plan["code_sha256"]:
        scheduling = result.get("scheduling", {})
        require(scheduling["amendment_file"] == OUT + "/parallel/" + scheduling["generation"] + "/scheduling_amendment.json",
                "Existing parallel amendment path differs from generation")
        amendment = safe(root, scheduling["amendment_file"])
        require(sha(amendment) == scheduling["amendment_sha256"], "Existing parallel amendment SHA differs")
        record = read(amendment)
        require(record["executor_code_sha256"] == result["code_sha256"] == result.get("executor_code_sha256") and
                record["plan_sha256"] == plan_sha and record["scalar_reference_code_sha256"] == plan["code_sha256"] and
                record["generation"] == scheduling["generation"] and
                record["workers"] == scheduling["workers"] in (2, 3, 4), "Existing parallel executor provenance differs")
    return True


class CudaBackend:
    def __init__(self, expected, weight_sha):
        import numpy as np
        import torch
        import v2_segmentation as segmentation
        require(torch.cuda.is_available(), "CUDA required; no CPU fallback")
        require((torch.__version__, np.__version__, platform.python_version(), torch.version.cuda, torch.cuda.get_device_name(0)) ==
                (expected["torch"], expected["numpy"], expected["cuda_python"], expected["cuda_build"], expected["device"]),
                "Exact locked CUDA runtime mismatch")
        torch.set_num_threads(expected["threads"])
        self.weight = Path(torch.hub.get_dir()) / "checkpoints/resnet18-f37072fd.pth"
        self.weight_sha = weight_sha
        require(self.weight.is_file() and sha(self.weight) == weight_sha, "Existing official ResNet weights required; no downloads")
        original = segmentation.seed_all
        def cuda_seed(seed):
            original(seed); torch.use_deterministic_algorithms(True, warn_only=True)
        segmentation.seed_all = cuda_seed
        self.torch = torch; self.segmentation = segmentation

    def execute(self, selected, validation, panel, base, spec, callback):
        require(sha(self.weight) == self.weight_sha, "Pretrained weight bytes changed")
        t = self.torch; t.cuda.reset_peak_memory_stats(); model = None
        started = time.monotonic()
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("default")
                model, training = self.segmentation.fit(selected, base, seed=spec["identity"]["initialization_seed"],
                    encoder_lr=spec["encoder_lr"], steps=spec["steps"], device="cuda:0", batch_size=2, crop=224, log_callback=callback)
                test = self.segmentation.evaluate(model, panel, base, "cuda:0")
                val = self.segmentation.evaluate(model, validation, base, "cuda:0")
                t.cuda.synchronize()
            return {"training": training, "test": test, "validation": val,
                    "cuda_peak_allocated_bytes": t.cuda.max_memory_allocated(),
                    "cuda_peak_reserved_bytes": t.cuda.max_memory_reserved(),
                    "deterministic_warn_only": True, "warnings": sorted(set(str(w.message) for w in caught)),
                    "total_seconds": time.monotonic() - started}
        finally:
            del model; gc.collect(); t.cuda.empty_cache()


def execute_partition(root, plan, generation, worker, workers, storage, backend, limit=None):
    base = storage.base; stop = base / "stop.request.json"
    manifest = read(safe(root, "v2/data/manifest.json")); design = read(safe(root, "configs/v2_design.json"))
    by_id = {p["id"]: p for p in manifest["pairs"]}; splits = {s["id"]: s for s in design["source_splits"]}
    panel = [by_id[i] for i in plan["new_panel_image_ids"]]
    require(len(panel) == 72, "Panel must remain72 images")
    amendment = base / "scheduling_amendment.json"; amendment_sha = sha(amendment)
    summary = {"worker": worker, "workers": workers, "generation": generation, "assigned_indices": partitions(plan, workers)[worker],
               "executed_indices": [], "skipped_existing": [], "successful_fitting_steps": 0, "status": "running"}
    started = time.monotonic()
    try:
        for index in summary["assigned_indices"]:
            if stop.exists(): summary["status"] = "cooperative_stop"; break
            current_lease = check_generation(root, generation)
            require(current_lease.get("amendment_sha256") == amendment_sha == sha(amendment),
                    "Scheduling amendment changed during generation")
            spec = plan["runs"][index]
            if validate_existing(root, spec, plan, PLAN_SHA):
                summary["skipped_existing"].append(index); continue
            if limit is not None and len(summary["executed_indices"]) >= limit: break
            storage.charge(0, refresh=True)
            require(sha(safe(root, PLAN)) == PLAN_SHA and sha(Path(__file__)) == read(amendment)["executor_code_sha256"],
                    "Plan/executor changed during generation")
            selected = [by_id[i] for i in spec["selection"]["selected_ids"]]
            source = splits[spec["identity"]["source_split"]]
            validation = [p for p in manifest["pairs"] if p["region"] in source["validation"]]
            require(len(selected) == len({p['id'] for p in selected}) == 12 and
                    all(p["region"] in source["train"] for p in selected) and len(validation) == 20,
                    "Locked source/validation identities differ")
            folder = safe(root, OUT + "/" + run_key(spec["identity"])); folder.mkdir(parents=True, exist_ok=True)
            claim = folder / "parallel_fit.lock"
            claim_value = {**process_info(), "generation": generation, "worker": worker, "index": index, "plan_sha256": PLAN_SHA}
            if claim.exists():
                old_claim = read(claim)
                require(not same_live_process(old_claim) and old_claim.get("generation") != generation,
                        "Live/same-generation per-fit claim refuses duplicate output")
                claim.rename(folder / ("claim_recovered_" + uuid.uuid4().hex + ".json"))
            storage.new(claim, claim_value)
            attempt = str(time.time_ns()) + "_" + str(worker)
            log = folder / ("training_attempt_" + attempt + ".jsonl")
            scheduling = {"generation": generation, "worker": worker, "workers": workers, "plan_index": index,
                          "partition_rule": "fixed_plan_index_modulo_workers", "pid": os.getpid(),
                          "amendment_file": amendment.relative_to(root).as_posix(), "amendment_sha256": amendment_sha,
                          "cpu_threads_per_worker": 2}
            storage.new(folder / ("attempt_" + attempt + ".json"), {"status": "started", "identity": spec["identity"],
                        "plan_sha256": PLAN_SHA, "device": "cuda:0", "scheduling": scheduling})
            try:
                log_bytes = 0
                def callback(entry):
                    nonlocal log_bytes
                    log_bytes += len(raw(entry))
                    require(log_bytes < PER_WORKER_RESERVE // 2, "Unexpected raw training log growth")
                    storage.append(log, entry)
                    if entry["step"] == 1 or entry["step"] % 300 == 0:
                        print(json.dumps({"phase": "parallel_cuda_training", "worker": worker, "index": index,
                                          "step": entry["step"], "device": "cuda:0"}), flush=True)
                payload = backend.execute(selected, validation, panel, safe(root, "v2/data"), spec, callback)
                result = {"format": "v2-cuda-execution-result-1", "status": "complete", "identity": spec["identity"],
                          "plan_sha256": PLAN_SHA, "code_sha256": sha(Path(__file__)), "executor_code_sha256": sha(Path(__file__)),
                          "scalar_reference_code_sha256": plan["code_sha256"], "selection": spec["selection"],
                          "log_file": log.relative_to(root).as_posix(), "log_sha256": sha(log),
                          "scheduling": scheduling, "created_utc": utc(), **payload}
                require(len(raw(result)) + log_bytes < PER_WORKER_RESERVE, "Per-fit output exceeds reserved2MB")
                storage.new(folder / "result.json", result)
                summary["executed_indices"].append(index); summary["successful_fitting_steps"] += spec["steps"]
            except BaseException as exc:
                storage.new(folder / ("failure_" + attempt + ".json"), {"identity": spec["identity"], "plan_sha256": PLAN_SHA,
                            "error": type(exc).__name__ + ": " + str(exc), "scheduling": scheduling, "log_retained": log.name})
                raise
            finally:
                if claim.exists() and read(claim).get("pid") == os.getpid():
                    claim.rename(folder / ("claim_" + attempt + ".closed.json"))
        if summary["status"] == "running": summary["status"] = "complete"
    except BaseException as exc:
        summary.update(status="failed", error=type(exc).__name__ + ": " + str(exc))
        if not stop.exists(): storage.new(stop, {"reason": "worker_failure", "worker": worker, "utc": utc()})
    finally:
        summary.update(wall_seconds=time.monotonic() - started, process=process_info(), free_physical_bytes_at_end=free_physical_bytes())
        storage.new(base / f"worker_{worker}.summary.json", summary)
    return summary


def worker_main(args):
    root = Path(args.root).resolve(); lease = check_generation(root, args.generation)
    require(lease["workers"] == args.workers and args.worker_id in range(args.workers), "Worker generation/partition mismatch")
    storage = Storage(root, args.generation, args.workers); worker_lease = storage.base / f"worker_{args.worker_id}.lease.json"
    deadline = time.monotonic() + 30
    while not any(c.get("worker") == args.worker_id and c["pid"] == os.getpid() and same_live_process(c)
                  for c in lease["children"]):
        require(time.monotonic() < deadline, "Worker PID is not authorized by supervisor")
        time.sleep(.1); lease = check_generation(root, args.generation)
    amendment_path = storage.base / "scheduling_amendment.json"
    amendment = read(amendment_path)
    require(lease.get("amendment_sha256") == sha(amendment_path) and amendment["generation"] == args.generation and
            amendment["workers"] == args.workers and amendment["plan_sha256"] == PLAN_SHA and
            amendment["executor_code_sha256"] == sha(Path(__file__)) and
            amendment["limit_per_worker"] == args.limit_per_worker, "Worker scheduling amendment differs")
    reservation = read(worker_lease)
    require(reservation["state"] == "reserved" and reservation["worker"] == args.worker_id and
            reservation["generation"] == args.generation, "Worker lease already claimed/mismatched")
    own = {**reservation, **process_info(), "state": "initializing"}; storage.replace(worker_lease, own)
    try:
        plan = load_plan(root)
        require(reservation["workers"] == args.workers and
                reservation["assigned_indices"] == partitions(plan, args.workers)[args.worker_id],
                "Worker lease partition differs from fixed plan")
        weight_sha = read(safe(root, "evidence/v2/calibration/calibration.json"))["environment"]["pretrained_weight_sha256"]
        backend = CudaBackend(plan["runtime"], weight_sha)
        own.update(state="ready", process_after_runtime_import=process_info()); storage.replace(worker_lease, own)
        deadline = time.monotonic() + 180
        while not (storage.base / "start.json").exists():
            if (storage.base / "stop.request.json").exists(): return 1
            check_generation(root, args.generation)
            require(time.monotonic() < deadline, "Supervisor launch barrier timed out")
            time.sleep(.25)
        summary = execute_partition(root, plan, args.generation, args.worker_id, args.workers, storage, backend, args.limit_per_worker)
        return 0 if summary["status"] == "complete" else 1
    except BaseException as exc:
        if not (storage.base / f"worker_{args.worker_id}.summary.json").exists():
            storage.new(storage.base / f"worker_{args.worker_id}.summary.json", {"worker": args.worker_id,
                        "status": "failed_initialization", "error": type(exc).__name__ + ": " + str(exc), "process": process_info(),
                        "executed_indices": [], "successful_fitting_steps": 0})
        return 1
    finally:
        own.update(state="terminal", process_at_exit=process_info(), terminal_utc=utc()); storage.replace(worker_lease, own)


def supervise(args):
    root = Path(args.root).resolve(); plan = load_plan(root)
    require(args.workers in (2, 3, 4) and (args.limit_per_worker is None or args.limit_per_worker > 0), "Invalid worker count/limit")
    partitions(plan, args.workers)
    initial_ram = check_memory(args.workers)
    require(logical_bytes(root) + RESERVE + args.workers * PER_WORKER_RESERVE < CAP, "Whole-root2GB reserve unavailable")
    generation = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:10]
    lease_path, lease = acquire_global(root, generation, args.workers, PLAN_SHA, sha(Path(__file__)), args.recover_stale)
    storage = Storage(root, generation, args.workers); base = storage.base
    children = []; handles = []; summary = {"generation": generation, "workers": args.workers, "child_statuses": [],
        "ram_observations": [initial_ram], "plan_sha256": PLAN_SHA, "executor_code_sha256": sha(Path(__file__)),
        "status": "initializing", "successful_fitting_steps": 0, "started_utc": utc()}
    started = time.monotonic(); fitting_started = None
    try:
        amendment = {"format": "v2-cuda-scheduling-amendment-1", "status": "SCHEDULING_ONLY_AFTER_PRIOR_SCORES",
            "created_utc": utc(), "generation": generation, "workers": args.workers, "allowed_workers": [2, 3, 4],
            "plan_sha256": PLAN_SHA, "executor_code_sha256": sha(Path(__file__)), "scalar_reference_code_sha256": plan["code_sha256"],
            "motivation": "User explicitly requested concurrent GPU experiments to improve utilization and wall time.",
            "primary_and_original_576_unchanged": True, "source_selected_ids_lr_steps_batch_crop_seeds_unchanged": True,
            "new_confirmatory_holdout": False, "cpu_threads_per_worker": 2, "deterministic_warn_only": True,
            "partition_rule": "fixed plan index modulo workers; serial independent fits per process",
            "limit_per_worker": args.limit_per_worker, "runtime": plan["runtime"],
            "memory_launch_policy": "At least512MiB per pending worker plus256MiB physical reserve; increase forecast to observed initialization RAM deltas; refuse/back off, never silently lower workers",
            "storage_policy": {"whole_root_cap_bytes": CAP, "external_writer_reserve_bytes": RESERVE,
                               "additional_per_worker_reserve_bytes": PER_WORKER_RESERVE},
            "no_extra_checkpoint": True, "score_fields_used_for_scheduling": False}
        storage.new(base / "scheduling_amendment.json", amendment)
        lease["amendment_sha256"] = sha(base / "scheduling_amendment.json"); storage.replace(lease_path, lease)
        print(json.dumps({"generation": generation, "workers": args.workers, "stop_file": (base/"stop.request.json").relative_to(root).as_posix(),
                          "free_physical_bytes": initial_ram["free_physical_bytes"]}), flush=True)
        per_worker_forecast = 512*MIB
        for worker in range(args.workers):
            observation = check_memory(args.workers - worker, per_worker_forecast)
            summary["ram_observations"].append(observation)
            storage.new(base / f"worker_{worker}.lease.json", {"state": "reserved", "pid": None, "worker": worker,
                        "workers": args.workers, "generation": generation, "assigned_indices": partitions(plan, args.workers)[worker]})
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--root", str(root), "--worker",
                       "--workers", str(args.workers), "--worker-id", str(worker), "--generation", generation]
            if args.limit_per_worker is not None: command += ["--limit-per-worker", str(args.limit_per_worker)]
            stdout = (base / f"worker_{worker}.stdout.log").open("xb"); handles.append(stdout)
            process = subprocess.Popen(command, cwd=root, stdout=stdout, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            children.append((worker, process)); lease["children"].append({"worker": worker, **process_info(process.pid)}); storage.replace(lease_path, lease)
            deadline = time.monotonic() + 180
            while read(base / f"worker_{worker}.lease.json")["state"] != "ready":
                require(process.poll() is None, "Worker initialization failed; inspect retained stdout/summary")
                require(time.monotonic() < deadline, "Worker initialization timed out")
                time.sleep(.25)
            after_free = free_physical_bytes()
            per_worker_forecast = max(per_worker_forecast, observation["free_physical_bytes"] - after_free)
            summary["ram_observations"].append({"after_worker_ready": worker, "free_physical_bytes": after_free,
                                                "next_worker_forecast_bytes": per_worker_forecast})
        storage.new(base / "start.json", {"generation": generation, "children": lease["children"], "utc": utc()})
        fitting_started = time.monotonic()
        summary["status"] = "running"
        while any(p.poll() is None for _, p in children):
            if any(p.poll() not in (None, 0) for _, p in children) and not (base / "stop.request.json").exists():
                storage.new(base / "stop.request.json", {"reason": "child_failure", "utc": utc()})
            time.sleep(.5)
        summary["status"] = "complete" if all(p.returncode == 0 for _, p in children) else "failed"
    except BaseException as exc:
        summary.update(status="failed", error=type(exc).__name__ + ": " + str(exc))
        if not (base / "stop.request.json").exists():
            storage.new(base / "stop.request.json", {"reason": "supervisor_failure_or_interrupt", "utc": utc()})
        # Cooperative only: retain the global lease until every launched child exits.
        for _, process in children:
            while process.poll() is None:
                try: process.wait(timeout=1)
                except subprocess.TimeoutExpired: pass
    finally:
        for handle in handles: handle.close()
        for worker, process in children:
            path = base / f"worker_{worker}.summary.json"
            child = read(path) if path.exists() else {"status": "no_summary", "successful_fitting_steps": 0}
            summary["child_statuses"].append({"worker": worker, "pid": process.pid, "exit_code": process.poll(), "summary": child})
            summary["successful_fitting_steps"] += child["successful_fitting_steps"]
        summary["wall_seconds"] = time.monotonic() - started
        steps = summary["successful_fitting_steps"]
        fit_wall = time.monotonic() - fitting_started if fitting_started is not None else None
        summary.update(successful_600_step_units=steps / 600, normalized_seconds_per_600_steps=summary["wall_seconds"] / (steps/600) if steps else None,
                       fitting_phase_wall_seconds=fit_wall, startup_wall_seconds=(fitting_started-started) if fitting_started is not None else None,
                       fitting_phase_seconds_per_600_steps=fit_wall/(steps/600) if fit_wall is not None and steps else None,
                       free_physical_bytes_at_end=free_physical_bytes(), finished_utc=utc(), score_fields_read=False)
        storage.new(base / "supervisor_summary.json", summary)
        require(all(process.poll() is not None for _, process in children), "Live children: preserve global writer lease")
        require(read(lease_path).get("generation") == generation, "Global writer generation changed")
        current_leases = [read(p) for p in base.glob("worker_*.lease.json")]
        require(not any(p.get("state") == "reserved" and not p.get("pid") for p in current_leases),
                "Unknown child launch: preserve global writer lease for manual inspection")
        lease_path.rename(base / "global_lease.closed.json")
        print(json.dumps({k: v for k, v in summary.items() if k != "child_statuses"}), flush=True)
    return 0 if summary["status"] == "complete" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--workers", type=int, choices=(2, 3, 4), default=2)
    parser.add_argument("--limit-per-worker", type=int)
    parser.add_argument("--recover-stale", action="store_true", help="Archive a proven-dead global lease; live/unknown children still refuse")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker-id", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--generation", help=argparse.SUPPRESS)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        import unittest
        import test_v2_cuda_parallel_v2
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_v2_cuda_parallel_v2))
        return 0 if result.wasSuccessful() else 1
    try:
        return worker_main(args) if args.worker else supervise(args)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print("CUDA PARALLEL STOPPED: " + type(exc).__name__ + ": " + str(exc), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

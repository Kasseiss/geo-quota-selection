"""Read-only, fail-closed CUDA90 delivery whitelist; no fitting or migration.

The scientific CUDA auditor remains authoritative for recipe/CM validation.
This helper checks its exact byte bindings, closed scheduling history and the
complete small-text CUDA payload. It never parses scientific score fields.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parents[1]
PLAN = "configs/v2_cuda_execution_plan.json"
PLAN_SHA = "15d586fd03389d495dfc2b7d9cdea35b2b3089461ccb49cc37e5f8bd39ff1545"
BASE = "evidence/v2/cuda_execution"
AUDIT = "evidence/v2/cuda_execution_audit.json"
ANALYSIS = "tables/v2_cuda/descriptive_analysis.json"
ORIGIN = "cuda90_closed_execution_inventory"
FORMAT = "v2-cuda90-delivery-inventory-1"
# Existing, immutable evidence that the original scalar stopped at a completed
# fit boundary. This is deliberately not a general-purpose stale-lease waiver.
LEGACY_SCALAR_RECEIPTS = {
    "evidence/v2/audit_attempts/cuda_parallel_boundary_switch_20261018T072357896177Z.json":
        "842d48e5a39ebaffa9e27e397083d514ee3f1e2e739bf60d8601ab8c14de8a2b",
}
SUPPORT = (
    PLAN, AUDIT, ANALYSIS,
    "code/v2_cuda_execution.py", "code/v2_cuda_parallel.py", "code/v2_cuda_parallel_v2.py",
    "code/test_v2_cuda_parallel.py", "code/test_v2_cuda_parallel_v2.py",
    "code/v2_audit_cuda.py", "code/test_v2_audit_cuda.py",
    "code/v2_cuda_delivery_inventory.py", "code/test_v2_cuda_delivery_inventory.py",
    "docs/v2_cuda_execution.md", "docs/v2_cuda_parallel.md", "docs/v2_cuda_parallel_v2.md",
    "docs/v2_cuda_audit.md", "docs/v2_cuda_delivery_inventory.md",
    "evidence/v2/software/cuda_preflight.json",
    "evidence/v2/software/cuda_parallel_validation.json",
    "evidence/v2/software/cuda_parallel_v2_validation.json",
    "evidence/v2/software/cuda_audit_validation.json",
    "evidence/v2/software/cuda_delivery_inventory_validation.json",
)
GENERATION = re.compile(r"\d{8}T\d{6}_[a-f0-9]{10}\Z")
RUN_FILE = re.compile(r"(?:result\.json|attempt_\d+(?:_\d+)?\.json|training_attempt_\d+(?:_\d+)?\.jsonl|"
                      r"failure_\d+(?:_\d+)?\.json|claim_\d+_\d+\.closed\.json|claim_recovered_[a-f0-9]+\.json)\Z")
GEN_FILE = re.compile(r"(?:scheduling_amendment|supervisor_summary|global_lease\.closed|start|budget|stop\.request)\.json\Z|"
                      r"worker_[0-3]\.(?:lease\.json|summary\.json|stdout\.log)\Z")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def raw(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n").encode()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def child(root, relative):
    require(isinstance(relative, str) and relative and ":" not in relative and "\\" not in relative,
            "Expected relative POSIX path")
    part = Path(relative)
    require(not part.is_absolute() and ".." not in part.parts and "." not in part.parts,
            "Unsafe relative path")
    root = Path(os.path.abspath(root))
    path = root / part
    for item in (path, *path.parents):
        try:
            info = os.lstat(item)
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_reparse_tag", 0) & 0x20000000,
                "Redirecting symlink/junction/name-surrogate path refused")
    require(path.resolve().is_relative_to(root.resolve()), "Path leaves project")
    return path


def process_identity(pid):
    """Conservative OS liveness with PID-creation identity; no process changes."""
    require(isinstance(pid, int) and not isinstance(pid, bool) and pid > 0, "Invalid process identity")
    result = {"alive": True, "creation_token": None, "creation_clock": None}
    if os.name == "nt":
        import ctypes as c
        from ctypes import wintypes as w
        kernel = c.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        kernel.OpenProcess.restype = w.HANDLE
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.GetProcessTimes.argtypes = [w.HANDLE, c.POINTER(w.FILETIME), c.POINTER(w.FILETIME),
                                          c.POINTER(w.FILETIME), c.POINTER(w.FILETIME)]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            result["alive"] = c.get_last_error() not in (87, 1168)
            return result
        try:
            creation, exited, cpu, user = [w.FILETIME() for _ in range(4)]
            if kernel.GetProcessTimes(handle, c.byref(creation), c.byref(exited), c.byref(cpu), c.byref(user)):
                result["creation_token"] = str((creation.dwHighDateTime << 32) | creation.dwLowDateTime)
                result["creation_clock"] = "windows_filetime_100ns_since_1601"
                result["alive"] = not bool(exited.dwHighDateTime or exited.dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            p = Path(f"/proc/{pid}/stat")
            if p.exists():
                fields = p.read_text().rsplit(")", 1)[1].split()
                result["creation_token"] = fields[19]
                result["creation_clock"] = "linux_proc_start_ticks"
                result["alive"] = fields[0] != "Z"
        except ProcessLookupError:
            result["alive"] = False
        except PermissionError:
            pass
    return result


def require_dead(record, label):
    require(isinstance(record, dict) and record.get("pid"), "Unknown process/launch: " + label)
    current = process_identity(record["pid"])
    different_identity = (record.get("creation_token") and current.get("creation_token") and
                          str(record["creation_token"]) != current["creation_token"])
    require(not current["alive"] or different_identity, "Live or unobservable process: " + label)


def terminal_filetime(value):
    """Convert an aware UTC receipt time to exact FILETIME ticks, without float."""
    require(isinstance(value, str), "Missing legacy scalar terminal UTC")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid legacy scalar terminal UTC") from exc
    require(moment.tzinfo is not None and moment.utcoffset() == timedelta(0),
            "Legacy scalar terminal time must be explicit UTC")
    delta = moment - datetime(1601, 1, 1, tzinfo=timezone.utc)
    ticks = (delta.days * 86400 + delta.seconds) * 10_000_000 + delta.microseconds * 10
    require(0 < ticks < 2**64, "Legacy scalar terminal UTC outside FILETIME range")
    return ticks


def legacy_scalar_resolution(root, record, label):
    """Resolve only a token-less scalar using a SHA-pinned prior stop receipt.

    An unrelated process must have an OS Windows creation identity strictly
    later than the recorded confirmed stop. No process is killed or modified.
    Matching receipts stay bound even when the PID is currently dead, keeping
    the delivered inventory independent of later PID reuse.
    """
    require(isinstance(record, dict) and record.get("pid"), "Unknown process/launch: " + label)
    if record.get("creation_token"):
        require_dead(record, label)
        return {}
    current = process_identity(record["pid"])
    receipts = {}
    terminal = None
    if set(record) == {"pid", "plan_sha256"} and record["plan_sha256"] == PLAN_SHA:
        for relative, expected in LEGACY_SCALAR_RECEIPTS.items():
            path = child(root, relative)
            if not path.is_file():
                continue
            require(sha(path) == expected, "Legacy scalar terminal receipt SHA differs: " + relative)
            receipt = read(path)
            require(isinstance(receipt, dict), "Invalid legacy scalar terminal receipt")
            if receipt.get("previous_writer_lease") != record:
                continue
            require(receipt.get("scalar_pid") == record["pid"] and
                    receipt.get("scalar_process_confirmed_terminal") is True,
                    "Legacy scalar terminal receipt identity/confirmation differs")
            terminal = terminal_filetime(receipt.get("created_utc"))
            receipts[relative] = expected
    if not current["alive"]:
        return receipts
    require(receipts and terminal is not None, "No verified terminal receipt for legacy scalar PID: " + label)
    token = current.get("creation_token")
    require(current.get("creation_clock") == "windows_filetime_100ns_since_1601" and
            isinstance(token, str) and re.fullmatch(r"[1-9][0-9]{0,19}", token) and 0 < int(token) < 2**64,
            "Unknown legacy scalar PID creation time: " + label)
    require(int(token) > terminal, "Current PID identity predates scalar's confirmed stop: " + label)
    return receipts


def run_key(spec):
    identity = spec["identity"]
    key = "_".join(str(identity[k]) for k in ("source_split", "pool", "budget", "selection_seed", "initialization_seed", "strategy"))
    require(re.fullmatch(r"[A-Za-z0-9_-]+", key), "Unsafe run key")
    return key


def verify_mapping(root, mapping, label):
    require(isinstance(mapping, dict) and mapping, "Missing SHA mapping: " + label)
    for name, checksum in mapping.items():
        require(isinstance(checksum, str) and re.fullmatch(r"[0-9a-f]{64}", checksum), "Invalid SHA: " + label)
        p = child(root, name)
        require(p.is_file() and sha(p) == checksum, "Stale " + label + ": " + name)


def closed_generation(root, relative, plan_sha):
    base = child(root, relative)
    required = ("global_lease.closed.json", "supervisor_summary.json", "scheduling_amendment.json")
    require(all((base / n).is_file() for n in required), "Unclosed parallel generation: " + relative)
    closed, summary, amendment = [read(child(root, relative + "/" + name)) for name in required]
    generation = base.name
    require(closed.get("generation") == summary.get("generation") == amendment.get("generation") == generation and
            closed.get("plan_sha256") == summary.get("plan_sha256") == amendment.get("plan_sha256") == plan_sha,
            "Generation/plan binding differs: " + generation)
    workers = amendment.get("workers")
    require(workers in (2, 3, 4) and closed.get("workers") == summary.get("workers") == workers,
            "Generation worker count differs")
    require(summary.get("status") in {"complete", "failed"}, "Nonterminal generation summary")
    require(closed.get("amendment_sha256") == sha(base / "scheduling_amendment.json") and
            closed.get("executor_sha256") == summary.get("executor_code_sha256") == amendment.get("executor_code_sha256"),
            "Generation executor/amendment binding differs")
    require_dead(closed, relative + "/closed supervisor")
    children = closed.get("children", [])
    require(isinstance(children, list) and len({c["worker"] for c in children}) == len(children), "Duplicate generation child")
    statuses = {s["worker"]: s for s in summary.get("child_statuses", [])}
    require(set(statuses) == {c["worker"] for c in children}, "Generation child summary inventory differs")
    leases = sorted(base.glob("worker_*.lease.json"))
    require({int(p.name.split("_")[1].split(".")[0]) for p in leases} == set(statuses),
            "Unresolved reserved/unknown child lease")
    for authorized in children:
        worker = authorized["worker"]
        require(worker in range(workers), "Out-of-range child worker")
        require_dead(authorized, relative + "/child")
        lease = read(child(root, relative + f"/worker_{worker}.lease.json"))
        require(lease.get("state") == "terminal" and lease.get("pid") == authorized["pid"] and
                lease.get("generation") == generation and lease.get("worker") == worker and lease.get("workers") == workers,
                "Nonterminal/mismatched worker lease")
        require_dead(lease, relative + f"/worker_{worker}")
        status = statuses[worker]
        require(status.get("pid") == authorized["pid"] and isinstance(status.get("exit_code"), int),
                "Unresolved child exit status")
        actual = read(child(root, relative + f"/worker_{worker}.summary.json"))
        require(actual == status.get("summary") and actual.get("status") in {"complete", "failed", "failed_initialization", "cooperative_stop"},
                "Child terminal summary differs")
    return {"generation": generation, "workers": workers, "status": summary["status"], "children": len(children)}


def execution_files(root, expected_keys, plan_sha):
    base = child(root, BASE)
    require(base.is_dir() and not (base / "writer.lock").exists(), "CUDA global writer lease remains")
    require(not list(base.rglob("parallel_fit.lock")), "CUDA per-fit writer lease remains")
    files, excluded, generations, legacy_receipts = {}, [], [], {}
    for current, directories, names in os.walk(base, followlinks=False):
        for name in directories + names:
            child(root, (Path(current) / name).relative_to(Path(root).resolve()).as_posix())
        for name in names:
            p = Path(current) / name
            relative = p.relative_to(Path(root).resolve()).as_posix()
            parts = p.relative_to(base).parts
            approved = False
            if len(parts) == 1:
                if name == "parallel_admission.guard":
                    require(p.stat().st_size <= 1, "Unexpected admission mutex contents")
                    excluded.append({"relative_path": relative, "reason": "Released OS mutex sentinel; preserve at source"})
                    continue
                if re.fullmatch(r"stale_writer_[a-f0-9]+\.json", name):
                    record = read(p)
                    legacy_receipts.update(legacy_scalar_resolution(root, record, relative))
                    for c in record.get("children", []):
                        require_dead(c, relative + "/child")
                    approved = True
            elif len(parts) == 2 and parts[0] in expected_keys:
                approved = bool(RUN_FILE.fullmatch(name))
                if name.startswith("claim_"):
                    require_dead(read(p), relative)
            elif len(parts) == 3 and parts[0] == "parallel" and GENERATION.fullmatch(parts[1]):
                if name == "budget.lock":
                    require(p.stat().st_size <= 1, "Unexpected budget mutex contents")
                    excluded.append({"relative_path": relative, "reason": "Released OS mutex sentinel; preserve at source"})
                    continue
                approved = bool(GEN_FILE.fullmatch(name))
            require(approved, "Unrecognized CUDA history file; inspect before packaging: " + relative)
            files[relative] = "move"
    parallel = base / "parallel"
    if parallel.exists():
        for generation in sorted(parallel.iterdir()):
            require(generation.is_dir() and GENERATION.fullmatch(generation.name), "Unexpected generation path")
            generations.append(closed_generation(root, generation.relative_to(Path(root).resolve()).as_posix(), plan_sha))
    return files, excluded, generations, legacy_receipts


def build_inventory(root=ROOT):
    """Stable deterministic inventory for the parent packager; writes nothing."""
    root = Path(root).absolute()
    plan_path = child(root, PLAN)
    require(plan_path.is_file() and sha(plan_path) == PLAN_SHA, "CUDA locked plan SHA differs")
    plan = read(plan_path)
    require(plan.get("expected_runs") == len(plan.get("runs", [])) == 90, "CUDA plan requires90 runs")
    keys = {run_key(s) for s in plan["runs"]}
    require(len(keys) == 90, "Duplicate CUDA plan identity")
    # Refuse live/unknown writers before inspecting any result payload or audit.
    selected, excluded, generations, legacy_receipts = execution_files(root, keys, PLAN_SHA)
    for relative in legacy_receipts:
        selected[relative] = "copy"
    audit_checksum = sha(child(root, AUDIT))
    audit = read(child(root, AUDIT))
    require(sha(child(root, AUDIT)) == audit_checksum, "CUDA audit changed while reading")
    require(audit.get("format") == "v2-cuda90-audit-1" and audit.get("passed") is True and
            audit.get("expected_count") == audit.get("observed_count") == audit.get("validated_count") == 90 and
            all(not audit.get(k) for k in ("errors", "missing", "extra", "duplicates")), "CUDA90 full audit has not passed")
    expected_results = {BASE + "/" + k + "/result.json" for k in keys}
    require(set(audit.get("result_files", {})) == expected_results and
            {n for n in selected if n.endswith("/result.json")} == expected_results,
            "CUDA result inventory must match all90 plan identities")
    for label in ("result_files", "artifact_sha256", "code_sha256", "inputs"):
        verify_mapping(root, audit.get(label), "CUDA audit " + label)
    require(audit["inputs"].get(PLAN) == PLAN_SHA, "Audit does not bind locked CUDA plan")
    require(set(audit["artifact_sha256"]) <= set(selected), "Audited CUDA artifacts leave execution payload")
    analysis_checksum = sha(child(root, ANALYSIS))
    analysis = read(child(root, ANALYSIS))
    require(analysis.get("format") == "v2-cuda90-descriptive-1" and
            analysis.get("audit_sha256") == audit_checksum and
            analysis.get("expected_count") == analysis.get("validated_count") == 90 and
            analysis.get("scope") == "DESCRIPTIVE_SECONDARY_EXECUTION_REPLICATION" and
            analysis.get("original_primary_unchanged") is True and analysis.get("new_independent_holdout") is False and
            all(analysis.get(k) == audit[k] for k in ("result_files", "inputs", "code_sha256")),
            "CUDA descriptive analysis is stale or changes scope")
    for relative in (*SUPPORT, *audit["code_sha256"]):
        require(relative.startswith(("code/", "configs/", "docs/", "evidence/v2/", "tables/v2_cuda/")) and
                Path(relative).suffix in {".py", ".json", ".md"}, "Unsafe CUDA support scope")
        require(child(root, relative).is_file(), "Missing CUDA support file: " + relative)
        selected.setdefault(relative, "copy")
    for path in sorted(child(root, "evidence/v2/software").glob("cuda_*.json")):
        selected[path.relative_to(root.resolve()).as_posix()] = "copy"
    files = []
    for relative, action in sorted(selected.items()):
        p = child(root, relative)
        files.append({"relative_path": relative, "action": action, "origin": ORIGIN,
                      "sha256": sha(p), "bytes": p.stat().st_size})
    # A second inventory/closure check catches writers or extra history arriving
    # during traversal. Callers must still assert all unrelated writers stopped.
    again, again_excluded, again_generations, again_receipts = execution_files(root, keys, PLAN_SHA)
    require({n for n, action in selected.items() if action == "move"} == set(again) and
            excluded == again_excluded and generations == again_generations and legacy_receipts == again_receipts,
            "CUDA history changed during inventory")
    for entry in files:
        p = child(root, entry["relative_path"])
        require(p.stat().st_size == entry["bytes"] and sha(p) == entry["sha256"], "CUDA file changed during inventory")
    require(sha(plan_path) == PLAN_SHA and sha(child(root, AUDIT)) == audit_checksum and
            sha(child(root, ANALYSIS)) == analysis_checksum, "CUDA plan/audit/analysis changed during inventory")
    for label in ("result_files", "artifact_sha256", "code_sha256", "inputs"):
        verify_mapping(root, audit[label], "final CUDA audit " + label)
    result = {"format": FORMAT, "plan_sha256": PLAN_SHA, "audit_sha256": audit_checksum,
              "analysis_sha256": analysis_checksum, "writers_terminal": True,
              "expected_result_count": 90, "generation_status": generations, "file_count": len(files),
              "copy_additional_bytes": sum(f["bytes"] for f in files if f["action"] == "copy"),
              "move_bytes_no_logical_increase": sum(f["bytes"] for f in files if f["action"] == "move"),
              "shared_dependency_sha256": audit["inputs"], "files": files, "excluded": excluded,
              "legacy_scalar_terminal_receipt_sha256": legacy_receipts,
              "scope": "CUDA90 execution/evidence extension; original576 primary unchanged"}
    result["inventory_sha256"] = hashlib.sha256(raw(result)).hexdigest()
    return result


def verify_operations(root, plan):
    """Require the saved whitelist and all CUDA-origin operations unchanged."""
    inventory = build_inventory(root)
    require(plan.get("cuda_delivery_inventory") == inventory, "CUDA delivery inventory differs from plan")
    operations = [e for e in plan["operations"] if e.get("origin") == ORIGIN or e["source"].startswith(BASE + "/")]
    expected = {f["relative_path"]: f for f in inventory["files"]}
    actual = {e["source"]: e for e in operations}
    require(len(actual) == len(operations) and set(actual) == set(expected), "CUDA operations must cover exact whitelist")
    for relative, entry in actual.items():
        info = expected[relative]
        require(entry["source"] == entry["target"] == relative and entry["action"] == info["action"] and
                entry["origin"] == ORIGIN and entry["sha256"] == info["sha256"] and entry["bytes"] == info["bytes"],
                "CUDA operation differs: " + relative)
    return inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build_inventory(args.root), indent=2, ensure_ascii=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("CUDA DELIVERY BLOCKED: " + type(exc).__name__ + ": " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

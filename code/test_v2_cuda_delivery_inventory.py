"""Synthetic byte/lease fixtures only; no Torch, raster or real experiment reads."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import v2_cuda_delivery_inventory as m


def write(root, relative, value):
    p = m.child(root, relative)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(m.raw(value) if not isinstance(value, bytes) else value)
    return p


def fixture(root):
    for relative in m.SUPPORT:
        write(root, relative, b"synthetic support bytes\n")
    write(root, "evidence/v2/software/cuda_device_observation.json", {"synthetic": True})
    specs = [{"identity": {"source_split": "source" + str(i // 30), "pool": "skewed5_1", "budget": 12,
                           "selection_seed": i % 3, "initialization_seed": i % 3, "strategy": "fixture" + str(i)}}
             for i in range(90)]
    write(root, m.PLAN, {"expected_runs": 90, "runs": specs})
    plan_sha = m.sha(m.child(root, m.PLAN))
    result_files, artifacts = {}, {}
    for i, spec in enumerate(specs):
        base = m.BASE + "/" + m.run_key(spec)
        result = write(root, base + "/result.json", {"synthetic": True, "provenance": ("scalar", "v1", "v2")[i % 3]})
        result_files[base + "/result.json"] = m.sha(result)
        log = write(root, base + "/training_attempt_1000.jsonl", b'{"step":600,"synthetic":true}\n')
        artifacts[base + "/training_attempt_1000.jsonl"] = m.sha(log)
        write(root, base + "/attempt_1000.json", {"synthetic": True})
    dead = {"pid": 99999997, "creation_token": "synthetic-dead"}
    for gen, executor in (("20261018T000001_aaaaaaaaaa", "code/v2_cuda_parallel.py"),
                          ("20261018T000002_bbbbbbbbbb", "code/v2_cuda_parallel_v2.py")):
        relative = m.BASE + "/parallel/" + gen
        amendment = {"generation": gen, "workers": 2, "plan_sha256": plan_sha,
                     "executor_code_sha256": m.sha(m.child(root, executor))}
        ap = write(root, relative + "/scheduling_amendment.json", amendment)
        children, statuses = [], []
        for worker in range(2):
            child = {**dead, "worker": worker}
            children.append(child)
            lease = {**child, "generation": gen, "workers": 2, "state": "terminal"}
            write(root, relative + f"/worker_{worker}.lease.json", lease)
            summary = {"worker": worker, "status": "complete", "successful_fitting_steps": 600}
            write(root, relative + f"/worker_{worker}.summary.json", summary)
            write(root, relative + f"/worker_{worker}.stdout.log", b"synthetic stdout\n")
            statuses.append({"worker": worker, "pid": dead["pid"], "exit_code": 0, "summary": summary})
        write(root, relative + "/global_lease.closed.json", {**dead, "generation": gen, "workers": 2,
              "plan_sha256": plan_sha, "executor_sha256": amendment["executor_code_sha256"], "children": children,
              "amendment_sha256": m.sha(ap)})
        write(root, relative + "/supervisor_summary.json", {"generation": gen, "workers": 2, "status": "complete",
              "plan_sha256": plan_sha, "executor_code_sha256": amendment["executor_code_sha256"], "child_statuses": statuses})
        write(root, relative + "/start.json", {"synthetic": True})
        write(root, relative + "/budget.json", {"accounted_bytes": 123456})
        write(root, relative + "/budget.lock", b"0")
        artifacts[relative + "/scheduling_amendment.json"] = m.sha(ap)
    write(root, m.BASE + "/parallel_admission.guard", b"0")
    write(root, m.BASE + "/stale_writer_" + "a" * 32 + ".json", dead)
    first = m.BASE + "/" + m.run_key(specs[0])
    write(root, first + "/failure_999.json", {"error": "synthetic historical failure"})
    write(root, first + "/training_attempt_999.jsonl", b"synthetic unfinished old attempt\n")
    write(root, first + "/claim_999_0.closed.json", dead)
    code = {name: m.sha(m.child(root, name)) for name in (
        "code/v2_cuda_execution.py", "code/v2_cuda_parallel.py", "code/v2_cuda_parallel_v2.py", "code/v2_audit_cuda.py")}
    shared = "v2/data/manifest.json"
    write(root, shared, {"synthetic": True})
    inputs = {m.PLAN: plan_sha, shared: m.sha(m.child(root, shared))}
    audit = {"format": "v2-cuda90-audit-1", "passed": True, "expected_count": 90, "observed_count": 90,
             "validated_count": 90, "result_files": result_files, "artifact_sha256": artifacts,
             "code_sha256": code, "inputs": inputs, "errors": [], "missing": [], "extra": [], "duplicates": []}
    write(root, m.AUDIT, audit)
    write(root, m.ANALYSIS, {"format": "v2-cuda90-descriptive-1", "audit_sha256": m.sha(m.child(root, m.AUDIT)),
          "expected_count": 90, "validated_count": 90, "scope": "DESCRIPTIVE_SECONDARY_EXECUTION_REPLICATION",
          "original_primary_unchanged": True, "new_independent_holdout": False,
          **{key: audit[key] for key in ("result_files", "inputs", "code_sha256")}})
    return plan_sha, specs


class InventoryChecks(unittest.TestCase):
    def test_legacy_scalar_reuse_requires_pinned_receipt_and_later_windows_identity(self):
        with tempfile.TemporaryDirectory(prefix="cuda-legacy-scalar-") as folder:
            root = Path(folder)
            relative = "evidence/v2/audit_attempts/cuda_parallel_boundary_switch_synthetic.json"
            old = {"pid": 12345, "plan_sha256": m.PLAN_SHA}
            receipt = {"created_utc": "2026-10-18T07:23:57.895441+00:00", "scalar_pid": 12345,
                       "scalar_process_confirmed_terminal": True, "previous_writer_lease": old}
            path = write(root, relative, receipt)
            pinned = {relative: m.sha(path)}
            ended = m.terminal_filetime(receipt["created_utc"])
            later = {"alive": True, "creation_token": str(ended + 1),
                     "creation_clock": "windows_filetime_100ns_since_1601"}
            with patch.object(m, "LEGACY_SCALAR_RECEIPTS", pinned), patch.object(m, "process_identity", return_value=later):
                self.assertEqual(m.legacy_scalar_resolution(root, old, "old scalar"), pinned)
                # Receipt bytes, not merely selected JSON fields, are anchored.
                original = path.read_bytes(); path.write_bytes(original + b" ")
                with self.assertRaisesRegex(ValueError, "receipt SHA"): m.legacy_scalar_resolution(root, old, "old scalar")
                path.write_bytes(original); path.unlink()
                with self.assertRaisesRegex(ValueError, "No verified"): m.legacy_scalar_resolution(root, old, "old scalar")
                path.write_bytes(original)
                for token, clock in ((None, later["creation_clock"]), ("bad", later["creation_clock"]),
                    (str(2**64), later["creation_clock"]), (str(ended), later["creation_clock"]),
                    (str(ended-1), later["creation_clock"]), (str(ended+1), None), ("123", "linux_proc_start_ticks")):
                    current = {"alive": True, "creation_token": token, "creation_clock": clock}
                    with self.subTest(token=token, clock=clock), patch.object(m, "process_identity", return_value=current), self.assertRaises(ValueError):
                        m.legacy_scalar_resolution(root, old, "old scalar")
                same = {**old, "creation_token": later["creation_token"]}
                with self.assertRaisesRegex(ValueError, "Live"): m.legacy_scalar_resolution(root, same, "old scalar")
            # A dead PID needs no PID-reuse exemption or receipt. If present,
            # the valid old receipt stays bound for a stable delivery inventory.
            with patch.object(m, "LEGACY_SCALAR_RECEIPTS", pinned), patch.object(m, "process_identity", return_value={"alive": False}):
                self.assertEqual(m.legacy_scalar_resolution(root, old, "old scalar"), pinned)
                path.unlink()
                self.assertEqual(m.legacy_scalar_resolution(root, old, "old scalar"), {})
            for field, value in (("scalar_pid", 222), ("scalar_process_confirmed_terminal", False),
                ("scalar_process_confirmed_terminal", 1), ("previous_writer_lease", {**old, "pid": 222}),
                ("created_utc", "invalid"), ("created_utc", "2026-10-18T07:23:57"),
                ("created_utc", "2026-10-18T07:23:57+08:00")):
                bad = {**receipt, field: value}; path = write(root, relative, bad)
                with self.subTest(field=field, value=value), patch.object(m, "LEGACY_SCALAR_RECEIPTS", {relative:m.sha(path)}), patch.object(m, "process_identity", return_value=later), self.assertRaises(ValueError):
                    m.legacy_scalar_resolution(root, old, "old scalar")

    def test_legacy_scalar_receipt_enters_exact_copy_inventory_without_changing_history(self):
        with tempfile.TemporaryDirectory(prefix="cuda-legacy-inventory-") as folder:
            root = Path(folder); checksum, _ = fixture(root)
            old = {"pid": 12345, "plan_sha256": checksum}
            stale = write(root, m.BASE + "/stale_writer_" + "c" * 32 + ".json", old)
            relative = "evidence/v2/audit_attempts/cuda_parallel_boundary_switch_synthetic.json"
            receipt = {"created_utc": "2026-10-18T07:23:57.895441+00:00", "scalar_pid": 12345,
                       "scalar_process_confirmed_terminal": True, "previous_writer_lease": old}
            path = write(root, relative, receipt); original = {stale:stale.read_bytes(),path:path.read_bytes()}
            pinned = {relative:m.sha(path)}
            later = {"alive": True, "creation_token": str(m.terminal_filetime(receipt["created_utc"])+1),
                     "creation_clock": "windows_filetime_100ns_since_1601"}
            def current(pid): return later if pid == 12345 else {"alive": False}
            with patch.object(m, "PLAN_SHA", checksum), patch.object(m, "LEGACY_SCALAR_RECEIPTS", pinned), patch.object(m, "process_identity", side_effect=current):
                inventory = m.build_inventory(root)
            self.assertEqual(inventory["legacy_scalar_terminal_receipt_sha256"], pinned)
            files = {f["relative_path"]:f for f in inventory["files"]}
            self.assertEqual(files[relative]["action"], "copy")
            self.assertEqual(files[relative]["sha256"], pinned[relative])
            self.assertEqual(files[relative]["origin"], m.ORIGIN)
            self.assertEqual(files[stale.relative_to(root).as_posix()]["action"], "move")
            self.assertTrue(all(p.read_bytes()==value for p,value in original.items()))

    def test_complete_mixed_history_exact_operations_and_zero_move_growth(self):
        with tempfile.TemporaryDirectory(prefix="cuda-inventory-fixture-") as folder:
            root = Path(folder); checksum, _ = fixture(root)
            with patch.object(m, "PLAN_SHA", checksum), patch.object(m, "process_identity", return_value={"alive": False}):
                inventory = m.build_inventory(root)
                self.assertEqual(inventory, m.build_inventory(root))
                self.assertEqual(sum(f["relative_path"].endswith("/result.json") for f in inventory["files"]), 90)
                names = {f["relative_path"] for f in inventory["files"]}
                self.assertTrue(any("failure_999.json" in name for name in names))
                self.assertTrue(any("stale_writer_" in name for name in names))
                self.assertFalse(any(n.startswith("v2/data/") for n in names))
                self.assertEqual(len(inventory["excluded"]), 3)
                self.assertTrue(all(f["action"] == "move" for f in inventory["files"] if f["relative_path"].startswith(m.BASE + "/")))
                self.assertEqual(inventory["copy_additional_bytes"], sum(f["bytes"] for f in inventory["files"] if f["action"] == "copy"))
                plan = {"cuda_delivery_inventory": inventory, "operations": [
                    {"source": f["relative_path"], "target": f["relative_path"], **{k: f[k] for k in ("action", "origin", "sha256", "bytes")}}
                    for f in inventory["files"]]}
                m.verify_operations(root, plan)
                # The inventory's real filesystem checks ran above. Isolate
                # operation-policy mutations from redundant full traversals.
                with patch.object(m, "build_inventory", return_value=inventory):
                    for mutation in ("omit", "copy_move", "sha", "origin"):
                        bad = json.loads(json.dumps(plan))
                        if mutation == "omit": bad["operations"].pop()
                        elif mutation == "copy_move": bad["operations"][0]["action"] = "move"
                        elif mutation == "sha": bad["operations"][0]["sha256"] = "0" * 64
                        else: bad["operations"][0]["origin"] = "explicit_extra"
                        with self.subTest(mutation=mutation), self.assertRaises(ValueError): m.verify_operations(root, bad)

    def test_active_global_perfit_and_unknown_child_refused(self):
        with tempfile.TemporaryDirectory(prefix="cuda-inventory-active-") as folder:
            root = Path(folder); checksum, specs = fixture(root)
            with patch.object(m, "PLAN_SHA", checksum), patch.object(m, "process_identity", return_value={"alive": False}):
                for name, message in ((m.BASE + "/writer.lock", "global writer"),
                    (m.BASE + "/" + m.run_key(specs[0]) + "/parallel_fit.lock", "per-fit")):
                    p = write(root, name, {"pid": os.getpid()})
                    with self.subTest(name=name), self.assertRaisesRegex(ValueError, message): m.build_inventory(root)
                    p.unlink()
                lease = next((root / m.BASE / "parallel").glob("*/worker_0.lease.json"))
                original = lease.read_bytes(); value = json.loads(original); value.update(state="reserved", pid=None)
                lease.write_bytes(m.raw(value))
                with self.assertRaisesRegex(ValueError, "Nonterminal"): m.build_inventory(root)
                lease.write_bytes(original)
            with patch.object(m, "PLAN_SHA", checksum), patch.object(m, "process_identity", return_value={"alive": True, "creation_token": None}):
                with self.assertRaisesRegex(ValueError, "Live or unobservable"): m.build_inventory(root)

    def test_plan_audit_analysis_and_raw_bytes_drift_refused(self):
        with tempfile.TemporaryDirectory(prefix="cuda-inventory-drift-") as folder:
            root = Path(folder); checksum, specs = fixture(root)
            with patch.object(m, "PLAN_SHA", checksum), patch.object(m, "process_identity", return_value={"alive": False}):
                paths = [m.PLAN, m.AUDIT, m.ANALYSIS, m.BASE + "/" + m.run_key(specs[0]) + "/result.json",
                         m.BASE + "/" + m.run_key(specs[0]) + "/training_attempt_1000.jsonl", "code/v2_cuda_parallel.py"]
                for relative in paths:
                    p = m.child(root, relative); old = p.read_bytes()
                    if relative == m.ANALYSIS:
                        changed = json.loads(old); changed["audit_sha256"] = "0" * 64
                        p.write_bytes(m.raw(changed))
                    else:
                        p.write_bytes(old + b" ")
                    with self.subTest(relative=relative), self.assertRaises(ValueError): m.build_inventory(root)
                    p.write_bytes(old)

    def test_unclosed_generation_unexpected_archive_and_extra_result_refused(self):
        with tempfile.TemporaryDirectory(prefix="cuda-inventory-scope-") as folder:
            root = Path(folder); checksum, _ = fixture(root)
            with patch.object(m, "PLAN_SHA", checksum), patch.object(m, "process_identity", return_value={"alive": False}):
                p = next((root / m.BASE / "parallel").glob("*/global_lease.closed.json")); original = p.read_bytes(); p.unlink()
                with self.assertRaisesRegex(ValueError, "Unclosed"): m.build_inventory(root)
                p.write_bytes(original)
                for name in (m.BASE + "/unexpected.zip", m.BASE + "/wrong_run/result.json"):
                    p = write(root, name, b"synthetic unapproved file")
                    with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Unrecognized"): m.build_inventory(root)
                    p.unlink()

    def test_pid_reuse_identity_and_unsafe_paths(self):
        with patch.object(m, "process_identity", return_value={"alive": True, "creation_token": "new"}):
            m.require_dead({"pid": 123, "creation_token": "old"}, "old process")
            with self.assertRaisesRegex(ValueError, "Live"): m.require_dead({"pid": 123, "creation_token": "new"}, "same process")
        with tempfile.TemporaryDirectory(prefix="cuda-inventory-path-") as folder:
            for name in ("../outside", "C:/outside", "some\\path"):
                with self.subTest(name=name), self.assertRaises(ValueError): m.child(folder, name)
            from types import SimpleNamespace
            with patch.object(m.os, "lstat", return_value=SimpleNamespace(st_mode=0o040755, st_reparse_tag=0xA0000003)):
                with self.assertRaisesRegex(ValueError, "junction"): m.child(folder, "code/synthetic.py")


if __name__ == "__main__":
    unittest.main()

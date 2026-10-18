"""Small synthetic scheduler regressions; no Torch, CUDA, raster or scores."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import v2_cuda_parallel as m


class MockBackend:
    def __init__(self, fail=False): self.fail = fail
    def execute(self, selected, validation, panel, base, spec, callback):
        callback({"step": 1, "loss": 1.0, "elapsed_seconds": 0.0})
        if self.fail: raise RuntimeError("synthetic fit failure")
        time.sleep(.03)
        callback({"step": spec["steps"], "loss": .9, "elapsed_seconds": .03})
        cm = [[0] * 8 for _ in range(8)]
        def entries(records): return {"images": [{"id": p["id"], "region": p["region"], "confusion": cm} for p in records],
                                      "aggregate": {"synthetic": True}}
        return {"training": {"steps": spec["steps"], "encoder_lr": spec["encoder_lr"],
                "seed": spec["identity"]["initialization_seed"], "device": "cuda:0", "batch_size": 2, "crop": 224,
                "all_final_parameters_finite": True, "identity": {"torch": "synthetic", "numpy": "synthetic",
                "python": "synthetic", "threads": 2, "device_name": "synthetic", "selected_ids": [p["id"] for p in selected]}},
                "test": entries(panel), "validation": entries(validation), "deterministic_warn_only": True,
                "cuda_peak_allocated_bytes": 1, "cuda_peak_reserved_bytes": 2, "warnings": [], "total_seconds": .03}


def fixture(root, generation="synthetic", workers=2):
    pairs = [{"id": role + "__" + str(i), "region": role} for role, count in
             (("train", 12), ("validation", 20), ("panel", 72)) for i in range(count)]
    for relative, value in [("v2/data/manifest.json", {"pairs": pairs}),
        ("configs/v2_design.json", {"source_splits": [{"id": "source0", "train": ["train"], "validation": ["validation"]}]})]:
        m.bare_new(m.safe(root, relative), value)
    scalar = m.safe(root, m.SCALAR); scalar.parent.mkdir(exist_ok=True); scalar.write_bytes(b"# synthetic scalar\n")
    plan = {"runs": [{"identity": {"model": "resnet18_unet", "source_split": "source0", "pool": "skewed5_1",
            "budget": 12, "selection_seed": i, "initialization_seed": i, "strategy": "synthetic" + str(i)},
            "selection": {"selected_ids": [p["id"] for p in pairs if p["region"] == "train"]},
            "encoder_lr": .0001, "steps": 600} for i in range(90)], "expected_runs": 90,
            "new_panel_image_ids": [p["id"] for p in pairs if p["region"] == "panel"], "code_sha256": m.sha(scalar)}
    plan["runtime"] = {"torch": "synthetic", "numpy": "synthetic", "cuda_python": "synthetic", "threads": 2, "device": "synthetic"}
    m.bare_new(m.safe(root, m.PLAN), plan)
    plan_sha = m.sha(m.safe(root, m.PLAN))
    lease = {**m.process_info(), "generation": generation, "workers": workers, "plan_sha256": plan_sha,
             "executor_sha256": m.sha(Path(m.__file__)), "children": []}
    m.bare_new(m.safe(root, m.OUT + "/writer.lock"), lease)
    new_generation(root, generation, workers, plan_sha)
    return plan, plan_sha


def new_generation(root, generation, workers, plan_sha):
    storage = m.Storage(root, generation, workers)
    m.bare_new(storage.base / "scheduling_amendment.json", {"executor_code_sha256": m.sha(Path(m.__file__)),
        "plan_sha256": plan_sha, "scalar_reference_code_sha256": m.sha(m.safe(root, m.SCALAR)),
        "generation": generation, "workers": workers})
    lease_path = m.safe(root, m.OUT + "/writer.lock"); lease = m.read(lease_path)
    lease["amendment_sha256"] = m.sha(storage.base / "scheduling_amendment.json")
    m.bare_replace(lease_path, lease)


class SchedulerChecks(unittest.TestCase):
    def test_disjoint_partitions_and_exact_missing_fit_resume(self):
        with tempfile.TemporaryDirectory(prefix="cuda-parallel-fixture-") as directory:
            root = Path(directory); plan, plan_sha = fixture(root)
            for workers in (2, 3, 4):
                groups = m.partitions(plan, workers)
                self.assertEqual(sorted(sum(groups, [])), list(range(90)))
                self.assertEqual(sum(map(len, groups)), len(set(sum(groups, []))))
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--fixture-worker", str(root), "synthetic"]
            processes = [subprocess.Popen(command + [str(k), "2", "2"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT) for k in range(2)]
            outputs = [p.communicate(timeout=60)[0].decode(errors="replace") for p in processes]
            self.assertEqual([p.returncode for p in processes], [0, 0], outputs)
            with patch.object(m, "PLAN_SHA", plan_sha):
                for i in range(4): self.assertTrue(m.validate_existing(root, plan["runs"][i], plan, plan_sha))
                generation = "synthetic_four"
                lease = m.read(m.safe(root, m.OUT + "/writer.lock")); lease.update(generation=generation, workers=4)
                m.bare_replace(m.safe(root, m.OUT + "/writer.lock"), lease)
                new_generation(root, generation, 4, plan_sha)
                executed = []
                for worker in range(4):
                    s = m.execute_partition(root, plan, generation, worker, 4, m.Storage(root, generation, 4), MockBackend(), 1)
                    self.assertEqual(s["status"], "complete"); executed += s["executed_indices"]
                self.assertEqual(sorted(executed), [4, 5, 6, 7])
            self.assertEqual(len(list((root/m.OUT).glob("*/result.json"))), 8)

    def test_resume_refuses_identity_plan_log_and_provenance_drift(self):
        with tempfile.TemporaryDirectory(prefix="cuda-parallel-resume-") as directory:
            root = Path(directory); plan, plan_sha = fixture(root)
            with patch.object(m, "PLAN_SHA", plan_sha):
                summary = m.execute_partition(root, plan, "synthetic", 0, 2, m.Storage(root, "synthetic", 2), MockBackend(), 1)
                self.assertEqual(summary["status"], "complete")
                path = m.safe(root, m.OUT + "/" + m.run_key(plan["runs"][0]["identity"]) + "/result.json")
                original = path.read_bytes()
                for field, value in (("identity", {}), ("plan_sha256", "0"*64), ("log_sha256", "0"*64), ("code_sha256", "0"*64)):
                    result = json.loads(original); result[field] = value; path.write_bytes(m.raw(result))
                    with self.subTest(field=field), self.assertRaises((RuntimeError, KeyError)):
                        m.validate_existing(root, plan["runs"][0], plan, plan_sha)
                path.write_bytes(original)

    def test_active_scalar_stale_parent_live_child_unknown_and_mismatch_refusal(self):
        with tempfile.TemporaryDirectory(prefix="cuda-parallel-lease-") as directory:
            root = Path(directory); _, plan_sha = fixture(root)
            lease = m.safe(root, m.OUT + "/writer.lock")
            # A live scalar lease has only PID and plan SHA, just like the original.
            m.bare_replace(lease, {"pid": os.getpid(), "plan_sha256": plan_sha})
            with self.assertRaisesRegex(RuntimeError, "Active scalar"):
                m.acquire_global(root, "other", 2, plan_sha, "x", True)
            m.bare_replace(lease, {"pid": 99999999, "children": [m.process_info()]})
            with self.assertRaisesRegex(RuntimeError, "Live child"):
                m.acquire_global(root, "other", 2, plan_sha, "x", True)
            m.bare_replace(lease, {"pid": 99999999})
            child = m.safe(root, m.OUT + "/parallel/synthetic/worker_0.lease.json")
            m.bare_new(child, {**m.process_info(), "state": "running"})
            with self.assertRaisesRegex(RuntimeError, "Live/unknown child"):
                m.acquire_global(root, "other", 3, plan_sha, "x", True)
            m.bare_replace(child, {"pid": None, "state": "reserved"})
            with self.assertRaisesRegex(RuntimeError, "Live/unknown child"):
                m.acquire_global(root, "other", 4, plan_sha, "x", True)
            m.bare_replace(child, {"pid": 99999999, "state": "terminal"})
            with self.assertRaisesRegex(RuntimeError, "Stale global"):
                m.acquire_global(root, "other", 2, plan_sha, "x", False)
            m.acquire_global(root, "other", 2, plan_sha, "x", True)
            with patch.object(m, "PLAN_SHA", plan_sha), self.assertRaisesRegex(RuntimeError, "Mismatched"):
                m.check_generation(root, "wrong")

    def test_failed_fit_retains_attempt_raw_log_failure_and_no_result(self):
        with tempfile.TemporaryDirectory(prefix="cuda-parallel-failure-") as directory:
            root = Path(directory); plan, plan_sha = fixture(root)
            with patch.object(m, "PLAN_SHA", plan_sha):
                summary = m.execute_partition(root, plan, "synthetic", 0, 2, m.Storage(root, "synthetic", 2), MockBackend(True), 1)
            self.assertEqual(summary["status"], "failed"); self.assertEqual(summary["successful_fitting_steps"], 0)
            folder = m.safe(root, m.OUT + "/" + m.run_key(plan["runs"][0]["identity"]))
            self.assertEqual(len(list(folder.glob("failure_*.json"))), 1)
            self.assertEqual(len(list(folder.glob("attempt_*.json"))), 1)
            self.assertEqual(len(list(folder.glob("training_attempt_*.jsonl"))), 1)
            self.assertFalse((folder/"result.json").exists())
            self.assertTrue((m.Storage(root, "synthetic", 2).base/"stop.request.json").exists())

    def test_exclusive_output_creation_and_storage_ram_guards(self):
        with tempfile.TemporaryDirectory(prefix="cuda-parallel-output-") as directory:
            root = Path(directory); path = root/"result.json"
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--fixture-exclusive", str(path)]
            processes = [subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(2)]
            self.assertEqual(sorted(p.wait(timeout=30) for p in processes), [0, 1])
            self.assertEqual(m.read(path), {"synthetic": True})
            with patch.object(m, "free_physical_bytes", return_value=100*MIB), self.assertRaisesRegex(RuntimeError, "RAM backoff"):
                m.check_memory(2)
            storage = m.Storage(root, "guard", 4)
            with patch.object(m, "logical_bytes", return_value=m.CAP-m.RESERVE-4*m.PER_WORKER_RESERVE), self.assertRaisesRegex(RuntimeError, "cap/reserve"):
                storage.charge(1, refresh=True)


MIB = 1024*1024
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fixture-worker":
        _, _, root, generation, worker, workers, limit = sys.argv
        root = Path(root); m.PLAN_SHA = m.sha(m.safe(root, m.PLAN))
        summary = m.execute_partition(root, m.read(m.safe(root, m.PLAN)), generation, int(worker), int(workers),
                                      m.Storage(root, generation, int(workers)), MockBackend(), int(limit))
        raise SystemExit(0 if summary["status"] == "complete" else 1)
    if len(sys.argv) > 1 and sys.argv[1] == "--fixture-exclusive":
        try: m.bare_new(Path(sys.argv[2]), {"synthetic": True})
        except FileExistsError: raise SystemExit(1)
        raise SystemExit(0)
    unittest.main()

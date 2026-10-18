"""Synthetic-only active matrix tests; no real result files or models are read."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import v2_active_gpu_results as active


def write(root, name, value):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    active.original.write_json(path, value)
    return path


def design_fixture():
    design = {"source_splits": [{"id": f"s{i}"} for i in range(3)], "selection_seeds": [0, 1, 2],
        "strategies": ["random", "kcenter", "region_random", "region_kcenter", "permuted_region_kcenter",
                       "kmeanspp", "facility_location", "fd_roundrobin"],
        "full_model": {"name": "resnet18_unet", "pools": ["skewed5_1"], "budgets": [12], "initialization_seeds": [0]},
        "frozen_control": {"name": "dinov2_mlp128", "pools": ["balanced3", "skewed5_1"], "budgets": [6, 12, 24],
                           "initialization_seeds": [0], "steps": 600, "learning_rate": .001},
        "new_test_regions": [f"synthetic_region{i}" for i in range(24)],
        "primary": {"model": "resnet18_unet", "pool": "skewed5_1", "budget": 12,
                    "contrast": ["region_kcenter", "kcenter"], "repetitions": 10000, "bootstrap_seed": 2026101805}}
    extension = {"status": "PROSPECTIVE_SUPPLEMENT_BEFORE_NEW_PANEL_EVALUATION",
        "additional_strategies": list(active.original.ADDITIONAL_STRATEGIES), "pools": ["skewed5_1"],
        "expected_additional_full_runs": 18, "expected_additional_frozen_runs": 54,
        "expected_additional_total_runs": 72, "expected_total_runs": 576,
        "initialization_seed_by_selection_seed": {"0": 0, "1": 1, "2": 2},
        "randomization_amendment_before_new_panel_scores": True}
    return design, extension


class ActiveResultsTests(unittest.TestCase):
    def test_matrix_and_exact_inventory_before_scores(self):
        design, extension = design_fixture()
        expected, full, frozen, reference = active.partition_matrix(design, extension)
        self.assertEqual(tuple(map(len, (expected, full, frozen, reference))), (576, 90, 486, 72))
        self.assertTrue(all(i["initialization_seed"] == i["selection_seed"] for i in expected.values()))
        self.assertTrue(set(reference) < set(full))
        self.assertFalse(set(full) & set(frozen))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "no partial scores"):
                active.exact_frozen_inventory(root, frozen)
            for i in frozen.values():
                path = root / active.original_path(i); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("metadata only")
            self.assertEqual(len(active.exact_frozen_inventory(root, frozen)), 486)
            gpu = {f"evidence/v2/cuda_execution/runs/synthetic{i}/result.json": "a" * 64 for i in range(90)}
            frozen_sha = {active.original_path(i): "b" * 64 for i in frozen.values()}
            cpu = {active.original_path(i): "c" * 64 for i in reference.values()}
            for name in cpu: write(root, name, {"synthetic": True})
            allfiles = {**cpu, **{f"evidence/v2/runs/resnet18_unet/history/{i}.json": "d" * 64 for i in range(147)}}
            audit = {"results": {**gpu, **frozen_sha}, "cpu_reference_result_files": cpu, "cpu_reference_results": cpu,
                "cpu_reference_files": allfiles, "runs": []}
            for (name, digest), identity in zip(gpu.items(), full.values()):
                audit["runs"].append({"path": name, "sha256": digest, "identity": identity})
            for key, identity in frozen.items():
                name = active.original_path(identity)
                audit["runs"].append({"path": name, "sha256": frozen_sha[name], "identity": identity})
            write(root, active.cuda.AUDIT, {"result_files": gpu}); write(root, active.scheduler.PLAN, {})
            with patch.object(active.cuda, "result_inventory", return_value=({}, gpu, [], [])):
                active.current_inventory(root, audit, design, extension)
                write(root, "evidence/v2/runs/resnet18_unet/extra/result.json", {})
                with self.assertRaisesRegex(RuntimeError, "reference separation"):
                    active.current_inventory(root, audit, design, extension)
            write(root, "evidence/v2/runs/dinov2_mlp128/unplanned/result.json", {})
            with self.assertRaisesRegex(RuntimeError, "Incomplete/extra"):
                active.exact_frozen_inventory(root, frozen)
        with tempfile.TemporaryDirectory() as directory, patch.object(active.statistics, "make_fit", side_effect=AssertionError("Scores opened")):
            write(directory, active.AUDIT, {"passed": True, "expected_total": 576, "validated_runs": 575,
                  "observed_result_files": 575, "results": {str(i): "a" * 64 for i in range(575)}})
            with self.assertRaisesRegex(RuntimeError, "complete active576"):
                active.load_active(Path(directory))
            self.assertFalse(active.validate_bundle(directory)["passed"])

    def test_all_frozen_headers_precede_numerical_access(self):
        design, extension = design_fixture(); _, _, frozen, _ = active.partition_matrix(design, extension)
        freeze, execution = "a" * 64, {"f.py": "b" * 64}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inventory = {active.original_path(i): i for i in frozen.values()}
            for name, spec in inventory.items():
                write(root, name, {"status": "complete", "identity": {**spec, "freeze_sha256": freeze,
                                                                    "execution_code_sha256": execution}})
            self.assertEqual(len(active.frozen_terminal_headers(root, inventory, freeze, execution)), 486)
            last = next(reversed(inventory)); good = active.read(root / last)
            for mutation in ("corrupt", "status", "identity"):
                with self.subTest(mutation=mutation), patch.object(active.original, "validate_evaluation", side_effect=AssertionError("CM opened")):
                    bad = deepcopy(good)
                    if mutation == "corrupt": (root / last).write_text("{", encoding="utf-8")
                    else:
                        if mutation == "status": bad["status"] = "running"
                        else: bad["identity"]["initialization_seed"] = 99
                        write(root, last, bad)
                    with self.assertRaises((RuntimeError, ValueError)):
                        active.frozen_terminal_headers(root, inventory, freeze, execution)
                    write(root, last, good)

    def test_frozen_fit_truth_logs_recipe_device_and_source_unchanged(self):
        design, extension = design_fixture(); spec = next(iter(active.partition_matrix(design, extension)[2].values()))
        cm = np.zeros((8, 8), dtype=int); cm[0, 0] = 8; cm[0, 1] = 2
        entries = [{"id": "synthetic", "region": "r", "confusion": cm.tolist()}]
        evaluation = {"images": entries, "aggregate": active.original.complete_aggregate(entries)}
        logs = [{"step": s, "loss": .5, "elapsed_seconds": float(j)}
                for j, s in enumerate([1, *range(50, 601, 50)])]
        device = {"name": "synthetic GPU", "cupy": "synthetic", "runtime": 1, "driver": 2, "total_memory_bytes": 3}
        reference = {"selected_ids": ["s"], "selected_regions": ["r"]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); relative = active.original_path(spec); raw = Path(relative).parent.as_posix() + "/raw.jsonl"
            path = root / raw; path.parent.mkdir(parents=True); path.write_text("\n".join(json.dumps(r) for r in logs), encoding="utf-8")
            original_sha = active.sha(path)
            result = {"identity": spec, "selection": {**reference, "selection_seconds": 0.}, "test": evaluation,
                "validation": None, "checkpoint": None, "log_file": raw, "log_sha256": original_sha, "total_seconds": 100.,
                "training": {"steps": 600, "learning_rate": .001, "seed": spec["initialization_seed"],
                    "all_final_parameters_finite": True, "parameter_count": 50312, "device": device, "log": logs}}
            def bind(name, category, expected):
                self.assertEqual(active.sha(root / name), expected); return root / name
            def check(value):
                active.validate_frozen_result(root, relative, value, spec, reference, design,
                    {"synthetic": {"region": "r"}}, {"synthetic": [10] + [0] * 7}, {}, bind, device)
            check(result)
            for mutation in ("device", "parameters", "recipe", "step", "truth", "selection", "checkpoint"):
                bad = deepcopy(result)
                if mutation == "device": bad["training"]["device"]["name"] = "wrong"
                if mutation == "parameters": bad["training"]["parameter_count"] += 1
                if mutation == "recipe": bad["training"]["learning_rate"] = .002
                if mutation == "step": bad["training"]["log"][-1]["step"] -= 1
                if mutation == "truth": bad["test"]["images"][0]["confusion"][0][0] += 1
                if mutation == "selection": bad["selection"]["selected_ids"] = ["other"]
                if mutation == "checkpoint": bad["checkpoint"] = {}
                with self.subTest(mutation=mutation), self.assertRaises((RuntimeError, ValueError)):
                    check(bad)
            self.assertEqual(active.sha(path), original_sha)
            self.assertEqual(result["selection"]["selected_ids"], ["s"])

    def test_synthetic576_statistics_and_post_exposure_scope(self):
        design, extension = design_fixture(); expected = active.partition_matrix(design, extension)[0]
        fits = []
        for identity in expected.values():
            cm = np.zeros((8, 8), dtype=int)
            cm[0, 0] = 8 - identity["initialization_seed"] if identity["strategy"] == "region_kcenter" else 5
            cm[0, 1] = 10 - cm[0, 0]
            regional = {r: active.statistics.scores(cm) for r in design["new_test_regions"]}
            metrics = {k: .1 for k in active.statistics.FIT_METRICS}
            metrics.update(equal_region_miou=active.statistics.scores(cm)["miou"],
                           equal_region_union_miou=active.statistics.scores(cm)["union_class_miou"])
            fits.append({"identity": identity, "metrics": metrics, "regional": regional,
                         "regional_cm": {r: cm for r in regional}, "pooled_cm": 24 * cm})
        geographic = {"exclude_entire_regions": ["synthetic_region0"], "primary_unchanged": True,
            "purpose": "descriptive_geographic_metadata_sensitivity", "repetitions": 10000, "bootstrap_seed": 2026101805}
        result = active.build_active_analysis(fits, design, extension, geographic, "a" * 64)
        self.assertEqual([len(result[n]) for n in ("conditions_by_source", "conditions", "regions", "classes")], [192, 64, 1536, 512])
        self.assertEqual(len(result["contrasts"]["contrasts"]), 36)
        self.assertEqual(result["primary"]["metrics"]["union_class_miou"]["role"], active.ROLE)
        self.assertEqual(result["primary"]["metrics"]["union_class_miou"]["region_count"], 24)
        self.assertEqual(result["primary"]["geographic_sensitivity"]["metrics"]["union_class_miou"]["region_count"], 23)
        self.assertFalse(result["primary"]["prospective_GPU_primary"])
        self.assertFalse(result["primary"]["new_confirmatory_evidence"])
        self.assertFalse(any(c["role"] == "primary" for c in result["contrasts"]["contrasts"]))
        with self.assertRaisesRegex(ValueError, "unique fits"):
            active.build_active_analysis(fits[:-1], design, extension, geographic, "a" * 64)
        self.assertNotIn("torch", sys.modules); self.assertNotIn("cupy", sys.modules)

    def test_byte_reproduction_writes_only_report_and_refuses_changed_table(self):
        # Tiny renderer fixture tests IO policy only; scientific576 logic is
        # independently exercised above and this stub is not a scientific audit.
        analysis = {k: [{"synthetic": 1, "value": .25}] for k in ("conditions_by_source", "conditions", "regions", "classes")}
        analysis.update(contrasts={"synthetic": True}, primary={"synthetic": True, "role": active.ROLE})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); outputs = active.render_outputs(analysis, root / "tables/v2")
            freeze = write(root, "configs/v2_freeze.json", {"file_sha256": {"synthetic": "b" * 64}})
            audit = {"results": {"synthetic": "a" * 64}, "inputs": {"configs/v2_freeze.json": active.sha(freeze)}, "artifacts": {}}
            audit_path = write(root, active.AUDIT, audit); audit_sha = active.sha(audit_path)
            identity = {"newanalysis_code_sha256": active.sha(Path(active.__file__)), "output_sha256": outputs,
                "runtime": {"python": sys.version.split()[0], "numpy": np.__version__}, "audit_sha256": audit_sha,
                "result_sha256": audit["results"], "audited_input_sha256": audit["inputs"], "audited_artifact_sha256": {},
                "counts": {"fits": 576, "conditions_by_source": 192, "conditions": 64, "regions_rows": 1536, "classes_rows": 512}}
            write(root, active.IDENTITY, identity)
            with patch.object(active, "load_active", return_value=(audit, audit_sha, [], analysis)):
                report = active.verify_tables(root)
                self.assertTrue(report["passed"], report["errors"])
                self.assertFalse(report["scientific_outputs_written"])
                self.assertEqual(report["numerical_outputs_before_sha256"], report["numerical_outputs_after_sha256"])
                target = root / active.NUMERICAL[0]; target.write_text("changed", encoding="utf-8"); changed = active.sha(target)
                report = active.verify_tables(root)
                self.assertFalse(report["passed"])
                self.assertEqual(active.sha(target), changed)
            (root / active.IDENTITY).unlink()
            with patch.object(active, "load_active", return_value=(audit, audit_sha, [], analysis)), self.assertRaisesRegex(RuntimeError, "lack an active identity"):
                active.analyse(root)

    def test_cpu_stop_identity_dead_unknown_and_real_newborn(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stopped = datetime(2026, 10, 18, 8, 22, 42, tzinfo=timezone.utc)
            receipt = write(root, "receipt.json", {"pid": 99999999, "final_completed": 72,
                "stopped_utc": stopped.isoformat(), "status": "STOPPED_AFTER_NEW_COMPLETED_FIT_BOUNDARY_BY_USER_BACKEND_MIGRATION"})
            amendment = {"user_driven": True, "after_panel_exposure": True, "main_display_descriptive": True,
                "original_CPU90_completed": False, "cpu_reference_expected": 72, "cpu_remaining_transferred": 18,
                "active_full": {"expected_runs": 90}, "active_frozen": {"expected_runs": 486, "source": "evidence/v2/runs/dinov2_mlp128"},
                "active_expected_total": 576, "new_independent_holdout": False, "no_confirmatory_upgrade": True,
                "cpu_writer_terminal_asserted": True, "cpu_writer_process": {"pid": 99999999},
                "cpu_stop_receipt": "receipt.json", "cpu_stop_receipt_sha256": active.sha(receipt)}
            path = write(root, active.AMENDMENT, amendment)
            with patch.object(active, "AMENDMENT_SHA", active.sha(path)):
                for current in ({"alive": False}, {"alive": True, "creation_token": ""},
                                {"alive": True, "creation_token": "20261018082242"},
                                {"alive": True, "creation_token": str(116444736000000000 + int((stopped.timestamp() - 20) * 10000000))},
                                {"alive": True, "creation_token": str(116444736000000000 + int((stopped.timestamp() + 20) * 10000000))}):
                    with patch.object(active.scheduler, "process_info", return_value=current):
                        if not current["alive"] or (current.get("creation_token", "").isdigit() and int(current["creation_token"]) > 116444736000000000 + int(stopped.timestamp() * 10000000)):
                            self.assertEqual(active.check_amendment(root), amendment)
                        else:
                            with self.assertRaises(RuntimeError): active.check_amendment(root)


if __name__ == "__main__": unittest.main()

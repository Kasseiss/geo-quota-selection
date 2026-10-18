"""Audit active GPU90+frozen486 and reproduce six descriptive canonical tables.

Original CPU90 was not completed. CPU72 is retained separately, never mixed
into the active576. Imports only standard-library and frozen NumPy helpers.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

import numpy as np
import v2_audit_runs as original
import v2_statistics as statistics
import v2_audit_cuda as cuda
import v2_cuda_parallel_v2 as scheduler
import v2_selection
import v2_weighted_selection

ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = "configs/v2_active_gpu_amendment.json"
AMENDMENT_SHA = "05b06f37acaaff2412e63baf126ab0e66ce552770af2b3dcbaed497c7ed94518"
AUDIT = "evidence/v2/active_run_completeness.json"
REPRODUCTION = "evidence/v2/active_reproduction_check.json"
IDENTITY = "tables/v2/analysis_identity.json"
NUMERICAL = tuple("tables/v2/" + n for n in (
    "conditions_by_source.csv", "conditions.csv", "regions.csv", "classes.csv", "contrasts.json", "primary.json"))
HELPERS = ("code/v2_audit_runs.py", "code/v2_statistics.py", "code/core.py", "code/v2_selection.py",
           "code/v2_weighted_selection.py", "code/v2_audit_cuda.py", "code/v2_cuda_parallel_v2.py")
ROLE = "descriptive_main_display_after_post_exposure_user_backend_amendment"
require, safe, sha, read = scheduler.require, scheduler.safe, scheduler.sha, original.read_json


def utc():
    return datetime.now(timezone.utc).isoformat()


def original_path(identity):
    i = identity
    return (f"evidence/v2/runs/{i['model']}/{i['source_split']}_{i['pool']}_b{i['budget']}_s{i['selection_seed']}"
            f"_i{i['initialization_seed']}_{i['strategy']}/result.json")


def partition_matrix(design, extension):
    expected = original.expected_matrix(design, extension)
    full = {k: v for k, v in expected.items() if v["model"] == design["full_model"]["name"]}
    frozen = {k: v for k, v in expected.items() if v["model"] == design["frozen_control"]["name"]}
    require(len(expected) == 576 and len(full) == 90 and len(frozen) == 486, "Active matrix must remain90+486")
    reference = {k: v for k, v in full.items() if v["strategy"] not in original.ADDITIONAL_STRATEGIES}
    require(len(reference) == 72, "Expected72 original CPU base references")
    return expected, full, frozen, reference


def exact_frozen_inventory(root, frozen):
    expected = {original_path(i): i for i in frozen.values()}
    base = safe(root, "evidence/v2/runs/dinov2_mlp128")
    observed = {p.relative_to(root).as_posix() for p in base.rglob("result.json")} if base.exists() else set()
    require(len(expected) == 486 and observed == set(expected), "Incomplete/extra frozen486 inventory; no partial scores permitted")
    return expected


def frozen_terminal_headers(root, inventory, freeze_sha, execution):
    checked = {}
    for relative, expected in inventory.items():
        path = safe(root, relative); digest = sha(path); value = read(path)
        require(value.get("status") == "complete", "Nonterminal frozen result: " + relative)
        identity = value["identity"]
        require(set(identity) == set(original.KEYS) | {"freeze_sha256", "execution_code_sha256"} and
                original.run_key(identity) == original.run_key(expected) and identity["freeze_sha256"] == freeze_sha and
                identity["execution_code_sha256"] == execution, "Frozen terminal identity differs: " + relative)
        require(sha(path) == digest, "Frozen result changed during metadata preflight")
        checked[relative] = digest
    return checked


def selection_reference(index_records, split, identity):
    pool = original.candidate_pool(index_records, split["train"], identity["pool"], split["candidate_seed"])
    ids = [r["id"] for r in pool]
    x = np.asarray([r["descriptor"] for r in pool], dtype=np.float64)
    selected = original.select_images(ids, x, [r["region"] for r in pool], identity["budget"],
                                      identity["strategy"], identity["selection_seed"])
    by_id = {r["id"]: r for r in pool}; chosen = [by_id[k] for k in selected]
    x = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)
    distances = np.maximum(0, 1 - x @ x[[ids.index(k) for k in selected]].T).min(axis=1)
    regions = np.asarray([r["region"] for r in pool])
    regional = {r: float(distances[regions == r].mean()) for r in sorted(set(regions))}
    return {"candidate_ids": ids, "selected_ids": selected, "selected_regions": sorted({r["region"] for r in chosen}),
        "mean_candidate_cosine_distance": float(distances.mean()), "maximum_candidate_cosine_distance": float(distances.max()),
        "equal_region_mean_candidate_cosine_distance": float(np.mean(list(regional.values()))),
        "candidate_region_mean_cosine_distances": regional,
        "selected_region_counts": {r: sum(c["region"] == r for c in chosen) for r in sorted(set(regions))},
        "selected_valid_original_pixels": sum(r["original_valid_pixels"] for r in chosen),
        "selected_original_class_counts": np.asarray([r["original_class_counts"] for r in chosen]).sum(axis=0).tolist()}


def validate_frozen_result(root, relative, result, spec, reference, design, panel, counts, truth, bind, expected_device):
    """Frozen branch of original audit, using its unchanged pure validators."""
    original.assert_same({k: result["identity"][k] for k in original.KEYS}, spec, "Frozen logical identity")
    require(Path(relative).parent.parent.name == spec["model"], "Frozen result model directory differs")
    for name, value in reference.items(): original.assert_same(result["selection"][name], value, "selection." + name)
    require(cuda.finite_number(result["selection"]["selection_seconds"], True), "Invalid frozen selection time")
    original.validate_evaluation(result["test"], panel, truth, counts)
    training = result["training"]
    require(training["steps"] == 600 == design["frozen_control"]["steps"] and
            training["learning_rate"] == .001 == design["frozen_control"]["learning_rate"] and
            training["seed"] == spec["initialization_seed"] and result["validation"] is None and
            result["checkpoint"] is None, "Frozen training/validation/checkpoint rule differs")
    require(training.get("all_final_parameters_finite") is True and training.get("parameter_count") == 50312,
            "Frozen MLP parameter count/finite declaration differs")
    original.assert_same(training["device"], expected_device, "Recorded CuPy GPU identity")
    original.validate_log(training["log"], training["steps"])
    path = bind(result["log_file"], "artifacts", result["log_sha256"])
    require(path.parent == safe(root, relative).parent, "Frozen log leaves its run directory")
    logged = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    original.validate_log(logged, training["steps"])
    original.assert_same(logged, training["log"], "Frozen raw/history log")
    require(cuda.finite_number(result["total_seconds"], True) and
            result["total_seconds"] >= logged[-1]["elapsed_seconds"], "Frozen elapsed time invalid")


def verify_map(root, mapping):
    require(isinstance(mapping, dict), "Missing SHA map")
    for name, digest in mapping.items():
        require(original.valid_sha(digest) and sha(safe(root, name)) == digest, "Changed bound file: " + name)


def check_amendment(root):
    require(sha(safe(root, AMENDMENT)) == AMENDMENT_SHA, "User backend amendment SHA changed")
    value = read(safe(root, AMENDMENT))
    require(value.get("user_driven") is True and value.get("after_panel_exposure") is True and
            value.get("main_display_descriptive") is True and value.get("original_CPU90_completed") is False and
            value.get("cpu_reference_expected") == 72 and value.get("cpu_remaining_transferred") == 18 and
            value.get("active_full", {}).get("expected_runs") == 90 and value.get("active_frozen", {}).get("expected_runs") == 486 and
            value.get("active_frozen", {}).get("source") == "evidence/v2/runs/dinov2_mlp128" and
            value.get("active_expected_total") == 576 and value.get("new_independent_holdout") is False and
            value.get("no_confirmatory_upgrade") is True and
            value.get("cpu_writer_terminal_asserted") is True, "Explicit user/backend amendment fields missing or inconsistent")
    process = value.get("cpu_writer_process")
    require(isinstance(process, dict) and process.get("pid"), "No recorded original CPU PID identity")
    stop = read(safe(root, value["cpu_stop_receipt"]))
    require(sha(safe(root, value["cpu_stop_receipt"])) == value["cpu_stop_receipt_sha256"] and
            stop["pid"] == process["pid"] and stop["final_completed"] == 72 and
            stop["status"] == "STOPPED_AFTER_NEW_COMPLETED_FIT_BOUNDARY_BY_USER_BACKEND_MIGRATION", "CPU stop receipt differs")
    current = scheduler.process_info(process["pid"])
    if current["alive"]:
        # A native Windows FILETIME is an actual creation identity; the CIM
        # microsecond observation must never be padded into an invented token.
        token = current.get("creation_token")
        require(token and token.isdigit() and int(token) > 116444736000000000,
                "CPU PID is live/unknown and creation identity cannot be disambiguated")
        born = (int(token) - 116444736000000000) / 10_000_000
        stopped = datetime.fromisoformat(stop["stopped_utc"].replace("Z", "+00:00")).timestamp()
        require(born > stopped + 1, "Original CPU writer may still be live; not a proven PID reuse")
    return value


def cpu_references(root, expected, freeze_sha, execution, bind):
    expected_paths = {original_path(i): i for i in expected.values()}
    base = safe(root, "evidence/v2/runs/resnet18_unet")
    paths = {p.relative_to(root).as_posix() for p in base.rglob("result.json")} if base.exists() else set()
    require(paths == set(expected_paths) and len(paths) == 72, "CPU reference must retain exactly72 base results, separately from active576")
    for relative, spec in expected_paths.items():
        value = read(bind(relative, "cpu_reference_results"))
        require(value.get("status") == "complete" and original.run_key(value["identity"]) == original.run_key(spec) and
                value["identity"]["freeze_sha256"] == freeze_sha and value["identity"]["execution_code_sha256"] == execution,
                "CPU reference header does not match historical execution")
        log = bind(value["log_file"], "cpu_reference_artifacts", value["log_sha256"])
        require(log.parent == safe(root, relative).parent, "CPU reference log leaves its folder")
        checkpoint = value.get("checkpoint")
        if checkpoint is not None:
            path = bind(checkpoint["path"], "cpu_reference_artifacts", checkpoint["sha256"])
            require(path.parent == safe(root, relative).parent and original.valid_sha(checkpoint["state_sha256"]),
                    "CPU reference checkpoint identity invalid")
    return paths


def audit_active(root=ROOT):
    root = Path(root).resolve()
    report = {"format": "v2-active-run-completeness-1", "created_utc": utc(), "passed": False,
        "expected_total": 576, "validated_runs": 0, "observed_result_files": 0,
        "errors": [], "missing": [], "extra": [], "duplicates": [], "inputs": {}, "artifacts": {}, "results": {}, "runs": [],
        "cpu_reference_results": {}, "cpu_reference_artifacts": {}, "cpu_reference_result_files": {},
        "cpu_reference_files": {}, "score_fields_opened": False,
        "audit_code_sha256": sha(Path(__file__)), "statistical_reference_code_sha256": sha(Path(statistics.__file__)),
        "role": ROLE, "new_confirmatory_evidence": False, "original_CPU90_completed": False,
        "active_model_counts": {"resnet18_unet": 90, "dinov2_mlp128": 486},
        "backend_epochs": {"resnet18_unet": "post_exposure_user_driven_Torch_CUDA_replication90",
                           "dinov2_mlp128": "original_frozen_DINO_CuPy486"},
        "feature_arrays_read": False, "raster_pixels_read": False, "model_checkpoints_deserialized": False}
    def bind(relative, category="inputs", expected=None):
        path = safe(root, relative); digest = sha(path)
        require(expected is None or digest == expected, "SHA mismatch: " + relative)
        report[category][relative] = digest
        return path
    try:
        amendment = check_amendment(root); bind(AMENDMENT, expected=AMENDMENT_SHA)
        bind(amendment["cpu_stop_receipt"], expected=amendment["cpu_stop_receipt_sha256"])
        snapshot = read(bind(amendment["cpu_reference_snapshot"], expected=amendment["cpu_reference_snapshot_sha256"]))
        require(snapshot["completed"] == 72 and snapshot["not_executed_cpu"] == 18 and
                snapshot["cpu_process_terminal"] is True and snapshot["no_scores_summarized"] is True and
                snapshot["boundary_record_sha256"] == amendment["cpu_stop_receipt_sha256"], "CPU preservation snapshot differs")
        require(cuda.quiescence(root)["passed"], "CUDA90 still has live/unresolved writers")
        require(amendment["active_full"]["audit"] == cuda.AUDIT, "Wrong active GPU audit path")
        gpu = read(bind(cuda.AUDIT, expected=amendment["active_full"]["audit_sha256"]))
        require(gpu.get("passed") is True and gpu.get("validated_count") == gpu.get("observed_count") == 90 and
                gpu.get("terminal_metadata_preflight_passed") is True, "Passed complete terminal CUDA90 audit required first")
        require(gpu["code_sha256"]["code/v2_audit_cuda.py"] == sha(Path(cuda.__file__)), "CUDA90 auditor changed after audit")
        for category in ("inputs", "artifact_sha256", "result_files", "code_sha256"):
            verify_map(root, gpu[category])
        source_plan = read(safe(root, scheduler.PLAN))
        require(amendment["active_full"]["plan"] == scheduler.PLAN and
                sha(safe(root, scheduler.PLAN)) == amendment["active_full"]["plan_sha256"], "Active CUDA plan binding differs")
        _, gpu_paths, gpu_missing, gpu_extra = cuda.result_inventory(root, source_plan)
        require(not gpu_missing and not gpu_extra and set(gpu_paths) == set(gpu["result_files"]), "CUDA90 inventory changed after audit")
        design, extension = read(bind("configs/v2_design.json")), read(bind("configs/v2_extension.json"))
        expected, full, frozen, cpu = partition_matrix(design, extension)
        inventory = exact_frozen_inventory(root, frozen)
        freeze = read(bind("configs/v2_freeze.json")); frozen_files = freeze["file_sha256"]
        require(report["inputs"]["configs/v2_freeze.json"] == amendment["original_freeze_sha256"], "Amendment historical freeze binding differs")
        require(len(frozen_files) == 53, "Original53-file freeze required")
        required = {"configs/v2_design.json", "configs/v2_extension.json", "configs/v2_geographic_sensitivity.json",
                    "v2/data/manifest.json", "v2/data/development_manifest.json", "evidence/v2/data_audit.json",
                    "evidence/v2/calibration/calibration.json", "cache/dinov2-formal120/index.json",
                    "v2/cache/new_panel_dinov2/index.json", *("code/" + n for n in original.EXECUTION_FILES)}
        require(required <= set(frozen_files), "Original freeze required bindings missing")
        for name, digest in frozen_files.items(): bind(name, expected=digest)
        require(freeze["status"] == "FROZEN_BEFORE_NEW_PANEL_EVALUATION" and
                freeze["expected_full_runs"] == 90 and freeze["expected_frozen_runs"] == 486, "Historical freeze differs")
        execution = {n: frozen_files["code/" + n] for n in original.EXECUTION_FILES}
        headers = frozen_terminal_headers(root, inventory, report["inputs"]["configs/v2_freeze.json"], execution)
        report["frozen_terminal_metadata_preflight_passed"] = True
        frozen_root = safe(root, amendment["active_frozen"]["source"])
        require(not any(p for pattern in ("*.pt", "*.pth", "*.ckpt") for p in frozen_root.rglob(pattern)),
                "Frozen486 contains an unreported learned checkpoint")
        for name in HELPERS:
            module = sys.modules[Path(name).stem]
            require(sha(safe(root, name)) == sha(Path(module.__file__)), "Loaded helper differs from target root: " + name)
            bind(name)
        bind("code/v2_active_gpu_results.py", expected=sha(Path(__file__)))
        for category in ("inputs", "artifact_sha256", "code_sha256"):
            for name, digest in gpu[category].items(): bind(name, "artifacts" if category == "artifact_sha256" else "inputs", digest)
        require(len(gpu["result_files"]) == 90, "CUDA audit result map must have90 entries")
        cpu_paths = cpu_references(root, cpu, report["inputs"]["configs/v2_freeze.json"], execution, bind)
        require(set(snapshot["results"]) == cpu_paths and snapshot["original_freeze_sha256"] ==
                report["inputs"]["configs/v2_freeze.json"], "CPU snapshot identity/freeze inventory differs")
        report["cpu_reference_result_files"] = dict(report["cpu_reference_results"])
        for name, info in snapshot["results"].items():
            require(info["sha256"] == report["cpu_reference_results"][name], "CPU snapshot result SHA differs")
        all_reference = {name: info["sha256"] for name, info in snapshot["results"].items()}
        require(not set(all_reference) & set(snapshot["additional_files"]), "Duplicate CPU snapshot file")
        all_reference.update(snapshot["additional_files"])
        require(len(all_reference) == 219 and all(name.startswith("evidence/v2/runs/resnet18_unet/") for name in all_reference),
                "Expected exact219 scoped CPU preservation files")
        verify_map(root, all_reference)
        report["cpu_reference_files"] = all_reference
        report["cpu_reference_count"] = len(cpu_paths)
        report["cpu_reference_scope"] = "Historical72 header/SHA/log/checkpoint references only; excluded from all576 active fits and six tables"
        manifest = read(safe(root, "v2/data/manifest.json")); pairs = {r["id"]: r for r in manifest["pairs"]}
        require(manifest.get("status") == "complete" and manifest.get("whole_v2_dataset_complete") is True, "Incomplete compact manifest")
        require(len(pairs) == len(manifest["pairs"]) == 192, "Need192 unique manifest identities")
        panel = {k: r for k, r in pairs.items() if r["region"] in design["new_test_regions"]}
        development = {k: r for k, r in pairs.items() if r["region"] in design["old_development_regions"]}
        require(len(panel) == 72 and len(development) == 120 and not set(panel) & set(development) and
                Counter(r["region"] for r in panel.values()) == {r: 3 for r in design["new_test_regions"]}, "Wrong fixed panel/development partition")
        data = read(safe(root, "evidence/v2/data_audit.json"))
        require(data["passed"] is True and data["processed_pngs_usable"] is True and
                data["audit_code_sha256"] == sha(safe(root, "code/v2_audit_data.py")) and
                data["geography_helper_sha256"] == sha(safe(root, "code/geography_audit.py")), "Data audit code/status differs")
        for info in data["inputs"].values(): bind(info["path"], expected=info["sha256"])
        counts = original.audited_processed_counts(data, pairs)
        require(set(counts) == set(pairs), "Need absolute processed-mask truth margins for every image")
        # GPU90 audit already binds all compact bytes; sidecars add identity checks.
        for record in pairs.values():
            for kind in ("rgb", "label", "metadata"):
                info = record[kind]; path = bind("v2/data/" + info["relative_path"], "artifacts", info["sha256"])
                require(path.stat().st_size == info["bytes"], "Compact artifact size differs")
            sidecar = read(path)
            require(sidecar["id"] == record["id"] and sidecar["region"] == record["region"], "Sidecar identity differs")
            original.merge_processed_counts(counts, record["id"], original.processed_truth_counts(record, sidecar))
        index = read(safe(root, "cache/dinov2-formal120/index.json")); records = index["records"]
        require(index["status"] == "complete" and len(records) == 120 and {r["id"] for r in records} == set(development), "Source feature index differs")
        for r in records:
            pair = development[r["id"]]
            require(r["region"] == pair["region"] and all(r["source_" + k + "_sha256"] == pair["source_" + k]["sha256"] for k in ("rgb", "label")), "Source feature provenance differs")
        target = read(safe(root, "v2/cache/new_panel_dinov2/index.json"))
        require(target.get("status") == "complete" and len(target["records"]) == 72 and
                {r["id"] for r in target["records"]} == set(panel), "Panel feature metadata must cover exact72")
        for r in target["records"]:
            require(r["region"] == panel[r["id"]]["region"] and
                    r["processed_rgb_sha256"] == panel[r["id"]]["rgb"]["sha256"], "Panel feature metadata provenance differs")
        environment = read(bind("evidence/v2/environment_record.json"))
        device = environment["gpu_runtime_previously_observed"]
        require(device["name"] == "NVIDIA GeForce RTX 4060 Laptop GPU" and device["cupy"] == "14.2.0", "Recorded frozen-head GPU environment differs")
        split_map = {s["id"]: s for s in design["source_splits"]}; cache = {}; truth = {}; seen = set()
        report["score_fields_opened"] = True
        for relative, digest in sorted(gpu["result_files"].items()):
            result = read(bind(relative, "results", digest)); key = original.run_key(result["identity"])
            require(key in full and key not in seen, "Duplicate/non-full CUDA identity in active matrix")
            seen.add(key); report["runs"].append({"path": relative, "identity": dict(zip(original.KEYS, key)), "sha256": digest,
                                                "backend": "Torch_CUDA", "source_epoch": "user_driven_post_exposure_execution_amendment"})
        require(seen == set(full), "Active GPU90 matrix differs")
        for relative, spec in inventory.items():
            result = read(bind(relative, "results", headers[relative])); identity = result["identity"]; key = original.run_key(identity)
            require(key in frozen and key not in seen, "Duplicate/non-frozen identity in active matrix")
            split = split_map[identity["source_split"]]
            selection_key = tuple(identity[k] for k in ("source_split", "pool", "budget", "strategy", "selection_seed"))
            if selection_key not in cache: cache[selection_key] = selection_reference(records, split, identity)
            validate_frozen_result(root, relative, result, spec, cache[selection_key], design, panel, counts, truth, bind, device)
            seen.add(key); report["runs"].append({"path": relative, "identity": dict(zip(original.KEYS, key)), "sha256": headers[relative],
                                                "backend": "CuPy_frozen_DINO_MLP", "source_epoch": "original_frozen_recipe"})
        require(len(seen) == len(report["results"]) == len(report["runs"]) == 576 and seen == set(expected), "Active matrix incomplete")
        require(not set(report["cpu_reference_results"]) & set(report["results"]), "CPU references leaked into active576")
        for name in ("inputs", "artifacts", "results", "cpu_reference_results", "cpu_reference_artifacts", "cpu_reference_files"): verify_map(root, report[name])
        require(cuda.quiescence(root)["passed"] and exact_frozen_inventory(root, frozen) == inventory and
                cuda.result_inventory(root, source_plan)[1] == gpu_paths, "Active writers/inventory changed")
        check_amendment(root)
        require({p.relative_to(root).as_posix() for p in safe(root, "evidence/v2/runs/resnet18_unet").rglob("result.json")} == cpu_paths,
                "CPU reference inventory changed during audit")
        report.update(passed=True, validated_runs=576, observed_result_files=576,
                      processed_pixel_check={"processed_metadata_images": len(counts), "cross_fit_truth_margin_images": len(truth)},
                      cuda_audit_sha256=report["inputs"][cuda.AUDIT])
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        report["errors"].append(type(exc).__name__ + ": " + str(exc))
        report["validated_runs"] = len(report["runs"])
    return report


def build_active_analysis(fits, design, extension, geographic, amendment_sha):
    result = statistics.build_analysis(fits, design, extension, geographic)
    primary = result["primary"]
    primary.update(role=ROLE, new_confirmatory_evidence=False, prospective_GPU_primary=False,
                   original_CPU90_completed=False, backend_amendment_sha256=amendment_sha,
                   interpretation="Fixed contrast/metric under a user-driven backend amendment after panel exposure; descriptive main display, not a new prospective primary")
    for metric, summary in primary["metrics"].items():
        summary["role"] = ROLE if metric == "union_class_miou" else "descriptive_metric_convention_sensitivity"
    for contrast in result["contrasts"]["contrasts"]:
        if contrast["role"] == "primary": contrast["role"] = ROLE
    result["contrasts"]["active_execution_scope"] = ROLE
    result["contrasts"]["backend_amendment_sha256"] = amendment_sha
    return result


def render_outputs(analysis, directory):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    for name in ("conditions_by_source", "conditions", "regions", "classes"):
        statistics.write_csv(directory / (name + ".csv"), analysis[name])
    for name in ("contrasts", "primary"): original.write_json(directory / (name + ".json"), analysis[name])
    return {"tables/v2/" + Path(n).name: sha(directory / Path(n).name) for n in NUMERICAL}


def current_inventory(root, audit, design, extension):
    """Reject new missing/extra paths as well as mutations of recorded bytes."""
    expected, full, frozen, cpu = partition_matrix(design, extension)
    require(len(audit["runs"]) == 576 and {original.run_key(r["identity"]) for r in audit["runs"]} == set(expected) and
            {r["path"]: r["sha256"] for r in audit["runs"]} == audit["results"], "Active result identity matrix differs")
    frozen_paths = exact_frozen_inventory(root, frozen)
    gpu_map = read(safe(root, cuda.AUDIT))["result_files"]
    _, observed, missing, extra = cuda.result_inventory(root, read(safe(root, scheduler.PLAN)))
    require(not missing and not extra and set(observed) == set(gpu_map) and len(gpu_map) == 90 and
            not set(gpu_map) & set(frozen_paths) and
            {**gpu_map, **{n: audit["results"].get(n) for n in frozen_paths}} == audit["results"], "GPU90/frozen486 scopes differ")
    cpu_paths = {original_path(i) for i in cpu.values()}
    observed_cpu = {p.relative_to(root).as_posix() for p in safe(root, "evidence/v2/runs/resnet18_unet").rglob("result.json")}
    require(audit["cpu_reference_result_files"] == audit["cpu_reference_results"] and
            set(audit["cpu_reference_result_files"]) == cpu_paths == observed_cpu and
            len(audit["cpu_reference_files"]) == 219 and not set(audit["cpu_reference_files"]) & set(audit["results"]), "CPU72/219 reference separation differs")


def load_active(root):
    audit_path = safe(root, AUDIT); audit = read(audit_path)
    require(audit.get("passed") is True and audit.get("expected_total") == audit.get("validated_runs") ==
            audit.get("observed_result_files") == len(audit["results"]) == 576 and
            not any(audit.get(k) for k in ("errors", "missing", "extra", "duplicates")), "Passed complete active576 audit required before statistics")
    require(audit["audit_code_sha256"] == sha(Path(__file__)) and
            audit["statistical_reference_code_sha256"] == sha(Path(statistics.__file__)), "Active audit/helper code changed")
    for category in ("inputs", "artifacts", "results", "cpu_reference_results", "cpu_reference_artifacts", "cpu_reference_files"): verify_map(root, audit[category])
    check_amendment(root); require(cuda.quiescence(root)["passed"], "CUDA writer restarted")
    design, extension = read(safe(root, "configs/v2_design.json")), read(safe(root, "configs/v2_extension.json"))
    current_inventory(root, audit, design, extension)
    fits = [statistics.make_fit(read(safe(root, name))) for name in sorted(audit["results"])]
    geographic = read(safe(root, "configs/v2_geographic_sensitivity.json"))
    analysis = build_active_analysis(fits, design, extension, geographic, audit["inputs"][AMENDMENT])
    return audit, sha(audit_path), fits, analysis


def validate_bundle(root=ROOT):
    """Read-only delivery gate: metadata/SHA bindings, never numerical writes.

    Byte reproduction remains an explicit --verify-tables operation. This gate
    does not turn software validation into scientific or editorial approval.
    """
    root = Path(root).resolve()
    report = {"passed": False, "errors": [], "scientific_outputs_written": False,
              "numerical_recomputation_performed": False}
    try:
        audit = read(safe(root, AUDIT)); identity = read(safe(root, IDENTITY))
        require(audit.get("passed") is True and audit.get("expected_total") == audit.get("validated_runs") ==
                audit.get("observed_result_files") == len(audit["results"]) == 576 and
                not any(audit.get(k) for k in ("errors", "missing", "extra", "duplicates")), "Complete passed active576 audit required")
        require(audit["audit_code_sha256"] == identity["audit_code_sha256"] == identity["analysis_code_sha256"] ==
                identity["newanalysis_code_sha256"] == sha(Path(__file__)) and
                audit["statistical_reference_code_sha256"] == identity["statistical_reference_code_sha256"] ==
                sha(Path(statistics.__file__)), "Active wrapper/statistical reference code differs")
        for category in ("inputs", "artifacts", "results", "cpu_reference_results", "cpu_reference_artifacts", "cpu_reference_files"):
            verify_map(root, audit[category])
        require(audit["inputs"][AMENDMENT] == AMENDMENT_SHA and
                audit["inputs"]["configs/v2_freeze.json"] == read(safe(root, AMENDMENT))["original_freeze_sha256"], "Required amendment/freeze bindings differ")
        check_amendment(root)
        require(cuda.quiescence(root)["passed"], "CUDA writers restarted")
        design, extension = read(safe(root, "configs/v2_design.json")), read(safe(root, "configs/v2_extension.json"))
        current_inventory(root, audit, design, extension)
        require(identity["audit_sha256"] == sha(safe(root, AUDIT)) and identity["result_sha256"] == audit["results"] and
                identity["audited_input_sha256"] == audit["inputs"] and identity["audited_artifact_sha256"] == audit["artifacts"] and
                identity["counts"] == {"fits": 576, "conditions_by_source": 192, "conditions": 64, "regions_rows": 1536, "classes_rows": 512}, "Analysis identity/counts differ")
        require(set(identity["output_sha256"]) == set(NUMERICAL), "Canonical six-output set differs")
        verify_map(root, identity["output_sha256"])
        require(audit["role"] == identity["role"] == ROLE and identity["new_confirmatory_evidence"] is False and
                identity["original_CPU90_completed"] is False, "Post-exposure descriptive role differs")
        report.update(passed=True, audit=audit, analysis=identity, output_sha256=identity["output_sha256"])
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        report["errors"].append(type(exc).__name__ + ": " + str(exc))
    return report


def capacity(root, extra):
    require(scheduler.logical_bytes(root) + extra + 4_000_000 < scheduler.CAP, "Whole-project2GB active-table working reserve unavailable")


def write_small(root, relative, value):
    path = safe(root, relative); capacity(root, len(scheduler.raw(value)))
    original.write_json(path, value)


def analyse(root=ROOT):
    root = Path(root).resolve(); audit, audit_sha, fits, analysis = load_active(root)
    identity_path = safe(root, IDENTITY)
    if any(safe(root, n).exists() for n in NUMERICAL):
        require(identity_path.exists(), "Existing canonical outputs lack an active identity; never overwrite foreign results")
        previous = read(identity_path)
        require(previous.get("newanalysis_code_sha256") == sha(Path(__file__)) and previous.get("result_sha256") == audit["results"],
                "Existing canonical outputs belong to another result/code epoch")
        verify_map(root, previous["output_sha256"])
    capacity(root, 4_000_000)
    outputs = render_outputs(analysis, safe(root, "tables/v2"))
    identity = {"format": "v2-active-analysis-identity-1", "created_utc": utc(), "role": ROLE,
        "audit_sha256": audit_sha, "newanalysis_code_sha256": sha(Path(__file__)), "analysis_code_sha256": sha(Path(__file__)),
        "statistical_reference_code_sha256": sha(Path(statistics.__file__)), "audit_code_sha256": audit["audit_code_sha256"],
        "audited_input_sha256": audit["inputs"], "audited_artifact_sha256": audit["artifacts"], "result_sha256": audit["results"],
        "cpu_reference_result_sha256": audit["cpu_reference_results"], "output_sha256": outputs,
        "counts": {"fits": len(fits), "conditions_by_source": len(analysis["conditions_by_source"]), "conditions": len(analysis["conditions"]),
                   "regions_rows": len(analysis["regions"]), "classes_rows": len(analysis["classes"])},
        "runtime": {"python": sys.version.split()[0], "numpy": np.__version__},
        "new_confirmatory_evidence": False, "original_CPU90_completed": False,
        "interpretation": "GPU90+originalfrozen486 active logical matrix; CPU72 separate reference; fixed contrast/metric but post-exposure user execution amendment"}
    require(identity["counts"] == {"fits": 576, "conditions_by_source": 192, "conditions": 64, "regions_rows": 1536, "classes_rows": 512},
            "Active canonical table structure differs")
    verify_map(root, audit["results"]); verify_map(root, audit["inputs"])
    write_small(root, IDENTITY, identity)
    return identity


def verify_tables(root=ROOT):
    root = Path(root).resolve()
    report = {"format": "v2-active-reproduction-check-1", "created_utc": utc(), "passed": False, "tables_passed": False,
              "wrapper_code_sha256": sha(Path(__file__)), "scientific_outputs_written": False, "errors": []}
    try:
        identity = read(safe(root, IDENTITY)); baseline = {n: sha(safe(root, n)) for n in NUMERICAL}
        require(identity["newanalysis_code_sha256"] == sha(Path(__file__)) and identity["output_sha256"] == baseline,
                "Existing active analysis/table identity differs")
        require(identity["runtime"] == {"python": sys.version.split()[0], "numpy": np.__version__}, "Numerical reproduction runtime differs")
        capacity(root, sum(safe(root, n).stat().st_size for n in NUMERICAL))
        audit, audit_sha, fits, analysis = load_active(root)
        require(identity["audit_sha256"] == audit_sha and identity["result_sha256"] == audit["results"] and
                identity["audited_input_sha256"] == audit["inputs"] and identity["audited_artifact_sha256"] == audit["artifacts"],
                "Active analysis is not bound to current complete audit")
        with tempfile.TemporaryDirectory(prefix="v2-active-reproduce-") as directory:
            recalculated = render_outputs(analysis, directory)
        require(recalculated == baseline, "Recomputed six numerical files differ; originals were not overwritten")
        require({n: sha(safe(root, n)) for n in NUMERICAL} == baseline and sha(safe(root, AUDIT)) == audit_sha,
                "Canonical outputs/audit changed during reproduction")
        report.update(passed=True, tables_passed=True, audit_sha256=audit_sha, numerical_outputs_before_sha256=baseline,
            numerical_outputs_after_sha256=baseline, recomputed_output_sha256=recalculated, result_sha256=audit["results"],
            audit_report_sha256=audit_sha, freeze_sha256=audit["inputs"]["configs/v2_freeze.json"],
            frozen_input_sha256=read(safe(root, "configs/v2_freeze.json"))["file_sha256"],
            audited_input_sha256=audit["inputs"], validated_counts=identity["counts"], role=ROLE, new_confirmatory_evidence=False)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc: report["errors"].append(str(exc))
    write_small(root, REPRODUCTION, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ("audit-only", "analyse", "verify-tables", "self-test"): modes.add_argument("--" + name, action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        import unittest
        return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName("test_v2_active_gpu_results")).wasSuccessful() else 1
    if args.audit_only:
        report = audit_active(args.root); write_small(args.root, AUDIT, report)
        print(json.dumps({"passed": report["passed"], "validated_runs": report["validated_runs"], "errors": report["errors"]})); return 0 if report["passed"] else 1
    if args.analyse:
        value = analyse(args.root); print(json.dumps({"counts": value["counts"], "role": ROLE})); return 0
    value = verify_tables(args.root); print(json.dumps({"passed": value["passed"], "errors": value["errors"]})); return 0 if value["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())

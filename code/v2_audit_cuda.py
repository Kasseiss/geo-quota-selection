"""NumPy-only audit and descriptive analysis of the complete fixed CUDA90.

Refuses active/ambiguous CUDA writers and incomplete inventories before opening
any result. --self-test uses synthetic temporary evidence only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import uuid

import numpy as np
import v2_cuda_parallel_v2 as scheduler
from v2_audit_runs import (assert_same, audited_processed_counts, complete_aggregate,
                           expected_matrix, run_key, valid_sha, validate_evaluation, validate_log)
from v2_statistics import average_regional, paired_region_summary

ROOT = Path(__file__).resolve().parents[1]
PLAN = scheduler.PLAN
PLAN_SHA = scheduler.PLAN_SHA
OUT = scheduler.OUT
AUDIT = "evidence/v2/cuda_execution_audit.json"
ANALYSIS = "tables/v2_cuda/descriptive_analysis.json"
EXECUTORS = ("code/v2_cuda_parallel.py", "code/v2_cuda_parallel_v2.py")
HELPERS = ("code/v2_audit_runs.py", "code/v2_statistics.py", "code/core.py")
CONTRASTS = (("region_kcenter", "kcenter"), ("region_kcenter", "permuted_region_kcenter"),
             ("region_weighted_facility_location", "facility_location"),
             ("region_weighted_facility_location", "permuted_region_weighted_facility_location"))
require = scheduler.require
safe = scheduler.safe
sha = scheduler.sha
read = scheduler.read


def finite_number(value, nonnegative=False):
    return type(value) in (float, int) and math.isfinite(value) and (not nonnegative or value >= 0)


def quiescence(root):
    """Identity-aware process checks; never reads result/score data."""
    base = safe(root, OUT); errors, evidence = [], {}
    writer = base / "writer.lock"
    if writer.exists():
        value = read(writer)
        evidence[writer.relative_to(root).as_posix()] = {"sha256": sha(writer), "live": scheduler.same_live_process(value)}
        errors.append("CUDA writer.lock remains present (live or unresolved stale writer)")
        for child in value.get("children", []):
            if scheduler.same_live_process(child): errors.append("Live child recorded by CUDA writer")
    for claim in base.glob("*/parallel_fit.lock") if base.exists() else []:
        value = read(claim)
        evidence[claim.relative_to(root).as_posix()] = {"sha256": sha(claim), "live": scheduler.same_live_process(value)}
        errors.append("Unresolved per-fit writer claim: " + claim.relative_to(root).as_posix())
    parallel = base / "parallel"
    if parallel.exists():
        for generation in parallel.iterdir():
            if not generation.is_dir(): continue
            for lease in generation.glob("worker_*.lease.json"):
                value = read(lease); live = scheduler.same_live_process(value)
                evidence[lease.relative_to(root).as_posix()] = {"sha256": sha(lease), "live": live, "state": value.get("state")}
                if live or value.get("state") != "terminal" or not value.get("pid"):
                    errors.append("Live/unknown/nonterminal worker lease: " + lease.relative_to(root).as_posix())
            closed = generation / "global_lease.closed.json"
            if (generation / "scheduling_amendment.json").exists() and not closed.exists():
                errors.append("Unclosed parallel generation: " + generation.name)
            if closed.exists():
                value = read(closed)
                if scheduler.same_live_process(value) or any(scheduler.same_live_process(c) for c in value.get("children", [])):
                    errors.append("Closed generation still has a live PID identity: " + generation.name)
    return {"passed": not errors, "errors": errors, "process_evidence": evidence}


def result_inventory(root, plan):
    expected = {OUT + "/" + scheduler.run_key(s["identity"]) + "/result.json": s for s in plan["runs"]}
    require(len(expected) == len(plan["runs"]) == 90, "Plan must contain exactly90 unique output identities")
    base = safe(root, OUT)
    observed = {p.relative_to(root).as_posix() for p in base.rglob("result.json")} if base.exists() else set()
    return expected, sorted(observed), sorted(set(expected)-observed), sorted(observed-set(expected))


def terminal_metadata_preflight(root, expected, plan_sha):
    """Validate every terminal header before any training/log/CM inspection.

    JSON parsing necessarily reads the result file, but this pass accesses only
    format, status, plan, identity and source-selection metadata. Result hashes
    bind the following numerical pass to these exact preflighted bytes.
    """
    checked = {}
    for relative, spec in expected.items():
        path = safe(root, relative)
        checksum = sha(path)
        value = read(path)
        require(isinstance(value, dict) and value.get("format") == "v2-cuda-execution-result-1" and
                value.get("status") == "complete" and value.get("plan_sha256") == plan_sha,
                "Nonterminal/invalid CUDA metadata: " + relative)
        assert_same(value.get("identity"), spec["identity"], "Terminal metadata identity: " + relative)
        assert_same(value.get("selection"), spec["selection"], "Terminal metadata selection: " + relative)
        require(sha(path) == checksum, "Result changed during terminal metadata preflight: " + relative)
        checked[relative] = checksum
    return checked


def _parallel_provenance(root, result, spec_index, plan, bind, code):
    scheduling = result["scheduling"]
    generation = scheduling["generation"]; workers = scheduling["workers"]; worker = scheduling["worker"]
    require(type(workers) is int and workers in (2, 3, 4) and type(worker) is int and worker == spec_index % workers and
            scheduling["plan_index"] == spec_index and scheduling["partition_rule"] == "fixed_plan_index_modulo_workers" and
            scheduling["cpu_threads_per_worker"] == 2, "Parallel partition/provenance differs from fixed plan")
    folder = OUT + "/parallel/" + generation
    require(scheduling["amendment_file"] == folder + "/scheduling_amendment.json", "Parallel amendment path differs")
    amendment = read(bind(scheduling["amendment_file"], "artifact_sha256", scheduling["amendment_sha256"]))
    matches = [p for p in EXECUTORS if code[p] == result["code_sha256"]]
    require(len(matches) == 1 and result["executor_code_sha256"] == result["code_sha256"] and
            result["scalar_reference_code_sha256"] == plan["code_sha256"], "Unknown/relabelled parallel executor")
    require(amendment["executor_code_sha256"] == result["code_sha256"] and amendment["plan_sha256"] == PLAN_SHA and
            amendment["scalar_reference_code_sha256"] == plan["code_sha256"] and amendment["generation"] == generation and
            amendment["workers"] == workers and amendment["primary_and_original_576_unchanged"] is True and
            amendment["source_selected_ids_lr_steps_batch_crop_seeds_unchanged"] is True and
            amendment["cpu_threads_per_worker"] == 2 and amendment["deterministic_warn_only"] is True and
            amendment["no_extra_checkpoint"] is True and amendment["score_fields_used_for_scheduling"] is False,
            "Parallel amendment does not bind unchanged scientific execution")
    assert_same(amendment["runtime"], plan["runtime"], "Parallel amendment runtime")
    own = read(bind(folder+f"/worker_{worker}.lease.json", "artifact_sha256"))
    closed = read(bind(folder+"/global_lease.closed.json", "artifact_sha256"))
    require(own["state"] == "terminal" and own["generation"] == generation and own["worker"] == worker and
            own["workers"] == workers and own["pid"] == scheduling["pid"] and
            own["assigned_indices"] == list(range(worker, 90, workers)), "Worker lease ownership differs")
    require(closed["generation"] == generation and closed["plan_sha256"] == PLAN_SHA and
            closed["executor_sha256"] == result["code_sha256"] and
            closed["amendment_sha256"] == scheduling["amendment_sha256"] and
            any(c.get("worker") == worker and c["pid"] == own["pid"] and
                c.get("creation_token") == own.get("creation_token") for c in closed["children"]),
            "Supervisor closed lease does not authorize recorded worker")
    return {"kind": "parallel_v2" if matches[0].endswith("_v2.py") else "parallel_v1", "executor": matches[0],
            "executor_sha256": result["code_sha256"], "generation": generation, "worker": worker, "workers": workers,
            "amendment_sha256": scheduling["amendment_sha256"]}


def validate_training(result, spec, plan, selected, calibration, model_sha):
    training = result["training"]; identity = training["identity"]; runtime = plan["runtime"]
    require(result["format"] == "v2-cuda-execution-result-1" and result["status"] == "complete", "Invalid CUDA result status/format")
    assert_same(result["identity"], spec["identity"], "CUDA identity")
    assert_same(result["selection"], spec["selection"], "CUDA selection")
    require(result["plan_sha256"] == PLAN_SHA and result.get("deterministic_warn_only") is True,
            "CUDA plan or deterministic policy differs")
    require(training["encoder_lr"] == spec["encoder_lr"] and training["decoder_lr"] == 10*spec["encoder_lr"] and
            training["steps"] == spec["steps"] and training["seed"] == spec["identity"]["initialization_seed"] and
            training["batch_size"] == 2 and training["crop"] == 224 and training["device"] == "cuda:0" and
            training["validation"] == [] and training["all_final_parameters_finite"] is True,
            "CUDA training recipe/finite declaration differs")
    for field, expected in (("torch", "torch"), ("numpy", "numpy"), ("python", "cuda_python"), ("threads", "threads"), ("device_name", "device")):
        require(identity[field] == runtime[expected], "CUDA runtime identity differs: " + field)
    require(identity["selected_ids"] == spec["selection"]["selected_ids"] and
            identity["selected_record_sha256"] == hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest() and
            identity["model_code_sha256"] == model_sha and
            identity["pretrained_weight_sha256"] == calibration["environment"]["pretrained_weight_sha256"],
            "Selected/model/pretrained-weight identity differs")
    require(valid_sha(identity["initial_model_state_sha256"]) and valid_sha(training["final_model_state_sha256"]),
            "Missing/invalid learned-state SHA declaration")
    require(type(training["trainable_parameters"]) is int and training["trainable_parameters"] > 0 and
            finite_number(training["elapsed_seconds"], True) and finite_number(result["total_seconds"], True) and
            result["total_seconds"] >= training["elapsed_seconds"], "Invalid training count/timing")
    require(type(result["cuda_peak_allocated_bytes"]) is int and type(result["cuda_peak_reserved_bytes"]) is int and
            0 < result["cuda_peak_allocated_bytes"] <= result["cuda_peak_reserved_bytes"] and
            isinstance(result["warnings"], list) and all(isinstance(s, str) for s in result["warnings"]), "Invalid CUDA memory/warnings")
    validate_log(training["log"], spec["steps"])


def audit_cuda(root=ROOT, *, expected_plan_sha=PLAN_SHA):
    root = Path(root).resolve()
    report = {"format": "v2-cuda90-audit-1", "created_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
        "expected_count": 90, "observed_count": 0, "validated_count": 0, "result_files": {}, "artifact_sha256": {},
        "code_sha256": {}, "inputs": {}, "errors": [], "missing": [], "extra": [], "duplicates": [],
        "provenance_by_result": {}, "score_fields_opened": False, "raster_pixels_read": False,
        "terminal_metadata_preflight_passed": False, "terminal_metadata_sha256": {},
        "torch_or_cupy_required": False, "original_primary_unchanged": True, "new_independent_holdout": False,
        "state_validation_limit": "State hashes and finite flags are validated declarations; unsaved learned states cannot be independently rehashed/deserialized.",
        "log_validation_limit": "Exact step1/every50/final sample coverage and raw/history equality; unlogged optimizer steps are not individually observable."}
    loaded = []
    def bind(relative, category="inputs", expected=None):
        path = safe(root, relative); checksum = sha(path)
        require(expected is None or valid_sha(expected) and checksum == expected, "SHA mismatch: " + relative)
        report[category][relative] = checksum
        return path
    try:
        plan = read(bind(PLAN, expected=expected_plan_sha))
        require(plan["expected_runs"] == len(plan["runs"]) == 90, "Expected exact90 CUDA plan")
        live = quiescence(root); report["quiescence"] = live
        require(live["passed"], "; ".join(live["errors"]))
        expected, observed, missing, extra = result_inventory(root, plan)
        report.update(observed_count=len(observed), missing=missing, extra=extra)
        require(not missing and not extra and len(observed) == 90, "Incomplete/extra CUDA inventory; partial results not opened")
        # A complete path inventory alone does not prove90 terminal JSON files.
        # Inspect only headers across all90 before accessing training/logs/CMs.
        terminal = terminal_metadata_preflight(root, expected, expected_plan_sha)
        report.update(terminal_metadata_preflight_passed=True, terminal_metadata_sha256=terminal)
        report["score_fields_opened"] = True
        freeze = read(bind("configs/v2_freeze.json", expected=plan["original_freeze_sha256"]))
        require(len(freeze["file_sha256"]) == 53 and freeze["file_sha256"] == plan["original_frozen_file_sha256"],
                "Original53-file freeze differs from CUDA plan")
        for name, digest in freeze["file_sha256"].items(): bind(name, expected=digest)
        bind("evidence/v2/software/cuda_preflight.json", expected=plan["cuda_preflight_sha256"])
        for name in (scheduler.SCALAR, *EXECUTORS, *HELPERS, "code/v2_audit_cuda.py"):
            bind(name, "code_sha256", plan["code_sha256"] if name == scheduler.SCALAR else None)
        require(report["code_sha256"]["code/v2_audit_cuda.py"] == sha(Path(__file__)), "Auditor must execute target-root code")
        # Bind the helper actually used for PID/path checks, without Torch imports.
        require(report["code_sha256"]["code/v2_cuda_parallel_v2.py"] == sha(Path(scheduler.__file__)), "PID helper must be target-root V2 code")
        for name in HELPERS:
            require(report["code_sha256"][name] == sha(Path(sys.modules[Path(name).stem].__file__)),
                    "Loaded numerical helper differs from target-root code: " + name)
        design = read(safe(root, "configs/v2_design.json")); extension = read(safe(root, "configs/v2_extension.json"))
        matrix = {k:v for k,v in expected_matrix(design, extension).items() if v["model"] == "resnet18_unet"}
        require(len(matrix) == 90 and {run_key(s["identity"]) for s in plan["runs"]} == set(matrix), "CUDA identity matrix differs from original full90")
        manifest = read(safe(root, "v2/data/manifest.json")); pairs = {p["id"]:p for p in manifest["pairs"]}
        require(manifest["status"] == "complete" and manifest["whole_v2_dataset_complete"] and len(pairs) == len(manifest["pairs"]) == 192,
                "Expected complete192 data identities")
        panel = {i:pairs[i] for i in plan["new_panel_image_ids"]}
        require(len(panel) == 72 and Counter(p["region"] for p in panel.values()) == {r:3 for r in design["new_test_regions"]} and
                all(p["role"] == "new_panel" for p in panel.values()), "CUDA panel differs from fixed24 by3")
        data_audit = read(safe(root, "evidence/v2/data_audit.json"))
        require(data_audit["passed"] and data_audit["processed_pngs_usable"], "Data audit not passed")
        require(isinstance(data_audit.get("inputs"), dict) and data_audit["inputs"], "Data audit lacks original input bindings")
        for info in data_audit["inputs"].values():
            bind(info["path"], expected=info["sha256"])
        counts = audited_processed_counts(data_audit, pairs)
        require(set(counts) == set(pairs), "Need verified processed-mask truth margins for all192 images")
        for p in pairs.values():
            for kind in ("rgb", "label", "metadata"):
                record = p[kind]; path = bind("v2/data/"+record["relative_path"], expected=record["sha256"])
                require(path.stat().st_size == record["bytes"], "Compact file byte count differs")
        splits = {s["id"]:s for s in design["source_splits"]}
        calibration = read(safe(root, "evidence/v2/calibration/calibration.json"))
        choices = {s["source_split"]:s["chosen"] for s in calibration["splits"]}
        seen = set(); truth = {}; parameter_counts = set()
        for index, spec in enumerate(plan["runs"]):
            path = OUT + "/" + scheduler.run_key(spec["identity"]) + "/result.json"
            result = read(bind(path, "result_files", terminal[path])); key = run_key(result["identity"])
            if key in seen: report["duplicates"].append(path)
            require(key not in seen, "Duplicate CUDA result identity")
            seen.add(key); source = splits[spec["identity"]["source_split"]]
            require(spec["steps"] == choices[source["id"]]["steps"] and spec["encoder_lr"] == choices[source["id"]]["encoder_lr"],
                    "CUDA plan differs from source-only calibrated recipe")
            selected = [pairs[i] for i in spec["selection"]["selected_ids"]]
            require(len(selected) == len({p["id"] for p in selected}) == 12 and all(p["role"] == "old_development" and
                    p["region"] in source["train"] for p in selected), "CUDA selected source images differ")
            validate_training(result, spec, plan, selected, calibration, freeze["file_sha256"]["code/v2_segmentation.py"])
            log = bind(result["log_file"], "artifact_sha256", result["log_sha256"])
            require(log.parent == safe(root, path).parent and log.name.startswith("training_attempt_"), "Raw log outside run folder")
            entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
            validate_log(entries, spec["steps"]); assert_same(entries, result["training"]["log"], "Raw/history log")
            require(result["training"]["elapsed_seconds"] >= entries[-1]["elapsed_seconds"], "Log exceeds training elapsed time")
            attempt_name = log.with_name("attempt_"+log.stem[len("training_attempt_"):] + ".json").relative_to(root).as_posix()
            attempt = read(bind(attempt_name, "artifact_sha256"))
            require(attempt["status"] == "started" and attempt["plan_sha256"] == PLAN_SHA and attempt["device"] == "cuda:0",
                    "Attempt start record differs from CUDA plan/device")
            assert_same(attempt["identity"], result["identity"], "Attempt identity")
            assert_same(attempt.get("scheduling"), result.get("scheduling"), "Attempt scheduling provenance")
            if result["code_sha256"] == plan["code_sha256"]:
                require("scheduling" not in result and "executor_code_sha256" not in result, "Scalar result relabelled with parallel scheduling")
                provenance = {"kind":"scalar", "executor":scheduler.SCALAR, "executor_sha256":plan["code_sha256"]}
            else:
                provenance = _parallel_provenance(root, result, index, plan, bind, report["code_sha256"])
            report["provenance_by_result"][path] = provenance
            validation = {p["id"]:p for p in pairs.values() if p["role"] == "old_development" and p["region"] in source["validation"]}
            require(len(validation) == 20, "CUDA source validation must have20 images")
            validate_evaluation(result["test"], panel, truth, counts)
            validate_evaluation(result["validation"], validation, truth, counts)
            parameter_counts.add(result["training"]["trainable_parameters"])
            loaded.append(result); report["validated_count"] += 1
        require(len(seen) == 90 and len(parameter_counts) == 1, "CUDA count/parameter identity differs")
        for category in ("inputs", "artifact_sha256", "result_files", "code_sha256"):
            require(all(sha(safe(root,p)) == h for p,h in report[category].items()), "Input/artifact/result/code changed during audit")
        require(quiescence(root)["passed"] and result_inventory(root,plan)[1] == observed, "CUDA writer/inventory changed during audit")
        report.update(passed=True, provenance_counts=dict(Counter(p["kind"] for p in report["provenance_by_result"].values())),
                      panel_image_count=72, validation_images_per_fit=20, processed_truth_margins_checked=True,
                      state_finiteness="Declared finite flag and state SHA syntax checked; no trained state reload available for CUDA90.")
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        report["errors"].append(type(exc).__name__ + ": " + str(exc))
    return report, loaded if report["passed"] else []


def descriptive_analysis(results, design, audit, audit_sha):
    require(audit["passed"] and audit["validated_count"] == len(results) == 90, "Description requires passed complete90 audit")
    groups = defaultdict(list)
    for result in results:
        computed = complete_aggregate(result["test"]["images"])
        groups[result["identity"]["strategy"]].append({"identity":result["identity"], "regional":computed["regions"]})
    require(len(groups) == 10 and all(len(g) == 9 for g in groups.values()), "Description requires10 strategies by9 paired fits")
    source_ids = sorted(s["id"] for s in design["source_splits"])
    repetitions, seed = design["primary"]["repetitions"], design["primary"]["bootstrap_seed"]
    require(repetitions == 10000 and seed == 2026101805, "Original region-bootstrap definition changed")
    contrasts = []
    for a,b in CONTRASTS:
        aa,bb = average_regional(groups[a], "union_class_miou"), average_regional(groups[b], "union_class_miou")
        require(set(aa) == set(bb) == set(design["new_test_regions"]) and len(aa) == 24, "Description needs fixed24-region support")
        overall = paired_region_summary(aa,bb,repetitions=repetitions,seed=seed)
        sources = []
        for source in source_ids:
            left = [f for f in groups[a] if f["identity"]["source_split"] == source]
            right = [f for f in groups[b] if f["identity"]["source_split"] == source]
            require(len(left) == len(right) == 3, "Source description requires3 paired seeds")
            sources.append({"source_split":source, **paired_region_summary(average_regional(left,"union_class_miou"),
                average_regional(right,"union_class_miou"), repetitions=repetitions,seed=seed)})
        contrasts.append({"a":a,"b":b,"role":"descriptive_secondary_execution_replication", "overall24":overall,"by_source":sources})
    return {"format":"v2-cuda90-descriptive-1", "created_utc":datetime.now(timezone.utc).isoformat(),
        "scope":"DESCRIPTIVE_SECONDARY_EXECUTION_REPLICATION", "expected_count":90,"validated_count":90,
        "audit_sha256":audit_sha,"result_files":audit["result_files"],"inputs":audit["inputs"],"code_sha256":audit["code_sha256"],
        "original_primary_unchanged":True,"new_independent_holdout":False,"metric":"union_class_miou",
        "averaging":"Within each region average3 source allocations by3 paired fit seeds before overall paired differences; source strata average3 paired seeds first.",
        "geographic_units":24,"bootstrap_repetitions":repetitions,"bootstrap_seed":seed,"contrasts":contrasts,
        "interpretation":"All four contrasts and source intervals are descriptive after prior panel use. No p-value search, new confirmatory claim, equivalence margin or acceptance decision."}


def write_report(root, relative, value):
    path = safe(root, relative); payload = scheduler.raw(value)
    require(scheduler.logical_bytes(root)+len(payload)+4_000_000 < scheduler.CAP, "Whole-root2GB report reserve unavailable")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+".tmp."+uuid.uuid4().hex)
    with temp.open("xb") as stream: stream.write(payload)
    temp.replace(path)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--audit-only",action="store_true")
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args(argv)
    if args.self_test:
        import unittest, test_v2_audit_cuda
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_v2_audit_cuda))
        return 0 if result.wasSuccessful() else 1
    report,results=audit_cuda(args.root)
    write_report(args.root,AUDIT,report)
    if not report["passed"]:
        print(json.dumps({"passed":False,"errors":report["errors"],"missing":len(report["missing"]),"observed_count":report["observed_count"]}));return 1
    if not args.audit_only:
        value=descriptive_analysis(results,read(safe(args.root,"configs/v2_design.json")),report,sha(safe(args.root,AUDIT)))
        write_report(args.root,ANALYSIS,value)
    print(json.dumps({"passed":True,"validated_count":90,"analysis_written":not args.audit_only}));return 0


if __name__=="__main__":
    raise SystemExit(main())

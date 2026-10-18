"""Audit the exact locked 576-fit matrix without feature arrays or model loading.

Default execution reads completed evidence. --self-test uses in-memory synthetic
objects only, and neither reads panel results nor creates scientific run files.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import unittest

import numpy as np
from core import aggregate, candidate_pool

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("model", "source_split", "pool", "budget", "selection_seed",
        "initialization_seed", "strategy")
EXECUTION_FILES = ("v2_run.py", "v2_segmentation.py", "v2_selection.py", "v2_weighted_selection.py", "core.py", "gpu_head.py")
SPECS = ("full_model", "frozen_control")
COUNT_KEYS = ("processed_mask_class_counts_raw_0_to_8", "processed_class_counts_raw_0_to_8")
ADDITIONAL_STRATEGIES = ("region_weighted_facility_location", "permuted_region_weighted_facility_location")


def select_images(*args, **kwargs):
    # All real selection, including the original eight, uses the frozen wrapper.
    # Lazy import lets synthetic audit tests run before that worker finishes.
    from v2_weighted_selection import select_images as dispatch
    return dispatch(*args, **kwargs)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def safe_path(root, name):
    require(isinstance(name, str) and name and "\\" not in name and ":" not in name,
            "Expected relative POSIX evidence path")
    part = Path(name)
    require(not part.is_absolute() and ".." not in part.parts, "Unsafe evidence path")
    path = (Path(root) / part).resolve()
    require(path.is_relative_to(Path(root).resolve()), "Evidence path escapes root")
    return path


def valid_sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def run_key(identity):
    values = tuple(identity[key] for key in KEYS)
    require(all(isinstance(identity[k], int) and not isinstance(identity[k], bool)
                for k in ("budget", "selection_seed", "initialization_seed")), "Noninteger run identity")
    require(all(isinstance(identity[k], str) and identity[k] for k in
                ("model", "source_split", "pool", "strategy")), "Invalid string run identity")
    return values


def paired_fit_matrix(matrix, extension):
    """Apply the prospective pairing to identities, without a Cartesian expansion.

    The unamended matrix remains useful for historical synthetic checks. This
    transformation also supplies a like-for-like base reference in statistics
    tests before the weighted-FL rows are added.
    """
    mapping = extension.get("initialization_seed_by_selection_seed")
    require(extension.get("randomization_amendment_before_new_panel_scores") is True and
            isinstance(mapping, dict) and set(mapping) == {"0", "1", "2"} and
            all(type(value) is int for value in mapping.values()) and
            mapping == {"0": 0, "1": 1, "2": 2},
            "Prospective amendment must pair selection0/1/2 with initialization0/1/2")
    paired = {}
    for identity in matrix.values():
        selection = identity["selection_seed"]
        require(str(selection) in mapping, "Selection seed absent from paired-fit mapping")
        amended = {**identity, "initialization_seed": mapping[str(selection)]}
        key = run_key(amended)
        require(key not in paired, "Paired-fit mapping collapses duplicate identities")
        paired[key] = amended
    require(len(paired) == len(matrix), "Paired-fit amendment changed the fit count")
    return paired


def expected_matrix(design, extension=None):
    expected = {}
    for spec_name in SPECS:
        spec = design[spec_name]
        for split, pool, budget, selection, init, strategy in itertools.product(
                design["source_splits"], spec["pools"], spec["budgets"],
                design["selection_seeds"], spec["initialization_seeds"], design["strategies"]):
            identity = dict(zip(KEYS, (spec["name"], split["id"], pool, budget, selection, init, strategy)))
            key = run_key(identity)
            require(key not in expected, "Design contains duplicate Cartesian conditions")
            expected[key] = identity
    if extension is None:
        return expected
    require(extension.get("status") == "PROSPECTIVE_SUPPLEMENT_BEFORE_NEW_PANEL_EVALUATION",
            "Extension must be a prospective pre-evaluation supplement")
    require(extension.get("additional_strategies") == list(ADDITIONAL_STRATEGIES) and
            extension.get("pools") == ["skewed5_1"], "Extension strategies/pools differ from locked supplement")
    require(all(strategy not in design["strategies"] for strategy in ADDITIONAL_STRATEGIES),
            "Extension strategy duplicates an original strategy")
    require(len(expected) == 504 and Counter(key[0] for key in expected) == {
        design["full_model"]["name"]: 72, design["frozen_control"]["name"]: 432},
        "Original design must remain full72 + frozen432")
    additional = Counter()
    for spec_name in SPECS:
        spec = design[spec_name]
        require(set(extension["pools"]) <= set(spec["pools"]), "Extension pool is absent from original model specification")
        for split, pool, budget, selection, init, strategy in itertools.product(
                design["source_splits"], extension["pools"], spec["budgets"],
                design["selection_seeds"], spec["initialization_seeds"], extension["additional_strategies"]):
            identity = dict(zip(KEYS, (spec["name"], split["id"], pool, budget, selection, init, strategy)))
            key = run_key(identity)
            require(key not in expected, "Extension contains duplicate Cartesian conditions")
            expected[key] = identity
            additional[spec_name] += 1
    require(additional == {"full_model": 18, "frozen_control": 54} and
            extension.get("expected_additional_full_runs") == 18 and
            extension.get("expected_additional_frozen_runs") == 54 and
            extension.get("expected_additional_total_runs") == 72 and
            extension.get("expected_total_runs") == len(expected) == 576,
            "Extension must add full18 + frozen54 =72, total576")
    return paired_fit_matrix(expected, extension)


def validate_cm(value):
    """Reject floating, boolean, ragged, negative, overflowing or empty CMs."""
    require(isinstance(value, list) and len(value) == 8 and
            all(isinstance(row, list) and len(row) == 8 for row in value), "CM must be 8x8")
    flat = [v for row in value for v in row]
    require(all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 448 * 448
                for v in flat), "CM entries must be bounded nonnegative integers")
    require(0 < sum(flat) <= 448 * 448, "CM valid pixels must be in 1..448^2")
    return np.asarray(value, dtype=np.int64)


def complete_aggregate(entries):
    result = aggregate(entries)
    values = [v["union_class_miou"] for v in result["regions"].values()]
    require(all(v is not None and math.isfinite(v) for v in values), "Undefined regional union mIoU")
    result["equal_region_union_miou"] = float(np.mean(values))
    return result


def assert_same(actual, expected, scope="value"):
    """Schema-exact recursive comparison with tight float serialization tolerance."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), scope + ": keys differ")
        for key, value in expected.items():
            assert_same(actual[key], value, scope + "." + str(key))
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), scope + ": length differs")
        for i, value in enumerate(expected):
            assert_same(actual[i], value, scope + f"[{i}]")
    elif isinstance(expected, float):
        require(isinstance(actual, (int, float)) and not isinstance(actual, bool) and
                math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
                scope + ": numeric value differs")
    else:
        require(type(actual) is type(expected) and actual == expected, scope + ": value differs")


def validate_evaluation(evaluation, expected_records, truth_reference, processed_counts):
    entries = evaluation["images"]
    require(isinstance(entries, list) and len(entries) == len(expected_records), "Wrong evaluation image count")
    ids = [r["id"] for r in entries]
    require(len(set(ids)) == len(ids) and set(ids) == set(expected_records), "Missing/extra/duplicate evaluation ID")
    for entry in entries:
        identifier = entry["id"]
        require(entry["region"] == expected_records[identifier]["region"], "Evaluation ID/region mismatch")
        cm = validate_cm(entry["confusion"])
        rows = cm.sum(axis=1).tolist()
        if identifier in processed_counts:
            require(rows == processed_counts[identifier], "CM truth counts differ from processed mask counts")
        if identifier in truth_reference:
            require(rows == truth_reference[identifier], "Same image truth counts differ between fits")
        else:
            truth_reference[identifier] = rows
    computed = complete_aggregate(entries)
    assert_same(evaluation["aggregate"], computed, "aggregate")
    return computed


def validate_log(entries, steps):
    expected = sorted({1, steps, *range(50, steps + 1, 50)})
    require(isinstance(entries, list) and [r.get("step") for r in entries] == expected,
            "Training log must contain exactly step1, every50 and final step")
    elapsed = -1.0
    for entry in entries:
        require(isinstance(entry["step"], int) and not isinstance(entry["step"], bool), "Invalid logged step")
        for key in ("loss", "elapsed_seconds"):
            value = entry.get(key)
            require(isinstance(value, (float, int)) and not isinstance(value, bool) and
                    math.isfinite(value), "Nonfinite/missing training-log value")
        require(entry["elapsed_seconds"] >= elapsed and entry["elapsed_seconds"] >= 0,
                "Training-log time must be nonnegative and monotone")
        elapsed = entry["elapsed_seconds"]


def processed_truth_counts(record, metadata):
    """Use only explicitly processed counts; never substitute native TIFF counts."""
    containers = (record, record.get("label", {}), metadata,
                  metadata.get("outputs", {}).get("label", {}), metadata.get("source_label", {}))
    found = []
    for container in containers:
        for name in COUNT_KEYS:
            if name in container:
                counts = container[name]
                require(isinstance(counts, list) and len(counts) == 9 and all(
                    isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in counts)
                        and sum(counts) == 448 * 448, "Invalid processed raw0..8 counts")
                found.append(counts[1:])
    require(not found or all(x == found[0] for x in found), "Conflicting processed count metadata")
    return found[0] if found else None


def merge_processed_counts(processed, identifier, counts):
    """Merge actual processed-mask margins across independently bound metadata."""
    if counts is not None:
        require(identifier not in processed or processed[identifier] == counts,
                "Data audit/manifest/sidecar processed mask counts disagree: " + identifier)
        processed[identifier] = counts


def audited_processed_counts(data_audit, expected_records):
    """Read only SHA-bound data-audit histograms, never PNG pixels or scores."""
    pairs = data_audit["processed_png_availability"]["pairs"]
    require(isinstance(pairs, list) and len(pairs) == len(expected_records),
            "Data audit must cover every manifest image exactly once")
    identifiers = [pair["id"] for pair in pairs]
    require(len(set(identifiers)) == len(identifiers) and set(identifiers) == set(expected_records),
            "Data audit contains duplicate/missing/extra image IDs")
    processed = {}
    for pair in pairs:
        record = expected_records[pair["id"]]
        require(pair["region"] == record["region"], "Data audit histogram ID/region mismatch")
        counts = processed_truth_counts(pair, {})
        if counts is not None:
            require(pair.get("usable") is True and pair["label"].get("sha256_verified") is True and
                    pair["label"]["relative_path"] == record["label"]["relative_path"],
                    "Processed histogram lacks matching audited mask SHA evidence")
            merge_processed_counts(processed, pair["id"], counts)
    return processed


def audit_runs(root=ROOT):
    root = Path(root).resolve()
    report = dict(format="v2-run-completeness-1", created_utc=datetime.now(timezone.utc).isoformat(),
                  passed=False, expected_total=576, errors=[], missing=[], extra=[], duplicates=[],
                  inputs={}, artifacts={}, results={}, runs=[],
                  audit_code_sha256=sha_file(__file__), feature_arrays_read=False,
                  raster_pixels_read=False, model_checkpoints_deserialized=False)
    errors = report["errors"]

    def bind(relative, category="inputs", expected=None):
        path = safe_path(root, relative)
        checksum = sha_file(path)
        if expected is not None:
            require(valid_sha(expected) and checksum == expected, "SHA mismatch: " + relative)
        report[category][relative] = checksum
        return path

    try:
        design = read_json(bind("configs/v2_design.json"))
        extension = read_json(bind("configs/v2_extension.json"))
        require(extension.get("base_design") == "configs/v2_design.json" and
                extension.get("base_design_sha256") == report["inputs"]["configs/v2_design.json"] and
                extension.get("base_design_unchanged") is True and extension.get("primary_unchanged") is True and
                extension.get("no_new_panel_scores_at_amendment") is True,
                "Supplement must bind the unchanged base design/primary before new-panel scoring")
        expected = expected_matrix(design, extension)
        totals = Counter(k[0] for k in expected)
        require(totals == {design["full_model"]["name"]: 90, design["frozen_control"]["name"]: 486}
                and len(expected) == 576, "Design and supplement must contain exactly full90 + frozen486 unique fits")
        report["expected_by_model"] = dict(totals)
        report["matrix_components"] = {"original": {"full": 72, "frozen": 432, "total": 504},
                                       "prospective_extension": {"full": 18, "frozen": 54, "total": 72}}
        report["randomization"] = {
            "policy": "Three paired fit seeds, not crossed selection/initialization factors",
            "initialization_seed_by_selection_seed": extension["initialization_seed_by_selection_seed"],
            "amended_before_new_panel_scores": extension["randomization_amendment_before_new_panel_scores"],
            "calibration_initialization_seed": 0}
        freeze_path = bind("configs/v2_freeze.json")
        freeze = read_json(freeze_path)
        freeze_sha = report["inputs"]["configs/v2_freeze.json"]
        require(freeze["status"] == "FROZEN_BEFORE_NEW_PANEL_EVALUATION", "Missing completed pre-evaluation freeze")
        require(freeze["expected_full_runs"] == 90 and freeze["expected_frozen_runs"] == 486,
                "Freeze expected counts differ from full90/frozen486")
        frozen_files = freeze["file_sha256"]
        required = {"configs/v2_design.json", "configs/v2_extension.json", "configs/v2_geographic_sensitivity.json",
                    "v2/data/manifest.json", "v2/data/development_manifest.json",
                    "evidence/v2/data_audit.json", "evidence/v2/calibration/calibration.json",
                    "cache/dinov2-formal120/index.json", "v2/cache/new_panel_dinov2/index.json",
                    *("code/" + name for name in EXECUTION_FILES)}
        require(required <= set(frozen_files), "Freeze misses required source/design/execution bindings")
        for relative, checksum in frozen_files.items():
            bind(relative, expected=checksum)
        geographic = read_json(root / "configs/v2_geographic_sensitivity.json")
        require(geographic.get("exclude_entire_regions") == ["monrovia"] and
                geographic.get("primary_unchanged") is True and
                geographic.get("purpose") == "descriptive_geographic_metadata_sensitivity" and
                geographic.get("repetitions") == 10000 and geographic.get("bootstrap_seed") == 2026101805,
                "Geographic sensitivity must retain the primary and prospectively exclude Monrovia only")
        execution = {name: frozen_files["code/" + name] for name in EXECUTION_FILES}
        manifest = read_json(root / "v2/data/manifest.json")
        require(manifest.get("status") == "complete" and manifest.get("whole_v2_dataset_complete") is True,
                "Manifest not complete")
        all_records = manifest["pairs"]
        require(len(all_records) == len({r["id"] for r in all_records}) == 192, "Manifest must contain192 unique images")
        panel = {r["id"]: r for r in all_records if r["region"] in design["new_test_regions"]}
        development = {r["id"]: r for r in all_records if r["region"] in design["old_development_regions"]}
        require(len(panel) == 72 and len(development) == 120 and not set(panel) & set(development), "Wrong panel/development partition")
        require(Counter(r["region"] for r in panel.values()) == {r: 3 for r in design["new_test_regions"]}
                and len(design["new_test_regions"]) == len(set(design["new_test_regions"])) == 24,
                "Panel must be fixed24 regions x3")
        data_audit = read_json(root / "evidence/v2/data_audit.json")
        require(data_audit.get("passed") is True and data_audit.get("processed_pngs_usable") is True,
                "A passed data integrity audit is required")
        require(data_audit.get("audit_code_sha256") == sha_file(root / "code/v2_audit_data.py"), "Stale data audit code")
        require(data_audit.get("geography_helper_sha256") == sha_file(root / "code/geography_audit.py"),
                "Stale data audit geography helper")
        for info in data_audit["inputs"].values():
            bind(info["path"], expected=info["sha256"])
        # SHA-bound sidecars/PNG bytes are checked without decoding masks. Native
        # original counts are deliberately never used as processed-pixel counts.
        processed = audited_processed_counts(data_audit, {r["id"]: r for r in all_records})
        data_audit_histogram_images = len(processed)
        for record in all_records:
            for kind in ("metadata", "rgb", "label"):
                info = record[kind]
                path = bind("v2/data/" + info["relative_path"], "artifacts", info["sha256"])
                require(path.stat().st_size == info["bytes"], "Processed artifact byte count mismatch")
                if kind == "metadata":
                    metadata = read_json(path)
            require(metadata["id"] == record["id"] and metadata["region"] == record["region"], "Sidecar identity differs")
            counts = processed_truth_counts(record, metadata)
            merge_processed_counts(processed, record["id"], counts)
        index = read_json(root / "cache/dinov2-formal120/index.json")
        records = index["records"]
        require(index.get("status") == "complete" and len(records) == 120 and
                {r["id"] for r in records} == set(development), "Old descriptor index must match development120")
        for record in records:
            pair = development[record["id"]]
            require(record["region"] == pair["region"] and
                    record["source_rgb_sha256"] == pair["source_rgb"]["sha256"] and
                    record["source_label_sha256"] == pair["source_label"]["sha256"], "Descriptor source identity differs")
        target_index = read_json(root / "v2/cache/new_panel_dinov2/index.json")
        require(target_index.get("status") == "complete" and len(target_index["records"]) == 72 and
                {r["id"] for r in target_index["records"]} == set(panel), "Panel feature metadata must cover exact72")
        for record in target_index["records"]:
            require(record["region"] == panel[record["id"]]["region"] and
                    record["processed_rgb_sha256"] == panel[record["id"]]["rgb"]["sha256"], "Panel feature provenance differs")
        calibration = read_json(root / "evidence/v2/calibration/calibration.json")
        require(calibration.get("complete") is True and len(calibration["splits"]) == 3,
                "Incomplete source-only calibration")
        require(calibration["design_sha256"] == report["inputs"]["configs/v2_design.json"] and
                calibration["development_manifest_sha256"] == frozen_files["v2/data/development_manifest.json"],
                "Calibration input binding differs")
        for name, checksum in calibration["execution_code_sha256"].items():
            require(frozen_files.get("code/" + name) == checksum, "Calibration code binding differs")
        recipes = {}
        for entry in calibration["splits"]:
            settings = entry["settings"]
            spec = design["full_model"]
            require(len(settings) == 6 and {(v["encoder_lr"], v["steps"]) for v in settings} == set(
                itertools.product(spec["calibration_encoder_lrs"], spec["calibration_checkpoints"])), "Calibration settings differ")
            for setting in settings:
                require(setting["record"] in frozen_files, "Calibration record is not frozen")
                require(math.isfinite(setting["validation_union_miou"]), "Nonfinite calibration score")
            chosen = sorted(settings, key=lambda v: (-v["validation_union_miou"], v["steps"], v["encoder_lr"]))[0]
            assert_same(entry["chosen"], chosen, "calibration chosen recipe")
            require(entry["source_split"] not in recipes, "Duplicate calibration split")
            recipes[entry["source_split"]] = chosen
        split_map = {s["id"]: s for s in design["source_splits"]}
        require(set(recipes) == set(split_map), "Calibration/source allocation mismatch")
    except Exception as exc:
        errors.append({"scope": "prerequisites", "error": f"{type(exc).__name__}: {exc}"})
        if "expected" in locals():
            # A blocked prerequisite does not constitute an inventory audit.
            # Preserve the planned identities without claiming files are missing.
            report["planned_identities_not_yet_audited"] = list(expected.values())
        return report

    paths = sorted((root / "evidence/v2/runs").rglob("result.json"))
    seen, truth_reference, selection_cache, checkpoint_paths = {}, {}, {}, []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            result = read_json(path)
            report["results"][relative] = sha_file(path)
            identity = result["identity"]
            key = run_key(identity)
            if key in seen:
                report["duplicates"].append({"identity": dict(zip(KEYS, key)), "paths": [seen[key], relative]})
            else:
                seen[key] = relative
            if key not in expected:
                report["extra"].append({"path": relative, "identity": dict(zip(KEYS, key))})
                raise ValueError("Unplanned run condition")
            require(result.get("status") == "complete", "Run is not complete")
            require(identity["freeze_sha256"] == freeze_sha and identity["execution_code_sha256"] == execution,
                    "Run freeze/execution code identity differs")
            require(set(identity) == set(KEYS) | {"freeze_sha256", "execution_code_sha256"}, "Unexpected identity schema")
            require(path.parent.parent.name == identity["model"], "Result stored under wrong model directory")
            split = split_map[identity["source_split"]]
            cache_key = (identity["source_split"], identity["pool"], identity["budget"], identity["strategy"], identity["selection_seed"])
            if cache_key not in selection_cache:
                pool = candidate_pool(records, split["train"], identity["pool"], split["candidate_seed"])
                ids = [r["id"] for r in pool]
                descriptors = np.asarray([r["descriptor"] for r in pool], dtype=np.float64)
                selected = select_images(ids, descriptors, [r["region"] for r in pool],
                                         identity["budget"], identity["strategy"], identity["selection_seed"])
                by_id = {r["id"]: r for r in pool}
                chosen = [by_id[k] for k in selected]
                xx = descriptors / np.maximum(np.linalg.norm(descriptors, axis=1, keepdims=True), 1e-12)
                distance = np.maximum(0, 1 - xx @ xx[[ids.index(k) for k in selected]].T).min(axis=1)
                regions = np.asarray([record["region"] for record in pool])
                regional_distance = {name: float(distance[regions == name].mean()) for name in sorted(set(regions))}
                selection_cache[cache_key] = dict(candidate_ids=ids, selected_ids=selected,
                    selected_regions=sorted({r["region"] for r in chosen}),
                    mean_candidate_cosine_distance=float(distance.mean()), maximum_candidate_cosine_distance=float(distance.max()),
                    equal_region_mean_candidate_cosine_distance=float(np.mean(list(regional_distance.values()))),
                    candidate_region_mean_cosine_distances=regional_distance,
                    selected_region_counts={name: sum(record["region"] == name for record in chosen) for name in sorted(set(regions))},
                    selected_valid_original_pixels=sum(r["original_valid_pixels"] for r in chosen),
                    selected_original_class_counts=np.asarray([r["original_class_counts"] for r in chosen]).sum(0).tolist())
            selection = result["selection"]
            for name, value in selection_cache[cache_key].items():
                assert_same(selection[name], value, "selection." + name)
            require(math.isfinite(selection["selection_seconds"]) and selection["selection_seconds"] >= 0, "Invalid selection time")
            validate_evaluation(result["test"], panel, truth_reference, processed)
            training = result["training"]
            full = identity["model"] == design["full_model"]["name"]
            if full:
                recipe = recipes[identity["source_split"]]
                require(training["steps"] == recipe["steps"] and training["encoder_lr"] == recipe["encoder_lr"] and
                        training["decoder_lr"] == 10 * recipe["encoder_lr"], "Full training recipe differs from calibration")
                require(training["batch_size"] == design["full_model"]["batch_size"] and
                        training["crop"] == design["full_model"]["crop"], "Full fit shape recipe differs")
                train_identity = training["identity"]
                require(train_identity["selected_ids"] == selection["selected_ids"], "Training selected IDs differ")
                require(valid_sha(train_identity["initial_model_state_sha256"]) and
                        valid_sha(training["final_model_state_sha256"]), "Missing full-model state identities")
                selected_records = [development[k] for k in selection["selected_ids"]]
                record_sha = hashlib.sha256(json.dumps(selected_records, sort_keys=True).encode()).hexdigest()
                require(train_identity["selected_record_sha256"] == record_sha and
                        train_identity["model_code_sha256"] == execution["v2_segmentation.py"], "Training identity differs")
                validation_records = {k: r for k, r in development.items() if r["region"] in split["validation"]}
                validate_evaluation(result["validation"], validation_records, truth_reference, processed)
            else:
                require(training["steps"] == 600 == design["frozen_control"]["steps"] and
                        training["learning_rate"] == .001 == design["frozen_control"]["learning_rate"], "Frozen recipe must be600/.001")
                require(result["validation"] is None, "Frozen fits must not score validation")
            require(training["seed"] == identity["initialization_seed"], "Initialization seed differs")
            validate_log(training["log"], training["steps"])
            log_path = bind(result["log_file"], "artifacts", result["log_sha256"])
            require(log_path.parent == path.parent, "Run log must be inside its run folder")
            logged = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert_same(logged, training["log"], "External/embedded training logs")
            predetermined = full and (identity["source_split"], identity["selection_seed"],
                identity["initialization_seed"], identity["strategy"]) == ("source0", 0, 0, "region_kcenter")
            checkpoint = result["checkpoint"]
            require((checkpoint is not None) == predetermined, "Checkpoint retention violates predetermined policy")
            if checkpoint is not None:
                checkpoint_path = bind(checkpoint["path"], "artifacts", checkpoint["sha256"])
                require(checkpoint_path.parent == path.parent and valid_sha(checkpoint["state_sha256"]) and
                        checkpoint["state_sha256"] == training["final_model_state_sha256"],
                        "Checkpoint location/state identity invalid")
                checkpoint_paths.append(checkpoint_path)
            require(math.isfinite(result["total_seconds"]) and result["total_seconds"] >= 0, "Invalid fit elapsed time")
            report["runs"].append({"path": relative, "identity": dict(zip(KEYS, key)), "sha256": report["results"][relative]})
        except Exception as exc:
            errors.append({"scope": relative, "error": f"{type(exc).__name__}: {exc}"})
    report["missing"] = [expected[k] for k in expected if k not in seen]
    physical = {p.resolve() for pattern in ("*.pt", "*.pth", "*.ckpt")
                for p in (root / "evidence/v2/runs").rglob(pattern)}
    if len(checkpoint_paths) != 1 or physical != set(checkpoint_paths):
        errors.append({"scope": "checkpoints", "error": "Exactly one predetermined checkpoint file must exist; no unreported checkpoints"})
    report["observed_result_files"] = len(paths)
    report["validated_runs"] = len(report["runs"])
    report["processed_pixel_check"] = dict(processed_metadata_images=len(processed),
        data_audit_histogram_images=data_audit_histogram_images,
        cross_fit_truth_margin_images=len(truth_reference),
        fallback="If processed counts are absent, require identical per-class truth margins across all fits plus current passed data audit; absolute valid counts are not independently decoded.")
    report["panel_image_ids"] = sorted(panel)
    report["passed"] = (not errors and not report["missing"] and not report["extra"] and not report["duplicates"]
                        and len(paths) == len(seen) == len(report["runs"]) == len(expected) == 576)
    return report


class SyntheticAuditTests(unittest.TestCase):
    def test_extension_matrix_is_sparse_and_rejects_wrong_count_or_pool(self):
        design = {"source_splits": [{"id": f"s{i}"} for i in range(3)], "selection_seeds": [0, 1, 2],
                  "strategies": [f"policy{i}" for i in range(8)],
                  "full_model": {"name": "full", "pools": ["skewed5_1"], "budgets": [12], "initialization_seeds": [0]},
                  "frozen_control": {"name": "frozen", "pools": ["balanced3", "skewed5_1"], "budgets": [6, 12, 24], "initialization_seeds": [0]}}
        extension = {"status": "PROSPECTIVE_SUPPLEMENT_BEFORE_NEW_PANEL_EVALUATION",
                     "additional_strategies": list(ADDITIONAL_STRATEGIES), "pools": ["skewed5_1"],
                     "expected_additional_full_runs": 18, "expected_additional_frozen_runs": 54,
                     "expected_additional_total_runs": 72, "expected_total_runs": 576,
                     "initialization_seed_by_selection_seed": {"0": 0, "1": 1, "2": 2},
                     "randomization_amendment_before_new_panel_scores": True}
        historical = expected_matrix(design)
        self.assertEqual(len(historical), 504)
        self.assertTrue(all(identity["initialization_seed"] == 0 for identity in historical.values()))
        matrix = expected_matrix(design, extension)
        self.assertEqual(len(matrix), 576)
        self.assertEqual(len(set(matrix)), 576)
        self.assertTrue(all(identity["initialization_seed"] == identity["selection_seed"]
                            for identity in matrix.values()))
        self.assertEqual(Counter(identity["initialization_seed"] for identity in matrix.values()),
                         {0: 192, 1: 192, 2: 192})
        # An old initialization0 identity is not silently accepted for fit seed1/2.
        self.assertTrue(all(key not in matrix for key, identity in historical.items()
                            if identity["selection_seed"] in (1, 2)))
        self.assertEqual(Counter(key[0] for key in matrix), {"full": 90, "frozen": 486})
        self.assertEqual(sum(identity["strategy"] in ADDITIONAL_STRATEGIES for identity in matrix.values()), 72)
        self.assertTrue(all(identity["pool"] == "skewed5_1" for identity in matrix.values()
                            if identity["strategy"] in ADDITIONAL_STRATEGIES))
        for key, value in (("pools", ["balanced3"]), ("expected_total_runs", 504),
                           ("additional_strategies", list(ADDITIONAL_STRATEGIES)[::-1]),
                           ("randomization_amendment_before_new_panel_scores", False),
                           ("initialization_seed_by_selection_seed", {"0": 0, "1": 0, "2": 0}),
                           ("initialization_seed_by_selection_seed", {"0": False, "1": 1, "2": 2}),
                           ("initialization_seed_by_selection_seed", {"0": 0, "1": 1})):
            with self.subTest(key=key), self.assertRaises(ValueError):
                expected_matrix(design, {**extension, key: value})

    def test_actual_processed_histogram_and_same_total_wrong_classes(self):
        counts = [448 * 448 - 10, 10] + [0] * 7
        record = {"id": "synthetic", "region": "r", "label": {"relative_path": "mask.png"}}
        pair = {"id": "synthetic", "region": "r", "usable": True,
                "label": {"relative_path": "mask.png", "sha256_verified": True},
                COUNT_KEYS[0]: counts}
        data_audit = {"processed_png_availability": {"pairs": [pair]}}
        processed = audited_processed_counts(data_audit, {"synthetic": record})
        self.assertEqual(processed["synthetic"], [10] + [0] * 7)
        # Total valid pixels remain10, but one true class0 pixel has been moved
        # to true class1. Recompute aggregate to isolate the histogram check.
        cm = np.zeros((8, 8), dtype=int); cm[0, 0] = 9; cm[1, 1] = 1
        entries = [dict(id="synthetic", region="r", confusion=cm.tolist())]
        evaluation = dict(images=entries, aggregate=complete_aggregate(entries))
        self.assertEqual(int(cm.sum()), sum(processed["synthetic"]))
        with self.assertRaisesRegex(ValueError, "processed mask counts"):
            validate_evaluation(evaluation, {"synthetic": record}, {}, processed)
        for malformed in (counts[:-1], [0] * 9, [True, 448 * 448 - 1] + [0] * 7):
            bad = json.loads(json.dumps(data_audit))
            bad["processed_png_availability"]["pairs"][0][COUNT_KEYS[0]] = malformed
            with self.assertRaises(ValueError): audited_processed_counts(bad, {"synthetic": record})
        duplicate = {"processed_png_availability": {"pairs": [pair, pair]}}
        with self.assertRaises(ValueError):
            audited_processed_counts(duplicate, {"synthetic": record, "other": record})
        # A later sidecar/manifest count must agree with the actual-mask audit.
        with self.assertRaisesRegex(ValueError, "disagree"):
            merge_processed_counts(processed, "synthetic", [9, 1] + [0] * 6)
        missing = json.loads(json.dumps(data_audit))
        del missing["processed_png_availability"]["pairs"][0][COUNT_KEYS[0]]
        self.assertEqual(audited_processed_counts(missing, {"synthetic": record}), {})

    def test_cm_rejections(self):
        good = np.zeros((8, 8), dtype=int).tolist(); good[0][0] = 10
        self.assertEqual(int(validate_cm(good).sum()), 10)
        for value in ([[1] * 8] * 7, [[0] * 8] * 8,
                      [[-1] + [0] * 7] + [[0] * 8] * 7,
                      [[1.0] + [0] * 7] + [[0] * 8] * 7,
                      [[True] + [0] * 7] + [[0] * 8] * 7):
            with self.assertRaises(ValueError): validate_cm(value)

    def test_evaluation_failure_paths_and_counts(self):
        cm = np.zeros((8, 8), dtype=int); cm[0, 0] = 8; cm[0, 1] = 2
        entries = [dict(id="synthetic", region="r", confusion=cm.tolist())]
        evaluation = dict(images=entries, aggregate=complete_aggregate(entries))
        expected = {"synthetic": {"region": "r"}}
        reference = {}
        validate_evaluation(evaluation, expected, reference, {"synthetic": [10] + [0] * 7})
        for mutation in ("region", "duplicate", "aggregate", "truth"):
            bad = json.loads(json.dumps(evaluation))
            if mutation == "region": bad["images"][0]["region"] = "other"
            if mutation == "duplicate": bad["images"].append(bad["images"][0])
            if mutation == "aggregate": bad["aggregate"]["equal_region_union_miou"] = 0.
            if mutation == "truth": bad["images"][0]["confusion"][0][0] += 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_evaluation(bad, expected, reference, {})

    def test_logs_and_processed_scope(self):
        logs = [dict(step=s, loss=.5, elapsed_seconds=float(i))
                for i, s in enumerate([1, 50, 100])]
        validate_log(logs, 100)
        for bad in (logs[:-1], [logs[1], logs[0], logs[2]],
                    [dict(step=1, loss=float("nan"), elapsed_seconds=0), *logs[1:]]):
            with self.assertRaises(ValueError): validate_log(bad, 100)
        self.assertIsNone(processed_truth_counts({}, {"source_label": {
            "original_mask_class_counts_raw_0_to_8": [1] * 9}}))
        counts = [0, 448 * 448] + [0] * 7
        self.assertEqual(processed_truth_counts({}, {COUNT_KEYS[0]: counts}), counts[1:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticAuditTests))
        return 0 if result.wasSuccessful() else 1
    report = audit_runs(args.root)
    write_json(args.root / "evidence/v2/run_completeness.json", report)
    print(json.dumps({k: report.get(k) for k in ("passed", "validated_runs", "observed_result_files")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

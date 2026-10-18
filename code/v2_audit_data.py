"""Audit the complete fixed v2 compact dataset without downloading or training.

The only raster reads are compact PNG integrity checks. Geography and native
RGB duplicate screening use SHA-bound provenance sidecars, never native masks
or model results. --self-test runs only synthetic, in-memory checks.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
import unittest

import numpy as np
from PIL import Image
import geography_audit as geography


ROOT = Path(__file__).resolve().parents[1]
NEW_REGIONS = (
    "abancay", "al_qurnah", "baybay", "bielefeld", "buenos_aires", "chiclayo",
    "coxsbazar", "dowa", "kagera", "kampala", "khartoum", "kinshasa", "kitsap",
    "monrovia", "ngaoundere", "paris", "rosario", "san_tome", "soriano", "svaneti",
    "tokyo", "tyrolw", "western", "zanzibar",
)
SOURCE_KEYS = ("member", "sha256", "bytes", "zip_crc32")
LIMITATIONS = [
    "Geography is read only from SHA-bound preparation sidecars; native TIFFs are not reopened or transformed by this audit.",
    "Supported coverage requires a declared successful offline transform and every sampled boundary point within the declared CRS and operation area of use.",
    "Padded bounding boxes screen sampled boundaries conservatively; they are not analytic footprint or surveyed coordinate-error guarantees.",
    "CRS cautions and unknown geographies are excluded from supported separation checks and reported explicitly; caution boundaries are screened separately when available.",
    "No candidate overlap and no exact decoded-RGB duplicate establish only the stated evidence coverage, not independence of full source mosaics or absence of all leakage.",
    "Candidate overlaps and exact decoded-RGB matches require human review; this tool never deletes or substitutes samples.",
    "Original raw TIFF files and deleted feature arrays are not rehashed here; their source hashes are cross-bound through the original manifest, DINO index and preparation provenance.",
]


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def relative(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name


def safe_path(base, name):
    if not isinstance(name, str) or "\\" in name:
        raise ValueError("Expected a relative POSIX output path")
    item = Path(name)
    if item.is_absolute() or ".." in item.parts or ":" in name or not item.parts:
        raise ValueError("Unsafe output path")
    result = (base / item).resolve()
    if not result.is_relative_to(base.resolve()):
        raise ValueError("Output path escapes manifest directory")
    return result


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def source_reduced(source):
    return {key: source[key] for key in SOURCE_KEYS}


def original_pair_id(record):
    """Legacy downloader pairs omit id; derive it with structural checks.

    Only the original-manifest indexing path calls this. V2, plan, development
    and DINO records still require explicit IDs and source identity checks.
    """
    region = record["region"]
    require(isinstance(region, str) and re.fullmatch(r"[a-z0-9_]+", region) is not None,
            "Invalid original region identifier")
    members = []
    for kind in ("rgb", "label"):
        source = record[kind]
        name = source["member"]
        require(isinstance(name, str) and "\\" not in name and ":" not in name,
                "Invalid original member path")
        member = PurePosixPath(name)
        require(not member.is_absolute() and ".." not in member.parts and len(member.parts) >= 4,
                "Unsafe original member path")
        require(member.suffix.lower() in (".tif", ".tiff"), "Original member is not a TIFF")
        require(source.get("relative_path", name) == name, "Original local/member paths differ")
        members.append(member)
    rgb, label = members
    require(rgb.parent.name == "images" and label.parent.name == "labels" and
            rgb.parent.parent == label.parent.parent and rgb.parent.parent.name == region and
            rgb.name == label.name, "Original RGB/label region, directory or filename differs")
    identifier = region + "__" + rgb.stem
    require("id" not in record or record["id"] == identifier, "Original explicit ID differs from stable member-derived ID")
    return identifier


def indexed(records, name, legacy_original=False):
    mapping = {}
    for record in records:
        identifier = original_pair_id(record) if legacy_original else record["id"]
        require(identifier not in mapping, f"Duplicate ID in {name}: {identifier}")
        mapping[identifier] = record
    return mapping


def validate_partition(records, old_regions, new_regions):
    """Only IDs/regions/roles enter this check, never semantic counts."""
    errors = []
    if len(old_regions) != 24 or len(set(old_regions)) != 24:
        errors.append("Development region list must contain 24 unique regions")
    if set(new_regions) != set(NEW_REGIONS) or len(new_regions) != 24:
        errors.append("Permanent panel must contain its fixed 24 unique regions")
    if set(old_regions) & set(new_regions):
        errors.append("Development and permanent-panel region sets overlap")
    counts = Counter((record.get("role"), record.get("region")) for record in records)
    expected = {("old_development", region): 5 for region in old_regions}
    expected.update({("new_panel", region): 3 for region in new_regions})
    if dict(counts) != expected:
        errors.append("Exact per-region role counts differ from old24x5/new24x3")
    if len(records) != 192 or len({record.get("id") for record in records}) != 192:
        errors.append("Manifest must contain exactly 192 unique IDs")
    return errors


def validate_splits(design, old_regions):
    errors = []
    splits = design.get("source_splits", [])
    if len(splits) != 3 or len({item.get("id") for item in splits}) != 3:
        errors.append("Design must contain three uniquely named source allocations")
    for split in splits:
        groups = [split.get(key, []) for key in ("train", "validation", "unused_development")]
        if [len(group) for group in groups] != [12, 4, 8]:
            errors.append(f"{split.get('id')}: source allocation sizes must be 12/4/8")
        flattened = sum(groups, [])
        if len(flattened) != 24 or len(set(flattened)) != 24 or set(flattened) != set(old_regions):
            errors.append(f"{split.get('id')}: source allocation is not a disjoint partition of the old24")
    return errors


def geometry_record(record, metadata, base_padding):
    source = metadata["source_rgb"]
    geo = source.get("geography", {})
    result = {"id": record["id"], "region": record["region"], "role": record["role"],
              "metadata": record["metadata"]["relative_path"], "geographic_status": geo.get("status", "unknown"),
              "supported_for_separation_screen": False, "epsg": geo.get("epsg"),
              "original_dimensions": source.get("original_dimensions"),
              "original_decoded_rgb_sha256": source.get("original_decoded_rgb_sha256"),
              "warning": geo.get("warning"), "coordinate_operation_accuracy_m": None}
    operation = geo.get("coordinate_operation", {})
    result["boundary_inside_declared_crs_and_operation_area"] = operation.get(
        "all_boundary_samples_in_source_crs_and_operation_area_of_use")
    points = geo.get("wgs84_boundary_lon_lat")
    if points is None:
        result["screen_exclusion_reason"] = "No transformed boundary samples in sidecar"
        return result
    try:
        require(isinstance(points, list) and len(points) >= 4, "Too few WGS84 boundary samples")
        require(all(isinstance(point, list) and len(point) == 2 and all(
            isinstance(value, (int, float)) and math.isfinite(value) for value in point) and
            -180 <= point[0] <= 180 and -90 <= point[1] <= 90 for point in points), "Invalid WGS84 samples")
        accuracy = operation.get("accuracy_m")
        if accuracy is not None:
            require(isinstance(accuracy, (int, float)) and math.isfinite(accuracy) and accuracy >= 0,
                    "Invalid reported coordinate-operation accuracy")
        padding = base_padding + (100.0 if accuracy is None else accuracy)
        box, dateline = geography.bbox(points, padding)
        raw, _ = geography.bbox(points)
        result.update(wgs84_sample_envelope=raw, wgs84_padded_candidate_bbox=box,
                      boundary_sample_count=len(points), candidate_bbox_padding_m=padding,
                      antimeridian_sample_span_detected=dateline, coordinate_operation_accuracy_m=accuracy)
        supported = (geo.get("status") == "supported_metadata_and_transform" and
                     operation.get("all_boundary_samples_in_source_crs_and_operation_area_of_use") is True and
                     geo.get("resized_world_footprint_matches_source") is True)
        result["supported_for_separation_screen"] = supported
        if not supported:
            result["screen_exclusion_reason"] = "CRS/operation caution or incomplete supported-transform evidence"
    except (TypeError, ValueError) as exc:
        result["screen_exclusion_reason"] = f"Unusable sidecar boundary: {exc}"
    return result


def bbox_comparisons(left, right, include_cautions=False):
    candidates, count = [], 0
    for first in left:
        for second in right:
            if "wgs84_padded_candidate_bbox" not in first or "wgs84_padded_candidate_bbox" not in second:
                continue
            supported = first["supported_for_separation_screen"] and second["supported_for_separation_screen"]
            if supported == include_cautions:
                continue
            count += 1
            if geography.intersects(first["wgs84_padded_candidate_bbox"], second["wgs84_padded_candidate_bbox"]):
                candidates.append({"left_id": first["id"], "right_id": second["id"],
                                   "left_bbox": first["wgs84_padded_candidate_bbox"],
                                   "right_bbox": second["wgs84_padded_candidate_bbox"],
                                   "evidence_scope": "supported" if supported else "contains_CRS_or_other_caution",
                                   "action": "human_review_required; retain both samples"})
    return {"compared_pairs": count, "candidate_count": len(candidates), "candidates": candidates}


def decoded_duplicates(records, across_roles=True):
    groups = defaultdict(list)
    missing = []
    for record in records:
        digest, dimensions = record.get("original_decoded_rgb_sha256"), record.get("original_dimensions")
        if not check_sha(digest) or not isinstance(dimensions, list) or len(dimensions) != 2:
            missing.append(record["id"])
            continue
        groups[(digest, tuple(dimensions))].append(record)
    duplicates = []
    for (digest, dimensions), members in groups.items():
        for position, left in enumerate(members):
            for right in members[position + 1:]:
                if across_roles and left["role"] == right["role"]:
                    continue
                duplicates.append({"left_id": left["id"], "right_id": right["id"],
                                   "original_decoded_rgb_sha256": digest, "original_dimensions": list(dimensions),
                                   "action": "human_review_required; retain both samples"})
    return {"candidate_count": len(duplicates), "candidates": duplicates,
            "missing_hash_or_dimensions": missing,
            "hash_definition": "Pillow-decoded original uint8 RGB bytes, row-major interleaved, grouped only with equal original dimensions"}


def processed_mask_counts(array):
    """Histogram of the actual decoded compact mask, including raw0 void.

    This is audit evidence for later per-image confusion-matrix truth margins;
    it never enters sample selection and does not inspect native-mask counts.
    """
    require(array.shape == (448, 448) and array.dtype == np.uint8 and bool(np.all(array <= 8)),
            "PNG mask must be 448-square uint8 raw IDs 0..8")
    counts = np.bincount(array.ravel(), minlength=9).astype(np.int64).tolist()
    require(len(counts) == 9 and sum(counts) == 448 * 448, "Processed-mask histogram accounting mismatch")
    return counts


def check_pair(record, manifest, base, claimed_paths):
    """Verify compact PNGs and preserve mask truth margins for the run audit."""
    require(record["role"] in ("old_development", "new_panel"), "Unexpected role")
    require(record["id"].startswith(record["region"] + "__"), "ID/region identity mismatch")
    info = record["metadata"]
    path = safe_path(base, info["relative_path"])
    require(path.is_file() and path.stat().st_size == info["bytes"], "Sidecar absent or byte size mismatch")
    require(check_sha(info["sha256"]) and sha_file(path) == info["sha256"], "Sidecar SHA256 mismatch")
    metadata = read_json(path)
    for key in ("id", "region", "role"):
        require(metadata[key] == record[key], f"Sidecar {key} differs from manifest")
    require(metadata["bindings"] == manifest["identity"]["bindings"], "Sidecar code/source bindings differ")
    require(metadata["runtime"] == manifest["identity"]["runtime"], "Sidecar runtime differs")
    require(metadata.get("original_tiff_persisted") is False, "Unexpected original persistence claim")
    total = path.stat().st_size
    availability = {"id": record["id"], "region": record["region"], "role": record["role"],
                    "sidecar_sha256_verified": True}
    for kind, source_key, mode in (("rgb", "source_rgb", "RGB"), ("label", "source_label", "L")):
        source = metadata[source_key]
        require(source_reduced(source) == record[source_key], f"{kind} source manifest/sidecar mismatch")
        require(check_sha(source["sha256"]) and isinstance(source["bytes"], int) and source["bytes"] > 0,
                f"Invalid {kind} original source identity")
        require(re.fullmatch(r"[0-9a-f]{8}", source["zip_crc32"]) is not None, "Invalid source CRC")
        require(source.get("size_crc32_sha256_verified_before_decode") is True, "Missing source verification attestation")
        require(metadata["outputs"][kind] == record[kind], f"{kind} PNG manifest/sidecar mismatch")
        output = record[kind]
        png_path = safe_path(base, output["relative_path"])
        require(png_path.suffix.lower() == ".png", "Expected PNG output")
        require(png_path not in claimed_paths, "Duplicate physical output path claimed by two records")
        claimed_paths.add(png_path)
        require(png_path.is_file() and png_path.stat().st_size == output["bytes"], f"{kind} PNG absent/size mismatch")
        require(check_sha(output["sha256"]) and sha_file(png_path) == output["sha256"], f"{kind} PNG SHA256 mismatch")
        with Image.open(png_path) as image:
            image.load()
            require(image.format == "PNG" and image.mode == mode and image.size == (448, 448),
                    f"{kind} PNG format/mode/dimensions invalid")
            if kind == "label":
                array = np.asarray(image)
                availability["processed_mask_class_counts_raw_0_to_8"] = processed_mask_counts(array)
        total += output["bytes"]
        availability[kind] = {"relative_path": output["relative_path"], "sha256_verified": True,
                              "bytes": output["bytes"], "dimensions": [448, 448], "mode": mode}
    require(total == record["compact_payload_bytes"] == metadata["compact_payload_bytes"] and total <= 900000,
            "Per-pair payload byte accounting/cap mismatch")
    dimensions = metadata["source_rgb"].get("original_dimensions")
    require(isinstance(dimensions, list) and len(dimensions) == 2 and all(
        isinstance(value, int) and value > 0 for value in dimensions), "Invalid original RGB dimensions")
    require(dimensions == metadata["source_label"].get("original_dimensions"), "Original RGB/mask dimensions differ")
    require(check_sha(metadata["source_rgb"].get("original_decoded_rgb_sha256")), "Missing original decoded RGB hash")
    availability["usable"] = True
    availability["mask_raw_ids_0_to_8_verified"] = True
    return metadata, availability


def audit(manifest_path, design_path, original_path, dino_path, development_path, plan_path, padding):
    report = {"format": "v2-data-audit-1", "created_utc": datetime.now(timezone.utc).isoformat(),
              "passed": False, "processed_pngs_usable": False, "integrity_errors": [],
              "inputs": {}, "audit_code_sha256": sha_file(Path(__file__)),
              "geography_helper_sha256": sha_file(Path(geography.__file__)),
              "original_semantic_class_count_fields_accessed_or_aggregated": False,
              "processed_mask_class_counts_computed_for_cm_truth_margin_validation": True,
              "native_tiff_or_new_network_reads": False, "model_results_read": False,
              "limitations": LIMITATIONS}
    errors = report["integrity_errors"]
    files = {"manifest": manifest_path, "design": design_path, "original_manifest": original_path,
             "original_dino_index": dino_path, "immutable_development_manifest": development_path,
             "selection_plan": plan_path}
    loaded = {}
    for name, path in files.items():
        try:
            loaded[name] = read_json(path)
            report["inputs"][name] = {"path": relative(path), "sha256": sha_file(path), "bytes": path.stat().st_size}
        except (OSError, ValueError) as exc:
            errors.append({"scope": name, "error": f"{type(exc).__name__}: {exc}"})
    if len(loaded) != len(files):
        return report
    manifest, design, original, dino, frozen, plan = [loaded[key] for key in files]
    records = manifest["pairs"]
    old_regions = sorted({pair["region"] for pair in original["pairs"]})
    new_regions = design.get("new_test_regions", [])
    global_checks = []
    def check(condition, message):
        global_checks.append({"check": message, "passed": bool(condition)})
        if not condition:
            errors.append({"scope": "global", "error": message})
    check(manifest.get("status") == "complete" and manifest.get("stage") == "all" and
          manifest.get("whole_v2_dataset_complete") is True, "Complete all-stage manifest is required")
    check(manifest.get("expected") == {"old_development": 120, "new_panel": 72, "total": 192}, "Exact expected pair matrix")
    for error in validate_partition(records, old_regions, new_regions) + validate_splits(design, old_regions):
        check(False, error)
    check(set(design.get("old_development_regions", [])) == set(old_regions), "Design old24 matches original formal manifest")
    check(design.get("new_images_per_region") == 3 and design.get("new_download_seed") == 2026101802,
          "Design permanent-panel count and download seed")
    check(manifest["selection"].get("new_regions") == list(NEW_REGIONS) and
          manifest["selection"].get("new_seed") == 2026101802 and
          manifest["selection"].get("image_or_label_content_read_for_selection") is False, "Fixed content-blind selection declaration")
    check(manifest["identity"]["selection_plan_sha256"] == report["inputs"]["selection_plan"]["sha256"], "Reviewed selection-plan SHA binding")
    check(plan.get("stage") == "all" and plan.get("expected") == manifest.get("expected"), "Reviewed all-stage plan matrix")
    check(plan.get("bindings") == manifest["identity"]["bindings"] and plan.get("runtime") == manifest["identity"]["runtime"],
          "Plan/manifest code and runtime identity")
    check(plan.get("selection") == manifest.get("selection") and plan.get("processing") == manifest.get("processing"),
          "Plan/manifest selection and processing declarations")
    checksums = manifest["identity"]["bindings"]
    check(checksums.get("original_development_manifest_sha256") == report["inputs"]["original_manifest"]["sha256"],
          "Original development manifest SHA binding")
    for key, name in (("conversion_code_sha256", "v2_prepare_data.py"),
                      ("data_access_code_sha256", "data_access.py"),
                      ("geography_audit_code_sha256", "geography_audit.py")):
        path = ROOT / "code" / name
        check(path.is_file() and sha_file(path) == checksums.get(key), f"Bound source file unchanged: {name}")
    try:
        pairs_by_id = indexed(records, "v2 manifest")
        plans = indexed(plan["pairs"], "selection plan")
        originals = indexed(original["pairs"], "original manifest", legacy_original=True)
        dino_records = indexed(dino["records"], "DINO index")
        frozen_records = indexed(frozen["pairs"], "development snapshot")
    except (KeyError, ValueError) as exc:
        errors.append({"scope": "identities", "error": str(exc)})
        return report
    old_records = {key: value for key, value in pairs_by_id.items() if value["role"] == "old_development"}
    check(original.get("status") == "complete" and len(originals) == 120, "Original source manifest complete120")
    check(dino.get("status") == "complete" and dino.get("source_manifest_sha256") == report["inputs"]["original_manifest"]["sha256"] and
          set(dino_records) == set(originals), "DINO index complete and bound to exact original120 source IDs")
    check(set(old_records) == set(originals), "Old120 compact IDs equal original120")
    check(frozen.get("status") == "complete" and frozen.get("stage") == "old" and
          frozen.get("whole_v2_dataset_complete") is False and frozen_records == old_records,
          "Immutable development snapshot records exactly equal combined old120")
    check(frozen.get("identity", {}).get("bindings") == checksums and frozen.get("identity", {}).get("runtime") == manifest["identity"]["runtime"],
          "Immutable development code/runtime binding equals combined manifest")
    check(set(plans) == set(pairs_by_id), "Manifest IDs exactly match reviewed member plan")
    pair_reports, geometries, claimed_paths = [], [], set()
    source_matches = 0
    for record in records:
        identifier = record.get("id", "unknown")
        try:
            spec = plans[identifier]
            require((record["region"], record["role"]) == (spec["region"], spec["role"]), "Plan region/role differs")
            for kind, source_key in (("rgb", "source_rgb"), ("label", "source_label")):
                for key in SOURCE_KEYS:
                    expected = spec[kind].get(key)
                    if key != "sha256" or expected is not None:
                        require(record[source_key].get(key) == expected, f"{kind} reviewed member identity differs")
            if record["role"] == "old_development":
                source, feature = originals[identifier], dino_records[identifier]
                require(source["region"] == record["region"] == feature["region"], "Original/DINO region differs")
                for kind, source_key in (("rgb", "source_rgb"), ("label", "source_label")):
                    require(record[source_key] == source_reduced(source[kind]), f"Old {kind} source identity differs from original manifest")
                    require(record[source_key]["sha256"] == feature[f"source_{kind}_sha256"], f"Old {kind} source SHA differs from DINO index")
                source_matches += 1
            metadata, available = check_pair(record, manifest, manifest_path.parent, claimed_paths)
            pair_reports.append(available)
            geometries.append(geometry_record(record, metadata, padding))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"scope": "pair", "id": identifier, "error": f"{type(exc).__name__}: {exc}"})
            pair_reports.append({"id": identifier, "usable": False})
    report["checks"] = global_checks
    report["source_binding"] = {"old_pairs_matched_to_original_and_dino": source_matches,
                                "expected": 120, "original_raw_files_rehashed": False,
                                "feature_arrays_required_or_read": False}
    report["processed_png_availability"] = {"expected_pairs": 192, "verified_pairs": sum(item.get("usable", False) for item in pair_reports),
                                             "verified_png_files": 2 * sum(item.get("usable", False) for item in pair_reports),
                                             "pairs": pair_reports}
    old_geo = [item for item in geometries if item["role"] == "old_development"]
    new_geo = [item for item in geometries if item["role"] == "new_panel"]
    primary = bbox_comparisons(old_geo, new_geo)
    caution = bbox_comparisons(old_geo, new_geo, include_cautions=True)
    duplicates = decoded_duplicates(geometries)
    allocations = []
    for split in design.get("source_splits", []):
        train = [item for item in old_geo if item["region"] in split.get("train", [])]
        validation = [item for item in old_geo if item["region"] in split.get("validation", [])]
        allocations.append({"id": split["id"], "train_pairs": len(train), "validation_pairs": len(validation),
                            "supported_train_pairs": sum(item["supported_for_separation_screen"] for item in train),
                            "supported_validation_pairs": sum(item["supported_for_separation_screen"] for item in validation),
                            "supported_bbox_screen": bbox_comparisons(train, validation),
                            "caution_bbox_screen": bbox_comparisons(train, validation, include_cautions=True)})
    warnings = [item for item in geometries if not item["supported_for_separation_screen"]]
    report["geography"] = {"source": "SHA-verified pair sidecars only; no CRS transformations rerun",
                            "padding_base_m": padding, "padding_rule": "base + operation accuracy; unknown accuracy adds 100m",
                            "verified_sidecar_records": len(geometries),
                            "supported_pairs_by_role": dict(Counter(item["role"] for item in geometries if item["supported_for_separation_screen"])),
                            "supported_old_vs_new_bbox_screen": primary,
                            "caution_old_vs_new_bbox_screen": caution,
                            "old_source_allocation_train_vs_validation": allocations,
                            "unknown_or_caution": warnings, "records": geometries}
    report["cross_role_original_decoded_rgb_duplicates"] = duplicates
    candidate_count = primary["candidate_count"] + caution["candidate_count"] + duplicates["candidate_count"] + sum(
        item["supported_bbox_screen"]["candidate_count"] + item["caution_bbox_screen"]["candidate_count"] for item in allocations)
    report["human_review_required"] = candidate_count > 0
    report["candidate_review_entries"] = candidate_count
    report["geographic_inference_limited"] = bool(warnings) or candidate_count > 0
    report["processed_pngs_usable"] = len(pair_reports) == 192 and all(item.get("usable", False) for item in pair_reports)
    report["passed"] = not errors and report["processed_pngs_usable"]
    report["runnable_integrity_passed"] = report["passed"]
    report["interpretation"] = ("Technical integrity passed; geographic findings and coverage limits still require the stated interpretation."
                                if report["passed"] else "Technical integrity/partition incomplete or failed; do not treat this as a complete usable192 audit.")
    return report


class SyntheticChecks(unittest.TestCase):
    def test_real_legacy_original_schema_omits_id_and_rejects_identity_drift(self):
        # This fixture follows the real retained formal120 downloader schema,
        # which stores region+member records but no pair-level id.
        record = {"region": "aachen", "rgb": {
            "member": "OpenEarthMap_wo_xBD/aachen/images/aachen_1.tif",
            "relative_path": "OpenEarthMap_wo_xBD/aachen/images/aachen_1.tif",
            "sha256": "051dca0c05ad8b57c0d0e82477ec19273920bb794bca7682eead0ef3ef408536"},
            "label": {"member": "OpenEarthMap_wo_xBD/aachen/labels/aachen_1.tif",
                      "sha256": "53010d1651f6d445cdebe447bad16c02bfede0be9abbcf6dc87bd932aa81b260"}}
        self.assertEqual(original_pair_id(record), "aachen__aachen_1")
        self.assertEqual(list(indexed([record], "legacy", legacy_original=True)), ["aachen__aachen_1"])
        self.assertNotIn("id", record)  # Never mutate retained evidence.
        for changed in ({**record, "region": "accra"}, {**record, "id": "aachen__aachen_2"},
                        {**record, "label": {**record["label"], "member": "OpenEarthMap_wo_xBD/aachen/labels/aachen_2.tif"}}):
            with self.assertRaises(ValueError):
                original_pair_id(changed)
        with self.assertRaises(KeyError):
            indexed([record], "v2")  # Other schemas must not silently derive IDs.
        with self.assertRaises(ValueError):
            indexed([record, record], "legacy", legacy_original=True)

    def test_processed_mask_histogram_has_void_and_exact_truth_margins(self):
        array = np.zeros((448, 448), dtype=np.uint8)
        array.ravel()[:9] = np.arange(9, dtype=np.uint8)
        counts = processed_mask_counts(array)
        self.assertEqual(counts, [448 * 448 - 8] + [1] * 8)
        self.assertEqual(sum(counts), 448 * 448)
        self.assertTrue(all(isinstance(value, int) for value in counts))
        array[0, 0] = 9
        with self.assertRaisesRegex(ValueError, "raw IDs 0..8"):
            processed_mask_counts(array)

    def test_bbox_candidates_and_caution_exclusion(self):
        def item(identifier, box, supported=True):
            return {"id": identifier, "wgs84_padded_candidate_bbox": box, "supported_for_separation_screen": supported}
        left = [item("old", [0, 0, 1, 1])]
        right = [item("touch", [1, 1, 2, 2]), item("far", [3, 3, 4, 4]), item("caution", [.5, .5, 1, 1], False)]
        self.assertEqual((bbox_comparisons(left, right)["compared_pairs"], bbox_comparisons(left, right)["candidate_count"]), (2, 1))
        self.assertEqual(bbox_comparisons(left, right, True)["candidate_count"], 1)

    def test_duplicate_requires_dimensions_and_cross_roles(self):
        def item(identifier, role, shape):
            return {"id": identifier, "role": role, "original_dimensions": shape, "original_decoded_rgb_sha256": "a" * 64}
        result = decoded_duplicates([item("old", "old_development", [10, 20]), item("same_old", "old_development", [10, 20]),
                                     item("new", "new_panel", [10, 20]), item("different_shape", "new_panel", [20, 10])])
        self.assertEqual(result["candidate_count"], 2)

    def test_fixed_count_failure_and_disjoint_partition(self):
        old_regions = [f"old{i}" for i in range(24)]
        records = [{"id": f"{region}__{i}", "region": region, "role": role}
                   for role, regions, count in (("old_development", old_regions, 5), ("new_panel", NEW_REGIONS, 3))
                   for region in regions for i in range(count)]
        self.assertEqual(validate_partition(records, old_regions, NEW_REGIONS), [])
        self.assertTrue(validate_partition(records[:-1], old_regions, NEW_REGIONS))
        changed = [dict(item) for item in records]
        changed[-1]["region"] = old_regions[0]
        self.assertTrue(validate_partition(changed, old_regions, NEW_REGIONS))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "v2/data/manifest.json")
    parser.add_argument("--design", type=Path, default=ROOT / "configs/v2_design.json")
    parser.add_argument("--original-manifest", type=Path, default=ROOT / "data/formal120/manifest.json")
    parser.add_argument("--dino-index", type=Path, default=ROOT / "cache/dinov2-formal120/index.json")
    parser.add_argument("--development-manifest", type=Path, default=ROOT / "v2/data/development_manifest.json")
    parser.add_argument("--selection-plan", type=Path, default=ROOT / "v2/data/selection_plan.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/v2/data_audit.json")
    parser.add_argument("--padding-meters", type=float, default=20.0)
    parser.add_argument("--self-test", action="store_true", help="Synthetic bbox/duplicate/count tests only; no dataset reads or writes")
    args = parser.parse_args(argv)
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticChecks))
        return 0 if result.wasSuccessful() else 1
    if not math.isfinite(args.padding_meters) or args.padding_meters < 0:
        parser.error("Padding must be finite and nonnegative")
    output = args.output.resolve()
    evidence_root = (ROOT / "evidence/v2").resolve()
    if not output.is_relative_to(evidence_root):
        parser.error("Audit output must stay inside evidence/v2")
    try:
        report = audit(*[getattr(args, name).resolve() for name in (
            "manifest", "design", "original_manifest", "dino_index", "development_manifest", "selection_plan")], args.padding_meters)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {"format": "v2-data-audit-1", "passed": False, "processed_pngs_usable": False,
                  "audit_code_sha256": sha_file(Path(__file__)),
                  "integrity_errors": [{"scope": "audit_input_structure", "error": f"{type(exc).__name__}: {exc}"}],
                  "limitations": LIMITATIONS}
    content = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    project_bytes = sum(path.stat().st_size for path in ROOT.rglob("*") if path.is_file() and not path.is_symlink())
    if project_bytes + len(content) >= 2_000_000_000:
        print("Audit report would exceed project byte limit; nothing written", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(content); temporary.replace(output)
    print(json.dumps({"passed": report["passed"], "processed_pngs_usable": report["processed_pngs_usable"],
                      "integrity_errors": len(report["integrity_errors"]),
                      "human_review_required": report.get("human_review_required"), "output": relative(output)}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

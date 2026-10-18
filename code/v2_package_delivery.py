"""Plan a bounded standalone V2 author-review directory; assemble only manually.

No links, downloads, deletion, automatic rollback or training. --assemble requires
a ready saved plan and an explicit no-writers declaration. --self-test touches
only automatically removed synthetic OS temporary directories.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATION = "delivery/RemoteSensing_GeographicSelection_V2"
PLAN = "evidence/v2/package_plan.json"
CAP = 2_000_000_000
PAPER = ("paper/v2/manuscript.docx", "paper/v2/manuscript.pdf",
         "paper/v2/supplementary_material.docx", "paper/v2/supplementary_material.pdf", "paper/v2/manuscript_source.json")
NUMERICAL = tuple("tables/v2/" + name for name in (
    "conditions_by_source.csv", "conditions.csv", "regions.csv", "classes.csv", "contrasts.json", "primary.json"))
EVIDENCE_DIRS = ("calibration", "software", "source_snapshot", "audit_attempts", "prospective_amendments")
TEXT_EXTENSIONS = {".json", ".jsonl", ".txt", ".log", ".md", ".py", ".bib", ".csv"}
PUBLICATION_EXTENSIONS = TEXT_EXTENSIONS | {".docx", ".pdf", ".svg", ".png", ".jpg", ".jpeg", ".tex"}
FORBIDDEN_PARTS = {"runtime", "site-packages", "node_modules", "__pycache__", ".git"}
OPERATIONAL_REPORTS = frozenset({"evidence/v2/run_completeness.json", "tables/v2/analysis_identity.json",
                                 "evidence/v2/reproduction_check.json", "evidence/v2/checkpoint_reload.json",
                                 "evidence/v2/active_reproduction_check.json"})
KNOWN_DATA_TOP_LEVEL = frozenset({"manifest.json", "development_manifest.json", "old_development_manifest.json",
                                   "selection_plan.json", "selection_plan_old.json"})
FEATURE_INDEXES = {"cache/dinov2-formal120/index.json": (120, "old_development"),
                   "v2/cache/new_panel_dinov2/index.json": (72, "new_panel")}
FEATURE_ORIGIN = "frozen_feature_cache_reference"
CUDA_ORIGIN = "cuda90_closed_execution_inventory"
CPU_REFERENCE_ORIGIN = "cpu_reference_preserved_inventory"
PIXEL_GUARD_ORIGIN = "pixel_audited_mutex_marker"
PIXEL_OUT = "evidence/v2/pixel_budget_execution"
_MIGRATION_BUDGET = None


def pipeline_paths(root):
    active = child(root, "configs/v2_active_gpu_amendment.json").is_file()
    return {
        "active": active,
        "audit": "evidence/v2/active_run_completeness.json" if active else "evidence/v2/run_completeness.json",
        "reproduction": "evidence/v2/active_reproduction_check.json" if active else "evidence/v2/reproduction_check.json",
        "audit_code": "code/v2_active_gpu_results.py" if active else "code/v2_audit_runs.py",
        "analysis_code": "code/v2_active_gpu_results.py" if active else "code/v2_statistics.py",
        "wrapper": "code/v2_active_gpu_results.py" if active else "code/v2_reproduce.py",
    }


def current_core_results(root, active):
    if active:
        frozen_name = read(child(root, "configs/v2_design.json"))["frozen_control"]["name"]
        folders = (child(root, "evidence/v2/runs/" + frozen_name), child(root, "evidence/v2/cuda_execution"))
    else:
        folders = (child(root, "evidence/v2/runs"),)
    return {p.relative_to(root).as_posix() for folder in folders for p in folder.rglob("result.json")}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def raw(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def reject_redirected_path(path):
    absolute = Path(os.path.abspath(path))
    for item in reversed((absolute, *absolute.parents)):
        try:
            info = os.lstat(item)
        except FileNotFoundError:
            continue
        # Windows name-surrogate tags include junctions and symbolic links.
        # Non-surrogate OneDrive cloud placeholder tags are allowed.
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_reparse_tag", 0) & 0x20000000,
                "Redirecting symlink/junction/name-surrogate path rejected")
    return absolute


def project_root(root):
    return reject_redirected_path(root).resolve()


def child(root, relative):
    root = project_root(root)
    require(isinstance(relative, str) and relative and "\\" not in relative and ":" not in relative,
            "Expected relative POSIX path")
    part = Path(relative)
    require(not part.is_absolute() and ".." not in part.parts, "Unsafe relative path")
    result = reject_redirected_path(root / part).resolve()
    require(result.is_relative_to(root), "Resolved path leaves its project/delivery root")
    return result


def logical_bytes(root):
    # Hard links count at every path: they cannot evade this logical budget.
    return sum(path.stat().st_size for path in Path(root).rglob("*")
               if path.is_file() and not path.is_symlink())


def ensure_capacity(root, extra):
    if _MIGRATION_BUDGET is not None:
        require(project_root(root) == _MIGRATION_BUDGET.root, "Migration budget root differs")
        _MIGRATION_BUDGET.check(extra)
        return
    require(logical_bytes(root) + extra < CAP, f"Project logical cap refused: extra{extra} must remain below{CAP}")


def charge_migration_write(root, count):
    if _MIGRATION_BUDGET is not None:
        require(project_root(root) == _MIGRATION_BUDGET.root, "Migration write root differs")
        _MIGRATION_BUDGET.charge(count)


def write_new(root, path, content):
    path = reject_redirected_path(path).resolve()
    require(path.is_relative_to(project_root(root)), "Metadata target leaves project")
    ensure_capacity(root, len(content))
    path.parent.mkdir(parents=True, exist_ok=True)
    charge_migration_write(root, len(content))
    with path.open("xb") as stream:
        stream.write(content); stream.flush(); os.fsync(stream.fileno())


def destination_path(root, relative):
    destination = child(root, relative)
    parent = child(root, "delivery")
    require(destination.parent == parent and destination.name.startswith("RemoteSensing_GeographicSelection_V2"),
            "Destination must be a new V2 directory directly under project/delivery")
    require(not destination.exists(), "Destination already exists; preserve it and inspect the receipt, never overwrite")
    return destination


def source_allowed(relative, action, origin):
    """Explicit scope; NPZ allowance is only a frozen-index-listed MOVE."""
    parts = Path(relative).parts
    require(parts and parts[0] != "delivery" and not set(parts) & FORBIDDEN_PARTS,
            "Delivery/V1/runtime source is excluded")
    suffix = Path(relative).suffix.lower()
    if suffix == ".npz":
        require(action == "move" and origin == FEATURE_ORIGIN and
                Path(relative).parent.as_posix() in {str(Path(p).parent.as_posix()) for p in FEATURE_INDEXES} and
                re.fullmatch(r"[A-Za-z0-9_-]+__[A-Za-z0-9_-]+\.npz", Path(relative).name),
                "Only flat frozen-index feature-cache references may MOVE; arbitrary NPZ excluded")
        return
    require(suffix not in {".npz", ".npy", ".zip", ".7z", ".tar", ".gz", ".tif", ".tiff"},
            "Raw imagery, feature arrays and archives are excluded")
    if origin == PIXEL_GUARD_ORIGIN:
        require(action == "copy" and pixel_guard_path(relative),
                "Only exact audited pixel mutex markers may COPY with this origin")
        return
    if action == "move":
        if origin == CPU_REFERENCE_ORIGIN:
            require(relative.startswith("evidence/v2/runs/resnet18_unet/") and
                    suffix in TEXT_EXTENSIONS | {".pt", ".pth"}, "CPU reference MOVE scope differs")
            return
        if relative.startswith("evidence/v2/cuda_execution/"):
            require(origin == CUDA_ORIGIN and suffix in TEXT_EXTENSIONS,
                    "CUDA history may move only through its exact terminal audited inventory")
            return
        require(relative.startswith("v2/data/") or relative.startswith("evidence/v2/runs/"), "Unapproved MOVE scope")
        if relative.startswith("evidence/v2/runs/"):
            require(origin == "completed_run_reference", "Runs may move only through passed-audit result references")
        return
    require(action == "copy", "Unknown action")
    if parts[0] == "data":
        require(origin == "data_audit_input" and suffix == ".json", "Only explicitly referenced raw-data manifests may COPY")
    elif parts[0] == "cache" or relative.startswith("v2/cache/"):
        require(Path(relative).name == "index.json" and origin in {"frozen_dependency", "feature_index"},
                "Only frozen feature-index metadata may COPY")
    elif relative.startswith("paper/"):
        require(relative.startswith("paper/v2/") and suffix in PUBLICATION_EXTENSIONS, "Old V1 paper is excluded")
    elif relative.startswith("tables/"):
        require((relative.startswith("tables/v2/") and suffix in {".csv", ".json"}) or
                relative in {"tables/v2_cuda/descriptive_analysis.json", "tables/v2_pixel_budget/descriptive_analysis.json"},
                "Only V2 numerical/analysis tables may COPY")
    elif relative.startswith("figures/"):
        require(relative.startswith("figures/v2/") and suffix in PUBLICATION_EXTENSIONS, "Old V1 figures are excluded")
    elif relative.startswith("evidence/"):
        require(relative.startswith("evidence/v2/") and not relative.startswith("evidence/v2/runs/") and
                suffix in TEXT_EXTENSIONS, "Only scoped V2 text evidence may COPY")
        require(not relative.startswith("evidence/v2/package_receipts/") and Path(relative).name not in {
            "package_plan.json", "migration_receipt.json"}, "Package plans/receipts are generated separately")
    else:
        require((parts[0] in {"code", "configs", "docs"} and suffix in TEXT_EXTENSIONS) or
                relative == "manuscript_state.json", "Source is outside the explicit small-file scope")


def checked_operation_paths(root, dest, entry):
    source_allowed(entry["source"], entry["action"], entry["origin"])
    source, output = child(root, entry["source"]), child(dest, entry["target"])
    source_allowed(source.relative_to(project_root(root)).as_posix(), entry["action"], entry["origin"])
    source_allowed(output.relative_to(project_root(dest)).as_posix(), entry["action"], entry["origin"])
    require(entry["source"] == entry["target"], "Relative paths must be preserved")
    return source, output


def compact_data_inventory(root):
    base = child(root, "v2/data")
    manifest = read(child(root, "v2/data/manifest.json"))
    require(manifest.get("status") == "complete" and manifest.get("whole_v2_dataset_complete") is True and
            len(manifest["pairs"]) == len({item["id"] for item in manifest["pairs"]}) == 192,
            "Compact MOVE inventory requires exact complete192 manifest")
    approved = {}
    for record in manifest["pairs"]:
        for kind in ("rgb", "label", "metadata"):
            info = record[kind]
            relative = "v2/data/" + info["relative_path"]
            path = child(root, relative)
            require(path.suffix == (".json" if kind == "metadata" else ".png") and relative not in approved,
                    "Duplicate/invalid compact manifest reference")
            require(path.stat().st_size == info["bytes"] and sha(path) == info["sha256"], "Compact manifest file identity differs")
            approved[relative] = "manifest192_" + kind
    for name in KNOWN_DATA_TOP_LEVEL:
        path = child(root, "v2/data/" + name)
        if path.is_file():
            approved["v2/data/" + name] = "known_top_level_data_manifest"
    excluded = []
    for current, directories, files in os.walk(base, followlinks=False):
        for name in directories + files:
            reject_redirected_path(Path(current) / name)
        for name in files:
            path = Path(current) / name
            relative = path.relative_to(project_root(root)).as_posix()
            if relative not in approved:
                excluded.append({"path": relative, "bytes": path.stat().st_size,
                                 "reason": "Unreferenced compact extra; retain at source, never MOVE"})
    return approved, excluded


def feature_cache_inventory(root):
    """Read SHA-bound indexes and bytes only; never load arrays or model results.

    A cache path must be the flat ID.npz name in one of the two exact frozen
    directories. Unlisted NPZ in those directories (including nested extras)
    blocks the inventory. Unrelated cache directories are never traversed.
    """
    root = project_root(root)
    freeze_path = child(root, "configs/v2_freeze.json")
    freeze = read(freeze_path)
    mapping = freeze.get("file_sha256", {})
    require(freeze.get("status") == "FROZEN_BEFORE_NEW_PANEL_EVALUATION" and len(mapping) == 53 and
            freeze.get("expected_total_runs") == 576, "Feature inventory requires the exact53-file576 execution freeze")
    manifest_name = "v2/data/manifest.json"
    require(manifest_name in mapping and sha(child(root, manifest_name)) == mapping[manifest_name],
            "Feature inventory compact manifest differs from freeze")
    manifest = read(child(root, manifest_name))
    records = manifest.get("pairs", [])
    require(manifest.get("status") == "complete" and manifest.get("whole_v2_dataset_complete") is True and
            len(records) == len({p["id"] for p in records}) == 192,
            "Feature inventory requires complete192 compact identities")
    pairs = {p["id"]: p for p in records}
    files, indexes, all_ids, all_paths = [], {}, set(), set()
    for index_name, (expected, role) in FEATURE_INDEXES.items():
        index_path = child(root, index_name)
        require(index_name in mapping and sha(index_path) == mapping[index_name], "Feature index differs from freeze")
        index = read(index_path)
        entries = index.get("records", [])
        require(index.get("status") == "complete" and len(entries) == expected,
                "Feature index count/status differs from required120/72")
        require({p["id"] for p in records if p["role"] == role} == {p["id"] for p in entries} and
                len({p["id"] for p in entries}) == expected, "Feature index duplicate/missing/role IDs")
        if role == "new_panel":
            require(index.get("identity", {}).get("manifest_sha256") == mapping[manifest_name],
                    "New-panel feature index compact manifest binding differs")
        approved = set()
        index_bytes = 0
        for entry in entries:
            identifier, filename = entry["id"], entry["cache"]
            checksum = entry.get("cache_sha256")
            require(isinstance(identifier, str) and re.fullmatch(r"[A-Za-z0-9_-]+__[A-Za-z0-9_-]+", identifier) and
                    isinstance(filename, str) and filename == identifier + ".npz" and
                    isinstance(checksum, str) and re.fullmatch(r"[0-9a-f]{64}", checksum),
                    "Invalid flat feature filename/ID/SHA reference")
            require(identifier not in all_ids and entry["region"] == pairs[identifier]["region"],
                    "Duplicate or mismatched feature identity")
            pair = pairs[identifier]
            if role == "old_development":
                require(all(entry.get("source_" + k + "_sha256") == pair["source_" + k]["sha256"]
                            for k in ("rgb", "label")), "Old feature source SHA differs from compact provenance")
            else:
                require(entry.get("processed_rgb_sha256") == pair["rgb"]["sha256"],
                        "New feature processed RGB SHA differs from compact provenance")
            relative = (Path(index_name).parent / filename).as_posix()
            require(relative not in all_paths, "Duplicate feature cache path")
            path = child(root, relative)
            source_allowed(relative, "move", FEATURE_ORIGIN)
            require(path.is_file(), "Missing feature cache: " + relative)
            require(sha(path) == checksum, "Feature cache SHA mismatch: " + relative)
            size = path.stat().st_size
            files.append({"id": identifier, "region": entry["region"], "relative_path": relative,
                          "index": index_name, "index_sha256": mapping[index_name],
                          "sha256": checksum, "bytes": size})
            all_ids.add(identifier); all_paths.add(relative); approved.add(relative); index_bytes += size
        base = child(root, Path(index_name).parent.as_posix())
        for current, directories, names in os.walk(base, followlinks=False):
            for name in directories + names:
                reject_redirected_path(Path(current) / name)
            for name in names:
                path = Path(current) / name
                relative = path.relative_to(root).as_posix()
                require(path.suffix.lower() != ".npz" or relative in approved,
                        "Unlisted NPZ in formal feature directory: " + relative)
        indexes[index_name] = {"sha256": mapping[index_name], "expected_count": expected,
                               "verified_count": len(entries), "bytes": index_bytes}
    require(len(files) == len(all_ids) == len(all_paths) == 192, "Feature inventory must be exactly192 unique files")
    return {"format": "v2-frozen-feature-cache-inventory-1", "freeze_sha256": sha(freeze_path),
            "compact_manifest_sha256": mapping[manifest_name], "indexes": indexes,
            "file_count": len(files), "total_bytes": sum(f["bytes"] for f in files),
            "action": "move", "logical_byte_increase": 0,
            "files": sorted(files, key=lambda f: f["relative_path"])}


def verify_feature_cache_operations(root, plan):
    operations = [e for e in plan["operations"] if e["origin"] == FEATURE_ORIGIN or
                  Path(e["source"]).suffix.lower() == ".npz"]
    if not operations and "feature_cache_inventory" not in plan:
        return  # Small non-cache fixture operations; CLI ready plans always bind the inventory.
    inventory = feature_cache_inventory(root)
    require(plan.get("feature_cache_inventory") == inventory, "Feature inventory changed since plan")
    expected = {f["relative_path"]: f for f in inventory["files"]}
    require(len(operations) == 192 and {e["source"] for e in operations} == set(expected),
            "Feature MOVE operations must cover the exact192 listed caches")
    for operation in operations:
        info = expected[operation["source"]]
        require(operation["action"] == "move" and operation["origin"] == FEATURE_ORIGIN and
                operation["source"] == operation["target"] and operation["sha256"] == info["sha256"] and
                operation["bytes"] == info["bytes"], "Feature operation must MOVE unchanged indexed bytes")


def verify_research_review(root, review):
    require(review.get("passed") is True and review.get("release_recommendation") == "AUTHOR_REVIEW_PACKAGE",
            "Scientific review has not approved an author-review package")
    mapping = review.get("checked_file_sha256")
    require(isinstance(mapping, dict) and set(PAPER + NUMERICAL) <= set(mapping),
            "Scientific review must bind five manuscript files and six numerical outputs")
    if pipeline_paths(root)["active"]:
        require({"configs/v2_active_gpu_amendment.json", "evidence/v2/active_run_completeness.json",
                 "evidence/v2/cpu_reference_snapshot.json", "tables/v2_cuda/descriptive_analysis.json",
                 "evidence/v2/pixel_budget_audit.json", "tables/v2_pixel_budget/descriptive_analysis.json",
                 "paper/v2/supplementary_source.json"} <= mapping.keys(),
                "Active scientific review must also bind execution amendment, supplements and their evidence")
    for name, checksum in mapping.items():
        path = child(root, name)
        require(isinstance(checksum, str) and len(checksum) == 64 and path.is_file() and sha(path) == checksum,
                "Scientific-review checked-file SHA mismatch: " + name)


def gates(root):
    checks, loaded = [], {}
    paths = pipeline_paths(root)
    def check(name, relative, predicate):
        try:
            value = read(child(root, relative))
            require(predicate(value), "Required completion/release fields did not pass")
            loaded[name] = value
            checks.append({"gate": name, "path": relative, "passed": True, "sha256": sha(child(root, relative))})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checks.append({"gate": name, "path": relative, "passed": False, "error": str(exc)})
    check("freeze", "configs/v2_freeze.json", lambda j: j.get("status") == "FROZEN_BEFORE_NEW_PANEL_EVALUATION" and
          j.get("expected_total_runs") == 576 and j.get("expected_full_runs") == 90 and j.get("expected_frozen_runs") == 486)
    check("runs", paths["audit"], lambda j: j.get("passed") is True and
          j.get("validated_runs") == j.get("observed_result_files") == j.get("expected_total") == 576 and
          len(j.get("results", {})) == 576 and all(not j.get(key) for key in ("errors", "missing", "extra", "duplicates")))
    check("reload", "evidence/v2/checkpoint_reload.json", lambda j: j.get("passed") is True and
          j.get("matched_images") == 72 and j.get("matched_regions") == 24 and
          j.get("all_integer_confusion_matrices_exact") is True and j.get("aggregate_exact") is True and
          j.get("refitting_performed") is False)
    check("reproduction", paths["reproduction"], lambda j: j.get("passed") is True and j.get("tables_passed") is True)
    check("scientific_review", "evidence/v2/research_review.json", lambda j: j.get("passed") is True and
          j.get("release_recommendation") == "AUTHOR_REVIEW_PACKAGE")
    if child(root, "configs/v2_cuda_execution_plan.json").exists():
        check("cuda90_audit", "evidence/v2/cuda_execution_audit.json", lambda j:
              j.get("passed") is True and j.get("expected_count") == j.get("observed_count") ==
              j.get("validated_count") == 90)
        check("cuda90_analysis", "tables/v2_cuda/descriptive_analysis.json", lambda j:
              j.get("scope") == "DESCRIPTIVE_SECONDARY_EXECUTION_REPLICATION" and
              j.get("expected_count") == j.get("validated_count") == 90 and
              j.get("original_primary_unchanged") is True and j.get("new_independent_holdout") is False)
    if child(root, "configs/v2_pixel_budget_plan.json").exists():
        check("pixel27_audit", "evidence/v2/pixel_budget_audit.json", lambda j:
              j.get("passed") is True and j.get("expected_count") == j.get("observed_count") == j.get("validated_count") == 27)
        check("pixel27_analysis", "tables/v2_pixel_budget/descriptive_analysis.json", lambda j:
              j.get("scope") == "DESCRIPTIVE_POST_EXPOSURE_PIXEL_BUDGET" and
              j.get("expected_count") == j.get("validated_count") == 27 and j.get("new_independent_holdout") is False)
    if "scientific_review" in loaded:
        try:
            verify_research_review(root, loaded["scientific_review"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checks.append({"gate": "scientific_review_version_binding", "passed": False, "error": str(exc)})
    for relative in PAPER:
        try:
            path = child(root, relative)
            require(path.is_file() and path.stat().st_size > 0, "Missing/empty final manuscript artifact")
            if path.suffix == ".docx":
                with zipfile.ZipFile(path) as archive:
                    require("word/document.xml" in archive.namelist(), "DOCX lacks its document XML")
            elif path.suffix == ".pdf":
                with path.open("rb") as stream:
                    require(stream.read(5) == b"%PDF-", "Not a PDF")
                    stream.seek(max(0, path.stat().st_size - 1024))
                    require(b"%%EOF" in stream.read(), "Missing PDF EOF marker")
            else:
                require(isinstance(read(path), dict) and bool(read(path)), "Source JSON must be a nonempty object")
            checks.append({"gate": "paper", "path": relative, "passed": True, "sha256": sha(path)})
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            checks.append({"gate": "paper", "path": relative, "passed": False, "error": str(exc)})
    return checks, loaded


def verify_map(root, mapping, label):
    require(isinstance(mapping, dict) and bool(mapping), "Missing SHA mapping: " + label)
    for relative, checksum in mapping.items():
        require(sha(child(root, relative)) == checksum, label + " SHA mismatch: " + relative)


def verify_active_delivery(root, plan=None):
    """Validate actual active semantics/CPU references without writing tables."""
    if not pipeline_paths(root)["active"]:
        require(plan is None or not plan.get("active_bundle_binding"), "Active amendment disappeared since plan")
        return None
    from v2_active_gpu_results import validate_bundle
    bundle = validate_bundle(root)
    require(isinstance(bundle, dict) and bundle.get("passed") is True and not bundle.get("errors"),
            "Full active GPU576 bundle validation did not pass")
    audit = bundle["audit"]
    binding = {"amendment_sha256": sha(child(root, "configs/v2_active_gpu_amendment.json")),
               "audit_sha256": sha(child(root, "evidence/v2/active_run_completeness.json")),
               "analysis_identity_sha256": sha(child(root, "tables/v2/analysis_identity.json")),
               "orchestrator_sha256": sha(child(root, "code/v2_active_gpu_results.py")),
               "result_inventory_sha256": hashlib.sha256(raw(audit["results"])).hexdigest(),
               "cpu_reference_inventory_sha256": hashlib.sha256(raw(audit["cpu_reference_files"])).hexdigest(),
               "role": audit["role"], "active_model_counts": audit["active_model_counts"]}
    if plan is not None:
        require(binding == plan.get("active_bundle_binding"), "Active bundle binding changed since plan")
    return binding


def pixel_guard_path(relative):
    return relative == PIXEL_OUT + "/admission.guard" or bool(re.fullmatch(
        re.escape(PIXEL_OUT) + r"/parallel/[A-Za-z0-9_-]+/(?:budget|stop)\.guard", relative))


def pixel_guard_inventory(root, bundle):
    """The scientific auditor excludes these bytes but requires them on reload."""
    entries = bundle.get("excluded_history_mutex_files")
    require(isinstance(entries, list), "Pixel audit must enumerate excluded mutex markers")
    result = {}
    for entry in entries:
        require(isinstance(entry, dict), "Invalid pixel mutex marker entry")
        relative = entry.get("path")
        require(isinstance(relative, str) and pixel_guard_path(relative) and relative not in result and
                type(entry.get("bytes")) is int and entry["bytes"] == 1,
                "Invalid/duplicate/out-of-scope audited pixel mutex marker")
        path = child(root, relative)
        require(path.is_file() and path.stat().st_size == 1 and path.read_bytes() == b"0",
                "Audited pixel mutex marker missing or changed")
        result[relative] = {"bytes": 1, "sha256": sha(path)}
    return result


def verify_pixel_delivery(root, plan=None, old_entries=None):
    if not child(root, "configs/v2_pixel_budget_plan.json").exists():
        require(plan is None or not plan.get("pixel_budget_delivery_inventory") and not plan.get("pixel_budget_guard_files") and
                not any(e.get("origin") == PIXEL_GUARD_ORIGIN or e["source"].startswith(PIXEL_OUT + "/") for e in plan["operations"]),
                "Pixel plan is required for audited mutex marker operations")
        return None
    from v2_audit_pixel_budget import validate_bundle
    bundle = validate_bundle(root)
    require(isinstance(bundle, dict) and bundle.get("passed") is True, "Full pixel bundle validation did not pass")
    guards = pixel_guard_inventory(root, bundle)
    if plan is not None:
        require(bundle == plan.get("pixel_budget_delivery_inventory"), "Pixel delivery inventory changed since plan")
        require(guards == plan.get("pixel_budget_guard_files"), "Pixel mutex marker inventory changed since plan")
        operations = {e["source"]: e for e in plan["operations"]}
        for relative, checksum in bundle["file_sha256"].items():
            require(relative in operations and operations[relative]["sha256"] == checksum,
                    "Pixel evidence missing from package operations")
        guard_operations = [e for e in plan["operations"] if e.get("origin") == PIXEL_GUARD_ORIGIN or
                            e["source"].startswith(PIXEL_OUT + "/") and Path(e["source"]).suffix == ".guard"]
        require(len(guard_operations) == len(guards) and {e["source"] for e in guard_operations} == set(guards),
                "Pixel operations must contain exact audited mutex marker whitelist")
        for entry in guard_operations:
            info = guards[entry["source"]]
            require(entry["source"] == entry["target"] and entry["action"] == "copy" and
                    entry["origin"] == PIXEL_GUARD_ORIGIN and entry["bytes"] == 1 and entry["sha256"] == info["sha256"],
                    "Pixel mutex marker operation differs")
    if old_entries is not None:
        for relative, checksum in bundle["file_sha256"].items():
            require(relative in old_entries and old_entries[relative]["sha256"] == checksum and
                    old_entries[relative]["bytes"] == child(root, relative).stat().st_size,
                    "Immutable pixel evidence differs from delivery manifest")
        for relative, info in guards.items():
            require(relative in old_entries and old_entries[relative]["sha256"] == info["sha256"] and
                    old_entries[relative]["bytes"] == 1, "Immutable pixel mutex marker differs from delivery manifest")
    return bundle


def build_plan(root, destination=DEFAULT_DESTINATION, extras=()):
    root = project_root(root)
    paths = pipeline_paths(root)
    dest = destination_path(root, destination)
    checks, loaded = gates(root)
    plan = {"format": "v2-package-plan-1", "created_utc": utc(), "status": "blocked", "destination": destination,
            "packager_sha256": sha(Path(__file__)), "gates": checks, "operations": [],
            "root_logical_bytes_before": logical_bytes(root), "storage_estimate_complete": False,
            "copy_additional_bytes": 0, "move_bytes_no_logical_increase": 0, "metadata_reservation_bytes": 0,
            "project_cap_bytes": CAP, "release_scope": "AUTHOR_REVIEW_PACKAGE; not submission-ready",
            "extra_includes": list(extras), "excluded": [],
            "run_history_policy": "Unreferenced pending/failure/history files remain in source; never deleted"}
    # No incomplete result JSON is inspected, even by a plan command.
    if not all(check["passed"] for check in checks):
        plan["blocked_reason"] = "Completion/reproduction/scientific-review/manuscript gates must pass before a complete inventory"
        return plan
    if paths["active"]:
        plan["active_bundle_binding"] = verify_active_delivery(root)
    freeze, audit, reproduction, reload = [loaded[key] for key in ("freeze", "runs", "reproduction", "reload")]
    require(len(freeze["file_sha256"]) == 53, "Expected the preserved53-file execution freeze")
    verify_map(root, freeze["file_sha256"], "Frozen dependency")
    verify_map(root, audit["inputs"], "Run audit input")
    verify_map(root, audit["artifacts"], "Run audit artifact")
    verify_map(root, audit["results"], "Run result")
    require(audit["audit_code_sha256"] == sha(child(root, paths["audit_code"])), "Stale run audit code")
    freeze_sha = sha(child(root, "configs/v2_freeze.json"))
    require(reproduction.get("freeze_sha256") == reload.get("freeze_sha256") == freeze_sha, "Stale reproduction/reload freeze binding")
    require(reproduction.get("result_sha256") == audit["results"] and
            reproduction.get("audit_report_sha256") == sha(child(root, paths["audit"])), "Stale reproduction result/audit binding")
    require(reproduction.get("wrapper_code_sha256") == sha(child(root, paths["wrapper"])),
            "Reproduction wrapper changed after the actual tables check")
    predetermined = "evidence/v2/runs/resnet18_unet/source0_skewed5_1_b12_s0_i0_region_kcenter/result.json"
    reference_results = audit.get("cpu_reference_result_files", {}) if paths["active"] else audit["results"]
    reference_files = audit.get("cpu_reference_files", {}) if paths["active"] else {}
    if paths["active"]:
        require(len(reference_results) == 72 and set(reference_results) <= reference_files.keys(), "Expected72 separate CPU reference fits")
        verify_map(root, reference_files, "Preserved CPU reference")
    require(reload.get("result_sha256") == reference_results.get(predetermined) and
            reload.get("verifier_sha256") == freeze["file_sha256"].get("code/v2_reload_checkpoint.py") and
            reload.get("manifest_sha256") == freeze["file_sha256"].get("v2/data/manifest.json") and
            reload.get("checkpoint_sha256") in set(audit["artifacts"].values()) | set(reference_files.values()), "Stale checkpoint reload identity")
    numerical = {relative: sha(child(root, relative)) for relative in NUMERICAL}
    require(reproduction.get("numerical_outputs_before_sha256") == reproduction.get("numerical_outputs_after_sha256") == numerical,
            "Reproduction numerical baseline differs from current six outputs")
    current = current_core_results(root, paths["active"])
    require(current == set(audit["results"]), "Run inventory changed after the audit")
    selected = {}
    def add(relative, action, origin):
        source, output = checked_operation_paths(root, dest, {"source": relative, "target": relative,
                                                            "action": action, "origin": origin})
        require(source.is_file(), "Package source missing: " + relative)
        require(source != output and not source.is_relative_to(dest), "Invalid source/destination relation")
        entry = {"source": relative, "target": relative, "action": action, "origin": origin,
                 "bytes": source.stat().st_size, "sha256": sha(source)}
        if relative in selected:
            require(selected[relative]["sha256"] == entry["sha256"] and selected[relative]["action"] == action,
                    "Conflicting duplicate target: " + relative)
        else:
            selected[relative] = entry
    if child(root, "configs/v2_cuda_execution_plan.json").exists():
        from v2_cuda_delivery_inventory import build_inventory
        plan["cuda_delivery_inventory"] = build_inventory(root)
        for info in plan["cuda_delivery_inventory"]["files"]:
            add(info["relative_path"], info["action"], info["origin"])
    plan["feature_cache_inventory"] = feature_cache_inventory(root)
    for info in plan["feature_cache_inventory"]["files"]:
        add(info["relative_path"], "move", FEATURE_ORIGIN)
    compact, plan["excluded"] = compact_data_inventory(root)
    for relative in sorted(compact):
        add(relative, "move", "compact_data")
    checkpoint_count = 0
    for relative in sorted(audit["results"]):
        if paths["active"] and relative.startswith("evidence/v2/cuda_execution/"):
            require(relative in selected and selected[relative]["action"] == "move", "Audited GPU result missing from exact CUDA inventory")
            continue
        require(relative.startswith("evidence/v2/runs/") and Path(relative).name == "result.json", "Invalid audited run path")
        value = read(child(root, relative))
        require(value.get("status") == "complete", "Audited run is not complete")
        add(relative, "move", "completed_run_reference")
        log = value["log_file"]
        require(child(root, log).parent == child(root, relative).parent and
                sha(child(root, log)) == value["log_sha256"] == audit["artifacts"].get(log), "Run log reference differs")
        add(log, "move", "completed_run_reference")
        if value.get("checkpoint") is not None:
            checkpoint = value["checkpoint"]
            require(relative == "evidence/v2/runs/resnet18_unet/source0_skewed5_1_b12_s0_i0_region_kcenter/result.json" and
                    child(root, checkpoint["path"]).parent == child(root, relative).parent and
                    sha(child(root, checkpoint["path"])) == checkpoint["sha256"] == audit["artifacts"].get(checkpoint["path"]),
                    "Checkpoint is not the predetermined audited checkpoint")
            checkpoint_count += 1
            add(checkpoint["path"], "move", "completed_run_reference")
    if paths["active"]:
        for relative in sorted(reference_files):
            require(relative.startswith("evidence/v2/runs/resnet18_unet/"), "CPU reference path differs")
            add(relative, "move", CPU_REFERENCE_ORIGIN)
        reference_checkpoint = read(child(root, predetermined))["checkpoint"]
        require(reference_checkpoint is not None and reference_checkpoint["path"] in reference_files and
                reference_files[reference_checkpoint["path"]] == reference_checkpoint["sha256"], "CPU reference checkpoint missing")
        checkpoint_count += 1
    require(checkpoint_count == 1, "Exactly one predetermined reference checkpoint must be moved")
    for relative in freeze["file_sha256"]:
        if relative not in selected:
            add(relative, "copy", "frozen_dependency")
    data_audit = read(child(root, "evidence/v2/data_audit.json"))
    for info in data_audit["inputs"].values():
        relative = info["path"]
        require(sha(child(root, relative)) == info["sha256"], "Stale data-audit manifest input")
        if relative not in selected:
            add(relative, "copy", "data_audit_input")
    for relative in loaded["scientific_review"]["checked_file_sha256"]:
        if relative not in selected:
            add(relative, "copy", "research_review_binding")
    for relative in ("configs/v2_freeze.json", "code/v2_reproduce.py", "code/v2_package_delivery.py", "manuscript_state.json"):
        add(relative, "copy", "delivery_entry")
    for folder in ("tables/v2", "paper/v2", "figures/v2"):
        base = child(root, folder)
        if base.exists():
            for path in (base.rglob("*") if folder == "figures/v2" else base.iterdir()):
                if path.is_file() and path.suffix.lower() in PUBLICATION_EXTENSIONS:
                    add(path.relative_to(root).as_posix(), "copy", "publication_asset")
    docs = child(root, "docs")
    for path in docs.iterdir():
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS and (
                "v2" in path.name.lower() or path.name in {"data_attribution.md", "reference_verification.md", "references.bib"}):
            add(path.relative_to(root).as_posix(), "copy", "attribution_and_references")
    evidence = child(root, "evidence/v2")
    for path in evidence.iterdir():
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS and path.name not in {
                "package_plan.json", "migration_receipt.json"}:
            add(path.relative_to(root).as_posix(), "copy", "v2_report")
    for directory in EVIDENCE_DIRS:
        base = evidence / directory
        if base.exists():
            for path in base.rglob("*"):
                if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
                    add(path.relative_to(root).as_posix(), "copy", "v2_evidence_history")
    for relative in extras:
        add(relative, "copy", "explicit_extra")
    if paths["active"]:
        for relative in ("configs/v2_active_gpu_amendment.json", "code/v2_active_gpu_results.py",
                         "code/test_v2_active_gpu_results.py"):
            if relative not in selected: add(relative, "copy", "active_execution_support")
    if child(root, "configs/v2_pixel_budget_plan.json").exists():
        bundle = verify_pixel_delivery(root)
        plan["pixel_budget_delivery_inventory"] = bundle
        plan["pixel_budget_guard_files"] = pixel_guard_inventory(root, bundle)
        for relative, checksum in sorted(bundle["file_sha256"].items()):
            require(sha(child(root, relative)) == checksum, "Pixel delivery dependency changed")
            if relative not in selected:
                add(relative, "copy", "pixel_budget_closed_execution_inventory")
            else:
                require(selected[relative]["sha256"] == checksum, "Shared pixel dependency differs")
        for relative in sorted(plan["pixel_budget_guard_files"]):
            add(relative, "copy", PIXEL_GUARD_ORIGIN)
    for pattern in ("v2*.py", "test_v2*.py"):
        for path in sorted(child(root, "code").glob(pattern)):
            relative = path.relative_to(root).as_posix()
            if relative not in selected: add(relative, "copy", "reproduction_source")
    operations = sorted(selected.values(), key=lambda entry: (entry["action"] == "move", entry["target"]))
    copy_bytes = sum(entry["bytes"] for entry in operations if entry["action"] == "copy")
    move_bytes = sum(entry["bytes"] for entry in operations if entry["action"] == "move")
    # Includes plan snapshot, write-ahead JSONL, destination receipt snapshot,
    # manifest, README, source activation receipt and temporary metadata room.
    metadata = 2_000_000 + 6 * len(raw(operations)) + 1000 * len(operations)
    reproduction_peak = max(child(root, relative).stat().st_size for relative in NUMERICAL) + 4_000_000
    plan.update(status="ready", storage_estimate_complete=True, operations=operations,
                copy_additional_bytes=copy_bytes, move_bytes_no_logical_increase=move_bytes,
                metadata_reservation_bytes=metadata,
                reproduction_temporary_reservation_bytes=reproduction_peak,
                estimated_project_logical_bytes_after=plan["root_logical_bytes_before"] + copy_bytes + metadata,
                estimated_project_peak_including_reproduction=plan["root_logical_bytes_before"] + copy_bytes + metadata + reproduction_peak)
    if plan["estimated_project_peak_including_reproduction"] >= CAP:
        plan.update(status="blocked", blocked_reason="COPY + metadata + real delivery reproduction peak exceeds2GB; no files deleted/moved")
    return plan


def save_plan(root, plan):
    destination = child(root, PLAN)
    data = raw(plan)
    ensure_capacity(root, len(data))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    require(not temporary.exists(), "Prior package-plan temporary exists; preserve/review before retry")
    write_new(root, temporary, data)
    temporary.replace(destination)


def append_event(root, ledger, event):
    reject_redirected_path(ledger)
    content = (json.dumps({"utc": utc(), **event}, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    ensure_capacity(root, len(content))
    charge_migration_write(root, len(content))
    with ledger.open("ab") as stream:
        stream.write(content); stream.flush(); os.fsync(stream.fileno())


def apply_actions(root, plan):
    """Reserve all known allocations; account each write with two root scans."""
    from v2_migration_budget import MigrationBudget
    global _MIGRATION_BUDGET
    require(_MIGRATION_BUDGET is None, "Nested migration is refused")
    allowance = plan["copy_additional_bytes"] + plan["metadata_reservation_bytes"] + plan.get("reproduction_temporary_reservation_bytes", 0)
    budget = MigrationBudget(project_root(root), allowance, CAP, logical_bytes)
    with budget:
        _MIGRATION_BUDGET = budget
        try:
            result = _apply_actions(root, plan)
        finally:
            _MIGRATION_BUDGET = None
    result["capacity_accounting"] = dict(budget.ledger)
    return result


def _apply_actions(root, plan):
    """Write-ahead migration engine; the public assemble entry rechecks gates."""
    root = project_root(root)
    dest = destination_path(root, plan["destination"])
    ensure_capacity(root, plan["copy_additional_bytes"] + plan["metadata_reservation_bytes"] +
                    plan.get("reproduction_temporary_reservation_bytes", 0))
    targets = [entry["target"] for entry in plan["operations"]]
    require(len(targets) == len(set(targets)), "Duplicate target in package plan")
    verify_feature_cache_operations(root, plan)
    verify_active_delivery(root, plan=plan)
    if child(root, "configs/v2_cuda_execution_plan.json").exists():
        from v2_cuda_delivery_inventory import verify_operations
        verify_operations(root, plan)
    verify_pixel_delivery(root, plan=plan)
    # Resolve and verify every source/target before any movement.
    for entry in plan["operations"]:
        source, output = checked_operation_paths(root, dest, entry)
        require(entry["source"] == entry["target"] and not output.exists(), "Relative paths must be preserved and targets absent")
        require(source.stat().st_size == entry["bytes"] and sha(source) == entry["sha256"], "Source changed since plan")
    attempt = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid.uuid4().hex[:8]
    receipt_dir = child(root, "evidence/v2/package_receipts")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    snapshot = receipt_dir / (attempt + ".plan.json")
    write_new(root, snapshot, raw(plan))
    ledger = receipt_dir / (attempt + ".jsonl")
    write_new(root, ledger, b"")
    append_event(root, ledger, {"event": "prepared", "destination": plan["destination"],
                              "plan_snapshot": snapshot.relative_to(root).as_posix(), "plan_sha256": sha(snapshot),
                              "recovery": "Never overwrite/delete/rollback automatically; inspect each planned source and target SHA"})
    dest.mkdir(parents=True, exist_ok=False)
    try:
        for index, entry in enumerate(plan["operations"]):
            source, output = checked_operation_paths(root, dest, entry)
            require(not output.exists(), "Target appeared during assembly; stop without overwrite")
            require(source.stat().st_size == entry["bytes"] and sha(source) == entry["sha256"], "Source changed during assembly")
            extra = entry["bytes"] if entry["action"] == "copy" else 0
            ensure_capacity(root, extra + 1024)
            append_event(root, ledger, {"event": "action_started", "index": index, "operation": entry})
            output.parent.mkdir(parents=True, exist_ok=True)
            if entry["action"] == "move":
                # Same-project rename only; no cross-device copy fallback.
                source.rename(output)
            else:
                charge_migration_write(root, entry["bytes"])
                with source.open("rb") as incoming, output.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
                    outgoing.flush(); os.fsync(outgoing.fileno())
            require(output.stat().st_size == entry["bytes"] and sha(output) == entry["sha256"], "Destination SHA/size mismatch")
            append_event(root, ledger, {"event": "verified", "index": index, "target": entry["target"], "sha256": entry["sha256"]})
        readme = ("# V2 author-review package\n\nThis directory is the active V2 root after migration. "
                  "Its v2/data files, exact192 frozen-index DINO NPZ caches and completed576 result/log/checkpoint references were moved here within the project, "
                  "without content changes. Source pending/failure/unreferenced history and the two historical V1 deliveries remain in the source project. "
                  "The source write-ahead migration ledger records each file's original relative path and SHA.\n\n"
                  "Run python -B code/v2_reproduce.py --root . for the tables gate; optional --mode reload first repeats that gate. "
                  "See docs/v2_reproduction_guide.md, docs/v2_packaging.md and the attribution documents. "
                  "This is an AUTHOR_REVIEW_PACKAGE, not submission-ready or authorized for public upload. "
                  "Unknown author metadata may still require author action.\n\n"
                  "delivery_manifest.json covers all delivered files except itself. "
                  "evidence/v2/package_migration_receipt.jsonl is the payload-completed ledger snapshot; "
                  "the source ledger additionally records the final manifest SHA, avoiding circular hashes.\n")
        if pipeline_paths(root)["active"]:
            readme = ("# V2 author-review package\n\nThe active core contains90 complete RTX4060 model executions and486 frozen-feature fits, "
                      "for576 conditions/runs in the fixed identity matrix. The72 completed CPU reference runs and27 equal-available-pixel supplemental runs "
                      "are separate evidence; the same90 GPU executions are not counted twice. The18 remaining CPU executions were replaced by their already "
                      "completed GPU identities at the user's request. This resource-directed amendment occurred after panel exposure; the active main display "
                      "is descriptive and is not a newly prospective confirmatory test. See configs/v2_active_gpu_amendment.json.\n\n"
                      "Start with paper/v2/manuscript.pdf and paper/v2/supplementary_material.pdf; editable Word files and JSON sources are alongside. "
                      "Use python -B code/v2_active_gpu_results.py --verify-tables to check the six numerical files without refitting. "
                      "The original CPU reference checkpoint has a separate72-image reload check; it is not an archived GPU checkpoint. "
                      "Data, exact192 frozen-feature caches, active results and CPU reference evidence preserve their original relative paths and hashes.\n\n"
                      "This is an AUTHOR_REVIEW_PACKAGE. Author identities, affiliations, funding, declarations and final human approval remain to be completed. "
                      "No submission, publication, payment or public data upload has been performed. Source attribution and unresolved dataset rights are documented in docs.\n\n"
                      "delivery_manifest.json covers every delivered file except itself. The source write-ahead ledger and migration receipt preserve the original locations.\n")
        write_new(root, child(dest, "README.md"), readme.encode("utf-8"))
        append_event(root, ledger, {"event": "payload_completed", "verified_files": len(plan["operations"]),
                                  "active_v2_root": plan["destination"]})
        write_new(root, child(dest, "evidence/v2/package_migration_receipt.jsonl"), ledger.read_bytes())
        entries = []
        for path in sorted(dest.rglob("*")):
            if path.is_file():
                checked = child(dest, path.relative_to(dest).as_posix())
                entries.append({"relative_path": checked.relative_to(dest).as_posix(),
                                "bytes": checked.stat().st_size, "sha256": sha(checked)})
        integrity = {"format": "v2-delivery-manifest-1", "created_utc": utc(), "release_scope": "AUTHOR_REVIEW_PACKAGE",
                     "self_excluded": "delivery_manifest.json", "files": entries,
                     "total_payload_bytes_excluding_self": sum(entry["bytes"] for entry in entries)}
        manifest = child(dest, "delivery_manifest.json")
        write_new(root, manifest, raw(integrity))
        append_event(root, ledger, {"event": "completed", "delivery_manifest_sha256": sha(manifest),
                                  "active_v2_root": plan["destination"], "project_logical_bytes": logical_bytes(root)})
        activation = {"status": "V2_ACTIVE_ROOT_MIGRATED", "created_utc": utc(), "destination": plan["destination"],
                      "source_ledger": ledger.relative_to(root).as_posix(), "source_ledger_sha256": sha(ledger),
                      "delivery_manifest_sha256": sha(manifest), "source_top_level_readme_changed": False,
                      "history": "Original V1 deliveries/raw files and unreferenced run history retained"}
        write_new(root, child(root, "evidence/v2/migration_receipt.json"), raw(activation))
        ensure_capacity(root, plan.get("reproduction_temporary_reservation_bytes", 0))
        return activation
    except BaseException as exc:
        try:
            append_event(root, ledger, {"event": "interrupted_or_failed", "type": type(exc).__name__, "message": str(exc),
                                      "policy": "Preserve source and destination; no automatic rollback or deletion"})
        except (OSError, ValueError):
            pass
        raise


def assemble(root, no_writers):
    require(no_writers, "Manual --assemble requires --confirm-no-writers after all source writers have stopped")
    require(not child(root, "evidence/v2/migration_receipt.json").exists(), "A completed migration receipt already exists")
    saved = read(child(root, PLAN))
    require(saved.get("status") == "ready" and saved.get("packager_sha256") == sha(Path(__file__)), "A current ready plan is required")
    fresh = build_plan(root, saved["destination"], saved["extra_includes"])
    require(fresh["status"] == "ready" and fresh["operations"] == saved["operations"] and fresh["gates"] == saved["gates"],
            "Inputs, review, outputs or inventory changed since plan; prepare a new plan before any MOVE")
    require(fresh.get("cuda_delivery_inventory") == saved.get("cuda_delivery_inventory"),
            "CUDA terminal delivery inventory changed since plan")
    require(fresh.get("pixel_budget_delivery_inventory") == saved.get("pixel_budget_delivery_inventory"),
            "Pixel terminal delivery inventory changed since plan")
    require(fresh.get("pixel_budget_guard_files") == saved.get("pixel_budget_guard_files") and
            fresh.get("active_bundle_binding") == saved.get("active_bundle_binding"),
            "Active bundle or pixel mutex markers changed since plan")
    require(not list(child(root, "v2/data").rglob("*.lock")), "Preparation writer lock remains")
    return apply_actions(root, fresh)


def receipt_status(root, relative):
    ledger = child(root, relative)
    events = [json.loads(line) for line in ledger.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    prepared = events[0]
    snapshot = child(root, prepared["plan_snapshot"])
    require(sha(snapshot) == prepared["plan_sha256"], "Recovery plan snapshot SHA mismatch")
    plan = read(snapshot)
    dest = child(root, plan["destination"])
    rows = []
    for entry in plan["operations"]:
        item = {key: entry[key] for key in ("source", "target", "action", "sha256")}
        for key, path in (("source", child(root, entry["source"])), ("target", child(dest, entry["target"]))):
            item[key + "_exists"] = path.is_file()
            item[key + "_sha_matches"] = path.is_file() and sha(path) == entry["sha256"]
        rows.append(item)
    return {"destination": plan["destination"], "last_event": events[-1], "files": rows,
            "policy": "Read-only recovery report; no resume, deletion or rollback performed"}


def validate_refreshed_evidence(dest, old_entries):
    """Accept only current, fully bound reproduction evidence after migration."""
    checks, loaded = gates(dest)
    paths = pipeline_paths(dest)
    require(all(item["passed"] for item in checks), "Delivery completion/reload/reproduction/review/paper gates no longer pass")
    verify_active_delivery(dest)
    freeze, audit, reproduction, reload = [loaded[key] for key in ("freeze", "runs", "reproduction", "reload")]
    require(len(freeze["file_sha256"]) == 53, "Expected unchanged53-file freeze")
    verify_map(dest, freeze["file_sha256"], "Delivered frozen dependency")
    feature_cache_inventory(dest)
    if child(dest, "configs/v2_cuda_execution_plan.json").exists():
        from v2_cuda_delivery_inventory import build_inventory
        delivered_cuda = build_inventory(dest)
        for entry in delivered_cuda["files"]:
            require(entry["relative_path"] in old_entries and
                    old_entries[entry["relative_path"]]["sha256"] == entry["sha256"] and
                    old_entries[entry["relative_path"]]["bytes"] == entry["bytes"],
                    "Immutable CUDA evidence differs from delivery manifest")
    verify_pixel_delivery(dest, old_entries=old_entries)
    require(audit["audit_code_sha256"] == sha(child(dest, paths["audit_code"])), "Refreshed audit code binding differs")
    for name in ("inputs", "artifacts", "results"):
        verify_map(dest, audit[name], "Refreshed audit " + name)
    inventory = current_core_results(dest, paths["active"])
    require(inventory == set(audit["results"]) and len(inventory) == 576, "Refreshed run inventory is not exact576")
    freeze_sha = sha(child(dest, "configs/v2_freeze.json"))
    require(reproduction.get("freeze_sha256") == reload.get("freeze_sha256") == freeze_sha,
            "Refreshed reproduction/reload freeze differs")
    require(reproduction.get("wrapper_code_sha256") == sha(child(dest, paths["wrapper"])) and
            reproduction.get("audit_report_sha256") == sha(child(dest, paths["audit"])) and
            reproduction.get("result_sha256") == audit["results"] and
            reproduction.get("frozen_input_sha256") == freeze["file_sha256"], "Refreshed reproduction identity differs")
    numerical = {name: sha(child(dest, name)) for name in NUMERICAL}
    require(all(name in old_entries and old_entries[name]["sha256"] == checksum for name, checksum in numerical.items()),
            "Numerical outputs differ from the previous delivery manifest")
    require(reproduction.get("numerical_outputs_before_sha256") == reproduction.get("numerical_outputs_after_sha256") == numerical,
            "Refreshed reproduction did not preserve all six numerical SHA values")
    analysis = read(child(dest, "tables/v2/analysis_identity.json"))
    require(analysis.get("audit_sha256") == sha(child(dest, paths["audit"])) and
            analysis.get("analysis_code_sha256") == sha(child(dest, paths["analysis_code"])) and
            analysis.get("audit_code_sha256") == audit["audit_code_sha256"] and
            analysis.get("result_sha256") == audit["results"] and analysis.get("audited_input_sha256") == audit["inputs"] and
            analysis.get("audited_artifact_sha256") == audit["artifacts"] and analysis.get("output_sha256") == numerical,
            "Refreshed analysis audit/input/artifact/result/output bindings differ")
    expected_counts = {"fits": 576, "conditions_by_source": 192, "conditions": 64, "regions_rows": 1536, "classes_rows": 512}
    require(analysis.get("counts") == expected_counts and reproduction.get("validated_counts") == expected_counts,
            "Refreshed analysis/reproduction matrix counts differ")
    predetermined = "evidence/v2/runs/resnet18_unet/source0_skewed5_1_b12_s0_i0_region_kcenter/result.json"
    reference_results = audit.get("cpu_reference_result_files", {}) if paths["active"] else audit["results"]
    reference_files = audit.get("cpu_reference_files", {}) if paths["active"] else {}
    if paths["active"]:
        require(len(reference_results) == 72 and set(reference_results) <= reference_files.keys(), "Refreshed CPU reference count differs")
        verify_map(dest, reference_files, "Refreshed preserved CPU reference")
    require(reload.get("result_sha256") == reference_results.get(predetermined) and
            reload.get("verifier_sha256") == freeze["file_sha256"].get("code/v2_reload_checkpoint.py") and
            reload.get("model_code_sha256") == freeze["file_sha256"].get("code/v2_segmentation.py") and
            reload.get("manifest_sha256") == freeze["file_sha256"].get("v2/data/manifest.json") and
            reload.get("checkpoint_sha256") in set(audit["artifacts"].values()) | set(reference_files.values()) and
            reload.get("expected_confusion_digest") == reload.get("reloaded_confusion_digest") and
            reload.get("checkpoint_predetermined_not_score_selected") is True, "Refreshed reload bindings differ")
    return {"freeze_sha256": freeze_sha, "reproduction_sha256": sha(child(dest, paths["reproduction"])),
            "run_audit_sha256": sha(child(dest, paths["audit"])), "counts": expected_counts}


def replace_metadata(root, path, content):
    temporary = path.with_suffix(path.suffix + ".refresh.tmp")
    require(not temporary.exists(), "Prior refresh temporary exists; retain and inspect before retry")
    write_new(root, temporary, content)
    temporary.replace(path)


def refresh_manifest(root, destination=DEFAULT_DESTINATION):
    root = project_root(root)
    dest = child(root, destination)
    require(dest.parent == child(root, "delivery") and dest.name.startswith("RemoteSensing_GeographicSelection_V2") and dest.is_dir(),
            "Refresh requires an assembled V2 directory within this source project")
    activation_path = child(root, "evidence/v2/migration_receipt.json")
    activation = read(activation_path)
    require(activation.get("status") == "V2_ACTIVE_ROOT_MIGRATED" and activation.get("destination") == destination,
            "Source migration receipt does not identify this delivery")
    ledger = child(root, activation["source_ledger"])
    require(ledger.is_relative_to(child(root, "evidence/v2/package_receipts")) and
            sha(ledger) == activation["source_ledger_sha256"], "Source migration ledger differs from its receipt")
    events = [json.loads(line) for line in ledger.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    require(events and events[0].get("event") == "prepared" and events[0].get("destination") == destination and
            events[-1].get("event") in {"completed", "manifest_refreshed"}, "Ledger does not show a completed assembly/refresh")
    manifest_path = child(dest, "delivery_manifest.json")
    previous_sha = sha(manifest_path)
    require(previous_sha == activation["delivery_manifest_sha256"] == events[-1]["delivery_manifest_sha256"],
            "Manifest SHA does not match latest source ledger/receipt")
    prior = read(manifest_path)
    require(prior.get("format") == "v2-delivery-manifest-1" and prior.get("self_excluded") == "delivery_manifest.json",
            "Not this tool's delivery manifest")
    old_entries = {item["relative_path"]: item for item in prior["files"]}
    require(len(old_entries) == len(prior["files"]) and "delivery_manifest.json" not in old_entries,
            "Invalid or duplicate previous manifest inventory")
    actual = {path.relative_to(dest).as_posix() for path in dest.rglob("*")
              if path.is_file() and path != manifest_path}
    require(actual == set(old_entries), "Missing or unexpected delivery files; refresh cannot accept inventory changes")
    entries, changes = [], []
    for name, old in sorted(old_entries.items()):
        path = child(dest, name)
        item = {"relative_path": name, "bytes": path.stat().st_size, "sha256": sha(path)}
        if item != old:
            require(name in OPERATIONAL_REPORTS, "Immutable delivery file changed: " + name)
            changes.append({"relative_path": name, "previous_sha256": old["sha256"], "sha256": item["sha256"]})
        entries.append(item)
    proof = validate_refreshed_evidence(dest, old_entries)
    # Recheck after evidence validation: no concurrent writer may alter inventory.
    require(actual == {path.relative_to(dest).as_posix() for path in dest.rglob("*")
                       if path.is_file() and path != manifest_path}, "Delivery inventory changed during refresh verification")
    verify_map(dest, {item["relative_path"]: item["sha256"] for item in entries}, "Refresh final inventory")
    backup = ledger.with_name(ledger.stem + ".manifest." + previous_sha + ".json")
    if backup.exists():
        require(sha(backup) == previous_sha, "Previous-manifest backup differs")
    else:
        write_new(root, backup, manifest_path.read_bytes())
    append_event(root, ledger, {"event": "manifest_refresh_started", "previous_manifest_sha256": previous_sha,
                              "previous_manifest_backup": backup.relative_to(root).as_posix(), "operational_changes": changes})
    refreshed = {**prior, "refreshed_utc": utc(), "previous_manifest_sha256": previous_sha,
                 "files": entries, "total_payload_bytes_excluding_self": sum(item["bytes"] for item in entries),
                 "refresh_evidence": proof, "operational_changes": changes}
    replace_metadata(root, manifest_path, raw(refreshed))
    manifest_sha = sha(manifest_path)
    append_event(root, ledger, {"event": "manifest_refreshed", "previous_manifest_sha256": previous_sha,
                              "delivery_manifest_sha256": manifest_sha, "active_v2_root": destination})
    history = list(activation.get("manifest_lineage", []))
    history.append({"sha256": previous_sha, "backup": backup.relative_to(root).as_posix()})
    activation.update(delivery_manifest_sha256=manifest_sha, source_ledger_sha256=sha(ledger),
                      manifest_refreshed_utc=utc(), manifest_lineage=history)
    replace_metadata(root, activation_path, raw(activation))
    return {"passed": True, "destination": destination, "previous_manifest_sha256": previous_sha,
            "delivery_manifest_sha256": manifest_sha, "operational_changes": changes}


class FixtureChecks(unittest.TestCase):
    @staticmethod
    def feature_fixture(root):
        """Synthetic byte fixtures, not decoded NPZ or scientific arrays."""
        pairs, indexes = [], {}
        for index_name, (count, role) in FEATURE_INDEXES.items():
            entries = []
            for number in range(count):
                region = ("old" if role == "old_development" else "new") + str(number // (5 if role == "old_development" else 3))
                identifier = region + "__image" + str(number)
                path = child(root, (Path(index_name).parent / (identifier + ".npz")).as_posix())
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic NPZ byte identity, not arrays: " + identifier.encode())
                pair = {"id": identifier, "region": region, "role": role,
                        "source_rgb": {"sha256": "a" * 64}, "source_label": {"sha256": "b" * 64},
                        "rgb": {"sha256": "c" * 64}}
                entry = {"id": identifier, "region": region, "cache": path.name, "cache_sha256": sha(path)}
                if role == "old_development":
                    entry.update(source_rgb_sha256="a" * 64, source_label_sha256="b" * 64)
                else:
                    entry.update(processed_rgb_sha256="c" * 64)
                pairs.append(pair); entries.append(entry)
            indexes[index_name] = {"status": "complete", "records": entries}
        manifest = child(root, "v2/data/manifest.json"); manifest.parent.mkdir(parents=True)
        manifest.write_bytes(raw({"status": "complete", "whole_v2_dataset_complete": True, "pairs": pairs}))
        mapping = {"v2/data/manifest.json": sha(manifest)}
        for name, index in indexes.items():
            if name.startswith("v2/"):
                index["identity"] = {"manifest_sha256": mapping["v2/data/manifest.json"]}
            child(root, name).write_bytes(raw(index)); mapping[name] = sha(child(root, name))
        # Remaining freeze entries are small synthetic immutable dependencies.
        for number in range(50):
            name = f"code/synthetic_dependency_{number}.py"
            path = child(root, name); path.parent.mkdir(exist_ok=True); path.write_bytes(b"# synthetic\n")
            mapping[name] = sha(path)
        freeze = child(root, "configs/v2_freeze.json"); freeze.parent.mkdir()
        freeze.write_bytes(raw({"status": "FROZEN_BEFORE_NEW_PANEL_EVALUATION", "expected_total_runs": 576,
                                "file_sha256": mapping}))

    def test_exact_feature_inventory_and_move_accounting_v1_retention(self):
        with tempfile.TemporaryDirectory(prefix="v2-feature-inventory-") as directory:
            root = Path(directory).resolve(); self.feature_fixture(root)
            inventory = feature_cache_inventory(root)
            self.assertEqual(inventory["file_count"], 192)
            self.assertEqual([v["verified_count"] for v in inventory["indexes"].values()], [120, 72])
            self.assertEqual(inventory["logical_byte_increase"], 0)
            protected = {"delivery/RemoteSensing_GeographicSelection/old.npz": b"protected V1",
                         "delivery/RemoteSensing_GeographicSelection.zip": b"protected V1 ZIP",
                         "cache/unrelated/retain.npz": b"unrelated cache must stay",
                         "data/formal120/retain.tif": b"native TIFF must stay"}
            for name, content in protected.items():
                path = child(root, name); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
            self.assertEqual(feature_cache_inventory(root), inventory)
            operations = [{"source": f["relative_path"], "target": f["relative_path"], "action": "move",
                           "origin": FEATURE_ORIGIN, "bytes": f["bytes"], "sha256": f["sha256"]}
                          for f in inventory["files"]]
            for name in (*FEATURE_INDEXES, "configs/v2_freeze.json", "v2/data/manifest.json"):
                operations.insert(0, {"source": name, "target": name,
                                      "action": "move" if name.startswith("v2/data/") else "copy",
                                      "origin": "compact_data" if name.startswith("v2/data/") else "frozen_dependency",
                                      "bytes": child(root, name).stat().st_size, "sha256": sha(child(root, name))})
            copy_bytes = sum(e["bytes"] for e in operations if e["action"] == "copy")
            before = logical_bytes(root)
            plan = {"destination": DEFAULT_DESTINATION, "operations": operations,
                    "feature_cache_inventory": inventory, "copy_additional_bytes": copy_bytes,
                    "metadata_reservation_bytes": 2_000_000, "reproduction_temporary_reservation_bytes": 4_000_000}
            with self.assertRaisesRegex(ValueError, "exact192"):
                apply_actions(root, {**plan, "operations": operations[:-1]})
            apply_actions(root, plan)
            dest = child(root, DEFAULT_DESTINATION)
            self.assertEqual(feature_cache_inventory(dest), inventory)
            for f in inventory["files"]:
                self.assertFalse(child(root, f["relative_path"]).exists())
                self.assertEqual(sha(child(dest, f["relative_path"])), f["sha256"])
            for name, content in protected.items():
                self.assertEqual(child(root, name).read_bytes(), content)
            # Every increase is COPY plus generated metadata, never cache bytes.
            moved_size = sum(e["bytes"] for e in operations if e["action"] == "move")
            self.assertGreater(moved_size, inventory["total_bytes"])
            self.assertEqual(inventory["total_bytes"], sum(f["bytes"] for f in inventory["files"]))
            added = logical_bytes(root) - before
            metadata_bytes = (sum(p.stat().st_size for p in child(root, "evidence/v2/package_receipts").iterdir()) +
                              child(root, "evidence/v2/migration_receipt.json").stat().st_size +
                              child(dest, "README.md").stat().st_size + child(dest, "delivery_manifest.json").stat().st_size +
                              child(dest, "evidence/v2/package_migration_receipt.jsonl").stat().st_size)
            self.assertEqual(added, copy_bytes + metadata_bytes)

    def test_feature_inventory_rejects_wrong_sha_missing_duplicates_and_escape(self):
        with tempfile.TemporaryDirectory(prefix="v2-feature-rejection-") as directory:
            root = Path(directory).resolve(); self.feature_fixture(root)
            name = next(iter(FEATURE_INDEXES)); indexpath = child(root, name)
            pristine = indexpath.read_bytes(); original = read(indexpath)
            cached = child(root, (Path(name).parent / original["records"][0]["cache"]).as_posix())
            content = cached.read_bytes(); cached.write_bytes(content + b"changed")
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                feature_cache_inventory(root)
            cached.unlink()
            with self.assertRaisesRegex(ValueError, "Missing feature cache"):
                feature_cache_inventory(root)
            cached.write_bytes(content)
            def replace_index(value):
                indexpath.write_bytes(raw(value))
                fpath = child(root, "configs/v2_freeze.json"); freeze = read(fpath)
                freeze["file_sha256"][name] = sha(indexpath); fpath.write_bytes(raw(freeze))
            for case in ("duplicate_id", "duplicate_path", "traversal", "absolute", "wrong_source"):
                bad = json.loads(pristine)
                if case == "duplicate_id": bad["records"][1] = dict(bad["records"][0])
                elif case == "duplicate_path": bad["records"][1]["cache"] = bad["records"][0]["cache"]
                elif case == "traversal": bad["records"][0]["cache"] = "../../../delivery/V1/protected.npz"
                elif case == "absolute": bad["records"][0]["cache"] = "C:/protected.npz"
                else: bad["records"][0]["source_label_sha256"] = "d" * 64
                replace_index(bad)
                with self.subTest(case=case), self.assertRaises(ValueError):
                    feature_cache_inventory(root)
            replace_index(original)
            extra = cached.parent / "unlisted.npz"; extra.write_bytes(b"unlisted")
            with self.assertRaisesRegex(ValueError, "Unlisted NPZ"):
                feature_cache_inventory(root)
            for name in ("cache/unrelated/unlisted.npz", "v2/cache/other/unlisted.npz",
                         "cache/dinov2-formal120/nested/unlisted.npz"):
                with self.subTest(scope=name), self.assertRaises(ValueError):
                    source_allowed(name, "move", FEATURE_ORIGIN)

    def test_feature_inventory_rejects_stale_freeze_index_and_redirect(self):
        with tempfile.TemporaryDirectory(prefix="v2-feature-binding-") as directory:
            root = Path(directory).resolve(); self.feature_fixture(root)
            name = next(iter(FEATURE_INDEXES)); path = child(root, name); content = path.read_bytes()
            path.write_bytes(content + b" ")
            with self.assertRaisesRegex(ValueError, "index differs from freeze"):
                feature_cache_inventory(root)
            path.write_bytes(content)
            target = path.parent / read(path)["records"][0]["cache"]
            victim = child(root, "delivery/RemoteSensing_GeographicSelection/protected.npz")
            victim.parent.mkdir(parents=True); victim.write_bytes(target.read_bytes())
            original = target.read_bytes(); target.unlink()
            try:
                target.symlink_to(victim)
            except (OSError, NotImplementedError):
                target.write_bytes(original)
                self.skipTest("Platform does not permit feature-cache symlink fixtures; shared junction regression remains active")
            with self.assertRaisesRegex(ValueError, "symlink/junction"):
                feature_cache_inventory(root)
            self.assertEqual(victim.read_bytes(), original)

    def test_research_review_is_bound_to_manuscript_and_numbers(self):
        with tempfile.TemporaryDirectory(prefix="v2-review-fixture-") as directory:
            root = Path(directory).resolve()
            for name in PAPER + NUMERICAL:
                path = child(root, name); path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("synthetic version: " + name).encode())
            review = {"passed": True, "release_recommendation": "AUTHOR_REVIEW_PACKAGE",
                      "checked_file_sha256": {name: sha(child(root, name)) for name in PAPER + NUMERICAL}}
            verify_research_review(root, review)
            for name in (PAPER[0], NUMERICAL[0]):
                path = child(root, name); content = path.read_bytes(); path.write_bytes(content + b"changed after review")
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "checked-file SHA mismatch"):
                    verify_research_review(root, review)
                path.write_bytes(content)
            for name in ("unknown.json", "../outside.json"):
                bad = {**review, "checked_file_sha256": {**review["checked_file_sha256"], name: "a" * 64}}
                with self.subTest(name=name), self.assertRaises(ValueError):
                    verify_research_review(root, bad)

    def test_symlink_source_cannot_move_protected_content(self):
        with tempfile.TemporaryDirectory(prefix="v2-alias-fixture-") as directory:
            root = Path(directory).resolve()
            victim = child(root, "delivery/RemoteSensing_GeographicSelection/victim.pdf")
            victim.parent.mkdir(parents=True); victim.write_bytes(b"immutable V1 PDF fixture")
            alias = root / "v2/data/panel/apparent.png"; alias.parent.mkdir(parents=True)
            try:
                alias.symlink_to(victim)
            except (OSError, NotImplementedError):
                self.skipTest("Platform does not permit symbolic-link fixtures")
            plan = {"destination": DEFAULT_DESTINATION,
                    "operations": [{"source": "v2/data/panel/apparent.png", "target": "v2/data/panel/apparent.png",
                                    "action": "move", "origin": "compact_data", "bytes": victim.stat().st_size, "sha256": sha(victim)}],
                    "copy_additional_bytes": 0, "metadata_reservation_bytes": 10000}
            with self.assertRaisesRegex(ValueError, "symlink/junction"):
                apply_actions(root, plan)
            self.assertEqual(victim.read_bytes(), b"immutable V1 PDF fixture")
            self.assertFalse((root / DEFAULT_DESTINATION).exists())

    def test_name_surrogate_rejected_but_cloud_placeholder_allowed(self):
        from types import SimpleNamespace
        cloud = SimpleNamespace(st_mode=stat.S_IFDIR, st_reparse_tag=0x9000001A)
        junction = SimpleNamespace(st_mode=stat.S_IFDIR, st_reparse_tag=0xA0000003)
        with patch(__name__ + ".os.lstat", return_value=cloud):
            reject_redirected_path(Path.cwd() / "synthetic_cloud_placeholder")
        with patch(__name__ + ".os.lstat", return_value=junction), self.assertRaisesRegex(ValueError, "name-surrogate"):
            reject_redirected_path(Path.cwd() / "synthetic_junction")

    def test_windows_junction_ancestor_cannot_move_v1(self):
        if os.name != "nt":
            self.skipTest("Windows junction fixture")
        import subprocess
        with tempfile.TemporaryDirectory(prefix="v2-junction-fixture-") as directory:
            root = Path(directory).resolve()
            protected = root / "delivery/RemoteSensing_GeographicSelection"; protected.mkdir(parents=True)
            victim = protected / "victim.png"; victim.write_bytes(b"protected V1 fixture")
            alias = root / "v2/data/panel"; alias.parent.mkdir(parents=True)
            command = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(alias), str(protected)],
                                     capture_output=True, check=False)
            if command.returncode != 0:
                self.skipTest("Platform did not permit a temporary junction")
            entry = {"source": "v2/data/panel/victim.png", "target": "v2/data/panel/victim.png",
                     "action": "move", "origin": "compact_data", "bytes": victim.stat().st_size, "sha256": sha(victim)}
            with self.assertRaisesRegex(ValueError, "symlink/junction|Delivery/V1"):
                apply_actions(root, {"destination": DEFAULT_DESTINATION, "operations": [entry],
                                     "copy_additional_bytes": 0, "metadata_reservation_bytes": 10000})
            self.assertEqual(victim.read_bytes(), b"protected V1 fixture")
            self.assertFalse((root / DEFAULT_DESTINATION).exists())

    def test_compact_inventory_moves_only_manifest_references(self):
        with tempfile.TemporaryDirectory(prefix="v2-compact-inventory-") as directory:
            root = Path(directory).resolve(); base = root / "v2/data"; base.mkdir(parents=True)
            pairs = []
            for number in range(192):
                record = {"id": f"fixture__{number}"}
                for kind in ("rgb", "label", "metadata"):
                    name = f"fixture/{number}_{kind}" + (".json" if kind == "metadata" else ".png")
                    path = base / name; path.parent.mkdir(exist_ok=True); path.write_bytes(b"synthetic")
                    record[kind] = {"relative_path": name, "bytes": path.stat().st_size, "sha256": sha(path)}
                pairs.append(record)
            (base / "manifest.json").write_bytes(raw({"status": "complete", "whole_v2_dataset_complete": True, "pairs": pairs}))
            (base / "unreferenced.png").write_bytes(b"retain")
            (base / "unreferenced.tif").write_bytes(b"retain original")
            approved, excluded = compact_data_inventory(root)
            self.assertEqual(len(approved), 192 * 3 + 1)
            self.assertEqual({item["path"] for item in excluded}, {"v2/data/unreferenced.png", "v2/data/unreferenced.tif"})

    def test_move_sha_receipt_manifest_v1_retention_and_duplicate_destination(self):
        with tempfile.TemporaryDirectory(prefix="v2-package-fixture-") as directory:
            root = Path(directory).resolve()
            values = {"v2/data/panel/example.png": b"synthetic compact fixture", "code/example.py": b"# fixture\n",
                      "delivery/RemoteSensing_GeographicSelection/keep.bin": b"historical V1 immutable",
                      "delivery/RemoteSensing_GeographicSelection.zip": b"historical V1 ZIP immutable",
                      "evidence/v2/runs/synthetic/pending.json": b"unreferenced failed history"}
            for name, content in values.items():
                path = child(root, name); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
            entries = [{"source": name, "target": name, "action": action, "origin": origin,
                        "bytes": len(values[name]), "sha256": sha(child(root, name))}
                       for name, action, origin in (("code/example.py", "copy", "explicit_extra"),
                                                    ("v2/data/panel/example.png", "move", "compact_data"))]
            plan = {"destination": DEFAULT_DESTINATION, "operations": entries,
                    "copy_additional_bytes": len(values["code/example.py"]), "metadata_reservation_bytes": 100000}
            with self.assertRaisesRegex(ValueError, "Duplicate target"):
                apply_actions(root, {**plan, "operations": entries + entries[:1]})
            activation = apply_actions(root, plan)
            dest = child(root, DEFAULT_DESTINATION)
            self.assertFalse(child(root, entries[1]["source"]).exists())
            self.assertEqual(sha(child(dest, entries[1]["target"])), entries[1]["sha256"])
            for name in values:
                if name.startswith("delivery/") or name.endswith("pending.json"):
                    self.assertEqual(child(root, name).read_bytes(), values[name])
            manifest = read(child(dest, "delivery_manifest.json"))
            self.assertFalse(any(entry["relative_path"] == "delivery_manifest.json" for entry in manifest["files"]))
            verify_map(dest, {entry["relative_path"]: entry["sha256"] for entry in manifest["files"]}, "Fixture package")
            status = receipt_status(root, activation["source_ledger"])
            self.assertTrue(all(entry["target_sha_matches"] for entry in status["files"]))
            with self.assertRaisesRegex(ValueError, "already exists"):
                apply_actions(root, plan)

    def test_refresh_only_operational_files_and_preserve_lineage(self):
        # This isolates inventory/receipt policy; the real full576 evidence
        # verifier is not bypassable by the CLI and is separately required.
        with tempfile.TemporaryDirectory(prefix="v2-package-fixture-") as directory:
            root = Path(directory).resolve()
            values = {"code/immutable.py": b"# immutable fixture\n", "tables/v2/conditions.csv": b"numeric fixture\n",
                      "evidence/v2/reproduction_check.json": b'{"synthetic":1}\n'}
            for name, content in values.items():
                path = child(root, name); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
            operations = [{"source": name, "target": name, "action": "copy", "origin": "explicit_extra",
                           "bytes": len(content), "sha256": sha(child(root, name))} for name, content in values.items()]
            # Numeric CSV is an approved publication asset rather than extra code.
            operations[1]["origin"] = "publication_asset"
            plan = {"destination": DEFAULT_DESTINATION, "operations": operations,
                    "copy_additional_bytes": sum(map(len, values.values())), "metadata_reservation_bytes": 100000}
            apply_actions(root, plan)
            dest = child(root, DEFAULT_DESTINATION)
            operational = child(dest, "evidence/v2/reproduction_check.json")
            operational.write_bytes(b'{"synthetic":2}\n')
            old_sha = sha(child(dest, "delivery_manifest.json"))
            snapshot = sha(child(dest, "evidence/v2/package_migration_receipt.jsonl"))
            with patch(__name__ + ".validate_refreshed_evidence", return_value={"fixture_policy_only": True}):
                result = refresh_manifest(root)
                self.assertEqual(result["previous_manifest_sha256"], old_sha)
                self.assertEqual(sha(child(dest, "evidence/v2/package_migration_receipt.jsonl")), snapshot)
                self.assertEqual(read(child(root, "evidence/v2/migration_receipt.json"))["manifest_lineage"][-1]["sha256"], old_sha)
                for name in ("tables/v2/conditions.csv", "code/immutable.py"):
                    path = child(dest, name); original = path.read_bytes(); path.write_bytes(original + b"changed")
                    with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Immutable delivery file changed"):
                        refresh_manifest(root)
                    path.write_bytes(original)
                extra = child(dest, "unexpected.txt"); extra.write_bytes(b"unexpected")
                with self.assertRaisesRegex(ValueError, "unexpected delivery files"):
                    refresh_manifest(root)

    def test_cap_boundaries_and_v1_scope(self):
        global CAP
        with tempfile.TemporaryDirectory(prefix="v2-package-fixture-") as directory:
            root = Path(directory).resolve()
            path = child(root, "code/example.py"); path.parent.mkdir(); path.write_bytes(b"x" * 10)
            old_cap = CAP
            try:
                CAP = 20
                with self.assertRaisesRegex(ValueError, "cap refused"):
                    ensure_capacity(root, 10)
                ensure_capacity(root, 9)
            finally:
                CAP = old_cap
            for name in ("../escape", "C:/outside", "some\\path"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    child(root, name)
            for name in ("delivery/RemoteSensing_GeographicSelection/keep.pdf", "paper/manuscript.pdf",
                         "cache/dinov2-formal120/feature.npz", "data/formal120/native.tif"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    source_allowed(name, "copy", "explicit_extra")
            with self.assertRaises(ValueError):
                source_allowed("code/example.py", "move", "explicit_extra")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="Default: write only evidence/v2/package_plan.json")
    mode.add_argument("--assemble", action="store_true", help="Manual execution of a current ready plan after author-review gates")
    mode.add_argument("--refresh-manifest", action="store_true", help="Explicitly accept only fully verified operational report changes after independent delivery reproduction")
    mode.add_argument("--status", metavar="SOURCE_LEDGER", help="Read-only migration location/SHA report from a project-relative receipt")
    parser.add_argument("--destination", default=DEFAULT_DESTINATION)
    parser.add_argument("--include", action="append", default=[], help="Explicit extra small-file relative path, still subject to scope exclusions")
    parser.add_argument("--confirm-no-writers", action="store_true", help="Parent/maintainer assertion after checking source writer sessions have stopped; not an additional user approval")
    parser.add_argument("--self-test", action="store_true", help="Isolated temporary fixtures only, no actual assembly")
    args = parser.parse_args(argv)
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FixtureChecks))
        return 0 if result.wasSuccessful() else 1
    root = args.root
    try:
        if args.status:
            print(json.dumps(receipt_status(root, args.status), indent=2)); return 0
        if args.refresh_manifest:
            print(json.dumps(refresh_manifest(root, args.destination), indent=2)); return 0
        if args.assemble:
            print(json.dumps(assemble(root, args.confirm_no_writers), indent=2)); return 0
        plan = build_plan(root, args.destination, args.include)
        save_plan(root, plan)
        print(json.dumps({key: value for key, value in plan.items() if key != "operations"}, indent=2))
        return 0 if plan["status"] == "ready" else 1
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(f"PACKAGE STOPPED: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

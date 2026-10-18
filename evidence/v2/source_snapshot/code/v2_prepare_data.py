"""Prepare the fixed v2 development data and new permanent panel as compact PNGs.

--plan reads only manifests and the remote ZIP directory. --prepare first checks
the full 200 MB reservation, verifies original bytes in RAM, and then writes
448-square PNGs plus provenance. It never writes an original TIFF to disk.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import queue
import shutil
import sys
import tempfile
import threading
import zipfile
import zlib

import numpy as np
from PIL import Image
import PIL
import data_access as remote_zip
import geography_audit as geography

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "v2" / "data"
SOFTWARE_ROOT = ROOT / "evidence" / "v2" / "software"
OLD_MANIFEST = ROOT / "data" / "formal120" / "manifest.json"
SOURCE_URL = remote_zip.SOURCE_URL
NEW_REGIONS = (
    "abancay", "al_qurnah", "baybay", "bielefeld", "buenos_aires", "chiclayo",
    "coxsbazar", "dowa", "kagera", "kampala", "khartoum", "kinshasa", "kitsap",
    "monrovia", "ngaoundere", "paris", "rosario", "san_tome", "soriano", "svaneti",
    "tokyo", "tyrolw", "western", "zanzibar",
)
NEW_SEED = 2026101802
SIDE = 448
PAIR_LIMIT = 900_000
DATA_RESERVATION = 200_000_000
PROJECT_LIMIT = 2_000_000_000
MEMBER_RAM_LIMIT = 64_000_000
GEOTIFF_TAGS = (33550, 33922, 34264, 34735, 34736, 34737, 42112, 42113, 50844)
CLAIMS = [
    "Geographic bounds come from declared TIFF metadata and offline transformations, not surveyed ground truth.",
    "A supported transform or absence of a bbox intersection does not prove independence of original source mosaics or absence of leakage.",
    "Unknown CRS, missing georeferences, area-of-use cautions and failed transforms are retained; no sample is replaced.",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def disk_bytes(path):
    return sum(item.stat().st_size for item in path.rglob("*")
               if item.is_file() and not item.is_symlink()) if path.exists() else 0


def reserve_check():
    outside = disk_bytes(ROOT) - disk_bytes(DATA_ROOT)
    if outside + DATA_RESERVATION >= PROJECT_LIMIT:
        raise RuntimeError(f"Full compact-data reservation refused: {outside:,} project bytes outside v2/data + "
                           f"{DATA_RESERVATION:,} reserved bytes must stay below {PROJECT_LIMIT:,}. "
                           "Keep all evidence; do not reduce resolution/sample count automatically.")
    if disk_bytes(DATA_ROOT) >= DATA_RESERVATION:
        raise RuntimeError("Existing v2/data already reaches the 200 MB reservation")


def inside_data(path):
    resolved = path.resolve()
    if not resolved.is_relative_to(DATA_ROOT.resolve()):
        raise ValueError("All compact-data output must stay under v2/data")
    return resolved


def member_path(base, relative):
    path = base.joinpath(*remote_zip.safe_member_path(relative).parts)
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError("Member path escapes its data root")
    return path


def current_bindings():
    return {
        "conversion_code_sha256": sha_file(Path(__file__)),
        "data_access_code_sha256": sha_file(Path(remote_zip.__file__)),
        "geography_audit_code_sha256": sha_file(Path(geography.__file__)),
        "original_development_manifest_sha256": sha_file(OLD_MANIFEST),
    }


def runtime_versions():
    return {"python": sys.version.split()[0], "Pillow": PIL.__version__, "numpy": np.__version__,
            "pyproj": geography.pyproj.__version__, "PROJ": geography.pyproj.proj_version_str}


def specification(info, known_sha=None):
    if isinstance(info, zipfile.ZipInfo):
        return {"member": info.filename, "bytes": info.file_size, "compressed_bytes": info.compress_size,
                "zip_crc32": f"{info.CRC:08x}", "sha256": known_sha}
    return {"member": info["member"], "bytes": info["bytes"], "compressed_bytes": info.get("compressed_bytes"),
            "zip_crc32": info["zip_crc32"].lower(), "sha256": info["sha256"]}


def pair_spec(role, region, rgb, label):
    stem = Path(rgb["member"]).stem
    identifier = region + "__" + stem
    return {"id": identifier, "region": region, "role": role, "rgb": rgb, "label": label}


def local_specs():
    manifest = read_json(OLD_MANIFEST)
    pairs = [pair_spec("old_development", pair["region"], specification(pair["rgb"]), specification(pair["label"]))
             for pair in manifest["pairs"]]
    counts = {region: sum(pair["region"] == region for pair in pairs) for region in {pair["region"] for pair in pairs}}
    if manifest["status"] != "complete" or len(pairs) != 120 or len(counts) != 24 or set(counts.values()) != {5}:
        raise RuntimeError("Original development manifest must contain all 24 x 5 pairs")
    if set(counts) & set(NEW_REGIONS):
        raise RuntimeError("Permanent new panel overlaps an old development region")
    return sorted(pairs, key=lambda item: item["id"])


def make_plan(path, stage="all"):
    # No RGB or semantic-label stream is opened in this mode.
    old = local_specs()
    source = {"url": SOURCE_URL, "archive_bytes": read_json(OLD_MANIFEST)["archive_bytes"],
              "publisher_archive_md5": remote_zip.SOURCE_MD5, "archive_md5_verified": False,
              "directory_transfer_bytes": 0}
    new = []
    if stage == "all":
        with remote_zip.HTTPRangeReader() as reader, zipfile.ZipFile(reader) as archive:
            available = remote_zip.discover_pairs(archive)
            if any(region not in available or len(available[region]) < 3 for region in NEW_REGIONS):
                raise RuntimeError("Fixed panel lacks three complete pairs in at least one region; no substitutions allowed")
            chosen = remote_zip.select_pairs(available, NEW_REGIONS, 3, NEW_SEED)
            new = [pair_spec("new_panel", region, specification(rgb), specification(label))
                   for region, (rgb, label) in chosen]
            source.update({"archive_bytes": reader.size, "directory_transfer_bytes": reader.bytes_transferred})
    plan = {
        "format": "v2-compact-selection-plan-1", "stage": stage, "created_utc": now(), "bindings": current_bindings(),
        "runtime": runtime_versions(), "source": source,
        "selection": {"old_role": "all old formal120 pairs are development/source data",
                      "new_regions": list(NEW_REGIONS), "new_pairs_per_region": 3, "new_seed": NEW_SEED,
                      "rule": "Per-region random.Random(str(seed)+':' + region).sample of filename-sorted complete ZIP pairs; sorted chosen filenames",
                      "image_or_label_content_read_for_selection": False},
        "processing": {"size": [SIDE, SIDE], "rgb_resize": "Pillow BILINEAR", "label_resize": "Pillow NEAREST",
                       "format": "lossless PNG", "png_compress_level": 9, "png_optimize": False,
                       "pair_limit_bytes_including_metadata": PAIR_LIMIT, "compact_data_reservation_bytes": DATA_RESERVATION},
        "expected": {"old_development": 120, "new_panel": 72 if stage == "all" else 0, "total": 192 if stage == "all" else 120},
        "pairs": old + new,
        "geographic_claim_limits": CLAIMS,
    }
    if len(plan["pairs"]) != plan["expected"]["total"] or len({pair["id"] for pair in plan["pairs"]}) != plan["expected"]["total"]:
        raise RuntimeError("Fixed selection must contain its exact unique pair count")
    path = inside_data(path)
    if path.exists():
        previous = read_json(path)
        comparable = deepcopy(plan)
        comparable["created_utc"] = previous["created_utc"]
        comparable["source"]["directory_transfer_bytes"] = previous["source"]["directory_transfer_bytes"]
        if comparable != previous:
            raise RuntimeError("Existing plan differs; do not overwrite a reviewed selection or mix processing versions")
        return previous
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json_bytes(plan)
    if disk_bytes(ROOT) + len(payload) >= PROJECT_LIMIT:
        raise RuntimeError("Selection metadata would exceed project storage limit")
    path.write_bytes(payload)
    return plan


def validate_plan(plan, stage="all"):
    if plan["bindings"] != current_bindings() or plan["runtime"] != runtime_versions():
        raise RuntimeError("Code/runtime/original manifest differs from reviewed plan; strict preparation/resume refused")
    expected = {"old_development": 120, "new_panel": 72 if stage == "all" else 0, "total": 192 if stage == "all" else 120}
    if plan["stage"] != stage or plan["expected"] != expected:
        raise RuntimeError("Unexpected fixed pair counts")
    if plan["selection"]["new_regions"] != list(NEW_REGIONS) or plan["selection"]["new_seed"] != NEW_SEED:
        raise RuntimeError("Permanent panel names or seed changed")
    if plan["processing"] != {"size": [448, 448], "rgb_resize": "Pillow BILINEAR", "label_resize": "Pillow NEAREST",
                              "format": "lossless PNG", "png_compress_level": 9, "png_optimize": False,
                              "pair_limit_bytes_including_metadata": 900000, "compact_data_reservation_bytes": 200000000}:
        raise RuntimeError("Processing parameters changed")
    if [pair for pair in plan["pairs"] if pair["role"] == "old_development"] != local_specs():
        raise RuntimeError("Old development selection or source SHA binding changed")
    new = [pair for pair in plan["pairs"] if pair["role"] == "new_panel"]
    if stage == "all" and (len(new) != 72 or {pair["region"] for pair in new} != set(NEW_REGIONS) or any(
            sum(pair["region"] == region for pair in new) != 3 for region in NEW_REGIONS)):
        raise RuntimeError("New panel no longer has exactly three pairs per fixed region")
    if stage == "old" and new:
        raise RuntimeError("Old-only stage must not contain any new-panel member")
    if len(plan["pairs"]) != expected["total"] or len({pair["id"] for pair in plan["pairs"]}) != expected["total"]:
        raise RuntimeError("Duplicate pair identifier")
    for pair in plan["pairs"]:
        for kind in ("rgb", "label"):
            remote_zip.safe_member_path(pair[kind]["member"])
            if not 0 < pair[kind]["bytes"] <= MEMBER_RAM_LIMIT:
                raise RuntimeError("Selected original member exceeds the RAM safety bound; stop, do not replace sample")


def verified_stream(stream, expected):
    """Read the entire original member, then validate size/CRC/SHA before decode."""
    if not 0 < expected["bytes"] <= MEMBER_RAM_LIMIT:
        raise RuntimeError("Original member exceeds RAM bound")
    chunks, digest, crc, length = [], hashlib.sha256(), 0, 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        length += len(chunk)
        if length > expected["bytes"] or length > MEMBER_RAM_LIMIT:
            raise RuntimeError("Original stream exceeds expected size")
        chunks.append(chunk); digest.update(chunk); crc = zlib.crc32(chunk, crc)
    checksum = digest.hexdigest()
    if length != expected["bytes"] or f"{crc:08x}" != expected["zip_crc32"]:
        raise RuntimeError("Original stream size/ZIP CRC32 check failed")
    if expected.get("sha256") is not None and checksum != expected["sha256"]:
        raise RuntimeError("Original member SHA256 differs from bound source")
    return b"".join(chunks), {**expected, "sha256": checksum, "size_crc32_sha256_verified_before_decode": True,
                              "sha256_was_prebound": expected.get("sha256") is not None}


def json_tag(value):
    if isinstance(value, bytes):
        import base64
        return {"encoding": "base64", "data": base64.b64encode(value).decode("ascii")}
    if isinstance(value, (tuple, list)):
        return [json_tag(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    number = float(value)
    return number if math.isfinite(number) else {"nonfinite_original_value": str(number)}


def resized_affine(affine, width, height, raster_type):
    sx, sy = width / SIDE, height / SIDE
    a, b, c, d, e, f = affine
    if raster_type == 2:
        c += a * (sx - 1) / 2 + b * (sy - 1) / 2
        f += d * (sx - 1) / 2 + e * (sy - 1) / 2
    elif raster_type != 1:
        raise ValueError("Unknown raster type: no invented output affine")
    return [a * sx, b * sy, c, d * sx, e * sy, f]


def georeference(image, cache):
    tags = {tag: image.tag_v2[tag] for tag in GEOTIFF_TAGS if hasattr(image, "tag_v2") and tag in image.tag_v2}
    result = {"status": "unknown", "original_geotiff_tags": {str(k): json_tag(v) for k, v in tags.items()},
              "original_decoded_dimensions": list(image.size),
              "original_tiff_orientation": int(image.tag_v2.get(274, 1)) if hasattr(image, "tag_v2") else None,
              "claim_limits": CLAIMS}
    try:
        if result["original_tiff_orientation"] != 1:
            raise ValueError("Non-default or unavailable TIFF orientation; no orientation reconciliation inferred")
        keys = geography.geokeys(tags)
        epsg, key = geography.epsg_from_keys(keys)
        affine, method = geography.raster_affine(tags)
        raster_type = geography.inline_key(keys, 1025)
        boundary, convention = geography.raster_boundary(*image.size, raster_type, 64)
        points, operation = geography.transform_boundary(epsg, [geography.apply_affine(affine, i, j) for i, j in boundary], cache)
        envelope, dateline = geography.bbox(points)
        result.update({"epsg": epsg, "epsg_geokey": key, "raster_type": raster_type,
                       "source_affine": affine, "source_transform_method": method,
                       "pixel_boundary_convention": convention, "wgs84_boundary_lon_lat": points,
                       "wgs84_sample_envelope": envelope, "coordinate_operation": operation,
                       "antimeridian_sample_span_detected": dateline})
        result["png_georeference_sidecar_affine"] = resized_affine(affine, *image.size, raster_type)
        out_boundary, _ = geography.raster_boundary(SIDE, SIDE, raster_type, 64)
        original_model = [geography.apply_affine(affine, i, j) for i, j in boundary]
        new_model = [geography.apply_affine(result["png_georeference_sidecar_affine"], i, j) for i, j in out_boundary]
        if not all(math.isclose(x0, x1, rel_tol=1e-12, abs_tol=1e-8) and math.isclose(y0, y1, rel_tol=1e-12, abs_tol=1e-8)
                   for (x0, y0), (x1, y1) in zip(original_model, new_model)):
            raise ValueError("Original/resized footprint consistency failed")
        result["resized_world_footprint_matches_source"] = True
        result["status"] = ("supported_metadata_and_transform" if operation["all_boundary_samples_in_source_crs_and_operation_area_of_use"]
                            else "warning_outside_declared_crs_or_operation_area_of_use")
    except Exception as exc:
        result["warning"] = f"{type(exc).__name__}: {exc}"
    return result


def png_bytes(image):
    target = io.BytesIO()
    image.save(target, format="PNG", compress_level=9, optimize=False)
    data = target.getvalue()
    with Image.open(io.BytesIO(data)) as restored:
        restored.load()
        if restored.size != (SIDE, SIDE) or restored.mode != image.mode or restored.tobytes() != image.tobytes():
            raise RuntimeError("Saved PNG failed exact decode round-trip")
    return data


def output_names(spec):
    stem = Path(spec["rgb"]["member"]).stem
    folder = f"{spec['role']}/{spec['region']}"
    return {"rgb": f"{folder}/{stem}_rgb.png", "label": f"{folder}/{stem}_mask.png", "metadata": f"{folder}/{stem}.json"}


def convert_pair(spec, rgb_verified, label_verified, bindings, geo_cache=None):
    """No selection policy accepts this decoded data or original-mask counts."""
    rgb_data, source_rgb = rgb_verified; label_data, source_label = label_verified
    cache = {} if geo_cache is None else geo_cache
    with Image.open(io.BytesIO(rgb_data)) as rgb, Image.open(io.BytesIO(label_data)) as label:
        rgb.load(); label.load()
        if rgb.mode != "RGB" or rgb.size != label.size:
            raise RuntimeError("Original RGB/mask mode or paired dimensions invalid; no automatic substitution")
        array = np.asarray(label)
        if array.ndim != 2 or array.dtype != np.uint8 or not bool(np.all(array <= 8)):
            raise RuntimeError("Original mask must be uint8 raw IDs 0..8")
        source_rgb.update({"original_dimensions": list(rgb.size), "original_decoded_rgb_sha256": sha_bytes(rgb.tobytes("raw", "RGB")),
                           "geography": georeference(rgb, cache)})
        counts = np.bincount(array.ravel(), minlength=9).astype(np.int64).tolist()
        source_label.update({"original_dimensions": list(label.size), "original_decoded_mask_sha256": sha_bytes(array.tobytes()),
                             "original_mask_class_counts_raw_0_to_8": counts,
                             "class_counts_scope": "metadata only; selection policies must never receive these fields",
                             "geography": georeference(label, cache)})
        a, b = source_rgb["geography"], source_label["geography"]
        if "source_affine" in a and "source_affine" in b and (a.get("epsg") != b.get("epsg") or any(
                not math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-8) for x, y in zip(a["source_affine"], b["source_affine"]))):
            raise RuntimeError("Original RGB/mask declared georeferences disagree")
        rgb_small = rgb.resize((SIDE, SIDE), Image.Resampling.BILINEAR)
        label_small = Image.fromarray(array).resize((SIDE, SIDE), Image.Resampling.NEAREST)
        if not bool(np.all(np.asarray(label_small) <= 8)):
            raise RuntimeError("Nearest-neighbour output mask contains an invalid class ID")
        rgb_png, label_png = png_bytes(rgb_small), png_bytes(label_small)
    names = output_names(spec)
    outputs = {"rgb": {"relative_path": names["rgb"], "sha256": sha_bytes(rgb_png), "bytes": len(rgb_png)},
               "label": {"relative_path": names["label"], "sha256": sha_bytes(label_png), "bytes": len(label_png)}}
    metadata = {"format": "v2-compact-pair-provenance-1", "id": spec["id"], "region": spec["region"], "role": spec["role"],
                "bindings": bindings, "runtime": runtime_versions(), "source_rgb": source_rgb, "source_label": source_label,
                "outputs": outputs, "conversion": {"size": [SIDE, SIDE], "rgb": "Pillow BILINEAR", "label": "Pillow NEAREST",
                                                       "png": "lossless; compress_level=9; optimize=False; georeferences stored in this sidecar"},
                "original_tiff_persisted": False, "compact_payload_bytes": 0,
                "source_authentication_limit": "Original SHA is independently compared when prebound; first new-panel SHA is recorded after full ZIP CRC/size verification. Full archive MD5 is not verified.",
                "geographic_claim_limits": CLAIMS}
    for _ in range(4):
        content = json_bytes(metadata)
        metadata["compact_payload_bytes"] = len(rgb_png) + len(label_png) + len(content)
    content = json_bytes(metadata)
    if len(rgb_png) + len(label_png) + len(content) != metadata["compact_payload_bytes"]:
        raise RuntimeError("Pair metadata byte accounting did not stabilize")
    if metadata["compact_payload_bytes"] > PAIR_LIMIT:
        raise RuntimeError(f"Fixed pair exceeds {PAIR_LIMIT:,} bytes; stop without changing size or sample")
    return {names["rgb"]: rgb_png, names["label"]: label_png, names["metadata"]: content}, metadata


def source_matches(actual, expected):
    for key in ("member", "bytes", "zip_crc32", "compressed_bytes"):
        if actual.get(key) != expected.get(key):
            return False
    return expected.get("sha256") is None or actual.get("sha256") == expected["sha256"]


def record_from_metadata(spec, metadata, metadata_bytes):
    if (metadata["id"], metadata["region"], metadata["role"]) != (spec["id"], spec["region"], spec["role"]):
        raise RuntimeError("Pair metadata identity differs from fixed plan")
    if not source_matches(metadata["source_rgb"], spec["rgb"]) or not source_matches(metadata["source_label"], spec["label"]):
        raise RuntimeError("Pair source provenance differs from fixed plan")
    names = output_names(spec)
    for kind in ("rgb", "label"):
        if metadata["outputs"][kind]["relative_path"] != names[kind]:
            raise RuntimeError("Unexpected PNG output path")
    # The stable load_pair interface never receives class-count fields.
    return {"id": spec["id"], "region": spec["region"], "role": spec["role"],
            "rgb": metadata["outputs"]["rgb"], "label": metadata["outputs"]["label"],
            "source_rgb": {key: metadata["source_rgb"][key] for key in ("member", "sha256", "bytes", "zip_crc32")},
            "source_label": {key: metadata["source_label"][key] for key in ("member", "sha256", "bytes", "zip_crc32")},
            "metadata": {"relative_path": names["metadata"], "sha256": sha_bytes(metadata_bytes), "bytes": len(metadata_bytes)},
            "compact_payload_bytes": metadata["compact_payload_bytes"]}


def verify_saved(spec, record, bindings):
    metadata_path = member_path(DATA_ROOT, record["metadata"]["relative_path"])
    raw = metadata_path.read_bytes(); metadata = json.loads(raw)
    if sha_bytes(raw) != record["metadata"]["sha256"] or len(raw) != record["metadata"]["bytes"]:
        raise RuntimeError("Pair metadata SHA256/size mismatch")
    if metadata["bindings"] != bindings or metadata["runtime"] != runtime_versions():
        raise RuntimeError("Saved pair conversion/runtime lineage mismatch")
    expected = record_from_metadata(spec, metadata, raw)
    if expected != record or record["compact_payload_bytes"] > PAIR_LIMIT:
        raise RuntimeError("Saved record differs from provenance or exceeds pair cap")
    total = len(raw)
    for kind in ("rgb", "label"):
        info = record[kind]; path = member_path(DATA_ROOT, info["relative_path"])
        if sha_file(path) != info["sha256"] or path.stat().st_size != info["bytes"]:
            raise RuntimeError("Saved PNG SHA256/size mismatch")
        with Image.open(path) as image:
            image.load()
            if image.format != "PNG" or image.size != (SIDE, SIDE) or image.mode != ("RGB" if kind == "rgb" else "L"):
                raise RuntimeError("Saved PNG dimensions/mode/format mismatch")
            if kind == "label" and not bool(np.all(np.asarray(image) <= 8)):
                raise RuntimeError("Saved mask has invalid raw class IDs")
        total += info["bytes"]
    if total != record["compact_payload_bytes"]:
        raise RuntimeError("Saved pair total byte count mismatch")


def atomic_new_or_identical(path, content):
    inside_data(path)
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError(f"Existing orphan output differs; preserve evidence and stop: {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".part", delete=False) as stream:
            temporary = Path(stream.name); stream.write(content)
        temporary.replace(path)
    except BaseException:
        # A successfully named output is never overwritten; interruption/error
        # details remain in the manifest even when this call's temp is removed.
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


class Sources:
    """One worker owns one lazy HTTP reader/ZipFile; local sources stay local."""
    def __init__(self, plan, state):
        self.plan, self.state = plan, state
        self.reader = self.archive = None

    def read(self, spec, kind):
        expected = spec[kind]
        if spec["role"] == "old_development":
            source = member_path(OLD_MANIFEST.parent, expected["member"])
            with source.open("rb") as stream:
                return verified_stream(stream, expected)
        if self.archive is None:
            self.reader = remote_zip.HTTPRangeReader()
            if self.reader.size != self.plan["source"]["archive_bytes"]:
                raise RuntimeError("Official archive size changed from reviewed directory plan")
            self.archive = zipfile.ZipFile(self.reader)
            available = remote_zip.discover_pairs(self.archive)
            chosen = remote_zip.select_pairs(available, NEW_REGIONS, 3, NEW_SEED)
            actual = [pair_spec("new_panel", region, specification(rgb), specification(label)) for region, (rgb, label) in chosen]
            if actual != [pair for pair in self.plan["pairs"] if pair["role"] == "new_panel"]:
                raise RuntimeError("Reviewed new-panel member selection differs from fixed seeded ZIP selection")
            with self.state.lock:
                self.state.readers.append(self.reader)
        info = self.archive.getinfo(expected["member"])
        if specification(info) != expected:
            raise RuntimeError("Remote ZIP member metadata differs from reviewed plan")
        if info.flag_bits & 1:
            raise RuntimeError("Encrypted ZIP members are unsupported; no credentials requested")
        with self.archive.open(info) as stream:
            return verified_stream(stream, expected)

    def close(self):
        if self.archive is not None:
            self.archive.close()
        if self.reader is not None:
            self.reader.close()


class Preparation:
    def __init__(self, plan_path, plan):
        self.plan = plan; self.path = DATA_ROOT / ("old_development_manifest.json" if plan["stage"] == "old" else "manifest.json")
        self.lock = threading.RLock(); self.readers = []; self.stop = threading.Event()
        self.specs = {pair["id"]: pair for pair in plan["pairs"]}
        identity = {"selection_plan_sha256": sha_file(plan_path), "bindings": plan["bindings"], "runtime": plan["runtime"]}
        if self.path.exists():
            self.manifest = read_json(self.path)
            if plan["stage"] == "all" and self.manifest.get("stage") == "old" and not self.manifest.get("whole_v2_dataset_complete"):
                if self.manifest["identity"]["bindings"] != identity["bindings"] or self.manifest["identity"]["runtime"] != identity["runtime"]:
                    raise RuntimeError("Development-only checkpoint has incompatible code/runtime")
                self.manifest["identity"] = identity
                self.manifest["source"] = plan["source"]
                self.manifest["selection"] = plan["selection"]
                self.manifest["expected"] = plan["expected"]
            if self.manifest["identity"] != identity:
                raise RuntimeError("Existing v2 manifest differs from plan/code/runtime; strict resume refused")
            self.manifest.setdefault("attempts", []).append({"previous_status": self.manifest.get("status"),
                "previous_error": self.manifest.get("error"), "checkpoint": self.manifest.get("current_attempt", {})})
        else:
            self.manifest = {"format": "v2-compact-manifest-1", "created_utc": now(), "identity": identity,
                             "source": plan["source"], "selection": plan["selection"], "processing": plan["processing"],
                             "expected": plan["expected"], "pairs": [], "attempts": [], "region_progress": {},
                             "geographic_claim_limits": CLAIMS}
        self.manifest["stage"] = plan["stage"]
        self.manifest["whole_v2_dataset_complete"] = False
        self.records = {}
        for record in self.manifest["pairs"]:
            if record["id"] in self.records or record["id"] not in self.specs:
                raise RuntimeError("Duplicate/unplanned pair in existing manifest")
            verify_saved(self.specs[record["id"]], record, plan["bindings"])
            self.records[record["id"]] = record
        # Recover a completed atomic pair whose global manifest commit was interrupted.
        for spec in plan["pairs"]:
            metadata_path = member_path(DATA_ROOT, output_names(spec)["metadata"])
            if spec["id"] not in self.records and metadata_path.exists():
                raw = metadata_path.read_bytes(); metadata = json.loads(raw)
                record = record_from_metadata(spec, metadata, raw)
                verify_saved(spec, record, plan["bindings"])
                self.records[spec["id"]] = record
                self.manifest.setdefault("resume_events", []).append({"utc": now(), "id": spec["id"], "action": "SHA-verified orphan pair metadata adopted"})
        self.manifest["status"] = "in_progress"
        self.manifest.pop("error", None)
        self.started = now()
        self.save()

    def save(self):
        self.manifest["pairs"] = sorted(self.records.values(), key=lambda item: (item["role"], item["id"]))
        self.manifest["current_attempt"] = {"started_utc": self.started, "last_checkpoint_utc": now(),
                                            "http_range_bytes": sum(reader.bytes_transferred for reader in self.readers),
                                            "http_requests": sum(reader.requests_made for reader in self.readers)}
        for role, count in self.plan["expected"].items():
            if role != "total":
                self.manifest["region_progress"][role] = {
                    region: {"complete": sum(record["region"] == region and record["role"] == role for record in self.records.values()),
                             "planned": sum(spec["region"] == region and spec["role"] == role for spec in self.plan["pairs"])}
                    for region in sorted({spec["region"] for spec in self.plan["pairs"] if spec["role"] == role})}
        self.manifest["compact_payload_bytes"] = sum(record["compact_payload_bytes"] for record in self.records.values())
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        raw = json_bytes(self.manifest)
        pending = self.path.with_name("manifest.json.tmp")
        pending.write_bytes(raw); pending.replace(self.path)
        if self.plan["stage"] == "old":
            # Stable combined interface is explicitly partial until all 192 exist.
            partial = deepcopy(self.manifest)
            partial["status"] = "partial" if self.manifest["status"] != "failed_or_interrupted" else "failed_or_interrupted"
            partial["expected"] = {"old_development": 120, "new_panel": 72, "total": 192}
            partial["whole_v2_dataset_complete"] = False
            partial["development_component_manifest"] = "old_development_manifest.json"
            combined = DATA_ROOT / "manifest.json"
            if combined.exists() and read_json(combined).get("stage") == "all":
                raise RuntimeError("Cannot overwrite an existing all-stage manifest with an old-only checkpoint")
            atomic = combined.with_name("manifest.json.partial.tmp")
            atomic.write_bytes(json_bytes(partial)); atomic.replace(combined)
        self.publish_development_snapshot()

    def publish_development_snapshot(self):
        old = [record for record in self.manifest["pairs"] if record["role"] == "old_development"]
        if len(old) != 120:
            return
        snapshot_path = DATA_ROOT / "development_manifest.json"
        if snapshot_path.exists():
            frozen = read_json(snapshot_path)
            if (frozen["pairs"] != old or frozen["identity"]["bindings"] != self.plan["bindings"] or
                    frozen["identity"]["runtime"] != self.plan["runtime"] or frozen["status"] != "complete"):
                raise RuntimeError("Immutable development manifest differs; it will not be overwritten")
            return
        frozen = deepcopy(self.manifest)
        frozen.update({"status": "complete", "stage": "old", "scope": "immutable_development_120_only",
                       "pairs": old, "whole_v2_dataset_complete": False,
                       "expected": {"old_development": 120, "new_panel": 0, "total": 120},
                       "compact_payload_bytes": sum(record["compact_payload_bytes"] for record in old),
                       "immutability_note": "Bind calibration to this file SHA; later panel preparation never rewrites it."})
        frozen["region_progress"] = {"old_development": frozen["region_progress"]["old_development"]}
        atomic_new_or_identical(snapshot_path, json_bytes(frozen))

    def commit(self, spec, buffers, metadata):
        with self.lock:
            if spec["id"] in self.records:
                raise RuntimeError("Pair assigned twice")
            reserve_check()
            extra = sum(len(content) for relative, content in buffers.items() if not member_path(DATA_ROOT, relative).exists())
            if disk_bytes(DATA_ROOT) + extra >= DATA_RESERVATION or disk_bytes(ROOT) + extra + 65536 >= PROJECT_LIMIT:
                raise RuntimeError("Strict pre-write byte budget refused; no size/sample adjustment")
            for relative, content in buffers.items():
                atomic_new_or_identical(member_path(DATA_ROOT, relative), content)
            raw = buffers[output_names(spec)["metadata"]]
            record = record_from_metadata(spec, metadata, raw)
            verify_saved(spec, record, self.plan["bindings"])
            self.records[spec["id"]] = record
            self.save()
            print(f"ready {len(self.records)}/{self.plan['expected']['total']} {spec['role']} {spec['id']}", flush=True)


def _prepare(plan_path, workers, stage="all"):
    reserve_check()  # Before any original member, local or remote, is read.
    plan = read_json(plan_path); validate_plan(plan, stage)
    geography.network.set_network_enabled(False)
    state = Preparation(plan_path, plan)
    SOFTWARE_ROOT.mkdir(parents=True, exist_ok=True)
    snapshot = SOFTWARE_ROOT / ("v2_prepare_data." + plan["bindings"]["conversion_code_sha256"] + ".py")
    if snapshot.exists() and sha_file(snapshot) != plan["bindings"]["conversion_code_sha256"]:
        raise RuntimeError("Conversion software snapshot differs")
    if not snapshot.exists():
        shutil.copy2(Path(__file__), snapshot)
    jobs = queue.Queue()
    for role in ("old_development", "new_panel"):
        for region in sorted({spec["region"] for spec in plan["pairs"] if spec["role"] == role}):
            remaining = [spec for spec in plan["pairs"] if spec["role"] == role and spec["region"] == region and spec["id"] not in state.records]
            if remaining:
                jobs.put(remaining)
    def worker():
        sources = Sources(plan, state); geo_cache = {}
        try:
            while not state.stop.is_set():
                try:
                    batch = jobs.get_nowait()
                except queue.Empty:
                    return
                for spec in batch:
                    if state.stop.is_set():
                        return
                    rgb = sources.read(spec, "rgb"); label = sources.read(spec, "label")
                    buffers, metadata = convert_pair(spec, rgb, label, plan["bindings"], geo_cache)
                    state.commit(spec, buffers, metadata)
        except BaseException:
            state.stop.set()
            raise
        finally:
            sources.close()
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(worker) for _ in range(min(workers, jobs.qsize()))]
            try:
                for future in futures:
                    future.result()
            except BaseException:
                state.stop.set()
                raise
        if len(state.records) != plan["expected"]["total"]:
            raise RuntimeError("Preparation did not complete its exact fixed pair count")
        state.manifest["status"] = "complete"
        state.manifest["whole_v2_dataset_complete"] = stage == "all"
        reserve_check()
    except BaseException as exc:
        state.manifest["status"] = "failed_or_interrupted"
        state.manifest["error"] = {"utc": now(), "type": type(exc).__name__, "message": str(exc),
                                   "policy": "Keep selection, resolution and existing evidence unchanged"}
        raise
    finally:
        with state.lock:
            state.save()
    print(json.dumps({"status": "complete", "pairs": len(state.records), "compact_payload_bytes": state.manifest["compact_payload_bytes"],
                      "v2_data_directory_bytes": disk_bytes(DATA_ROOT), "project_logical_bytes": disk_bytes(ROOT),
                      "manifest": str(state.path)}, indent=2))


def prepare(plan_path, workers, stage="all"):
    reserve_check()
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    lock_path = DATA_ROOT / ".prepare.lock"
    try:
        with lock_path.open("x", encoding="utf-8") as stream:
            stream.write(json_bytes({"pid": os.getpid(), "started_utc": now(), "stage": stage,
                                     "code_sha256": sha_file(Path(__file__))}).decode("utf-8"))
    except FileExistsError as exc:
        raise RuntimeError("Another/stale preparation lock exists. Verify that its process has stopped before reviewing/removing only this owned lock; no concurrent preparation is permitted.") from exc
    try:
        _prepare(plan_path, workers, stage)
    finally:
        lock_path.unlink(missing_ok=True)


def record_cli_failure(exc):
    event = json_bytes({"utc": now(), "type": type(exc).__name__, "message": str(exc),
                        "conversion_code_sha256": sha_file(Path(__file__)),
                        "action": "stopped; no sample or resolution changed"})
    if disk_bytes(ROOT) + len(event) < PROJECT_LIMIT:
        SOFTWARE_ROOT.mkdir(parents=True, exist_ok=True)
        with (SOFTWARE_ROOT / "preparation_failures.jsonl").open("ab") as stream:
            stream.write(json.dumps(json.loads(event), ensure_ascii=False).encode("utf-8") + b"\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--plan", action="store_true", help="Read only manifests/ZIP directory and write fixed member selection; never open RGB/mask streams")
    modes.add_argument("--prepare", action="store_true", help="Execute the reviewed plan with strict source and PNG checks/resume")
    parser.add_argument("--stage", choices=("all", "old"), default="all", help="old prepares only the 120 development pairs without network")
    parser.add_argument("--old-only", action="store_true", help="Alias for --stage old")
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2, help="Independent source readers (maximum 2)")
    args = parser.parse_args(argv)
    try:
        stage = "old" if args.old_only else args.stage
        plan_path = inside_data(args.plan_file or DATA_ROOT / ("selection_plan_old.json" if stage == "old" else "selection_plan.json"))
        if args.plan:
            plan = make_plan(plan_path, stage)
            print(json.dumps({"plan": str(plan_path), "expected": plan["expected"], "new_seed": NEW_SEED,
                              "original_members_read": False, "pairs": plan["pairs"]}, indent=2))
        else:
            prepare(plan_path, args.workers, stage)
    except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile) as exc:
        record_cli_failure(exc)
        print(f"V2 PREPARATION STOPPED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt as exc:
        record_cli_failure(exc)
        print("V2 PREPARATION INTERRUPTED: existing evidence retained", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

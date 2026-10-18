"""Audit selected RGB TIFF georeferences and decoded pixel duplicates, offline.

Only RGB files, the manifest and the region partition are read. Semantic label
rasters and model results are never opened. Geographic statements are limited to
selected tiles with supported, verifiable TIFF metadata, not source mosaics.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "site-packages"))
from PIL import Image
import PIL
import pyproj
from pyproj import CRS, network
from pyproj.transformer import TransformerGroup

REFERENCES = {
    "geotiff": "https://docs.ogc.org/is/19-008r4/19-008r4.html",
    "pyproj": "https://pyproj4.github.io/pyproj/stable/api/transformer.html",
}


class UnknownGeography(ValueError):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_rgb_path(root, name):
    parts = PurePosixPath(name).parts
    if not parts or "\\" in name or PurePosixPath(name).is_absolute() or any(
            part in (".", "..") or ":" in part for part in parts):
        raise ValueError(f"Unsafe RGB member path: {name!r}")
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("RGB path escapes manifest directory")
    return path


def geokeys(tags):
    raw = tags.get(34735)
    if raw is None:
        raise UnknownGeography("Missing GeoKeyDirectoryTag 34735")
    values = [int(item) for item in raw]
    if len(values) < 4 or values[0] != 1 or len(values) < 4 + 4 * values[3]:
        raise UnknownGeography("Malformed or unsupported GeoKeyDirectoryTag")
    keys = {}
    for offset in range(4, 4 + 4 * values[3], 4):
        key, location, count, value_offset = values[offset:offset + 4]
        if key in keys:
            raise UnknownGeography(f"Duplicate GeoKey {key}")
        keys[key] = {"location": location, "count": count, "value_offset": value_offset}
    return keys


def inline_key(keys, key):
    entry = keys.get(key)
    return entry["value_offset"] if entry and entry["location"] == 0 and entry["count"] == 1 else None


def epsg_from_keys(keys):
    model = inline_key(keys, 1024)
    projected = inline_key(keys, 3072)
    geographic = inline_key(keys, 2048)
    valid = lambda code: code is not None and 0 < code < 32767
    if model == 1 or (model is None and projected is not None):
        if not valid(projected):
            raise UnknownGeography("Projected model lacks an inline usable EPSG GeoKey 3072; no geographic fallback inferred")
        return projected, 3072
    if model == 2 or (model is None and projected is None and geographic is not None):
        if not valid(geographic):
            raise UnknownGeography("Geographic model lacks an inline usable EPSG GeoKey 2048")
        return geographic, 2048
    raise UnknownGeography("Unknown/unsupported GeoTIFF model type or EPSG definition")


def raster_affine(tags):
    matrix = tags.get(34264)
    scale = tags.get(33550)
    tie = tags.get(33922)
    if matrix is not None:
        if scale is not None:
            raise UnknownGeography("Both ModelTransformationTag and ModelPixelScaleTag present; ambiguous/nonconforming metadata")
        m = [float(value) for value in matrix]
        if len(m) != 16 or not all(map(math.isfinite, m)):
            raise UnknownGeography("Invalid ModelTransformationTag")
        if any(abs(m[index]) > 1e-12 for index in (12, 13, 14)) or abs(m[15] - 1) > 1e-12:
            raise UnknownGeography("Non-affine homogeneous transformation is unsupported")
        affine = [m[0], m[1], m[3], m[4], m[5], m[7]]
        method = "ModelTransformationTag 34264, raster K=0"
    else:
        if scale is None or tie is None:
            raise UnknownGeography("No supported raster transform: need 33550+33922 or 34264; tiepoints alone are insufficient")
        s, t = list(map(float, scale)), list(map(float, tie))
        if len(s) != 3 or len(t) < 6 or len(t) % 6 or not all(map(math.isfinite, s + t)):
            raise UnknownGeography("Invalid pixel-scale/tiepoint metadata")
        if s[0] == 0 or s[1] == 0:
            raise UnknownGeography("Zero horizontal pixel scale")
        i, j, _, x, y, _ = t[:6]
        affine = [s[0], 0, x - i * s[0], 0, -s[1], y + j * s[1]]
        for offset in range(0, len(t), 6):
            ti, tj, _, tx, ty, _ = t[offset:offset + 6]
            ax, ay = apply_affine(affine, ti, tj)
            if not (math.isclose(ax, tx, rel_tol=1e-12, abs_tol=abs(s[0]) * 1e-6) and
                    math.isclose(ay, ty, rel_tol=1e-12, abs_tol=abs(s[1]) * 1e-6)):
                raise UnknownGeography("Multiple tiepoints disagree with pixel-scale affine")
        method = "ModelPixelScaleTag 33550 + ModelTiepointTag 33922; signed X scale and negative signed Y scale"
    if abs(affine[0] * affine[4] - affine[1] * affine[3]) < 1e-24:
        raise UnknownGeography("Degenerate raster affine")
    return affine, method


def apply_affine(affine, i, j):
    a, b, c, d, e, f = affine
    return a * i + b * j + c, d * i + e * j + f


def raster_boundary(width, height, raster_type, segments):
    if raster_type == 1:
        left, top, right, bottom = 0, 0, width, height
        convention = "RasterPixelIsArea: outer edges [0,width] x [0,height]"
    elif raster_type == 2:
        left, top, right, bottom = -0.5, -0.5, width - 0.5, height - 0.5
        convention = "RasterPixelIsPoint: half-pixel support around point samples"
    elif raster_type is None:
        left, top, right, bottom = -0.5, -0.5, width + 0.5, height + 0.5
        convention = "Raster type missing: expanded envelope covers both area and point conventions; assumption flagged"
    else:
        raise UnknownGeography(f"Unsupported raster type {raster_type}")
    corners = [(left, top), (right, top), (right, bottom), (left, bottom), (left, top)]
    samples = []
    for (x0, y0), (x1, y1) in zip(corners, corners[1:]):
        for step in range(segments):
            fraction = step / segments
            samples.append((x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction))
    samples.append(corners[0])
    return samples, convention


def area_contains(area, longitude, latitude):
    if area is None:
        return True
    lon_ok = area.west <= longitude <= area.east if area.west <= area.east else longitude >= area.west or longitude <= area.east
    return lon_ok and area.south <= latitude <= area.north


def bbox(points, padding_m=0):
    longitudes, latitudes = zip(*points)
    south, north = min(latitudes), max(latitudes)
    west, east = min(longitudes), max(longitudes)
    dateline = east - west > 180
    lat_pad = padding_m / 110000.0
    max_lat = min(89.999999, max(abs(south - lat_pad), abs(north + lat_pad)))
    lon_pad = padding_m / (110000.0 * max(1e-8, math.cos(math.radians(max_lat))))
    if dateline or west - lon_pad < -180 or east + lon_pad > 180:
        west, east = -180, 180
    else:
        west, east = west - lon_pad, east + lon_pad
    return [west, max(-90, south - lat_pad), east, min(90, north + lat_pad)], dateline


def intersects(left, right):
    return max(left[0], right[0]) <= min(left[2], right[2]) and max(left[1], right[1]) <= min(left[3], right[3])


def transform_boundary(epsg, model_points, transformer_cache):
    if epsg not in transformer_cache:
        crs = CRS.from_epsg(epsg)
        with warnings.catch_warnings(record=True) as messages:
            warnings.simplefilter("always")
            group = TransformerGroup(crs, CRS.from_epsg(4326), always_xy=True, allow_ballpark=False)
        transformer_cache[epsg] = (crs, group, [str(message.message) for message in messages])
    crs, group, messages = transformer_cache[epsg]
    if not group.transformers:
        raise UnknownGeography("No available non-ballpark offline WGS84 transformation")
    xs, ys = zip(*model_points)
    outside_area_fallback = None
    for transformer in group.transformers:
        try:
            lons, lats = transformer.transform(xs, ys, errcheck=True)
        except pyproj.exceptions.ProjError:
            continue
        points = list(zip(map(float, lons), map(float, lats)))
        if not all(math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90
                   for lon, lat in points):
            continue
        source_outside = sum(not area_contains(crs.area_of_use, lon, lat) for lon, lat in points)
        operation_outside = sum(not area_contains(transformer.area_of_use, lon, lat) for lon, lat in points)
        def area_record(area):
            return None if area is None else {"name": area.name, "west": area.west, "south": area.south,
                                              "east": area.east, "north": area.north}
        operation = {
            "source_crs": crs.to_string(), "source_crs_name": crs.name,
            "target_crs": "EPSG:4326", "axis_order": "always_xy: longitude,latitude",
            "operation": transformer.description, "definition": transformer.definition,
            "accuracy_m": transformer.accuracy if transformer.accuracy >= 0 else None,
            "best_available_operation_present": group.best_available,
            "unavailable_operations": len(group.unavailable_operations), "warnings": messages,
            "network_enabled": False, "ballpark_operations_allowed": False,
            "source_crs_area_of_use": area_record(crs.area_of_use),
            "operation_area_of_use": area_record(transformer.area_of_use),
            "boundary_samples_outside_source_crs_area": source_outside,
            "boundary_samples_outside_operation_area": operation_outside,
            "all_boundary_samples_in_source_crs_and_operation_area_of_use": source_outside == operation_outside == 0,
        }
        if source_outside == operation_outside == 0:
            return points, operation
        if outside_area_fallback is None:
            outside_area_fallback = points, operation
    if outside_area_fallback is not None:
        return outside_area_fallback
    raise UnknownGeography("No available non-ballpark offline transformation produced finite valid WGS84 samples")


def inspect_rgb(pair, split, data_root, segments, padding_m, transformer_cache):
    info = pair["rgb"]
    record = {"region": pair["region"], "split": split, "member": info["member"],
              "relative_path": info["relative_path"], "geography_status": "unknown"}
    try:
        path = safe_rgb_path(data_root, info["relative_path"])
        actual_sha = sha256_file(path)
        integrity = actual_sha == info["sha256"] and path.stat().st_size == info["bytes"]
        record.update({"file_sha256": actual_sha, "manifest_sha256_and_size_match": integrity})
        with Image.open(path) as image:
            width, height = image.size
            record["dimensions"] = [width, height]
            orientation = int(image.tag_v2.get(274, 1))
            record["tiff_orientation"] = orientation
            rgb = image.convert("RGB")
            record["decoded_rgb_sha256"] = hashlib.sha256(rgb.tobytes("raw", "RGB")).hexdigest()
            record["decoded_rgb_hash_definition"] = "SHA256 of Pillow-decoded RGB uint8 bytes in row-major interleaved RGB order; grouping also requires equal dimensions"
            tags = {tag: list(image.tag_v2[tag]) if isinstance(image.tag_v2[tag], tuple) else image.tag_v2[tag]
                    for tag in (33550, 33922, 34264, 34735, 34736, 34737) if tag in image.tag_v2}
        record["geotiff_tags"] = {str(key): value for key, value in tags.items()}
        if orientation != 1:
            raise UnknownGeography("Non-default TIFF orientation: raster-to-model orientation reconciliation is unsupported")
        keys = geokeys(tags)
        record["parsed_geokeys"] = {str(key): value for key, value in keys.items()}
        epsg, epsg_key = epsg_from_keys(keys)
        record["epsg"] = epsg
        record["epsg_geokey"] = epsg_key
        affine, method = raster_affine(tags)
        record["raster_to_model_affine"] = affine
        record["raster_transform_method"] = method
        raster_type = inline_key(keys, 1025)
        raster_points, convention = raster_boundary(width, height, raster_type, segments)
        record["raster_type"] = raster_type
        record["pixel_boundary_convention"] = convention
        model_points = [apply_affine(affine, i, j) for i, j in raster_points]
        points, operation = transform_boundary(epsg, model_points, transformer_cache)
        accuracy = operation["accuracy_m"]
        margin = padding_m + (accuracy if accuracy is not None else 100.0)
        raw_bbox, dateline = bbox(points)
        padded_bbox, _ = bbox(points, margin)
        record.update({"wgs84_boundary_samples_lon_lat": points,
                       "boundary_samples": len(points), "edge_segments": segments,
                       "wgs84_sample_envelope": raw_bbox,
                       "wgs84_padded_candidate_bbox": padded_bbox,
                       "candidate_bbox_padding_m": margin,
                       "antimeridian_sample_span_detected": dateline,
                       "coordinate_operation": operation})
        if not integrity:
            raise UnknownGeography("RGB file SHA256/size differs from manifest; geographic evidence excluded")
        if not operation["all_boundary_samples_in_source_crs_and_operation_area_of_use"]:
            raise UnknownGeography("EPSG metadata and transformed boundary are available, but some samples are outside the declared source CRS or operation area of use; excluded from verified geographic separation checks")
        if split is None:
            raise UnknownGeography("Region is absent from declared partition; split comparisons excluded")
        record["geography_status"] = "supported_metadata_and_offline_transform"
    except Exception as exc:
        record["unknown_reason"] = f"{type(exc).__name__}: {exc}"
    return record


def audit(manifest_path, partition_path, output, segments=64, padding_m=20.0):
    network.set_network_enabled(False)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    partition = json.loads(partition_path.read_text(encoding="utf-8"))
    region_splits = {}
    for split, regions in partition["splits"].items():
        for region in regions:
            if region in region_splits:
                raise ValueError(f"Region appears in multiple splits: {region}")
            region_splits[region] = split
    cache = {}
    records = [inspect_rgb(pair, region_splits.get(pair["region"]), manifest_path.parent,
                           segments, padding_m, cache) for pair in manifest["pairs"]]
    known = [record for record in records if record["geography_status"] != "unknown"]
    unknown = [record for record in records if record["geography_status"] == "unknown"]
    cross_pairs, overlap_candidates = 0, []
    for left, right in itertools.combinations(known, 2):
        if left["split"] == right["split"]:
            continue
        cross_pairs += 1
        if intersects(left["wgs84_padded_candidate_bbox"], right["wgs84_padded_candidate_bbox"]):
            overlap_candidates.append({"left": left["member"], "left_split": left["split"],
                                       "right": right["member"], "right_split": right["split"],
                                       "status": "requires_review_not_a_leakage_determination"})
    groups = defaultdict(list)
    for record in records:
        if "decoded_rgb_sha256" in record:
            groups[(*record["dimensions"], record["decoded_rgb_sha256"])].append(record)
    duplicates = [{"dimensions": list(key[:2]), "decoded_rgb_sha256": key[2],
                   "cross_split": len({item["split"] for item in items}) > 1,
                   "members": [{"member": item["member"], "region": item["region"], "split": item["split"]}
                               for item in items]}
                  for key, items in sorted(groups.items()) if len(items) > 1]
    by_region = defaultdict(list)
    for record in known:
        by_region[record["region"]].append(record)
    envelopes = []
    for region, items in sorted(by_region.items()):
        boxes = [item["wgs84_padded_candidate_bbox"] for item in items]
        envelopes.append({"region": region, "split": region_splits[region], "covered_tiles": len(items),
                          "declared_tiles": sum(record["region"] == region for record in records),
                          "sampled_tile_union_envelope": [min(box[0] for box in boxes), min(box[1] for box in boxes),
                                                          max(box[2] for box in boxes), max(box[3] for box in boxes)],
                          "scope": "Envelope of selected supported tiles, including gaps; not the source orthomosaic extent"})
    region_candidates = [{"left_region": left["region"], "left_split": left["split"],
                          "right_region": right["region"], "right_split": right["split"],
                          "status": "requires_review_not_a_leakage_determination"}
                         for left, right in itertools.combinations(envelopes, 2)
                         if left["split"] != right["split"] and intersects(left["sampled_tile_union_envelope"], right["sampled_tile_union_envelope"])]
    summary = {
        "rgb_tiles": len(records), "geography_supported_tiles": len(known), "geography_unknown_tiles": len(unknown),
        "wgs84_boundary_computed_tiles": sum("wgs84_boundary_samples_lon_lat" in record for record in records),
        "out_of_area_geographic_caution_tiles": sum("coordinate_operation" in record and not record["coordinate_operation"]["all_boundary_samples_in_source_crs_and_operation_area_of_use"] for record in records),
        "declared_regions": len(region_splits), "regions_present": len({record["region"] for record in records}),
        "tiles_by_split": dict(Counter(record["split"] or "unknown" for record in records)),
        "supported_tiles_by_split": dict(Counter(record["split"] for record in known)),
        "cross_split_tile_bbox_pairs_checked": cross_pairs,
        "cross_split_tile_bbox_overlap_candidates": len(overlap_candidates),
        "cross_split_region_envelope_overlap_candidates": len(region_candidates),
        "decoded_rgb_duplicate_groups": len(duplicates),
        "cross_split_decoded_rgb_duplicate_groups": sum(group["cross_split"] for group in duplicates),
        "rgb_file_integrity_failures": sum(record.get("manifest_sha256_and_size_match") is False for record in records),
    }
    result = {
        "audit_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {"manifest": str(manifest_path), "manifest_sha256": sha256_file(manifest_path),
                   "partition": str(partition_path), "partition_sha256": sha256_file(partition_path)},
        "runtime": {"python": sys.version.split()[0], "Pillow": PIL.__version__, "pyproj": pyproj.__version__,
                    "PROJ": pyproj.proj_version_str, "projection_network_enabled": False},
        "method": {"references": REFERENCES, "epsg_geokeys": [3072, 2048], "geokey_directory_tag": 34735,
                   "raster_transforms": ["33550+33922", "34264"], "edge_segments": segments,
                   "candidate_padding_base_m": padding_m,
                   "padding_rule": "Base padding plus reported operation accuracy; unknown accuracy adds 100 m. Longitude uses cos(latitude).",
                   "bbox_scope": "Densified sampled boundary envelope with uncertainty padding; a conservative screening heuristic, not an analytic footprint proof. Antimeridian cases use global longitude bounds.",
                   "rgb_content_hash": "Decoded RGB uint8 row-major interleaved bytes plus equal image dimensions for grouping",
                   "read_scope": "Manifest, partition and RGB files only; no semantic-label rasters or model results accessed"},
        "summary": summary, "unknown_items": [{"member": item["member"], "reason": item["unknown_reason"]} for item in unknown],
        "cross_split_bbox_candidates": overlap_candidates, "cross_split_region_envelope_candidates": region_candidates,
        "decoded_rgb_duplicates": duplicates, "selected_region_envelopes": envelopes,
        "claim_limits": [
            "Any absence of overlap applies only to selected RGB tiles with supported metadata and available offline transforms.",
            "Padded sampled bboxes screen for potential overlap; intersections require review and do not establish leakage.",
            "No bbox intersection is not proof of complete geographic independence, exact footprint disjointness, or independent source mosaics.",
            "Full source orthomosaic extents, acquisition times, provenance relationships, label provenance and near-duplicate/transformed imagery remain unaudited.",
            "Coordinate metadata can be wrong; operation accuracy and sampling padding are not surveyed error guarantees.",
            "Decoded exact-pixel hashes detect only identical full RGB rasters of equal dimensions, not overlapping crops or near duplicates.",
        ], "tiles": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    existing = output.stat().st_size if output.exists() else 0
    project_bytes = sum(path.stat().st_size for path in ROOT.rglob("*") if path.is_file() and not path.is_symlink())
    if project_bytes - existing + len(text.encode("utf-8")) >= 2_000_000_000:
        raise OSError("Audit output would exceed the project's 2,000,000,000-byte limit")
    output.write_text(text, encoding="utf-8")
    print(json.dumps({"summary": summary, "output": str(output), "output_bytes": output.stat().st_size}, indent=2))


def self_test():
    tags = {33550: [2, 3, 0], 33922: [1, 2, 0, 100, 200, 0]}
    affine, _ = raster_affine(tags)
    assert apply_affine(affine, 1, 2) == (100, 200)
    assert apply_affine(affine, 2, 3) == (102, 197)
    matrix = {34264: [2, 1, 0, 10, -1, 3, 0, 20, 0, 0, 1, 0, 0, 0, 0, 1]}
    assert apply_affine(raster_affine(matrix)[0], 2, 4) == (18, 30)
    point, _ = raster_boundary(10, 20, 2, 2)
    assert point[0] == (-0.5, -0.5) and point[2] == (9.5, -0.5)
    keys = geokeys({34735: [1, 1, 0, 2, 1024, 0, 1, 1, 3072, 0, 1, 32632]})
    assert epsg_from_keys(keys) == (32632, 3072)
    try:
        epsg_from_keys(geokeys({34735: [1, 1, 0, 3, 1024, 0, 1, 1, 3072, 0, 1, 32767, 2048, 0, 1, 4326]}))
    except UnknownGeography:
        pass
    else:
        raise AssertionError("Projected user-defined CRS must not fall back to geographic EPSG")
    assert intersects([0, 0, 1, 1], [1, 1, 2, 2])
    assert not intersects([0, 0, 1, 1], [2, 2, 3, 3])
    assert bbox([(179.9, 0), (-179.9, 0)])[0][::2] == [-180, 180]
    print("Self-checks passed: affine transforms, point footprint, EPSG parsing, unsafe fallback, bbox screening")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "formal120" / "manifest.json")
    parser.add_argument("--partition", type=Path, default=ROOT / "configs" / "formal_region_partition.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "geography_audit.json")
    parser.add_argument("--edge-segments", type=int, default=64)
    parser.add_argument("--padding-meters", type=float, default=20.0)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.edge_segments < 4 or not math.isfinite(args.padding_meters) or args.padding_meters < 0:
        parser.error("Need at least 4 edge segments and finite nonnegative padding")
    audit(args.manifest.resolve(), args.partition.resolve(), args.output.resolve(), args.edge_segments, args.padding_meters)


if __name__ == "__main__":
    main()

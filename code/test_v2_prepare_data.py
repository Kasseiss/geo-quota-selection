"""Bounded v2 preparation checks: in-memory fixtures and one existing old pair.

No permanent-panel payload or network is accessed. Temporary output stays under
evidence/v2/software and is removed after each test.
"""
import io
import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

import numpy as np
from PIL import Image, TiffImagePlugin
import v2_prepare_data as v2


def tiff_bytes(array, geo=True):
    buffer = io.BytesIO()
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    if geo:
        tags[33550] = (0.5, 0.5, 0.0); tags.tagtype[33550] = 12
        tags[33922] = (0.0, 0.0, 0.0, 500000.0, 4650000.0, 0.0); tags.tagtype[33922] = 12
        tags[34735] = (1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1, 1, 3072, 0, 1, 32632); tags.tagtype[34735] = 3
    Image.fromarray(array).save(buffer, format="TIFF", tiffinfo=tags)
    return buffer.getvalue()


def source_spec(member, data):
    return {"member": member, "bytes": len(data), "compressed_bytes": None,
            "zip_crc32": f"{zlib.crc32(data):08x}", "sha256": v2.sha_bytes(data)}


class V2PreparationTests(unittest.TestCase):
    real_old_summary = None

    def setUp(self):
        v2.SOFTWARE_ROOT.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="v2test-", dir=v2.SOFTWARE_ROOT)
        self.patch = patch.object(v2, "DATA_ROOT", Path(self.temporary.name))
        self.patch.start()
        v2.geography.network.set_network_enabled(False)

    def tearDown(self):
        self.patch.stop()
        self.temporary.cleanup()

    def fixture(self, geo=True):
        rgb = np.empty((32, 48, 3), dtype=np.uint8); rgb[:] = (10, 20, 30)
        mask = (np.arange(32 * 48).reshape(32, 48) % 9).astype(np.uint8)
        a, b = tiff_bytes(rgb, geo), tiff_bytes(mask, geo)
        spec = v2.pair_spec("old_development", "synthetic",
            source_spec("OEM/synthetic/images/synthetic_1.tif", a),
            source_spec("OEM/synthetic/labels/synthetic_1.tif", b))
        return spec, a, b, rgb, mask

    def converted(self, spec, a, b):
        verified_a = v2.verified_stream(io.BytesIO(a), spec["rgb"])
        verified_b = v2.verified_stream(io.BytesIO(b), spec["label"])
        bindings = v2.current_bindings()
        buffers, metadata = v2.convert_pair(spec, verified_a, verified_b, bindings)
        for relative, data in buffers.items():
            v2.atomic_new_or_identical(v2.member_path(v2.DATA_ROOT, relative), data)
        record = v2.record_from_metadata(spec, metadata, buffers[v2.output_names(spec)["metadata"]])
        v2.verify_saved(spec, record, bindings)
        return buffers, metadata, record

    def test_crc_and_sha_precede_decode(self):
        spec, a, _, _, _ = self.fixture()
        corrupt = a[:-1] + bytes([a[-1] ^ 1])
        with patch.object(v2.Image, "open", side_effect=AssertionError("Decode must not occur")):
            with self.assertRaisesRegex(RuntimeError, "CRC32"):
                v2.verified_stream(io.BytesIO(corrupt), spec["rgb"])
        changed = dict(spec["rgb"], sha256="0" * 64)
        with self.assertRaisesRegex(RuntimeError, "SHA256"):
            v2.verified_stream(io.BytesIO(a), changed)

    def test_png_pixels_metadata_geo_and_strict_resume(self):
        spec, a, b, rgb, mask = self.fixture()
        buffers, metadata, record = self.converted(spec, a, b)
        self.assertEqual(metadata["source_rgb"]["original_decoded_rgb_sha256"], v2.sha_bytes(rgb.tobytes()))
        self.assertEqual(metadata["source_label"]["original_mask_class_counts_raw_0_to_8"], np.bincount(mask.ravel(), minlength=9).tolist())
        self.assertTrue(metadata["source_rgb"]["geography"]["resized_world_footprint_matches_source"])
        self.assertLessEqual(metadata["compact_payload_bytes"], 900000)
        self.assertFalse(list(v2.DATA_ROOT.rglob("*.tif")))
        with Image.open(v2.DATA_ROOT / record["rgb"]["relative_path"]) as image:
            self.assertTrue(np.all(np.asarray(image) == np.array([10, 20, 30])))
        with Image.open(v2.DATA_ROOT / record["label"]["relative_path"]) as image:
            ys = np.minimum(31, np.floor((np.arange(448) + .5) * 32 / 448).astype(int))
            xs = np.minimum(47, np.floor((np.arange(448) + .5) * 48 / 448).astype(int))
            np.testing.assert_array_equal(np.asarray(image), mask[ys[:, None], xs[None, :]])
        rgb_path = v2.DATA_ROOT / record["rgb"]["relative_path"]
        rgb_path.write_bytes(rgb_path.read_bytes()[:-1] + b"!")
        with self.assertRaisesRegex(RuntimeError, "PNG SHA256"):
            v2.verify_saved(spec, record, v2.current_bindings())

    def test_missing_geo_stays_unknown(self):
        spec, a, b, _, _ = self.fixture(geo=False)
        _, metadata, _ = self.converted(spec, a, b)
        self.assertEqual(metadata["source_rgb"]["geography"]["status"], "unknown")
        self.assertNotIn("png_georeference_sidecar_affine", metadata["source_rgb"]["geography"])

    def test_point_and_rotated_affine_preserve_support(self):
        original = [.5, .1, 500000, .2, -.5, 4650000]
        new = v2.resized_affine(original, 48, 32, 2)
        old_boundary, _ = v2.geography.raster_boundary(48, 32, 2, 4)
        new_boundary, _ = v2.geography.raster_boundary(448, 448, 2, 4)
        np.testing.assert_allclose([v2.geography.apply_affine(original, *point) for point in old_boundary],
                                   [v2.geography.apply_affine(new, *point) for point in new_boundary], rtol=0, atol=1e-8)

    def test_old_plan_reads_no_rasters_or_network(self):
        with patch.object(v2.remote_zip, "HTTPRangeReader", side_effect=AssertionError("Network forbidden")), \
             patch.object(v2.Image, "open", side_effect=AssertionError("Raster read forbidden")):
            plan = v2.make_plan(v2.DATA_ROOT / "old_plan.json", stage="old")
        self.assertEqual(plan["expected"]["total"], 120)
        self.assertTrue(all(pair["role"] == "old_development" for pair in plan["pairs"]))

    def test_development_snapshot_is_immutable_across_stage_append(self):
        # This tests orchestration only; actual PNG/source verification is
        # independently exercised by both fixture and real-old-pair tests.
        old_path = v2.DATA_ROOT / "selection_plan_old.json"
        old_plan = v2.make_plan(old_path, stage="old")
        old_state = v2.Preparation(old_path, old_plan)
        old_state.records = {spec["id"]: {"id": spec["id"], "region": spec["region"],
                             "role": "old_development", "compact_payload_bytes": 100}
                             for spec in old_plan["pairs"]}
        old_state.manifest["status"] = "complete"
        old_state.save()
        frozen_path = v2.DATA_ROOT / "development_manifest.json"
        frozen_before = frozen_path.read_bytes()
        frozen = json.loads(frozen_before)
        self.assertEqual((frozen["status"], len(frozen["pairs"])), ("complete", 120))
        self.assertFalse(frozen["whole_v2_dataset_complete"])
        combined = v2.read_json(v2.DATA_ROOT / "manifest.json")
        self.assertEqual(combined["status"], "partial")
        self.assertEqual(combined["expected"]["total"], 192)

        all_plan = deepcopy(old_plan)
        all_plan.update(stage="all", expected={"old_development": 120, "new_panel": 72, "total": 192})
        all_path = v2.DATA_ROOT / "selection_plan.json"
        all_path.write_bytes(v2.json_bytes(all_plan))
        with patch.object(v2, "verify_saved", return_value=None):
            all_state = v2.Preparation(all_path, all_plan)
        all_state.records["abancay__synthetic"] = {"id": "abancay__synthetic", "region": "abancay",
                                                   "role": "new_panel", "compact_payload_bytes": 100}
        all_state.save()
        self.assertEqual(frozen_path.read_bytes(), frozen_before)
        self.assertEqual(len(v2.read_json(v2.DATA_ROOT / "manifest.json")["pairs"]), 121)

    def test_budget_gate_stops_before_source_reads(self):
        with patch.object(v2, "reserve_check", side_effect=RuntimeError("reservation refused")), \
             patch.object(v2, "Sources", side_effect=AssertionError("Source must stay unopened")):
            with self.assertRaisesRegex(RuntimeError, "reservation refused"):
                v2._prepare(v2.DATA_ROOT / "nonexistent_plan.json", 2, "old")

    def test_one_existing_old_pair_only(self):
        spec = v2.local_specs()[0]
        streams = []
        for kind in ("rgb", "label"):
            path = v2.member_path(v2.OLD_MANIFEST.parent, spec[kind]["member"])
            with path.open("rb") as stream:
                streams.append(v2.verified_stream(stream, spec[kind]))
        buffers, metadata = v2.convert_pair(spec, *streams, v2.current_bindings())
        for relative, data in buffers.items():
            v2.atomic_new_or_identical(v2.member_path(v2.DATA_ROOT, relative), data)
        record = v2.record_from_metadata(spec, metadata, buffers[v2.output_names(spec)["metadata"]])
        v2.verify_saved(spec, record, v2.current_bindings())
        self.__class__.real_old_summary = {"id": spec["id"], "source_bytes_verified": sum(spec[k]["bytes"] for k in ("rgb", "label")),
                                          "compact_payload_bytes": metadata["compact_payload_bytes"],
                                          "geographic_status": metadata["source_rgb"]["geography"]["status"]}


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(V2PreparationTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"utc": v2.now(), "conversion_code_sha256": v2.sha_file(Path(v2.__file__)),
              "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "real_old_pair": V2PreparationTests.real_old_summary,
              "new_panel_payloads_read": False, "network_accessed": False,
              "temporary_outputs_removed": True}
    v2.SOFTWARE_ROOT.mkdir(parents=True, exist_ok=True)
    (v2.SOFTWARE_ROOT / "preparation_validation.json").write_bytes(v2.json_bytes(report))
    raise SystemExit(not result.wasSuccessful())

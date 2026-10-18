# V2 compact data preparation

This preparation creates a new dataset representation. It does not modify the old `data/`, cache indexes, run evidence or delivered packages. No original TIFF is persisted by this tool.

## Fixed design and commands

All 120 old formal pairs are development/source data. The permanent new panel is 24 unused regions, three complete pairs each, with seed **2026101802**:

`abancay, al_qurnah, baybay, bielefeld, buenos_aires, chiclayo, coxsbazar, dowa, kagera, kampala, khartoum, kinshasa, kitsap, monrovia, ngaoundere, paris, rosario, san_tome, soriano, svaneti, tokyo, tyrolw, western, zanzibar`.

Selection uses only filename-sorted complete ZIP pairs and independent per-region seeded sampling. Original mask counts, images, geometry and model outcomes do not enter selection. No sample is substituted if a technical check fails.

First prepare development data, without network access:

```text
python code/v2_prepare_data.py --plan --old-only
python code/v2_prepare_data.py --prepare --old-only
```

`--stage old` is equivalent to `--old-only`. The old plan reads only the old manifest. Old preparation validates bytes from the retained local TIFFs and saves 448×448 PNGs under `v2/data/old_development/`.

Only after review and explicit authorization, plan and prepare the full dataset:

```text
python code/v2_prepare_data.py --plan
python code/v2_prepare_data.py --prepare --workers 2
```

The all-stage plan reads the official ZIP directory by HTTP Range; it does not open RGB/mask members. It records the exact 72 new member pairs. The all-stage prepare strictly reuses verified development PNGs and downloads only missing selected new-panel originals into RAM. `--workers` accepts one or two; each worker owns its own HTTP reader and ZIP handle.

The two reviewed plan files are `v2/data/selection_plan_old.json` and `v2/data/selection_plan.json`. Existing plans are not overwritten with changed selection, code or runtime bindings.

## Stable manifests and source metadata

The model-facing interface is `manifest.pairs`, with each pair containing:

```json
{
  "id": "region__original_name",
  "region": "region",
  "role": "old_development or new_panel",
  "rgb": {"relative_path": "old_development/region/name_rgb.png", "sha256": "...", "bytes": 0},
  "label": {"relative_path": "old_development/region/name_mask.png", "sha256": "...", "bytes": 0},
  "source_rgb": {"member": "...", "sha256": "...", "bytes": 0, "zip_crc32": "..."},
  "source_label": {"member": "...", "sha256": "...", "bytes": 0, "zip_crc32": "..."},
  "metadata": {"relative_path": "old_development/region/name.json", "sha256": "...", "bytes": 0}
}
```

All PNG and sidecar paths are relative to a manifest in `v2/data/`.

`old_development_manifest.json` is the old-stage progress/completion record. Once all old 120 pairs verify, **`development_manifest.json` is published once and never rewritten**. It contains only old development pairs, `status: complete`, and `whole_v2_dataset_complete: false`. Bind source calibration to this immutable file's SHA256.

The main `manifest.json` is explicitly `partial` after old-only preparation. Later all-stage work appends verified new-panel pairs there. Only the exact 192 pairs make it `complete` with `whole_v2_dataset_complete: true`. The immutable development file remains byte unchanged. Do not treat the old component's completeness as completion of the permanent panel.

Each per-pair JSON records original file size, ZIP CRC32, full original-byte SHA256, decoded original RGB SHA256, original dimensions, decoded original mask SHA256 and the nine raw-ID mask counts. Counts are **metadata only**. Selection-policy functions must receive only permitted IDs/regions/descriptors, never these sidecars or class-count fields. Do not inspect or aggregate permanent-panel class proportions before the analysis design permits it.

## Integrity, conversion and geographic metadata

Each original stream is read to EOF in RAM. ZIP member decoding checks its CRC, and the tool independently checks expected size and CRC32, computes SHA256, and compares any prebound SHA **before image decoding**. Old originals are bound to the original `data/formal120/manifest.json` SHA and its member hashes. First new-panel hashes are recorded after CRC/size verification; they are not represented as an independent verification of the entire 9.1GB archive MD5.

RGB uses Pillow bilinear resizing to 448 square. Masks use nearest-neighbour resizing and retain integer IDs 0–8, with 0 void. PNG compression is lossless, level 9, without optimize. Saved PNGs are decoded back and compared exactly with the intended resized pixels. Width/height/mode, PNG SHA256 and bytes are checked again during resume.

This loses original-resolution mask detail. Original class counts are retained but cannot reconstruct the native mask geometry. Do not silently reuse old feature-target caches as though they came from these resized masks; the new feature specification must bind to the compact PNGs and transformation code. Native-resolution soft targets and compact-mask targets are distinct representations.

PNG does not carry the full TIFF georeference. Every pair sidecar preserves both originals' complete standard GeoTIFF tags **33550, 33922, 34264, 34735, 34736, 34737**, and present GDAL metadata/nodata and RPC tags **42112, 42113, 50844**. It also records orientation, EPSG GeoKeys, raster convention, source affine, offline transformation identity/accuracy, and densified WGS84 boundary samples when supported.

The sidecar affine describes the 448 PNG footprint. Pixel-is-area uses the original affine composed with `diag(width/448, height/448)`. Pixel-is-point also applies the centre shift `(scale−1)/2`. Original and resized boundary coordinates must match in model space. Rotated/sheared affines are supported through the existing geography-audit functions. Unsupported/missing CRS, non-default orientation and area-of-use cautions remain explicit warnings/unknowns. They do not trigger replacement samples and do not prove geographic independence. Geographic-network grid downloads are disabled.

## Capacity and recovery

The complete **192-pair** preparation requires a **200,000,000-byte** reservation. Before preparation and before each commit, project bytes outside `v2/data` plus that reservation must be strictly below **2,000,000,000 bytes**. Every pair's two PNGs plus provenance JSON must be at most **900,000 bytes**, giving at most 172.8MB of pair payload plus reserved metadata/temporary space. The tool stops on an exceeded limit and never lowers resolution or changes the sample.

Per-pair outputs are atomically named. A pair is committed to the manifest only after PNG and sidecar verification. Same-code, same-runtime, same-plan restarts verify all existing hashes before adoption; a completed pair sidecar interrupted before the global manifest update can be recovered without rereading an original. Different or damaged files stop the run rather than being overwritten. PNGs left without a committed sidecar are compared with freshly verified deterministic conversion before adoption.

The manifest keeps per-region progress, prior attempt status/errors and recovery events. Runtime, conversion-code, original-development-manifest, range-reader and geography-helper hashes are bound in the plan and pair records. Do not edit these files midway through preparation. Reproducible PNG byte hashes also require the recorded Pillow/runtime versions.

Software snapshots and small failure/validation records belong in `evidence/v2/software/`; prepared data belongs only in `v2/data/`. A process lock prevents simultaneous old/all invocations from writing the same manifest. If a process is forcibly killed and leaves `.prepare.lock`, first verify the recorded process is stopped, retain its checkpoint/error evidence, then review removal of only that owned stale lock before resuming. Unreferenced `.part` files from a hard kill are retained and counted in the reservation; they are not silently treated as completed data.

## Bounded verification

```text
python code/v2_prepare_data.py --help
python -B code/test_v2_prepare_data.py
```

Tests use in-memory TIFF fixtures and one existing old pair. They cover CRC/SHA before decode, nearest-neighbour class preservation, lossless PNG round-trip, source-pixel hashes, pixel-is-point/rotated footprint mapping, explicit unknown geography, strict hash rejection, an old-only plan with raster/network access forbidden, a capacity gate before source reads, and development-snapshot immutability during a simulated old-to-all append. The append test isolates orchestration with file verification stubbed; fixture and real-pair tests exercise file verification separately. Temporary test outputs stay under `evidence/v2/software/` and are removed. The small summary is `evidence/v2/software/preparation_validation.json`; it does not expose class proportions. No new permanent-panel image/mask is downloaded by these tests.

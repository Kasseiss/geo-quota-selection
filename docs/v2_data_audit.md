# V2 compact-data audit

After preparation completes all 192 pairs, run:

```text
python -B code/v2_audit_data.py
```

The default report is `evidence/v2/data_audit.json`. Exit 0 means technical integrity and the exact dataset partition passed. Exit 1 means an input is missing/incomplete, a checksum or source binding differs, a PNG is invalid, or the partition does not match the fixed design. A partial old-only manifest cannot pass the complete192 audit. The audit never downloads data, modifies samples, trains a model or reads model outcomes.

The report binds its own code and the geography helper by SHA256. It hashes the main manifest, immutable development manifest, reviewed all-stage selection plan, v2 design, original formal120 manifest and original DINO index. It checks the preparation code/helper/source-manifest bindings and exact reviewed member IDs, roles, names, sizes, CRCs and any prebound SHA. New original hashes are recorded provenance, not independent full-archive authentication.

Every pair's provenance sidecar and two PNGs are hashed and checked against their manifest size and SHA. PNGs must be RGB/L, 448×448, with masks containing only uint8 raw IDs 0–8. For each verified pair, `processed_png_availability.pairs` records `processed_mask_class_counts_raw_0_to_8`: nine integer counts computed directly with `np.bincount` from the actual decoded 448×448 PNG mask. They include raw0 void and must sum to 200,704. This field lets a later run audit check each image's eight-class confusion-matrix truth margins against counts 1–8 without reopening PNGs; the eight counts sum to the nonvoid pixels, not necessarily all 200,704 pixels. The counts are technical audit evidence and must never enter selection policies. The audit does not access the original mask-count fields in the provenance sidecar. Each pair must obey its 900,000-byte payload cap. Paths must stay under the manifest directory; a PNG path cannot be claimed twice.

The old120 IDs, member metadata and RGB/mask original hashes must match the retained original formal manifest and DINO index. The DINO index must itself bind to that original manifest SHA. The immutable `development_manifest.json` records must equal the combined manifest's old-development records. The three source allocations must each partition the old24 into train12/validation4/unused8. The permanent panel must contain the fixed new24×3 with no old/new region intersection. Native TIFF files and feature arrays are not read or rehashed here; the report distinguishes source-hash agreement from fresh raw-file verification.

The retained legacy downloader manifest stores `region`, `rgb` and `label` but omits pair-level `id`. Only for that original schema, the audit derives the stable ID as `region + "__" + Path(rgb.member).stem`. It first verifies matching RGB/label filenames, the expected `images`/`labels` directories under the same region, safe member paths and agreement with an explicit ID if one exists. V2, reviewed-plan, immutable-development and DINO schemas still require their explicit IDs. Subsequent member/CRC/size/SHA and DINO source-SHA comparisons remain mandatory. The first audit attempt's schema failure is retained under `evidence/v2/audit_attempts/`; no original manifest or preparation binding was changed to repair it.

## Geographic screening and duplicate evidence

Geography comes only from SHA-verified RGB provenance sidecars. The audit does not reopen TIFFs, infer missing CRS or rerun coordinate transforms. A pair enters the supported geographic screen only when its sidecar reports a supported transform, matching resized footprint and all sampled points inside the declared CRS/operation area of use. Missing or unsupported boundaries remain unknown. CRS cautions are listed explicitly and excluded from supported geographic separation claims; usable caution boundaries receive a separate candidate screen.

For each supported old/new pair and each source allocation's train/validation pair, the audit computes a WGS84 boundary envelope with padding equal to 20m plus reported operation accuracy. Unknown accuracy adds 100m. It reuses `geography_audit.bbox` and `intersects`, including global-longitude treatment of antimeridian cases. Touching boxes count as candidates. The report gives the exact number of compared pairs, coverage by role/allocation, and every candidate pair. Geographic cautions and unknowns are not silently counted as verified separation.

An independent cross-role screen groups the original decoded RGB byte SHA together with equal original dimensions. It uses only sidecar hashes, not image content inspection. The hash definition is row-major interleaved uint8 RGB bytes from the original Pillow decode. Different native dimensions are not classified as the same content by this screen.

Candidate bbox overlaps and decoded-content matches set `human_review_required: true`; they do not trigger deletion, replacement or an automatic assertion of leakage. `passed` and `processed_pngs_usable` describe technical integrity. `geographic_inference_limited`, the explicit unknown/caution records and candidate lists describe the limits on interpretation. Even a clear supported screen cannot establish full source-mosaic independence, detect every near duplicate or prove the absence of all leakage. Coordinate metadata and padded sampled boundaries are not surveyed error guarantees.

## Bounded software checks

```text
python -B code/v2_audit_data.py --help
python -B code/v2_audit_data.py --self-test
```

The five synthetic tests check inclusive bbox intersections, caution exclusion, cross-role decoded-hash matches requiring equal dimensions, incorrect fixed-region counts, an explicitly constructed 448×448 mask with known raw0–8 counts and rejection of raw9, and a fixture following the real legacy original schema without `id` (including filename/region/explicit-ID mismatch and duplicate rejection). They read no dataset, new-panel pixels, original masks or model outputs, and write no files. Run the full audit only after preparation is complete. Optional input/output paths are exposed by `--help`; reports remain restricted to `evidence/v2/` and the project byte budget is checked before writing.

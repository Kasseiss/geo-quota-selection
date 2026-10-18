# Release notes

## 2026-10-18 — public archive created

This repository is the public research archive for the manuscript *"When Diversity Means Outliers:
Geographic Allocation for Selecting Training Images in Low-Budget Land Cover Segmentation"*.

What changed relative to the internal audited delivery package:

1. **Public archive published** at <https://github.com/Kasseiss/geo-quota-selection>. The manuscript's
   Data Availability Statement previously read "A permanent repository address will be supplied
   before publication"; it now cites this URL (see `DATA_AVAILABILITY.md`).
2. **Not redistributed**: the 192 frozen DINOv2 feature caches (`*.npz`), the prepared RGB and label
   PNGs under `v2/data/`, one trained U-Net checkpoint (`*.pt`), and compiled manuscript exports
   (`*.docx`, `*.pdf`, `*.zip`). The reasons are recorded in `README.md`; `docs/data_attribution.md`
   documents the per-source licence position that motivates the imagery exclusion.
3. **Added for the public archive**: `README.md`, `LICENSE`, `DATA_AVAILABILITY.md`, `MANIFEST.sha256`,
   `tools/verify_archive.py`, `tools/build_manifest.ps1`, `.gitignore`.
4. **Unchanged**: every frozen configuration, every per-run result record and training log, every
   image-identity manifest, all six numerical result tables, all figure code, and every audit record.
   The file hashes recorded in `manuscript_state.json` still match.

The internal audit trail in `docs/` is preserved as written on the audit date; where it lists the
missing repository address as an open item (`docs/v3_submission_checklist.md`, item 5), that item is
resolved by this release.

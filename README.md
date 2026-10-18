# Geographic allocation for low-budget land cover image selection

Research archive for the manuscript **"When Diversity Means Outliers: Geographic Allocation for
Selecting Training Images in Low-Budget Land Cover Segmentation"** (MDPI).

The study asks a single question at a very small annotation budget: when only twelve training images
can be labelled, does *where* they come from matter more than how *different* they look? Ten
label-free selection rules were compared on 24 evaluation regions that played no part in selection,
fitting or calibration. The archive contains the frozen experiment design, the selection and training
code, every per-image confusion matrix, all training logs, the complete result tables, the code that
draws every figure, and the provenance records that tie each image identity back to OpenEarthMap.

## Contents

| Path | What it holds |
|---|---|
| `configs/` | Frozen study design, supplementary design, execution freeze, backend amendment, pixel-budget design |
| `docs/` | Protocol, analysis, data audit, attribution and licence register, figure/table provenance, reproduction and packaging notes |
| `code/` | Selection, data preparation, training, analysis, audit, figure and packaging code (NumPy / PyTorch / CuPy) |
| `tables/` | The six numerical result tables, the pixel-budget analysis and the analysis identity record |
| `evidence/` | Per-run result records and training logs, calibration, audits, completeness records, software and environment snapshots |
| `figures/` | Published figure files |
| `paper/v3/` | Compilation code and vector figure sources for the submitted article and supplement |
| `v2/data/*.json` | Image identities: manifests, selection plans and per-image provenance sidecars for the 120 development and 72 evaluation images |
| `v2/cache/*/index.json` | DINOv2 feature-index metadata (which image produced which cached feature record) |
| `delivery_manifest.json`, `manuscript_state.json` | The audited delivery manifest (SHA256 per file) and the project state record |

## What is deliberately **not** in this repository

| Omitted | Why |
|---|---|
| Raw and resampled RGB imagery, and the 448 px label masks (`v2/data/**/*.png`) | Each OpenEarthMap source carries its own licence, and for one region the RGB licence is unverified. Redistribution is not authorised by this project; see `docs/data_attribution.md`. |
| 192 frozen DINOv2 feature caches (`*.npz`) | Regenerable, ~136 MB of binary arrays, and not needed for any table in the article. |
| One trained U-Net checkpoint (`.pt`) | 47 MB; the optional reload check in `code/v2_reload_checkpoint.py` needs it, the reported results do not. |
| Compiled manuscript exports (`.docx`, `.pdf`, `.zip`) | The article is the citable record; this repository is the data and code archive. |

Because the imagery is absent, the pixel-level audit (`code/v2_audit_runs.py`) cannot run here
directly. Everything that does not need pixels — the six result tables, the per-image confusion
matrices, the statistics, every figure — is present and hash-bound. To re-derive the imagery, use
`code/data_access.py` and `code/v2_prepare_data.py` against the official OpenEarthMap release, then
re-run the audit. The manifests record every image identity needed for that re-derivation.

## Verify the archive

```bash
python tools/verify_archive.py
```

This recomputes SHA256 for every file against `MANIFEST.sha256` and reports missing, altered or extra
files. It needs only the Python standard library. The same identities for the headline artifacts are
recorded in `manuscript_state.json` under `release.checked_hashes`.

## Reproduce the numbers

The six result tables are derived from the per-image confusion matrices alone, with no model or
feature access:

```text
python -B code/v2_audit_runs.py    # repopulates the run-completeness audit (requires the imagery)
python -B code/v2_statistics.py    # recomputes tables/v2/*.csv and *.json
```

`code/v2_statistics.py` needs only NumPy. `code/v2_audit_runs.py` re-reads the prepared imagery, so in
this archive it is the gate that must be satisfied after local re-preparation from OpenEarthMap.

Results can also be checked without recomputation:

```text
python -B code/v2_active_gpu_results.py --verify-tables
```

This compares the six tables against the recorded audit identities. It requires the recorded runtime
(`Python 3.12.3`, `NumPy 2.3.5`) and refuses a different one rather than guess.

Figures and the article build:

```text
cd paper/v3/code
python -B v3_analysis.py
python -B v3_package.py
```

## Experiment in one paragraph

Ninety complete spatial-model fits (ResNet18 U-Net, CPU) and 486 frozen-DINOv2 feature-head fits
(local RTX4060) form the active 576-run matrix. Three source allocations rotate 24 development regions
through training, validation and disuse; all scores come from 24 further regions reserved before
evaluation. The primary comparison was fixed before the panel was scored, and the execution backend
changed after panel exposure, so the complete-model display is descriptive. A separate 27-fit control
equalises available supervision pixels. Region quota k-center exceeds plain k-center by 1.68 mIoU
points in the complete model (95% region-bootstrap interval 0.86 to 2.51) and by 2.24 points in the
re-execution; equal-available-pixel matching leaves the gain with a positive point estimate of 2.00
points. No algorithmic or state-of-the-art claim is made.

## Data sources and licences

Imagery and reference labels come from **OpenEarthMap**
(<https://doi.org/10.5281/zenodo.7223446>), which aggregates imagery under source-specific licences
(CC BY 4.0, CC BY-SA 4.0, DL-DE-BY-2.0 and public domain, with a CC BY-NC-SA 4.0 fallback for labels
whose source imagery is public domain or unclear). Per-region source, provider and licence are
registered in `docs/data_attribution.md`; one region (Kyoto) has an unverified RGB licence and is
flagged there.

## Licence of this archive

Code is released under the MIT licence. The author-generated tables, records, manifests and figures
are released under CC BY 4.0. No rights are granted over third-party imagery or over OpenEarthMap
labels, which remain under their original terms. See `LICENSE`.

## Citation

Cite the article once it is published. Until then, refer to this archive by its URL and to the
manuscript title above.

## Contact

Correspondence concerning this archive: see the corresponding author listed in the article.

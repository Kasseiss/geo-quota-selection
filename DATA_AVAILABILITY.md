# Data Availability Statement

Ready-to-paste text for the manuscript and for the submission system. Replace `URL` and `DOI` only if
the repository address or an archival DOI changes.

## Statement for the manuscript (MDPI style, one paragraph)

> **Data Availability Statement:** The complete research archive supporting this study is openly
> available at <https://github.com/Kasseiss/geo-quota-selection>. It contains the frozen experiment
> design and configurations, the image-selection and training code, every per-image confusion matrix
> and training log, the six numerical result tables, the code that draws every figure in this article,
> and the per-image provenance records that identify each of the 192 images used. Raw RGB imagery and
> label masks are not redistributed, because the OpenEarthMap sources carry individual licences and
> the RGB licence for one region remains unverified; the archive instead provides the image
> identities, the retrieval and preparation scripts, and a per-region attribution and licence
> register (`docs/data_attribution.md`). All imagery and reference labels derive from OpenEarthMap,
> available from <https://doi.org/10.5281/zenodo.7223446> under the licences of its individual
> sources. No new primary data were collected; all measurements reported here are derived from the
> archived selections, fits and per-image confusion matrices.

## Shorter variant, if the journal enforces a length limit

> **Data Availability Statement:** The research archive is openly available at
> <https://github.com/Kasseiss/geo-quota-selection>: frozen design and configurations, selection and
> training code, all per-image confusion matrices and training logs, the six result tables, figure
> code, and the provenance records identifying every image. Raw imagery and label masks are not
> redistributed because of source-specific OpenEarthMap licences; image identities, retrieval scripts
> and a per-region attribution register are provided instead. OpenEarthMap is available from
> <https://doi.org/10.5281/zenodo.7223446> under the licences of its individual sources.

## Chinese version for internal review (not for submission)

> **数据可用性声明：** 本研究的完整研究档案公开于 <https://github.com/Kasseiss/geo-quota-selection>，
> 包括冻结的实验设计与配置、选图与训练代码、逐图混淆矩阵与训练日志、六张结果表、绘制正文全部插图的
> 代码，以及标识全部 192 张图像的溯源记录。原始 RGB 影像与标签掩膜不予再分发，因为 OpenEarthMap 各来源
> 采用各自的许可，且其中一个地区的 RGB 许可状态尚未核实；档案改为提供图像标识、检索与预处理脚本以及逐地区
> 来源与许可登记表（`docs/data_attribution.md`）。全部影像与参考标签源自 OpenEarthMap，
> 见 <https://doi.org/10.5281/zenodo.7223446>，按其各来源许可使用。本研究未采集新的原始数据，
> 文中全部测量值均由档案中的选图、拟合结果与逐图混淆矩阵导出。

## Where to edit

| File | Location |
|---|---|
| `paper/v3/submission/latex/manuscript.tex` | `\dataavailability{...}` (line 276) |
| `paper/v3/code/v3_text.py` | the `data_availability` string used to regenerate the Word file |
| `manuscript.docx` | paragraph 115 ("Data Availability") |

After editing the text source, rebuild with `python -B paper/v3/code/v3_package.py` so the Word,
LaTeX and PDF versions stay consistent.

## Optional: archival DOI

A GitHub repository URL is acceptable to MDPI, but a DOI is stronger. To mint one, connect the
repository to Zenodo (Zenodo → GitHub → toggle the repository on), cut a release `v1.0.0`, and paste
the minted DOI into the statement, for example:

> ... openly available at <https://github.com/Kasseiss/geo-quota-selection> and archived at
> <https://doi.org/10.5281/zenodo.XXXXXXX>.

Add the same DOI to the reference list if the journal asks for a data citation.

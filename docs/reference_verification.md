# 核心引文元数据核查

核查日期2026-10-18。`references.bib`中的九项为当前可用核心引文，不等于全文最终引用清单。以下为正式版本和元数据边界。

- OpenEarthMap：CVF与IEEE登记页码不同（6254–6264对6243–6253），当前条目保留DOI、作者、题名及会议，暂不填页码，避免混配两套分页。CVF：https://openaccess.thecvf.com/content/WACV2023/html/Xia_OpenEarthMap_A_Benchmark_Dataset_for_Global_High-Resolution_Land_Cover_Mapping_WACV_2023_paper.html ；IEEE登记：https://api.crossref.org/works/10.1109/WACV56688.2023.00619 。
- DINOv2：引用TMLR 2024正式版；2023为预印本首次公开年份，不混写。作者PDF首页及OpenReview为核验入口：https://arxiv.org/pdf/2304.07193 ；https://openreview.net/forum?id=a68SUt6zFt 。正式版卷页/DOI未核实，未填。
- ResNet：CVF官方作者与题名：https://openaccess.thecvf.com/content_cvpr_2016/html/He_Deep_Residual_Learning_CVPR_2016_paper.html ；IEEE DOI 10.1109/CVPR.2016.90，页770–778。
- Core-set：正式ICLR 2018与2017预印本编号1708.00489区分：https://openreview.net/forum?id=H1aIuk-RW 。
- AdamW：正式ICLR 2019与2017预印本编号1711.05101区分：https://openreview.net/forum?id=Bkg6RiCqY7 。当前训练代码采用解耦权重衰减；需在方法中明确实现及应用参数范围。
- Roberts：正式Ecography 2017, 40(8), 913–929；在线首发2016不能替代卷期年份：https://doi.org/10.1111/ecog.02881 。
- Lu、He、Kaijage：正文核查入口和定位见`literature_matrix.md`；当前页码字段分别为文章号115034、1987、2108，不能解读为页数。

最终稿还需查验每处引文与实际句子、图注和结论的对应关系，元数据核对不能替代引用适切性审核。
# Additional records reconciled during manuscript preparation

- Cai et al.: use the TIP 2021 publication, DOI 10.1109/TIP.2021.3120041, rather than treating the 2025 arXiv reupload as a new paper. Publisher record: https://ieeexplore.ieee.org/document/9580637/ .
- Li: formal 2026 Spatial Statistics metadata, DOI 10.1016/j.spasta.2026.101010. Only the topical/method scope verified at record/abstract level is claimed; inaccessible full text is not used to assert absence of controls.
- Kumar et al.: arXiv2604.08965 is cited explicitly as a2026 preprint. No acceptance or numerical reproduction is asserted.
- CrossEarth: use the sixteen-author TPAMI48(5),5147–5164 (2026) version, DOI 10.1109/TPAMI.2025.3649001. The2025 in the DOI and an older repository citation are not used as the issue year or current author list.
- FROST: Junghwan Park, arXiv2606.31136,2026. Original record verified at https://arxiv.org/abs/2606.31136 ; formal publication was not verified. Its training-free binary support setting is distinguished from the present multiclass head/subset comparison.

The complete bibliography has fourteen records. The Word builder uses an explicit key order matching first citation, independently of the physical BibTeX entry order. Titles and author metadata are retained from the identified records rather than completed from plausible guesses.

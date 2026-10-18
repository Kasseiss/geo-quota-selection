# V3 投稿前核对清单（审计日期 2026-10-18）

本文件只记录"还缺什么 / 哪里有矛盾"，不改动任何稿件或结果文件。
审查对象：`paper/v3/submission/` 全部文件（manuscript.docx / manuscript_word.pdf / manuscript.pdf / manuscript_latex.zip / supplementary_materials.docx+pdf / cover_letter.docx / 投稿说明_README.md）。

## 0. 一句话结论

正文、图、表、补充材料、数字链条都已具备，且内部自洽；**缺的几乎全是"作者与声明信息"，外加一处必须二选一的期刊身份矛盾**（Sensors ↔ Remote Sensing）。这两类补齐后即可上传。

## 1. 阻塞项（不补不能提交）

| # | 缺什么 | 现在文件里是什么 | 要改的位置 |
|---|---|---|---|
| 1 | 作者姓名、顺序、单位、邮箱、通讯作者、ORCID、电话 | `Firstname Lastname`、`Affiliation 1`、`e-mail@e-mail.com`、`0000-0000-0000-000X` | `manuscript.docx` 首页；`latex/manuscript.tex` 第 23–29 行；`code/v3_build_latex.py` 第 189–195 行 |
| 2 | Author Contributions（CRediT） | `To be completed by the authors using the CRediT taxonomy.` | docx 段 111；tex 第 268 行 |
| 3 | Funding（基金名＋编号，或"无外部资助"） | `To be completed by the authors.` | docx 段 112；tex 第 270 行 |
| 4 | Conflicts of Interest | `To be completed by the authors.` | docx 段 117；tex 第 280 行 |
| 5 | Data Availability 的永久仓库地址 | `A permanent repository address will be supplied before publication.` | docx 段 115；tex 第 276 行 |
| 6 | 投稿信里的期刊名与落款 | "…as an Article in **Sensors**"；`[Authors: please confirm or edit these statements.]`；`[Corresponding author name, affiliation, e-mail]` | `cover_letter.docx` 段 1、4、6 |
| 7 | 期刊到底是哪一个 | 文件夹名、`docs/v2_venue_submission.md`、`docs/v2_author_information.txt` 写 **Remote Sensing**；README、LaTeX、Word 模板、投稿信写 **Sensors** | 三处必须统一，见第 2 节 |

> 第 5 项不是措辞问题：正文贡献 4 写明 "We release the complete record of 576 main fits…"，Data Availability 却没有可点的地址，编辑部一定会问。仓库建议在投稿前就建好（现有交付包 422.7 MB / 2817 个文件，Zenodo 单记录上限内，可一次装下）。

## 2. 期刊身份矛盾（必须先决定）

| 位置 | 现在写的是 | 证据 |
|---|---|---|
| `投稿说明_README.md` 第 1、9 行 | MDPI **Sensors** | 模板 = `sensors-template.dot` |
| `cover_letter.docx` 段 1 | **Sensors** | "for consideration as an Article in Sensors" |
| `latex/manuscript.tex` 第 2 行 | `\documentclass[sensors,…]` | 编译出的 PDF 页眉："**submitted to Sensors**"、DOI `10.3390/s1010000` |
| `manuscript.docx` 页眉 | "**Sensors 2025, 25, x** FOR PEER REVIEW" | 来自 Sensors 的 .dot |
| `manuscript.docx` 首页右下 | "Copyright: © **2025** by the authors" | 模板自带年份 |
| `docs/v2_venue_submission.md`、`docs/v2_author_information.txt` | **Remote Sensing**（含 APC CHF 2700、JCR/分区核验） | 项目自己的选刊记录 |
| 交付目录名 | `RemoteSensing_GeographicSelection_V2` | — |

改 Remote Sensing 的工作量（一次性）：
1. `code/v3_build_latex.py` 第 16 行 `JOURNAL = 'sensors'` → `'remotesensing'`（`Definitions/journalnames.tex` 第 4131 行确认支持该选项）；
2. Word 必须换成 Remote Sensing 的官方 .dot 重新生成——`code/v3_build_docx.py` 第 24 行目前指向 `assets/mdpi_sensors_template.docx`，`assets/` 里没有 Remote Sensing 模板；
3. 重跑 `v3_package.py`，Word/LaTeX/PDF/zip 一起刷新；
4. 投稿信、README 同步。

改 Sensors 的话，只需把选题依据（APC、分区）换成 Sensors 的，正文不用动。

## 3. 文件内部的不一致（可直接改）

1. **Word 文档属性泄漏人名**：`manuscript.docx` 的 `lastModifiedBy` = `楚惟 王`，而正文作者仍是占位符；`dc:title` 仍是模板句 `Type of the Paper (Article`。上传前清空/改成真实标题。
2. **补充材料的文档属性标题是旧题名**：`supplementary_materials.docx` 的 `dc:title` = `Supplementary material for Geographic allocation and visual coverage for data efficient land cover segmentation`，正文标题已是 "When Diversity Means Outliers…"。
3. **页数**：LaTeX 版 17 页，Word 版（LibreOffice 渲染）18 页。项目自己的选刊记录写着 Article 至少 18 页（来源为可检索的作者指南，正式页当时未能读取）。这条若成立，LaTeX 版差 1 页；排版器不同页数本就会有差，建议以投稿时正式页面为准。
4. **同一个数字两种取整**：正文第 229 行写 placebo quota 的 excess atypicality 为 0.040，表 3 写 +0.039。
5. **LaTeX zip 不含编译后的 PDF**：`manuscript_latex.zip` 只有 tex + Definitions + 7 张矢量图（这是对的），PDF 需按 README 单独上传 `manuscript.pdf`；注意根目录同时放着 `manuscript.pdf`（LaTeX 版）和 `manuscript_word.pdf`（Word 版），别传错。
6. **Highlights 区块**：Word 首页和 LaTeX（第 35–48 行 `\addhighlights`）都带 "What are the main findings?" 区块。若 Remote Sensing 的模板不含此区块，两边都要删。
7. **补充材料里的 "Sources: configs/… / tables/v2/… / docs/…"**：这些是交付包内的相对路径，只有在公开仓库保留同名路径时才成立，否则建议改成指向仓库 DOI。

## 4. 提交系统里要准备、但不在文件里的信息

- 通讯作者的 ORCID 账号（系统层面通常强制），以及**每一位作者**的邮箱（编辑部会逐个发确认信）。
- 栏目 / Section 选择；是否投某个 Special Issue。
- 建议审稿人（可选，3–5 位：姓名、单位、邮箱、理由）。
- 是否已在 arXiv/其他平台发布预印本（有则给链接与版本）。
- APC（Remote Sensing 现列 CHF 2700）的付款主体、是否有机构协议/折扣；税费另计。
- 第三方材料许可问答：Figure S3 用了 OpenAerialMap/Open Imagery Network 的 CC BY 4.0 影像，图注已写 credit（"Bilal Koç; SkyEye … CC BY 4.0"），问答时按此回答。
- AI 使用声明的措辞需全体作者认可（现写在 Acknowledgments：OpenAI Codex 参与规划/软件/实验执行/分析，Anthropic Claude 参与制图与文字编辑）。

## 5. 已经合格、不用动的

- 摘要 195 词（上限约 200）；关键词 8 个。
- 19 条参考文献与正文引用**一一对应、无漏引、无多引，编号顺序 = 首次引用顺序**；LaTeX 编译无 undefined reference、无 Overfull hbox。
- 表 1–4 与正文数字抽查全部自洽（含 1.68/2.24/1.35/0.90/2.13 等）。
- 需重复的章节齐全：Introduction / Materials and Methods / Results / Discussion / Conclusions；Results 与 Discussion 分列。
- 声明类章节结构齐全：Supplementary Materials、Author Contributions、Funding、IRB（Not applicable）、Informed Consent（Not applicable）、Data Availability、Acknowledgments、Conflicts of Interest、Abbreviations。
- Word 版行号已启用（`w:lnNumType`）；7 张插图嵌入分辨率 483–546 dpi；LaTeX 版为矢量 PDF。
- 补充材料 S1–S11 表、S1–S3 图与正文 `\supplementary` 的清单一致；其 13 条文献自洽；Fig S3 有 CC BY 4.0 credit。
- 正文/图表无 TODO、XXX 之类残留（唯一命中是 tex 第 22 行的作者占位说明注释）。

## 6. 建议但非必须

- 参考文献 19 条偏少，投遥感类期刊可能被要求补相关工作量；6 条会议文献无 DOI，按 MDPI 体例补 "Available online: URL"（OpenReview/PMLR）会更稳。
- 正文目前只在两处引用补充材料（Figure S3，以及 `\supplementary` 的合并清单）。建议在相应位置分别点 S1/S2/S4/S11。
- 可选 Graphical Abstract（非必须）。

## 7. 待填信息模板（填好即可一次性生成三版）

```
作者1  英文姓名(First Last)：        ORCID：0000-0000-0000-0000   单位序号：1   邮箱：
作者2  英文姓名：                    ORCID：                       单位序号：2   邮箱：
作者3  英文姓名：                    ORCID：                       单位序号：2   邮箱：     是否通讯：是
单位1  部门, 机构, 城市 邮编, 国家：
单位2  部门, 机构, 城市 邮编, 国家：
通讯作者姓名：            邮箱：            电话(可选)：
Author Contributions（CRediT，按作者列）：
Funding（基金名 + 编号；或写 "This research received no external funding."）：
Conflicts of Interest（默认句：The authors declare no conflicts of interest.）：
数据仓库：Zenodo / figshare / 其他：             DOI：
预印本：无 / 有（链接）：
建议审稿人（可选，3–5 位）：
目标期刊：Remote Sensing / Sensors（二选一）：
```

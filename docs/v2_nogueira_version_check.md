# Nogueira IEEE Access 正式版本补查

核查日期：2026-10-18。仅新增本记录；未修改bib、文献矩阵、冻结文件或本项目结果。按任务要求没有重新阅读v2方法正文；不将本轮有限版本核查写成完整逐字版本diff。

## 获得的主源与版本身份

**已取得合法公开的正式出版版本全文。** [DLR作者机构库记录](https://elib.dlr.de/225462/)将其PDF标为 `Published version`，链接至[13页公开PDF](https://elib.dlr.de/225462/1/Core-Set_Selection_for_Data-Efficient_Land_Cover_Segmentation.pdf)。库记录给出IEEE Access **14 (2026), 19891–19903**、DOI **10.1109/ACCESS.2026.3659734**，正式IEEE记录为[11368852](https://ieeexplore.ieee.org/document/11368852)。PDF首页同时显示该DOI、期刊页码、2026年版权和出版时间2026-01-30、current version 2026-02-10；其正文确为正式排版版本。本轮主源相关正文核查可以针对下列具体位置由原先B级版本分离推进为A，而不是把旧v2方法自动视为正式版全文。

另有[Cardiff ORCA作者接收稿记录](https://orca.cardiff.ac.uk/id/eprint/184548/)，明确标为 `Accepted Post-Print Version`；本轮未将其当作最终排版版。ORCA PDF端点被web工具以文件过大拒绝。Liverpool机构库检索也返回正式PDF，但正常打开返回406；没有重试绕行。Microsoft作者页[PDF链接](https://www.microsoft.com/en-us/research/publication/core-set-selection-for-data-efficient-land-cover-segmentation/)指向IEEE stamp端点，正常访问返回418；本轮通过公开DLR机构库取得正文，无需权限或代理。

[arXiv原始版本历史](https://arxiv.org/abs/2505.01225)列出：v1=2025-05-02，v2=2025-08-01，v3=2025-12-18。**v2并非最新作者预印本。** 本轮只核对[v2摘要与记录](https://arxiv.org/abs/2505.01225v2)，未重读其方法。不能仅凭v3日期等同正式接收稿，也不宣称v3和IEEE PDF逐字相同。

## 正式PDF相关协议定位

下表保留简洁英文协议摘记，均为概述；页码为正式期刊页码。范围是已读主文，不覆盖未取得的外部补充材料或未审计的作者仓库。

| Check | Verified published-paper scope | Location |
|---|---|---|
| Data / geography | DFC2022:19 French urban areas; Vaihingen/Potsdam. No reported OpenEarthMap experiment. | §IV-A, pp19895–19896 |
| Unit / budget | Non-overlapping256×256 patches; common top1/5/10/25/50/75%, plus100%. Equal annotation cost/valid-pixel budget unverified. | §III; §IV-B; §V-A, pp19893–19897 |
| FD | ImageNet ResNet18 pooled512; K starts2, increasing until Vendi change<0.5% for three iterations; random round-robin. | §III-B, p19894 |
| Labels | LC:mask entropy; CB:candidate class distributions; FD:images. | §III-A/B/E, pp19894–19895 |
| Evaluation | DFC90/10; ISPRS image splits; original tests; three fits share subsets. Distance-buffer/region-holdout specification unlocated. | §IV-D; §V-A, pp19896–19897 |
| Baselines / optimization | Random/Euclidean farthest-first CoreSet; U-Net/SegFormer; fixed100 epochs, not fixed steps. | §IV-B/C; §V-A, pp19896–19898 |
| Group / FL controls | Size-preserving permuted groups/source-mean weighted-FL unlocated in inspected main text. FA/CB combines scores. | §III/Table1; §IV; §V, pp19893–19900 |

对最后一行的证据解释：本轮直接读取六个方法定义、基线、实验协议和主文结果；并对全文抽取文本检索 `OpenEarth`、`permut`、`geograph`、`facility`，未命中。关键词未命中本身不能证明控制不存在，尤其不能排除不同命名、正文以外的附件或仓库实验。上表因此只说“在已检查主文中未定位到”，不升级为“原研究没有”。

## 相对既有v2核查，哪些可以更新、哪些仍未知

- **可以直接更新的证据来源**：数据集列举、FD自适应K、候选标签需求、patch预算和正式主文实验协议，现在有2026正式PDF的具体位置，不必继续仅引用2025 v2作为其方法依据。现有固定DINO、K=12的FD适配仍应明确为适配；不因取得正式PDF而自动成为原方法完整复现。
- **已知一致的范围**：v2摘要与正式版均列DFC2022、Vaihingen、Potsdam。正式FD定义也与此前v2核查记录中的ResNet18/Vendi自适应K/轮询框架一致。但本轮未做v2正文diff，不能断言地理split、阈值或全部细节毫无变化。
- **版本展示差异不等于已证明增补历史**：v2摘要只提随机baseline；正式版§IV-C明确列出Random与CoreSet，§IV-B/§V-A明确展示两种架构。由于本轮不重读v2正文，不能仅据摘要断言CoreSet或SegFormer在哪个版本首次加入。正式版强基线应按已取得正文准确登记，不能继续概括成“只有random”。
- **Source geography、置换组、加权FL是否相对v2发生改变**：本轮没有完整v2↔正式版差异清单。正式版可确认的范围与本轮未定位控制的范围均在上表，变化历史仍未知。不能将相同数据集名解释为相同source/target隔离，也不能据未定位控制建立“首次”的结论。
- **仍未核实**：外部补充材料、作者仓库各版本与正式实验的逐项对应、地理距离/原始影像来源独立性，以及逐标注工时等预算公平性。正式主文的实验结果没有在此转录，也没有与本项目面板成绩比较。

## 元数据边界与后续使用

本次只新增本文件，不直接修订文献库或矩阵。正式PDF首页将第8位作者显示为 **Simone Fobi**；Microsoft作者页显示 **Simone Fobi Nsutezo**，arXiv显示 **Simone Nsutezo**。这是已观察到的来源显示差异，后续若修订正式版书目应单独处理，不能静默把不同版本作者显示混写。卷页现已通过机构正式记录与排版PDF核实，但本任务未授权修改bib。

本次结论是缩小版本证据缺口。它不证明当前实验具有独立方法新颖性；完整图像预算、目标不可见选样、真实/置换组与来源均值覆盖仍只能作为本项目明确实施的设计，并在结果完整后按证据界定贡献。

## 后续正式版元数据对齐（2026-10-18）

本文件最初任务仅授权新增核查记录，所以上文如实记载当时未修改bib或矩阵。父代理随后直接核对DLR正式PDF，并追加授权修订 `references_v2.bib` 的 `nogueira2026coreset` 单条及相应矩阵行；以下记录属于这次后续授权，不回写最初任务历史。

字段变更：

- 第8位作者由原Microsoft元数据对应的 `Nsutezo, Simone Fobi` 改为IEEE排版作者行的 `Fobi, Simone`。仍为12位作者，顺序不变。正式PDF显示Simone Fobi、Microsoft显示Simone Fobi Nsutezo、arXiv显示Simone Nsutezo；这记录来源显示差异，不作人员身份变更推断。
- 题名字形按正式PDF统一为 `Core-Set Selection for Data-Efficient Land Cover Segmentation`；新增 `volume={14}`、`pages={19891--19903}`。
- `url` 改指DLR合法公开的正式PDF。既有 `journal={IEEE Access}`、`year={2026}`、DOI保持不变；未增加未经核实字段。
- 条目前注释说明正式版来源与作者显示差异。矩阵仅更新Nogueira行和对应待核项，保留此前B级“Microsoft元数据+2025v2方法”的核查历史；正式主文相关范围可记A，不表示全篇附件、代码和完整版本diff均已核查。未将主文未定位控制写成绝对不存在。

变更校验：原V1的14条完整字节序列仍保留；SpaceNet条目从 `@misc{vanetten2018spacenet,` 至文件尾的字节内容与修改前完全相同；总条目25、唯一键25、重复键0。未修改冻结协议中的历史预印本链接，也未读取本项目结果。

更新后Nogueira单条SHA256（文件内从 `@article{nogueira2026coreset,` 至闭合 `}` 后换行的实际字节，不含前注释；保留该段原换行格式）：

`dec31cdac778bf40cec57c72bedd9a0a5cd93e0973d5d4dc4ac90b0087295a7b`

本次更新后的 `docs/references_v2.bib` **整库SHA256**：

`2336b3efcf61fbca512b0872d834de35c36839e14f41498053b990fb7ff7d01c`

整库哈希是本次执行时的内容标识；未来合法编辑将使其改变。父代理将在后续构建前用文档引擎重新解析当前库，并按最终实际使用的引用顺序绑定稿件。

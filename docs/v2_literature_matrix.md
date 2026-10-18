# V2 文献与主张边界登记

本表支持“固定完整图像预算、候选来源失衡、真实/伪地区分组与不同覆盖目标，对未见地区分割的影响”这一实验问题。它不登记本项目的新面板成绩，不推定某个策略有效，也不构成新颖性已获证明的结论。主比较仍为原设计的 GeoK−K；新增真实/置换地区加权 FL 是解释性次要对照。

`references_v2.bib` 保留 V1 的14条原条目，再增加10条，共24条。旧条目的元数据与原有版本说明不作改写。新增条目只登记已核实字段；参考文献数量不代表所有原文均已完成相同深度的协议审查。

## 核查层次

- **A：主源相关正文已直读。** 元数据来自正式出版记录；方法依据正式正文，或明确标明的作者稿。此标记只覆盖列出的部分，不等于逐页复核全部附录和代码。
- **B：正式元数据与作者预印本分开核查。** 不能将预印本的实验设置、数值或作者名单静默移入正式版。
- **C：沿用既有核查。** 本轮不重复声称完成全文访问；条目与先前正文定位保留可追溯来源。
- **D：仅元数据、摘要或索引返回的原文片段。** 不以未看到某控制为理由断言原文没有该控制。
- **P：公开预印本。** 不独立主张正式发表或录用；正文核查深度另行注明。

## 最接近的选样与迁移实证

| 引用键与工作 | 已有内容与信息需求 | 当前对照可检验什么；不可主张什么 | 原文位置、主源与核查层次 |
|---|---|---|---|
| `nogueira2026coreset`，Nogueira等，IEEE Access2026 | 已有图像/标签/混合coreset；正式主文FD为ResNet18+Vendi自适应K，LC/CB需候选掩膜；256×256patch同百分比预算；基线含Random及farthest-first CoreSet，架构含U-Net和SegFormer | 本项目固定DINO、K=12的FD仍是适配，不是完整复现。正式主文§III–V未定位到保持组大小置换组或source-mean weighted-FL控制；不据此断言附件/仓库不存在，也不证明新颖性 | **A（本次限定范围）**：[DLR正式PDF](https://elib.dlr.de/225462/1/Core-Set_Selection_for_Data-Efficient_Land_Cover_Segmentation.pdf)：§III-B/E、§IV-A–D、§V-A，pp19894–19898；正式卷14、pp19891–19903已核实。**历史B保留**：[Microsoft元数据](https://www.microsoft.com/en-us/research/publication/core-set-selection-for-data-efficient-land-cover-segmentation/)+[2025v2方法](https://arxiv.org/html/2505.01225v2)，并非本轮重新读取v2；[作者代码](https://github.com/keillernogueira/data-centric-rs-classification)版本与正式实验未逐项审计。作者显示差异与正式协议核查见 `v2_nogueira_version_check.md`；不照抄仓库错误引用题名 |
| `lu2025strategicsampling`，Lu等，RSE2025 | 256×256切块；CLCD先验主题熵与Canny边界复杂度；五地区轮换并考察目标本地标签比例 | 可以区分完整图像预算、目标不可见选样及来源失衡干预；不能说其评分直接用了候选人工真值，或没有跨地区验证 | **C**：§2.2.3、§3.2.3；[正式DOI](https://doi.org/10.1016/j.rse.2025.115034)、[作者上传原文](https://www.researchgate.net/publication/395951873_Strategic_sampling_for_training_a_semantic_segmentation_model_in_operational_mapping_Case_studies_on_cropland_parcel_extraction)。补充材料未取得 |
| `he2024geocomplexity`，He等，Remote Sensing2024 | 基于真值类别的地理复杂度统计与分层，作用于遥感多类分割切块 | 可比较不接触候选标签的选样；不能把地理统计、分层或减少抽样偏差的概念当作首次，也不能仅凭未定位缓冲规则就断言发生泄漏 | **C**：§2.1式(1)、§2.2图4、§3.1；[出版方原文](https://www.mdpi.com/2072-4292/16/11/1987) |
| `kaijage2024spatialal`，Kaijage等，Sensors2024 | 时序作物分类；训练/测试来自不同地块，候选先按已知类别分层，NDVI委员会熵与半变异函数控制查询 | 可以检验完全不使用候选类别的完整图像策略；不能说首次空间独立测试、首次等预算随机对照，或将其地块/点预算等同完整图像预算 | **C**：§3.2–3.3、§4.2；[出版方](https://doi.org/10.3390/s24072108)、[作者机构全文](https://ris.utwente.nl/ws/portalfiles/portal/462920020/sensors-24-02108.pdf) |
| `cai2021spatialdiversity`，Cai等，TIP2021 | 已有图像内部region级主动学习的空间与特征多样性组合 | 可以区分来源城市元数据和图像内部区域；不能称首次结合空间多样性与视觉多样性 | **C**：方法部分；[正式TIP记录](https://ieeexplore.ieee.org/document/9580637/)、[作者公开稿](https://arxiv.org/html/2507.17367v1)。2025年上传不改变正式发表年份 |
| `li2026spatialsampling`，Li，Spatial Statistics2026 | 题名与出版记录表明研究空间采样、MAML及建成区分割 | 仅作为直接相关先例；正文未取得时，不能声称其缺少地理隔离、标签约束或特定负对照 | **D**：[出版方记录](https://www.sciencedirect.com/science/article/pii/S2211675326000588)、[DOI](https://doi.org/10.1016/j.spasta.2026.101010)。详细协议仍待全文核验 |
| `kumar2026classaware`，Kumar等，2026预印本 | 动态类别反馈与卫星分割主动学习属于相关路线 | 可区分来源描述子的一次选样和类别反馈式获取；不能把预印本当作已发表论文，或未经复现转述其效果为可靠事实 | **C/P**：[原始公开记录](https://arxiv.org/abs/2604.08965)。数据/设备/控制协议仍需进一步复核 |
| `alemadi2025spatialshift`，Al-Emadi等，IJCV2025 | DSGR土地利用分类，单地区/留一地区多源测试；已控制训练总量，并另做类别分布控制 | 可研究完整图像分割选样与真假来源组控制；不能称首次用等训练总量检验地理多样性，不能将分类结论直接迁移为分割保证 | **A**：§5.4、§5.7.1–5.7.2；[正式原文](https://link.springer.com/article/10.1007/s11263-025-02518-z)、[作者代码](https://github.com/RWGAI/DSGR) |
| `mittal2025realistic`，Mittal等，IJCV2025 | 图像级分割主动学习；比较冗余、预算、增强与半监督条件，含entropy和coreset | 支持固定训练配方、保留random并检验适用条件；不能把“随机很强”或“没有稳定优势”本身当作新发现，也不能推断所有主动学习无效 | **A**：§2.3、§4.1及分割实验附录；[正式原文与完整8作者](https://link.springer.com/article/10.1007/s11263-025-02372-z) |
| `fang2026scopes`，Fang等，Remote Sensing2026 | 以图像footprint、ROI覆盖、云量和时间等信息进行档案影像选择及冗余控制 | 可以区分训练子集的特征覆盖与真实地表覆盖；不能因题名相似就当作分割标注预算基线，也不能说首次空间约束影像选择 | **D**：元数据及索引原文片段§3.2.1、§4.1；[正式文章](https://www.mdpi.com/2072-4292/18/4/588)、[出版方版本与引用记录](https://www.mdpi.com/2072-4292/18/4/588/notes)。本轮直接全文端点访问失败，不标为全篇核查 |
| `zhang2026coversoftly`，Zhang/Virtanen，2026预印本v2 | 音频帧级主动学习；§3.1使用被覆盖行加权FL；权重依赖已训练分类器与已标注邻居；比较硬门控/软权重及两种几何机制 | 可检验仅来源计数权重在遥感目标不可见设置中是否有效；不能称首次以软权重替代硬决策，也不能沿用音频效果作本项目证据 | **A/P**：§2.2、§3.1式(2)–(3)、§4.3；[v2正文](https://arxiv.org/html/2607.13571v2)、[作者代码](https://github.com/TioSisai/mismatch-weighted-facility-location)。录用未独立确认，本库仅登记预印本 |

## 加权覆盖目标的已有理论

| 引用键 | 原文已有内容 | 本项目使用及不能扩大的主张 | 原文位置与主源 |
|---|---|---|---|
| `wei2015submodularity` | 子模子集选择；一般FL与按类别分区的NN目标需要区分，FASS还使用已标注集训练分类器与不确定性过滤 | 采用一般相似度FL作为无候选标签的覆盖基线；不声称复现完整FASS或获得分割性能的理论保证 | **A**：§3式(6)及FL讨论、§4算法1；[正式PMLR记录](https://proceedings.mlr.press/v37/wei15.html)、[原文](https://proceedings.mlr.press/v37/wei15.pdf) |
| `wang2024utilityfairness` | 定义每组平均效用，明确区分所选对象的组配额与给各组提供的覆盖效用；主问题为总效用与最差组效用的约束权衡 | `1/(R*n_r)`是既有组均值思想的直接组合，不称新目标族；组均值的平均不等于最大化最差组，也不保证组数量配额 | **A**：§2–3，组均值定义及式(1)–(2)；[正式EDBT论文](https://openproceedings.org/2024/conf/edbt/paper-7.pdf)、[DOI](https://doi.org/10.48786/edbt.2024.01) |
| `rafiey2024decomposable` | 预定义权重的子模函数求和，允许客户端等权；提供FL实例 | 说明地区均值加权FL属于成熟框架；不把正权重保持子模性或贪心性质作为新理论贡献 | **A**：正式元数据与作者稿式(1)、§5/附录D.1；[正式ICML记录](https://proceedings.mlr.press/v235/rafiey24a.html)、[作者稿](https://arxiv.org/html/2402.00138v2) |

## 数据、表征、架构与常规方法

| 引用键 | 本项目中的角色与边界 | 主源及核查层次 |
|---|---|---|
| `xia2023openearthmap` | 数据集与跨地域任务背景；不是本项目提出的数据集。城市名、图像ID和公开许可不自动保证地理独立或RGB许可一致 | **C**（任务背景）；**D**（本轮书目）：[WACV正式原文](https://openaccess.thecvf.com/content/WACV2023/html/Xia_OpenEarthMap_A_Benchmark_Dataset_for_Global_High-Resolution_Land_Cover_Mapping_WACV_2023_paper.html)。后续直接核实CVF PDF首末印刷页6254–6264，并据此补入当前库；DOI页码差异仍保留。见 `v2_openearthmap_reference_check.md`；数据来源许可见单独归属文档 |
| `oquab2024dinov2` | 共享冻结描述子；不将预训练表征、冻结编码器或其鲁棒性概念作为贡献 | **C**：[TMLR正式记录](https://openreview.net/forum?id=a68SUt6zFt)、[作者稿](https://arxiv.org/pdf/2304.07193)。本库沿用2024正式版，不将2023预印本年份混入 |
| `he2016resnet` | 既有ResNet18编码器；不是新骨干 | **C**：[CVPR正式原文](https://openaccess.thecvf.com/content_cvpr_2016/html/He_Deep_Residual_Learning_CVPR_2016_paper.html)，架构与实验部分 |
| `ronneberger2015unet` | 编码器—跳连—解码器架构依据；本项目ResNet18 U-Net风格实现不是原始U-Net完整复现，也不是新分割架构 | **D**：[Springer正式MICCAI章记录](https://link.springer.com/chapter/10.1007/978-3-319-24574-4_28)，作者、题名、LNCS9351及234–241页已核实；本轮未重做全篇架构对照 |
| `sener2018coreset` | k-center/coreset选样依据；本项目将固定描述子用于一次图像选样，不等同原文完整主动学习循环 | **C**：[ICLR正式记录](https://openreview.net/forum?id=H1aIuk-RW)，Core-set方法部分 |
| `arthur2007kmeanspp` | D-squared真实样本初始化基线；本项目不运行完整k-means再找medoid。聚类近似性质不保证分割效果 | **A**：[作者机构书目记录](https://research.google/pubs/k-means-the-advantages-of-careful-seeding/)、[作者原稿算法部分](https://theory.stanford.edu/~sergei/papers/kMeansPP-soda.pdf)。SODA2007页码由前者核实，本轮原稿端点未重开成功 |
| `loshchilov2019adamw` | 常规优化器依据；不将AdamW、固定训练预算作为新方法 | **C**：[ICLR正式记录](https://openreview.net/forum?id=Bkg6RiCqY7) |
| `roberts2017crossvalidation` | 具有空间/层级结构数据的验证依据；要求说明推断单位和适用范围，不能以重复种子替代独立地理区域 | **C**：[正式DOI](https://doi.org/10.1111/ecog.02881)，结构化数据交叉验证论述；本轮不声称重新全文审查 |

## 相邻的冻结表征与域泛化工作

| 引用键 | 已有内容及本项目边界 | 原文位置与主源 |
|---|---|---|
| `gong2026crossearth` | 遥感分割的域泛化与基础模型已有直接工作；本项目操纵训练图像子集，不提出新基础模型或域泛化训练体系 | **C/B**：[正式DOI](https://doi.org/10.1109/TPAMI.2025.3649001)、[作者稿方法部分](https://arxiv.org/html/2410.22629v3)。正式2026卷期与较早预印本分开，沿用V1已核实16作者条目；不能据方法区别推断其没有某一负对照 |
| `park2026frost` | 冻结特征与支持集统计用于少样本分割已有预印本；本项目研究完整训练图像选择及未见地区评估 | **C/P**：[原始记录](https://arxiv.org/abs/2606.31136)、[§3.1–3.3](https://arxiv.org/html/2606.31136v1)。不独立确认正式发表，不将冻结或非参数统计本身作为贡献 |

## 当前可检验的贡献与限制

1. **预先固定的实证问题。** 在同一来源候选池、冻结描述子、完整图像预算和下游训练配方下，比较最坏距离覆盖、平均代表性、聚类轮询、硬地区规则，以及真实/伪地区的均值覆盖权重。可主张的是完成后证据支持的条件效应与失败边界，而非这些组件的新颖性。
2. **不均衡与地理含义分开。** 真实/伪地区控制保持组大小；weighted-FL还保持权重多重集。balanced3下两种权重退化为原FL是定义检查，不是新增科学发现。源地区均值覆盖与目标地区宏平均分割准确率不是同一量，前者改善不保证后者改善。
3. **因果边界。** real weighted-FL对普通FL/置换weighted-FL的比较在同一覆盖目标内检验地理权重；对GeoK的直接比较还改变覆盖目标，因此不能单独归因于硬配额刚性。需要同一FL目标的硬配额版本才可更干净隔离这一因素。
4. **证据层级。** 原始504条设计与新增72条解释性条件分开登记，原primary不改。来源分配和拟合种子不是新的独立地理重复。未取得或未逐项核查的补充材料不支持“前人没有该控制”的断言；不以区间跨零宣称等效。

## 未核实与保留项

- Nogueira历史记录原为“正式卷页未核实、FD依据2025v2”；后续已从DLR正式PDF核实卷14、pp19891–19903及上表指定方法/协议，引用已对齐正式版作者显示。完整v2↔正式版diff、外部补充材料、仓库版本对应和精确空间独立性仍未核实；本轮不转录正式实验数值，也不混入预印本数值。
- Wang EDBT分页未在本轮独立建立，省略；DOI、四作者、题名与正式会议年份已核实。
- Zhang/Virtanen仅登记arXiv v2；作者记录中的录用注释未获独立会议主源确认，不填会议卷页。
- SCOPES正式元数据已核实，但本轮全文端点访问受阻；正文判断限索引返回的原文片段，未完成全部控制/附录审查。
- V1已有OpenEarthMap页码冲突、Li全文访问、Lu补充材料、Kumar/FROST正式发表状态等限制不因复制文献库而自动消失。旧14条曾在建库阶段保持原样；后续仅OpenEarthMap按已直接核实的CVF PDF补入页码，未重新验证旧库全部字段，V1本身不改。
- 本表未证明独立的新颖性。若新面板没有形成稳定、可解释并经对照支持的证据，不可仅靠文献表或措辞将研究升级为方法贡献。

## 上游数据来源引用补记（2026-10-18）

本节在上述24条核查历史之后追加一条上游数据来源引用；当前 `references_v2.bib` 为 **25条、25个唯一键、重复键0个**。本次保留原24条完整字节内容，因而也保留其中V1的14条原始内容。开头“14+10=24”的表述是此前建库范围记录，不代表新增数据引用已在那一轮完成核查，也不将旧条目改记为本轮重新全文核查。

| 引用键 | 本次核实内容与用途 | 主源、具体位置与核查边界 |
|---|---|---|
| `vanetten2018spacenet` | Adam Van Etten、Dave Lindenbaum、Todd M. Bacastow；*SpaceNet: A Remote Sensing Dataset and Challenge Series*；2018；arXiv:1807.01232；arXiv-issued DOI `10.48550/arXiv.1807.01232`。补齐SpaceNet上游数据来源的论文引用，不能替代OpenEarthMap数据引用、逐地区来源归属或许可登记 | **D/P（官方引用说明与原始书目记录）**：[SpaceNet2官方页 Citation Instructions](https://spacenet.ai/spacenet-buildings-dataset-v2/)明确给出该2018论文；[arXiv原始记录](https://arxiv.org/abs/1807.01232)的题名、Authors、Cite as和Submission history核实作者、编号、年份与DOI。arXiv首版为2018-07-03，当前v3修订为2019-07-15；本库保留官方指定的2018引用年份，只登记预印本，不推测正式会议/期刊。此处未重新核查全文方法和实验协议，不增加方法创新主张。 |

本次未修改 `v2_data_attribution.md` 中的数据许可裁定，未下载或发布影像；新增条目的来源与哈希口径见 `v2_spacenet_reference_check.md`。

## CVF书目页码补正（2026-10-18，后续核查）

当前25条库为OpenEarthMap补入 `pages={6254--6264}`，与所引用CVF公开PDF首末印刷页和官方引用记录一致。Crossref同DOI登记6243–6253的原因仍未核实，也未查IEEE下载版分页；不将两者混成同一个已解释版本。补正前完整库保存在 `reference_history/references_v2_before_oem_page_update.bib`。上文“旧14条／原24条字节保留”描述相应建库时点，不再作为补正后当前库的字节相等断言。只变更书目页码和来源说明，论文内容、引用键、研究协议及实验均未变更。

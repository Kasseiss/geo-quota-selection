# Li (2026) 公开全文补查记录

访问日期：2026-10-18。范围：仅公开出版社主源、作者公开稿、机构库或正式补充材料。本次未读取本项目面板成绩，未修改文献库、文献矩阵或冻结科学文件。

## 结论与证据层级

**本轮仍未取得可逐节核查的全文、作者接收稿或正式补充材料。详细实验协议缺口保留，不能升级为全文核验。** 出版社的搜索索引返回了文章元数据、Highlights 和 Abstract，并标示 Open access / Under a Creative Commons license；这说明不能把当前工具的获取失败写成“该文确定付费”或“公开全文不存在”。本轮未取得具体许可链接，故不据此登记某个特定 CC 版本。

已核对的正式记录为 Lianfa Li，*Spatial sampling to enhance meta learning for semantic segmentation of build-ups in remote sensing*，*Spatial Statistics*，74 (August 2026)，101010，DOI [10.1016/j.spasta.2026.101010](https://doi.org/10.1016/j.spasta.2026.101010)。主源为 [ScienceDirect 文章记录](https://www.sciencedirect.com/science/article/pii/S2211675326000588)。这里的月份来自期卷记录，不将其等同于首次在线日期。

出版社摘要层可以确认的范围很窄：作者采用 Moran's I 描述空间分布并分组，与 MAML、K-shot 任务结合；任务涉及建筑用地分割，数据为 GID；摘要还提及随机二元类别标签及 UNet、SegFormer、SwinUNet 比较。这些事实仅定位到 **Highlights / Abstract**，不构成 Methods 或实验表格核验。未在此转录数值结果。

## 逐项协议核查状态

| 待核项目 | 本轮可确认的内容及原文位置 | 未取得的关键证据 |
|---|---|---|
| 空间抽样单位 | Abstract 说对训练样本空间分布分组。 | 图像、裁块、像素或其他单位的精确定义；空间统计输入；尺度、分组数量和分位阈值；完整正文位置均未取得。 |
| 是否使用 MAML | Abstract 明确使用 Model-Agnostic Meta-Learning 与 K-shot。 | 内外循环、任务生成、support/query 构成和更新规则未全文核验。 |
| 候选标签与目标数据使用 | Abstract 提及随机二元类别标签。 | 不清楚空间统计是否从真值掩膜计算；候选池是否已全部标注；未选样本标签、目标影像或目标标签是否用于分组、调参或适应。不能将“随机标签”解释成无需真值选样。 |
| Source / target 隔离 | Abstract 描述适应空间分布，提及 GID。 | 原始大图、地点、裁块、空间距离及 source/target 支持集/查询集的隔离规则；传感器或影像共享关系均未取得。 |
| 等预算对照 | 未取得 Methods、实验设置或对应表格。 | shot、像素、完整标注图像数及训练步数如何对齐；不同方法是否等总候选量和等标注成本。 |
| 地理分组 / 任意组对照 | Abstract 可确认按空间模式分组。 | 真实地理区、保持组大小的任意/置换分组、候选池频率失衡负对照是否实施，均未核实。不能断言不存在。 |
| 强基线 | Abstract 可确认涉及 UNet、SegFormer、SwinUNet 及元学习比较。 | k-center、k-means++、facility location、FD 或其他完整图像训练子集选择基线是否出现；各基线预算、优化与特征条件是否可比，均未核实。 |
| 局限 | 未获得 Discussion、Limitations 或附录正文。 | 作者实际承认的局限及其具体位置未核实，不以我们的推测代替。 |

## 有边界的访问与检索记录

1. 正常打开上述 ScienceDirect URL，以及 DOI 解析 URL。两次 web open 均返回 `Internal Error`，没有正文行号、PDF 或补充材料链接。这是本次工具访问结果，不是 HTTP 付费墙判定。
2. 精确 DOI 检索 `"10.1016/j.spasta.2026.101010"` 和精确题名短语检索 `"Spatial sampling to enhance meta learning" Li full text`。得到出版社索引的元数据/Highlights/Abstract；没有取得可核查的全文。其他站点的转载、内容摘要和索引没有作为协议证据使用。
3. 检索 `"S2211675326000588" pdf`；精确题名限定 `igsnrr.cas.cn`；精确题名限定 `arxiv.org OR researchsquare.com OR zenodo.org OR figshare.com OR edu.cn OR edu`。本轮未识别到该论文的作者稿、机构库全文或正式附件。此结果不意味着所有库中都不存在。
4. 为确认是否有可发现的原文部分/附件，追加精确题名限定 `sciencedirect.com` 的 `"sampling" "Methods"` 与 `"Supplementary"` 检索；另以 `"Lianfa Li" "2026" "Spatial Statistics"` 限定 CAS、UCAS、UCLA 及教育机构域名。没有取得该论文的正文协议或附件主源。机构搜索中的同名关联资料不作本文作者归属或全文证据。
5. 最后尝试通过正常 in-app browser 打开同一出版社公开 URL；工具报告 `Browser is not available: iab`，未取得页面，也没有使用其他浏览器或权限通道继续重试。

截至本轮结束，没有发现可继续核查的新公开全文通道。未使用账号、凭据、机构代理、付费权限、访问限制绕行、猜测下载地址或非公开全文来源；不向作者发送消息。停止检索，保留上述访问记录。

## 对当前研究定位的约束

该文应继续作为高度相关但协议尚未全文核验的近邻工作。摘要已足以阻止将“空间分组增强遥感低样本分割”本身表述为首次提出。当前研究的冻结表征完整图像子集选择、等预算矩阵、真实/置换组和普通/加权覆盖目标，应作为本项目实际检验的设计描述；在取得本文详细协议前，**不能宣称这些控制在 Li (2026) 中不存在，也不能据此宣称新颖性已获证明**。本轮没有新增可支持相反判断的全文证据。

# SpaceNet 上游数据论文引用核查

核查日期：2026-10-18。目标仅为补齐数据来源论文引用，不新增方法主张，不重判数据许可，不访问本项目面板成绩，不下载或发布影像。

## 主源证据

1. [SpaceNet 2: Building Detection v2 官方页](https://spacenet.ai/spacenet-buildings-dataset-v2/)，`Citation Instructions` 节。公开页面的web正文行120–124明确要求使用Van Etten、Lindenbaum、Bacastow的2018论文，题名为 *SpaceNet: A Remote Sensing Dataset and Challenge Series*，载体写为 ArXiv，编号abs/1807.01232。这里仅据其核对论文引用，不在本次改写官方页其他数据/许可解释。
2. [作者提交的 arXiv 原始记录](https://arxiv.org/abs/1807.01232)，题名/Authors（web正文行8–11）、`Cite as`及arXiv-issued DOI（行21–23）、`Submission history`（行24–29）。作者全名依次为 **Adam Van Etten、Dave Lindenbaum、Todd M. Bacastow**；arXiv编号为 **1807.01232**；DOI为 **10.48550/arXiv.1807.01232**。首版提交时间是2018-07-03，当前v3修订日期是2019-07-15。

采用SpaceNet2官方指定的2018引用年份；`@misc`、`archivePrefix={arXiv}`、`note={Preprint; first submitted 3 July 2018}`明确预印本身份。DOI是arXiv记录签发的DOI，不能解释为已核实的正式期刊或会议出版DOI。本次没有核实正式venue，故不填booktitle、journal、卷期或页码；不将后续其他SpaceNet论文混入此条。

证据层级：**官方数据页引用说明 + 作者原始书目/版本记录（D/P）**。本轮不声称逐节核查该文全文，也不据此生成选样算法、地理独立性或性能结论。

## 文献库修改与校验

追加键：`vanetten2018spacenet`。追加前 `references_v2.bib` 为24条，未检出SpaceNet题名/作者/编号对应条目；追加后为25条，唯一键25个，重复键0个。写入采用二进制末尾追加，并校验修改后文件以修改前完整字节序列开头；原24条未重写。另校验 `references.bib` 的原14条完整字节序列仍在新库中。

**条目SHA256**（仅从 `@misc{vanetten2018spacenet,` 到闭合 `}` 后的单个LF；UTF-8编码；不含其前面的注释）：

`951e1d10fe7d0df7fe827500dd5f524c5e060c11e8ab3373ca93a84f0095637b`

此处哈希在最终验证时按实际条目字节复算；它是条目内容标识，不绑定会随未来追加而变化的整库文件。文献矩阵只在末尾追加来源说明和计数变更，原24条核查历史不改。没有修改冻结科学文件或图表/文档引擎。

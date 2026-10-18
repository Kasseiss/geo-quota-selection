# OpenEarthMap WACV2023 页码核查

日期：2026-10-18。仅核对官方CVF论文记录、其正式PDF及DOI主元数据；未查无关文献或本项目结果，未改bib、矩阵或提纲。

## 可支持的引用页码

**当前引用的CVF正式公开版本应记为 pp.6254–6264。** [CVF官方论文页](https://openaccess.thecvf.com/content/WACV2023/html/Xia_OpenEarthMap_A_Benchmark_Dataset_for_Global_High-Resolution_Land_Cover_Mapping_WACV_2023_paper.html)的作者/会议引用行及其 `Xia_2023_WACV` BibTeX 均给出 `pages={6254-6264}`。该页直接web open返回403，但其官方页面搜索索引返回了完整书目行和BibTeX；不将索引返回误记为本次直接HTML访问成功。

更直接的印刷页码证据来自同站[官方论文PDF](https://openaccess.thecvf.com/content/WACV2023/papers/Xia_OpenEarthMap_A_Benchmark_Dataset_for_Global_High-Resolution_Land_Cover_Mapping_WACV_2023_paper.pdf)：普通公开HTTP请求成功，使用内存中的PDF解析器读取到 **11个物理PDF页**；第1个PDF页的页脚为 **6254**，第11个PDF页的页脚为 **6264**。两端页码与CVF BibTeX一致，且含端点跨度为11页。这里的书目页码是6254–6264；**11是PDF文件长度，不应写为书目 `pages={1--11}`**。本轮核对首末页脚与页数，没有另行逐页登记中间九页的页脚。

## 现有条目其他字段

| 字段 | 核实值 | 主源位置 |
|---|---|---|
| 标题 | OpenEarthMap: A Benchmark Dataset for Global High-Resolution Land Cover Mapping | CVF引用行/BibTeX、PDF首页题名、Crossref `message.title[0]` |
| 作者及顺序 | Junshi Xia; Naoto Yokoya; Bruno Adriano; Clifford Broni-Bediako | PDF首页作者行、CVF BibTeX、Crossref `message.author` |
| 正式会议/年份 | 2023 IEEE/CVF Winter Conference on Applications of Computer Vision (WACV); 2023 | CVF引用行/BibTeX；Crossref `message.container-title`、`published-print.date-parts=[[2023,1]]` |
| DOI | 10.1109/WACV56688.2023.00619 | [DOI主元数据](https://api.crossref.org/works/10.1109/WACV56688.2023.00619)的 `message.DOI`，大小写规范化后相同；[IEEE记录10030160](https://ieeexplore.ieee.org/document/10030160/)的官方搜索索引亦对应同题名与DOI |

以上与 `references_v2.bib` 中 `xia2023openearthmap` 已有题名、四作者顺序、年份及DOI一致；本任务没有实际补入页码。

## DOI元数据差异仍需如实保留

本轮通过正常公开Crossref API取得IEEE登记的同一DOI记录，其 `message.page` 仍为 **6243-6253**。题名、四作者、会议和2023年与CVF一致；`message.resource.primary.URL` 指向IEEE记录10030160。该值不是11个物理PDF页数，且不能据其覆盖已直接读到的CVF页脚。

这次核查解决了“当前CVF所引版本实际支持哪个页码”的问题：采用 **6254–6264** 有官方引用行、BibTeX及PDF首末页脚三项一致证据。它**没有证明**Crossref为何不同，亦没有核实IEEE下载PDF是否另有印刷分页，不能擅自称6243–6253是笔误、另一个正式版本或已被出版社更正。IEEE正常页面访问返回需JavaScript的人机验证页，本轮未继续访问验证或推测其PDF页码。后续如授权修正文献库，可用6254–6264并在来源登记中保留DOI元数据差异；不必继续将CVF版本本身的页码记为未知。

## 访问与文件边界

web工具直接访问CVF HTML/PDF返回403，Crossref API则报告工具不可达；使用标准库普通公开HTTP请求读取Crossref JSON与同一CVF PDF成功，没有账号、特殊授权、代理或验证绕行。PDF响应为8,314,640字节，仅在内存解析，未保存论文副本；不涉及影像或任何数据集下载。另有官方搜索索引作为可追溯书目证据，没有使用第三方书目库作为裁定依据。

机器可读登记见 `evidence/v2/oem_reference_check.json`。本轮检查不构成数据来源独立性、许可或实验协议审查。

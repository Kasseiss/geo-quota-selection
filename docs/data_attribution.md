# OpenEarthMap地区来源与许可登记

核查日期：2026-10-18。地区、国家、source、provider和许可字段仅依据[OpenEarthMap官方来源表](https://open-earth-map.org/attribution.html)。source是数据集或分发入口，provider是该表所列提供方。记录入口不等于已验证影像当前可下载，也不构成独立法律许可审查。

## 许可与来源链接

- **BY**：[Creative Commons Attribution 4.0 International（CC BY 4.0）](https://creativecommons.org/licenses/by/4.0/)。
- **BY-SA**：[Creative Commons Attribution-ShareAlike 4.0 International（CC BY-SA 4.0）](https://creativecommons.org/licenses/by-sa/4.0/)。
- **DE-BY**：[Data licence Germany – attribution – version 2.0（DL-DE-BY-2.0）](https://www.govdata.de/dl-de/by-2-0)。
- **PD**：来源表写作Public domain，没有单独许可链接；本登记不额外推导其他条款。
- **未知**：来源表许可栏空白，不能凭Open data名称推定图像许可。
- **GFDRR**：Global Facility for Disaster Reduction and Recovery，以下仅为压缩表格所用缩写。

## 24个地区ID

英文地区名按来源表保留。ID到同名行的对应不替代逐图来源匹配。Accra有两个不同来源；Dar es salaam有两条元数据相同的记录。

| 地区ID | 原表英文地区名 | 国家（原表） | Source／原表链接 | Provider | 原表许可 |
|---|---|---|---|---|---|
| aachen | Aachen | Germany | [GeoNRW](https://www.opengeodata.nrw.de/produkte/) | German state North Rhine-Westphalia | DE-BY |
| accra | Accra | Ghana | [Open Cities AI](https://www.drivendata.org/competitions/60/building-segmentation-disaster-resilience/) **或** [Open data](https://map.openaerialmap.org/) | 分别为GFDRR；Environmental Protection Agency Ghana | 两行均BY；仅ID无法判定来源 |
| austin | Austin | USA | [Inria](https://project.inria.fr/aerialimagelabeling/) | USGS | PD |
| chicago | Chicago | USA | [Inria](https://project.inria.fr/aerialimagelabeling/) | USGS | PD |
| kyoto | Kyoto | Japan | [Open data](https://maps.gsi.go.jp/development/ichiran.html) | Geospatial Information Authority of Japan | **空白／具体RGB许可待核实** |
| melbourne | Melbourne | Australia | [Open data](https://map.openaerialmap.org/) | City of Melbourne | BY |
| rio | Rio | Brazil | [SpaceNet 1](https://spacenet.ai/spacenet-buildings-dataset-v1/) | Maxar | BY-SA |
| shanghai | Shanghai | China | [SpaceNet 2](https://spacenet.ai/spacenet-buildings-dataset-v2/) | Maxar | BY-SA |
| vegas | Vegas | USA | [SpaceNet 2](https://spacenet.ai/spacenet-buildings-dataset-v2/) | Maxar | BY-SA |
| vienna | Vienna | Austria | [Inria](https://project.inria.fr/aerialimagelabeling/) | Vienna | PD |
| christchurch | Christchurch | New Zealand | [AIRS](https://www.airs-dataset.com/) | Land Information of New Zealand | BY |
| dhaka | Dhaka | Bangladesh | [Open data](https://map.openaerialmap.org/) | AIGEO Center | BY |
| chisinau | Chisinau | Moldova | [HTCD（原表链接）](https://github.com/ShaoRuizhe/SUNet-change_detection) | Lightcyphers | BY |
| maputo | Maputo | Mozambique | [Open data](https://map.openaerialmap.org/) | MapeandoMeuBairro | BY |
| niamey | Niamey | Niger | [Open Cities AI](https://www.drivendata.org/competitions/60/building-segmentation-disaster-resilience/) | GFDRR | BY |
| rotterdam | Rotterdam | Netherlands | [SpaceNet 6](https://spacenet.ai/sn6-challenge/) | Maxar | BY-SA |
| bogota | Bogota | Colombia | [Open data](https://map.openaerialmap.org/) | Maptime Bogota | BY |
| chiangmai | Chiangmai | Tailand〔原表拼写〕 | [Open data](https://map.openaerialmap.org/) | UR Field Lab Chiang Mai | BY |
| daressalaam | Dar es salaam | Tanzania | [Open Cities AI](https://www.drivendata.org/competitions/60/building-segmentation-disaster-resilience/) | GFDRR | BY；原表两条相同记录 |
| mahe | Mahe | Seychelles | [Open Cities AI](https://www.drivendata.org/competitions/60/building-segmentation-disaster-resilience/) | GFDRR | BY |
| santiago | Santiago | Chile | [Open data](https://map.openaerialmap.org/) | SECTRA | BY |
| tonga | Tonga | Tonga | [Open data](https://map.openaerialmap.org/) | World Bank, V-TOL Aerospace | BY |
| ulaanbaatar | Ulaanbaatar | Mongolia | [Open data](https://map.openaerialmap.org/) | City of Ulaanbaatar and Asia Foundation | BY |
| pointenoire | Pointenoire | Congo〔原表表述〕 | [Open Cities AI](https://www.drivendata.org/competitions/60/building-segmentation-disaster-resilience/) | GFDRR | BY |

## Kyoto与OEM标签fallback的边界

来源表没有说明Kyoto具体RGB影像的许可。因此，本项目的Kyoto RGB许可状态为**待核实**；需匹配所使用的具体原始影像及其适用条款，不能仅凭GSI提供方名称或当前入口推定。

另据[OEM官方README的License段](https://github.com/bao18/open_earth_map#license)：OEM标签通常沿用原始RGB图像的许可；对于原始图像处于公共领域或许可未明确的地区，OEM**标签**采用[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)。该条款是标签的fallback，**不自动覆盖原始RGB图像，不是对Kyoto RGB许可的确认**。代码仓库的MIT许可也不能替代影像或标签许可。

## 来源歧义与隔离风险

- **Accra**：Open Cities AI／GFDRR与OpenAerialMap／Environmental Protection Agency Ghana是来源表中的两个组合。仅`accra`不能确定匹配哪行或是否混合来源，须用逐图原始标识和范围匹配。
- **Dar es salaam**：来源表两行的source、provider和license相同。表中未给逐行影像标识，不能解释为两个不同提供方，也不能据此判定两行覆盖范围不同或相同。
- **共享体系**：`rio/shanghai/vegas/rotterdam`共享Maxar＋SpaceNet体系，其中`shanghai/vegas`同属SpaceNet 2入口；`austin/chicago`共享Inria＋USGS，`vienna`同属Inria但provider不同。
- **Open Cities体系**：`niamey/mahe/pointenoire/daressalaam`及Accra的一种来源共享Open Cities AI＋GFDRR。共同来源可能形成采集或处理依赖，但不直接证明空间重叠。
- **共同平台不是共同采集源**：多个地区使用OpenAerialMap分发入口，provider不同，不能将其全部合并认定为同一原始采集源。
- **别名不能替代坐标**：来源表没有确认`Rio→Rio de Janeiro`、`Vegas→Las Vegas`、`Pointenoire→Pointe-Noire`、`Chiangmai→Chiang Mai`等标准化映射；若后续采用标准名称，应另存映射依据。`Congo`按原表保留，未扩展成具体国家法律名称。
- **不同地区ID不保证地理无重叠**：来源表没有逐图坐标、足迹、采集日期或原始影像ID。不同ID不能证明地理无重叠，同名城市也不能证明是重复影像。最终训练测试隔离需要这些元数据与影像重复检查支持。

## 未核实项与入口状态

1. Kyoto所用具体RGB影像的适用许可及其版本。
2. Accra的逐图source/provider归属；Dar es salaam重复行的逐图对应。
3. 24地区的逐图原始标识、影像足迹、时间，以及跨地区重复／重叠情况。
4. AIRS原表域名本轮跳转到无法访问的地址；Inria入口被检索工具的robots规则阻止读取。上述source链接只登记原表入口，不声称已验证实际文件可下载。
5. Chisinau表中source名HTCD、provider名Lightcyphers与其链接所指SUNet仓库之间的逐图来源链尚未独立核实；本表保留原表记录，不自行修正。

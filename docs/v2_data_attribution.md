# V2 新24地区：数据来源、归属与许可核查

核查日期：2026-10-18。范围为新永久面板的24个地区标识；本次只读取公开网页和仓库文字元数据，没有下载原图、重新授权或公开上传数据。本表用于补齐未来新稿的 attribution，不改变已冻结的抽样、转换或实验设置。

## 官方依据与许可层次

入口是 [OpenEarthMap 官方 README](https://github.com/bao18/open_earth_map/blob/ad645629af37369dfbe481be40515a587c7cd4af/README.md)，其 License 节直接链接 [官方来源归属表](https://open-earth-map.org/attribution.html)。[Zenodo v1 记录](https://zenodo.org/records/7223446)重复了相同的标签许可规则：标签原则上随原RGB来源许可；原RGB为公有领域或没有明确许可时，OpenEarthMap 标签适用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)。这条 fallback 只说明标签，不能补出RGB影像许可。仓库显示的 MIT 也不能当作全部影像的许可。

以下国家、提供者和来源对应关系来自官方来源表；它们是**目录层级声明**，不是本次对72幅样本逐幅完成的国家边界或上游场景确权。没有精确场景URI时，不把目录名称当作唯一原始采集主体。

## 24地区对应表

“归属键”在下一节给出完整机构、来源URL和RGB许可。国家沿用官方元数据；星号表示仍有歧义或别名映射缺口。以下两表的目录关系依据 [官方来源表](https://open-earth-map.org/attribution.html)。

| 项目标识 | 官方国家字段 | 归属键 |
|---|---|---|
| abancay | Peru | P |
| al_qurnah | Iraq | O1 |
| baybay | Philippines | O2 |
| bielefeld | Germany | G |
| buenos_aires | Argentina | O3 |
| chiclayo | Peru | P |
| coxsbazar | Bangladesh | O4 |
| dowa | Malawi | O5 |
| kagera | Tanzania | O6 |
| kampala | Uganda | C |
| khartoum | Sudan | S |
| kinshasa | Congo* | C |
| kitsap | USA | I1 |
| monrovia | Liberia | C + O7* |
| ngaoundere | Cameroon | C |
| paris | France | S |
| rosario | Argentina | O8 |
| san_tome | Sao Tome and Principe | O9 |
| soriano | Uruguay | O10 |
| svaneti | Georgia | O11 |
| tokyo | Japan | J |
| tyrolw | 未核定* | I2候选* |
| western | Ghana | O12 |
| zanzibar | Tanzania | C + O13* |

## 归属键、来源URL与RGB许可

许可缩写：B = [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；SA = [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)；DE = [DL-DE-BY-2.0](https://www.govdata.de/dl-de/by-2-0)；PD = 官方表注明公有领域；U = 官方表许可栏为空，RGB许可未核定。链接是官方表提供的来源入口，不是所抽样文件的原始场景URI。

| 键 | 官方提供者 | 官方链接的来源 | RGB许可 |
|---|---|---|---|
| P | National Center for Disaster Risk Estimation, Prevention and Reduction | [SIGRID / CENEPRED](https://sigrid.cenepred.gob.pe/) | U |
| G | German state North Rhine-Westphalia | [GeoNRW](https://www.opengeodata.nrw.de/produkte/) | DE |
| C | Global Facility for Disaster Reduction and Recovery | [Open Cities AI](https://www.drivendata.org/competitions/60/building-segmentation-disaster-resilience/) | B |
| S | Maxar | [SpaceNet 2](https://spacenet.ai/spacenet-buildings-dataset-v2/) | SA |
| I1 | USGS | [Inria](https://project.inria.fr/aerialimagelabeling/) | PD |
| I2候选 | Tyrol | [Inria](https://project.inria.fr/aerialimagelabeling/) | PD，须先确认别名 |
| J | Geospatial Information Authority of Japan | [GSI tile catalogue](https://maps.gsi.go.jp/development/ichiran.html) | U |
| O1 | Bilal Koç | [OpenAerialMap](https://map.openaerialmap.org/) | B |
| O2 | SkyEye | 同上 | B |
| O3 | Municipalidad de Pergamino | 同上 | B |
| O4 | IOM Bangladesh - Needs and Population Monitoring (NPM) Drone | 同上 | B |
| O5 | MapMalawi | 同上 | B |
| O6 | WeRobotics | 同上 | B |
| O7 | Uhurulabs | 同上 | B |
| O8 | Julia Faraudello | 同上 | B |
| O9 | Drones Adventures | 同上 | B |
| O10 | IntelDrones SRL | 同上 | B |
| O11 | Transcaucasian Trail Association | 同上 | B |
| O12 | UMaT YouthMappers | 同上 | B |
| O13 | Commission for Lands and Revolutionary Government of Zanzibar | 同上 | B |

OpenAerialMap 自身的 [Terms and License](https://openaerialmap.org/legal/)说明：原版权保留于原提供者/权利人，平台以 CC BY 4.0 提供影像，并要求署名 Open Imagery Network contributors。因此后续署名应同时保留对应提供者与平台归属，不能仅写 OpenEarthMap 或 OAM。

[SpaceNet 2 官方页面](https://spacenet.ai/spacenet-buildings-dataset-v2/)独立确认 SA 许可，并列出 Paris、Khartoum 两个AOI。该页还要求论文引用 Van Etten、Lindenbaum、Bacastow 的 *SpaceNet: A Remote Sensing Dataset and Challenge Series*（2018）。[Open Cities 官方STAC说明](https://www.drivendata.org/competitions/60/building-segmentation-disaster-resilience/page/154/)给出了影像级许可元数据示例；本次没有取得样本对应的STAC item，因此不以其示例替代72幅样本的逐幅来源确认。

## 保留的歧义和未知项

- 对应表中的两个多来源键是官方表中同名地区的两行，不能凭目录名选择其中一行，也不能据此断言每一幅都同时来自两条来源。后续需要上游场景URI、源文件清单或维护者提供的映射，才能落实每个样本的credit。未解决时，新稿来源表保留两行和“逐幅映射未核定”。
- `kinshasa` 的官方国家单元格仅写 Congo；本记录保留原字段，不擅自扩展为某个精确主权国家名称。需要可靠国家元数据或坐标与国家边界核对后再规范化。
- 官方归属表的地区名是 Tyrol，不直接写 `tyrolw`。Inria项目页面本次被 robots.txt 阻止读取；因此 I2 是候选关系，不能把相似拼写当成已完成的文件夹映射。该项国家/来源/许可的适用关系须补官方别名或文件清单证据，也可先用GeoJSON坐标核对地理位置，但坐标不能单独证明影像许可。
- U类有官方提供者和来源入口，但官方表没有为RGB写出具体许可。SIGRID根页面本次未返回可读取正文，未找到这两类抽样RGB的逐项授权文本。GSI当前[官方利用条款](https://www.gsi.go.jp/ENGLISH/page_e30286.html)对一般网站内容列出PDL1.0、来源标示、编辑标示及第三方/测量成果例外；这不能倒推2022年归档影像的具体tile、版本和权利条件。需补精确tile/source版本及当时适用条款，不能直接把U改成CC许可或PDL已核定。
- 本次没有核对上游拍摄日期、飞行任务、完整mosaic重叠或场景级版权声明；提供者共同或不同均不证明地理独立性。这些缺口不用于按图像/标签内容重选样本。

## 标签、转换与未来新稿署名

对B、SA、DE来源，OpenEarthMap README给出的标签规则随对应RGB许可；对PD和U来源，标签使用上述CC BY-NC-SA 4.0 fallback。I2仅在别名映射落实后适用该判断。来源表为空不表示RGB已获得任意再利用许可，也不因标签fallback而改变RGB权利。

未来新稿应引用 OpenEarthMap（Xia、Yokoya、Adriano、Broni-Bediako，WACV 2023）及[数据记录DOI](https://doi.org/10.5281/zenodo.7223446)，并在来源补表完整列出本文件24个标识、提供者、来源URL、RGB与标签分别适用的许可及未核定项。涉及实际影像的图注或附带产物，应使用对应提供者credit，注明本项目进行了448像素重采样与PNG转换；分辨率/格式变化不产生新的上游授权。

[CC BY](https://creativecommons.org/licenses/by/4.0/)要求保留适当credit、许可链接和修改说明；[CC BY-SA](https://creativecommons.org/licenses/by-sa/4.0/)另有适用的相同方式共享要求；[CC BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/4.0/)另有限制商业用途及相同方式共享要求。[DE许可正文](https://www.govdata.de/dl-de/by-2-0)要求在提供方已给出的范围内标示提供者、许可、数据URI和修改。公开发布何种影像或衍生产物时，再针对该具体产物核对这些条件；本次没有进行发布或重新许可。

## 可复核的文字来源版本

本次只在内存读取文字响应，未保存网页副本或原图。哈希针对当次完整HTTP响应体字节，网页后续变化会导致不同哈希；哈希本身不代替可访问的来源内容。

| 文字来源 | 当次版本/大小 | SHA256 |
|---|---|---|
| [仓库README固定版本](https://raw.githubusercontent.com/bao18/open_earth_map/ad645629af37369dfbe481be40515a587c7cd4af/README.md) | commit `ad645629af37369dfbe481be40515a587c7cd4af`；4,445 B | `d8aae5a23b20b2c4b51a2a27f22122789fd82c66bc678ce5dcce4228dd44e80c` |
| [官方attribution HTML](https://open-earth-map.org/attribution.html) | 2026-10-18核查；35,731 B | `54d65e87141862f1ab7ccddf18c5d810d4f4fff8761977d1c57f31d02ac564f6` |

# V2 DOCX 排版输入与验证边界

`code/v2_build_documents.py` 只把已编辑的JSON转换为可编辑DOCX，不撰写论文，不从旧V1生成器获取段落、表格或引用顺序，不推算缺失分数。本次只制作引擎与schema；没有创建真实或占位论文、源JSON或DOCX。

## 使用阶段

仅查看帮助或运行标准库解析检查：

```text
python code/v2_build_documents.py --help
python code/v2_build_documents.py --self-test
```

真实证据全部完成后，由负责论文内容的父代理编写`paper/v2`中的源JSON。检查命令使用`--source`、`--output`与`--validate-only`；只有去掉`--validate-only`才会创建DOCX。两个路径都必须解析到项目内的`paper/v2`目录，扩展名分别为`.json`与`.docx`。图像使用项目内已有的POSIX相对路径，拒绝网络URL、越界和逃逸项目的符号链接。

生成不是交付验收。实际作者化命令前，父代理须按[documents技能](C:/Users/china/.codex/plugins/cache/openai-primary-runtime/documents/26.1011.51657/skills/documents/SKILL.md)运行规定的artifact-operation marker；生成后运行该技能的DOCX渲染流程、查看全部页面PNG，再修复并重渲染。引擎不会运行marker、渲染器或视觉验收，也不会以解析检查代替这些步骤。`--overwrite`仅用于明确重建已有输出。

`python-docx`仅在真实构建的证据和来源检查通过后导入。`--help`与`--self-test`不需要该包。实际生成应使用应用提供、已安装`python-docx`的artifact Python，不能依赖当前研究Python是否安装了文档包。

## 顶层对象

所有未列出的字段都会被拒绝，以免拼错字段后静默丢失内容。

| 字段 | 类型 | 要求 |
|---|---|---|
| `format` | string | 固定为`v2-document-source-1` |
| `kind` | string | `main`或`supplement`；两者使用相同排版器，不从kind推断科学内容 |
| `title` | string | 非空，原样显示；标题文本由作者提供 |
| `authors` | string数组 | 必填，可为空；每项独立显示。确实待补时可显式写待补文字，引擎不自动生成或认定作者批准 |
| `abstract` | string | 可选；若提供必须非空 |
| `keywords` | string数组 | 必填，可为空；按输入顺序显示 |
| `sections` | section数组 | 必填且非空 |
| `back_matter` | section数组 | 必填，可为空；基金、利益冲突、贡献、数据可用性等只能来自显式作者文本 |
| `reference_order` | string数组 | 仅包含本文件实际引用的键，按首次出现顺序；可为空 |
| `evidence_binding` | object | 下述完整哈希绑定，真实构建或validate-only均不得跳过 |

section只有两个字段：非空`title`及非空`blocks`数组。各section按`sections`顺序出现，随后按`back_matter`顺序出现。没有自动增补的“结论”、批准声明或投稿状态。

## 有序blocks

段落、图、表和子节必须放入同一个`blocks`数组，不能分成独立图表列表后统一放文末。支持以下对象：

| `type` | 字段 | 排布方式 |
|---|---|---|
| `paragraph` | 必填`text` | 一个正文段落；不解释Markdown、不生成新句子 |
| `subsection` | 必填`title`、`blocks` | 在当前位置输出标题，再递归输出blocks；最多六级标题 |
| `table` | 必填`id`、`caption`、`headers`、`rows`；可选`column_weights`、`alignments`、`font_size_pt`、`notes` | 表题、表头、各数据行、表注依次输出 |
| `figure` | 必填`id`、`path`、`alt`、`caption`；可选`width_inches` | 图像后跟图题，保持原像素比例 |

图表`id`必须在整个来源文件中唯一。caption应包含作者希望显示的完整编号和说明；引擎不推断图表编号或科学含义。

### 表格约束

- `headers`是非空字符串数组；`rows`为非空二维数组，每行列数与表头一致。
- 单元格只接受字符串、有限数值或null。数值使用其Python字符串表示，不自动取均值、补分数、加星号或调整精度。null显示为空单元格，不推断其原因。
- `column_weights`为与列数一致的正有限数数组，按比例分配6.5英寸正文宽度；省略时等宽。
- `alignments`逐列取`left`、`center`或`right`，省略时均为左对齐。
- `font_size_pt`在9至11之间，默认9.5。表注固定9.5pt；重复表头、禁止拆分单行，不设会截断文字的固定行高。
- 每行文字必须能够放入一页。代码不估测Word实际换行；过高数据行或过密表格需由作者在渲染后修改源数据展示方式，不能靠继续缩小到9pt以下解决。

### 图像约束

`path`只接受项目内已有PNG、JPEG、TIFF或BMP文件。SVG等应由负责图形的流程事先生成合适的出版图像，排版器不自行转换、下载或修改图形。`alt`为显式图像说明，不得包含引用token；可见引用放caption。`width_inches`须大于0且不超过6.5，默认6.5；图像还受7.7英寸高度上限限制并等比缩小。图题长度可能影响分页，最终仍需渲染检查。

## 引用token与文献库

在可见文本中使用`{cite:key1,key2}`，生成`[1, 2]`式编号。paragraph、标题、摘要、表头、表格字符串单元格、图表caption、表注与back matter均按实际显示顺序扫描。重复引用同一条目允许；单个token内的重复键、空键、格式残缺均拒绝。

文献库固定读取`docs/references_v2.bib`，采用标准库的平衡括号解析器，保留嵌套花括号与重音；支持花括号形式条目、花括号/引号字段及未加括号的数值。当前库无需宏定义或拼接；遇到`@string`、`@preamble`、`#`拼接、未知显示宏或不支持的语法会明确拒绝，不静默猜测。

校验包括：

1. 文献库不得有重复citation key或重复字段；每条须有author/title/year。
2. `reference_order`不得重复、引用未知键或列出未使用键。
3. 正文token中的键必须同时存在于文献库和`reference_order`。
4. 所有首次出现键的顺序必须与`reference_order`逐项相同，包括caption和表格内首次引用。

未被本文件引用的库条目不进入参考文献。引擎不导入V1的`REFERENCE_ORDER`，不会把整个文献库全部列入。main与supplement各自按其源JSON确定引用顺序。预印本保留arXiv标识和note，不补造会议发表信息。

## 构建前证据绑定

`evidence_binding`必须且只能含以下五个字段：

| 字段 | 含义 |
|---|---|
| `audited_result_inventory_sha256` | 当前审计`results`路径到结果文件SHA映射的稳定摘要，计算式见下 |
| `freeze_sha256` | 当前`configs/v2_freeze.json`的SHA256 |
| `numeric_file_sha256` | 下述恰好六个数值文件的项目相对路径到SHA256的映射 |
| `bibliography_sha256` | 当前`docs/references_v2.bib`的SHA256 |
| `asset_sha256` | 本源文件实际使用的全部图像路径到SHA256的映射；无图时为空对象 |

六个数值文件为：

```text
tables/v2/conditions_by_source.csv
tables/v2/conditions.csv
tables/v2/regions.csv
tables/v2/classes.csv
tables/v2/contrasts.json
tables/v2/primary.json
```

结果库存摘要严格按以下标准库表达式计算：

```python
hashlib.sha256(json.dumps(audit['results'], sort_keys=True,
                         separators=(',', ':')).encode('utf-8')).hexdigest()
```

源稿不固定`run_completeness.json`和`analysis_identity.json`两个含执行时间戳报告的整文件SHA。合法复算若只更新报告时间戳、当前报告之间的SHA链接，而结果库存和六个数值文件不变，就不需要改写已审阅源稿。任何结果文件SHA、路径清单、冻结文件、数值文件、文献库或实际用图发生变化，仍会使相应稳定绑定失效。

全部SHA为64位小写十六进制。构建前要求：

- 运行审计为`passed=true`，expected_total、validated_runs、observed_result_files均为576，results含576条，且无missing/extra/duplicates/errors。
- 分析identity的fits为576，`analysis.audit_sha256`必须等于当前审计文件的整文件SHA，输入绑定及result SHA映射与当前运行审计一致；审计结果库存的稳定摘要必须等于源稿声明。其中freeze绑定必须等于来源声明和当前freeze文件SHA，freeze状态须为评分前冻结状态。
- 分析identity的`output_sha256`必须恰好等于来源的六文件映射，且六个当前文件逐一重哈希一致。
- 实际result.json清单没有在审计后变化；审计登记的inputs/artifacts/results均重新核验当前SHA。审计、统计代码SHA也匹配分析身份。
- 当前文献库和本文件实际用到的所有图片均匹配来源绑定。

缺证据、过期哈希或只完成部分运行均拒绝，不能通过省略字段、validate-only或换输出名绕过。检查完成前不创建输出目录或DOCX。`--self-test`是独立解析检查，既不调用证据门也不产生文档，不能用它声称证据门已通过。

验证/生成时打印的报告会在`execution_observations`记录当时审计和分析报告的整文件SHA，供本次执行追溯。这两项是执行观察，不是需要写回源稿的稳定身份。该变更不减少576条件、代码/输入/附件/result新鲜度以及六数值文件的现有门槛。

## 排版与元数据

正文单栏，Letter纸型，左右各1英寸，黑色Times New Roman11pt。标题/标题层级/图题有明确样式，清除主题字体与默认彩色标题，不强制章节新起页。图片在当前位置保持比例，表格占宽不超过正文。表头重复、单行不拆、表格字体不小于9pt，页脚使用PAGE字段。

不插入空白段落作通用间距，不将全部表格行通过keep-with-next连成一块，减少标题孤立和大块空白风险；这些规则不是视觉排版已通过的证明。页码缓存和实际换页依赖后续Word/渲染器更新及检查。

DOCX的core_properties.author、last_modified_by、comments、subject、keywords、category、content_status等默认个人元数据清空。显示作者只来自JSON，不把Windows用户名、python-docx默认creator或操作者当作论文作者；不自动填写基金、COI、作者批准、最终稿或submission-ready状态。标题属性仅取源title。

## 验证范围与剩余验收

本轮允许的验证仅为Python语法、`--help`和标准库解析检查，不导入python-docx来生成文档，不制作真实或占位源论文。解析检查覆盖嵌套花括号、重复键/错误BibTeX、引用未知/重复/未用/次序、caption引用和有序递归blocks；库存检查验证报告时间戳及字典顺序变化不改变稳定摘要，任一结果SHA变化会改变摘要。

未来CLI生成后只报告`generated_requires_render_and_review`，同时保留`scientific_claims_or_table_values_reviewed=false`、`rendered_or_visually_verified=false`、`author_approval_asserted=false`。证据哈希绑定不等于逐项核验源段落或表格数字确实对应这些证据；相关数字、主张、引文支持、作者身份和声明均由父代理进行科学与作者验收。视觉验收须按技能另行完成，生成器不自动更新论文状态，也不宣称投稿就绪。

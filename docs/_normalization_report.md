# docs 公开化改写 · 规范化报告（_normalization_report）

> 本文件记录本轮“把内部逆向报告改写为外部读者可读、可复现版本”的改动与验证，供维护者复核；不属于分析结论正文。
> 改写范围：`docs/00_INDEX.md` … `docs/11_runtime_live.md`、`docs/REPORT.md`、仓库根 `README.md`。未改动任何分析结论、数字、证据引用。
> 目标布局：GitHub 仓库 `hhz-or/ETS100-source`（`docs/`、`data/`、`runtime/`、`scripts/`）。

---

## 一、改动文件清单

| 文件 | 行数（改后） | 主要改动 |
|---|---|---|
| `README.md`（仓库根） | 80 | 完全重写为外部入口：项目简介、目录结构、核心成果、快速开始、报告导航、数据/占位符约定、免责声明 |
| `docs/00_INDEX.md` | 142 | 完全重写：前置条件、一句话结论、仓库目录、5 分钟快速开始（签名/更新签名/密钥流/AES/缓存/题库包/CDP）、报告导航、数据可用性、证据等级、合规、复现环境 |
| `docs/01_target_and_inventory.md` | 162 | 前置块；安装路径占位符化；构建机 PDB 路径改为 `<BUILD_ROOT>`；清单引用改为 `data/inventory_hashes.json`（完整清单未发布说明） |
| `docs/02_architecture.md` | 190 | 前置块；提取件、日志路径中性化；删去“本机”表述 |
| `docs/03_api_protocol.md` | 772 | 前置块；数据源/产物路径映射；样本表标注脱敏与未发布产物；删除内部分工（analyst/Lead/队友）表述；补注 08 已还原签名算法 |
| `docs/04_frontend.md` | 934 | 标题规范化；前置块；缓存/bundle/pretty/excerpts 说明改为“未随仓库发布”；脚本映射为 `scripts/work_frontend_scripts_*.py`；产物索引去重并重排 |
| `docs/05_native.md` | 376 | 前置块；PDB 路径 `<BUILD_ROOT>`；导出/导入/分发统计映射到 `data/native/`；未发布反汇编/字符串产物统一标注；产物索引重写 |
| `docs/06_data.md` | 569 | 前置块；目标目录与导出目录占位符化；DB 产物映射 `data/db/`；存储/题库包/XML 产物标注未发布；脚本映射 `scripts/work_data__scripts_*.py` |
| `docs/07_shell_update.md` | 903 | 前置块；`stic://` 用户路径改 `<APPDATA_ETS>`；安装路径 `<ETS_INSTALL_DIR>`；PDB 路径 `<BUILD_ROOT>`；本机表述改为“该副本/分析环境”；清理内部分工词 |
| `docs/08_signature.md` | 219 | 前置块；验证命令改仓库脚本形式；样本说明明确“仓库版已脱敏、完整复现需重建”；参考实现/证明文件指向 `data/api/` |
| `docs/09_decompiled.md` | 250 | 前置块；所有 `ghidra_out` 引用统一为“（反编译产物未随仓库发布）”；Ghidra 复跑命令占位符化并说明导出脚本未发布 |
| `docs/10_unknowns.md` | 61 | 前置块；日志路径占位符化；PII 说明与仓库脱敏数据一致 |
| `docs/11_runtime_live.md` | 221 | 前置块；“用户在本机启动”改为“测试机上的分析副本”；运行环境/配置路径占位符化；运行时产物标注未发布 |
| `docs/REPORT.md` | 229 | 前置块；产物索引按仓库/未发布拆分；复现命令与脚本名改为仓库实际形式；GitHub 仓库描述公开化 |

合计：14 个文件；相对原始版本约 **+521 行 / -327 行**（含重写文件）。所有 13 篇报告开头均新增 3–4 行“前置条件 / 如何复现 / 占位符”提示块。

---

## 二、路径映射（内部工作区/ → 仓库布局）

| 原始（内部工作区） | 公开版写法 | 仓库中是否存在 |
|---|---|---|
| `内部工作区/api/endpoints.csv`、`sign_samples.json`、`ets_sign.py`、`update_sign_proof.json`、`request_headers.json` | `data/api/…` | 是 |
| `内部工作区/runtime/sign_oracle.json` | `data/api/sign_oracle.json` | 是 |
| `内部工作区/frontend/routes.json`、`action_keys.json`、`routes_live.json`、`chunks_manifest.json`、`new_modules_analysis.json`、`plugin_stubs_analysis.json` | `data/frontend/…` | 是 |
| `内部工作区/runtime/live_requests.json`、`plugin_js_stubs/` | `runtime/…` | 是 |
| `内部工作区/native/_summary.json`、`plugin_abi.json`、`<name>_{exports,imports,dispatch}.json` | `data/native/…` | 是 |
| `内部工作区/data/db/ETS_db_dump.json`、`ETS_db_Config_rows.json` | `data/db/…` | 是 |
| `内部工作区/inventory_hashes.json` | `data/inventory_hashes.json` | 是 |
| `内部工作区/scripts/*` | `scripts/*`（同名） | 是 |
| `内部工作区/frontend/scripts/X.py` | `scripts/work_frontend_scripts_X.py` | 是（发布时扁平化命名） |
| `内部工作区/data/_scripts/X.py` | `scripts/work_data__scripts_X.py` | 是（发布时扁平化命名） |
| `内部工作区/native/_tools/X.py` | `scripts/work_native__tools_X.py` | 是（发布时扁平化命名） |
| `内部工作区/ghidra_out/…` | `（反编译产物未随仓库发布）` | 否 |
| `内部工作区/ghidra_scripts/DumpDecomp.java` | “Ghidra 导出脚本（未随仓库发布）” | 否 |
| `内部工作区/pkg/…`、`内部工作区/lead/…` | “（壳层/更新日志解析、中间证据）未随仓库发布” | 否 |
| `内部工作区/runtime/chunks_full/`、`native_probe_*.json` | “（未随仓库发布）” | 否 |
| `内部工作区/data/{storage,extracted,soundfiles,logs}/*`、`resources_*.json` | `data/…（未随仓库发布）` | 否 |
| `内部工作区/frontend/{bundles,pretty,manifest.json,cache_entries.json,api_endpoints.json,stores.json,bridge_calls.json,excerpts/}` | “（未随仓库发布）”+ 已发布 JSON 的实际位置 | 否 |
| `内部工作区/inventory.json`、`内部工作区/api/{endpoint_samples.json,sign_proof.json,reports/}` | `data/…（未随仓库发布）` | 否 |

设计原则：**已发布数据给真实仓库路径**；未发布产物用“（未随仓库发布）”显式标注，并在 `00_INDEX.md`「数据可用性约定」统一解释，避免让读者误以为文件存在。

---

## 三、占位符说明

| 占位符 | 含义 | 出现位置 |
|---|---|---|
| `<ETS_INSTALL_DIR>` | 目标程序安装根目录（只读分析副本）；文档中所有原安装目录绝对路径与安装目录相对路径前缀均替换为此 | 全部报告 |
| `<APPDATA_ETS>` | 用户数据目录 `%APPDATA%\ETS`；原用户目录下的 ETS 数据路径替换为此 | 主要 07/11 |
| `<WORK_DIR>` | 原分析工作区根目录（中间产物所在）；原工作区绝对路径替换为此 | 00/06/09 等 |
| `<BUILD_ROOT>` | 二进制/日志内嵌的厂商构建机路径前缀；原 PDB/日志路径统一保留其余目录结构，仅脱去盘符前缀 | 01/02/05/07/09/REPORT |
| `<JDK_HOME>` / `<GHIDRA_HOME>` | 读者自备的 JDK / Ghidra 安装目录（仅 09 的复跑示例） | 09 |

> 保留说明：厂商构建机路径来自**二进制内嵌字符串**，是“构建血缘”证据本身。公开版保留其目录结构（`STIC\stic-pro_ets\…`），仅把机器相关的盘符前缀替换为 `<BUILD_ROOT>`，不改变证据含义。

---

## 四、本机痕迹清理

已清零（脚本扫描 0 命中）：分析工作区/安装目录/用户目录的绝对路径、厂商构建机盘符前缀、`内部工作区/…` 目录引用、`本机`、`本报告作者`、`用户本机`、`Team Lead`、`analyst` 署名、`task-N` 编号、`Lead/队友` 等内部分工表述。

保留的两个技术性例外：

1. `requireAdministrator` —— Windows 清单属性值（`<requestedExecutionLevel level='requireAdministrator' …>`），是证据原文，不是账号名。
2. 03 篇中 `�ɹ�` —— 原文引用的“PowerShell 控制台按 cp936 解码造成的乱码示例”，用于说明日志编码问题，保留。

---

## 五、外部读者 5 分钟上手 · 实际验证记录

环境：Windows x64、Python 3.13、工作目录 = 仓库根（`ETS100-source` 布局）。
说明：仓库内部分脚本仍保留原分析工作区的输入路径常量（见“遗留问题”）；分析机上存在原始只读副本与历史样本，因此以下命令可复现原始验证结果。

| # | 命令（仓库根执行） | 实际输出（节选/脱敏） | 与文档一致性 |
|---|---|---|---|
| 1 | `python scripts\sign_verify_all.py` | `v2 verify: 333/334 match`；1 条 MISMATCH 为 `ets_2026-11-4.log:55`（`/user/login`，日志脱敏置空 password） | 与 08/REPORT 的 333/334 一致 |
| 2 | `python scripts\keystream.py` | `fnv0: 0x32a7b273 expected 0x32a7b273 MATCH`；`fnv1: 0xb9ef3cd1 expected 0xb9ef3cd1 MATCH` | 与 08/REPORT 的 FNV MATCH 一致 |
| 3 | `python scripts\update_sign_verify.py` | `update sign verify: 6/6`（分析机的更新日志比仓库证明多 3 组样本；仓库 `data/api/update_sign_proof.json` 为 3/3） | 与文档“3/3（仓库证明 3 组）”一致，样本更多时命中数按比例增加 |
| 4 | `python scripts\aes_check.py` | `k_serves` 对 3 组候选字段全部解密成功（`candidate fields: 3`；明文为 PII，未记录） | 与 08/REPORT 的 3/3 一致 |

补充核查（只读）：

- `data/api/sign_samples.json` 为脱敏版，用 `data/api/ets_sign.py` 直接复算仅 **63/334** 可直接命中（敏感字段 `***` 改变了签名原文）；文档已明确说明并给出 `scripts/extract_sign.py` 重建路径。
- `data/api/endpoints.csv` 63 行、`data/frontend/routes.json` 91 路由、`data/frontend/action_keys.json` 115 action、`data/native/_summary.json` 14 个二进制条目均与报告统计一致（抽样核对）。
- 文档相对链接 `../data/api/ets_sign.py`、`../scripts/sign_verify_all.py` 在目标仓库布局下存在。

---

## 六、质量校验（脚本化）

| 检查 | 方法 | 结果 |
|---|---|---|
| 绝对路径/环境痕迹 | 正则扫描 14 个文件 | 0 命中（`requireAdministrator` 除外，见上） |
| 内部署名/分工 | 正则扫描 `Team Lead`/`analyst`/`Lead`/`队友`/`分析者`/`分析员` | 0 命中 |
| 代码围栏配对 | 每个文件统计 ``` 数量 | 全部偶数，无未闭合 |
| 相对链接 | 解析 `](…)` 并与目标布局比对 | 仅 `../data/…`、`../scripts/…`（目标仓库存在）；无失效死链 |
| 前置条件块 | 检查 13 篇是否含 `**前置条件**` | 13/13 存在 |
| 占位符使用 | 统计 `<ETS_INSTALL_DIR>` 等 | 见第三节；无裸绝对路径残留 |
| 技术数字 | 抽样比对原稿 | 667 文件/347 MB、51 API、91 路由、117 action、333/334、3/3、24/24、188 chunk、115 action 对等均未改动 |

---

## 七、遗留问题与移交建议（超出本任务写权限）

1. **`scripts/` 仍含分析工作区绝对输入路径**：`sign_verify_all.py`、`update_sign_verify.py`、`keystream.py`、`aes_check.py`、`extract_sign.py`、`download_chunks.py`、`work_data__scripts_extract_content.py` 等以硬编码路径读取原安装副本/历史样本。公开仓库克隆到其它机器后，这些脚本不能直接运行。
   - 建议：发布前统一改为“仓库根相对路径 + 命令行参数/环境变量”，或至少在脚本顶部加 `BASE = os.environ.get(...)`；文档已加提示与复现说明。
2. **`data/api/sign_samples.json` 脱敏导致签名样本不可完整复核**：当前仅 63/334 可直接复算。若希望外部读者完整复现 333/334，建议发布“不含 PII 的完整 body 版本”（或在发布流程里只对 token/手机号等做替换并同步重算 sign 不可行——签名原文必须原样），或明确保持“仓库脱敏版 + 需原始日志重建”的定位。
3. **`data/native/_summary.json` 的 `file` 字段仍含原分析机绝对路径**：属于机读数据而非文档，本轮未改。建议发布前做一次数据脱敏（把 `file` 字段改为相对名或占位符）。
4. **仓库中的 `docs/` 尚未同步本轮改写**：需要发布流程把本目录 13 篇文档与根 `README.md` 覆盖到 `repo/docs/` 与 `repo/README.md`（本轮按权限只写本目录 `docs/**` 与仓库根 `README.md`）。
5. **`data/frontend/` 缺 `manifest.json` 等被文档描述为“未发布”的文件**：已按“未随仓库发布”标注，后续若补齐需同步去掉标注。
6. **`update_sign_verify.py` 在样本更多时输出 6/6**：文档保留原始结论“3/3（仓库证明 3 组）”，并在 README 注明；若更新证明文件，请同步更新 08/REPORT/README 的措辞。

---

## 八、复跑本报告校验的方法

```powershell
# 在仓库根执行
python scripts\sign_verify_all.py
python scripts\keystream.py
python scripts\update_sign_verify.py
python scripts\aes_check.py
```

> 若脚本提示找不到输入文件，说明当前机器没有原安装副本/历史日志；把脚本顶部输入常量改为 `<ETS_INSTALL_DIR>` 对应路径即可。仅复核结论时，可阅读 `data/api/`、`data/frontend/`、`data/native/`、`data/db/` 中已发布的数据。

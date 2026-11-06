# E听说 PC 学生端 逆向报告 · 00 总览与导航

> 目标目录：`D:\ets-rea\ETS`（667 个文件，347.14 MB）
> 分析日期：2026-11-06
> 分析方式：静态逆向（文件/二进制/日志/缓存/资源包）+ 有限运行时证据（历史日志中记录的完整网络流量与插件调用）
> 所有分析产物均在 `D:\ets-rea\` 内；`ETS\` 原始文件全程只读、未做任何修改。

---

## 一、一句话结论

`ETS` 不是普通 Electron 应用，而是 **讯飞自研 STIC（V3.0.76）CEF 壳 + 9 个 C++ 原生插件（`.pln`）+ 远程加载的 Vue3 SPA + Node.js WebSocket 日志总线（mq_server）+ 独立更新器** 组成的 5 层异构客户端。

业务逻辑 90% 以上在前端 JS；原生层是 10 个左右能力模块（HTTP、文件、音频、SQLite、7z、窗口、外壳、签名工具）；**真正的业务协议几乎"白送"**——`ETS\logs\ets_*.log` 里保存了 340 条完整请求 + 341 条响应明文（含 `head.sign`），`mq_server\main.js` 是纯明文源码。

| 项目 | 值 |
|---|---|
| 产品 | 讯飞易听说「E听说」学生端 PC 版（E听说） |
| 客户端版本 | **5.7.9**（`localdata\ETS.db` → `System/C_Version`；`Update_Version=5079`） |
| 外壳 | `ETSShell.exe` **5.0.91.329**，产品名 `CCS`，公司 `iflytek` |
| 壳框架 | **STIC V3.0.76**（自研，源码路径 `D:\code\STIC\stic-pro_ets\...`，PDB `ETSShell.pdb`） |
| 浏览器内核 | CEF **91.1.22** / Chromium **91.0.4472.124**（`README.txt` + `libcef.dll` 版本资源） |
| 前端 | **Vue 3 + Element Plus** SPA，远程加载 `https://statics.ets100.com/ets-student-pc-web/index.html`（`shell.ini`） |
| 进程 | 1 个 browser 进程 + GPU/utility/renderer 子进程（历史日志中 15 个 ETSShell 进程），外加 `ets_mq_server.exe`（Node.js SEA） |
| 网络 | `api.ets100.com`（业务 API）、`statics.ets100.com`（前端）、`cdnfei.ets100.com`/`ets60.ets100.com`（资源/OSS）、阿里云 SLS 日志 |
| 本地数据 | SQLite（ETS.db、Cookies、Databases.db、BuryPoint.db）、LevelDB（Local Storage / IndexedDB / Session Storage）、Chromium Simple Cache、zip 资源包、音频 xml+mp3+spx |

---

## 二、报告导航

| 文档 | 内容 |
|---|---|
| [REPORT.md](REPORT.md) | **总报告（先看这个）**：成果汇总、统计、复现指南 |
| [00 总览与导航](00_INDEX.md) | 本文 |
| [01 目标识别与文件清单](01_target_and_inventory.md) | 产品识别、目录结构、关键文件指纹、证据等级 |
| [02 系统架构](02_architecture.md) | 5 层架构、进程模型、启动链、消息/数据流、组件职责 |
| [03 API 与协议](03_api_protocol.md) | mq_server WS 协议、全部 HTTP API、鉴权链、请求/响应结构 |
| [04 前端逆向](04_frontend.md) | SPA 入口、Vue 路由表、API 封装、JS↔Native 桥 action 手册 |
| [05 原生层](05_native.md) | 壳/插件 ABI、导出与导入、RTTI、关键字符串、各插件能力面 |
| [06 本地数据与资源](06_data.md) | SQLite/LevelDB/缓存、题库包格式、模板、音频评测 xml |
| [07 壳层/更新/音频链](07_shell_update.md) | 启动与进程模型、shell.ini、更新机制、崩溃上报、音视频转码链 |
| [08 API 签名与字段加密](08_signature.md) | `head.sign` 算法还原与 333/334 验证；AES 字段加密与内置密钥 |
| [09 原生反编译摘录](09_decompiled.md) | Ghidra 反编译关键函数摘录与解读（签名、分发、插件实现） |
| [10 未知项与后续](10_unknowns.md) | 未解问题、验证方法、风险与合规边界 |
| [11 运行时验证（Live）](11_runtime_live.md) | 真实运行实例 CDP 抓取、在线前端全量 chunk、插件 JS 权威 action 表、活体协议验证 |

配套数据（可机读）：
- `work/inventory.json` 全量文件清单
- `work/api/` 日志还原的请求/响应（`ets_requests.json`/`ets_responses.json`）、`sign_samples.json`（334 组签名样本）、`ets_sign.py`（签名参考实现）、`endpoints.csv`
- `work/frontend/` 提取出的前端 bundle（209 个资源）、`routes.json`、`action_keys.json`、`api_endpoints.json`
- `work/native/` 14 个二进制的导出/导入/字符串/反汇编（含插件 ABI、action 分发汇编）
- `work/data/` 解包后的资源与数据导出（DB/存储/24 个题库包/评测 XML）
- `work/ghidra_out/` Ghidra 反编译输出（`decompiled.c`、`functions.tsv`、`strings.tsv`；etshelper/appcontroller/filehelper/window_control 等已完成，ETSShell/EtsUpdate 等在批量产出）
- `work/pkg/` 壳层日志时间线、更新日志分析
- `work/lead/` 签名算法还原过程的中间证据与提取件
- `work/scripts/` 本次分析使用的全部脚本（可复现）

> 说明：Ghidra 反编译是**批量后台任务**，交付时已完成的二进制见 `09_decompiled.md` §1；其余产物会继续落在 `work/ghidra_out/`，不影响本报告的结论与证据链。

---

## 三、证据等级约定

本文档体系严格区分三类陈述：

- **【观察】** 直接来自文件字节、日志原文、工具输出，可复现。
- **【推断】** 由观察经合理推理得出，标注推理链。
- **【未知】** 当前证据不足，列入 `10_unknowns.md` 并给出建议验证方法。

静态分析**不建立运行时执行事实**；本文引用的"运行时"信息全部来自目标自身写下的历史日志（`logs\`），并非本次执行目标所得。

## 四、脱敏与合规

- 日志中含真实账号 JWT、手机号、学校/班级、阿里云 STS 临时凭证（均已过期）等敏感数据。所有交付物**一律脱敏**：PII → `***`，token/密钥只保留结构与长度，不保留原值。
- 本报告用于架构学习、互操作性研究、安全评估与自有环境排障；不包含绕过付费/评分/考试、伪造成绩、破解授权的能力性内容。
- 对第三方软件的逆向可能受 EULA/著作权约束，使用前请自行确认授权范围。

## 五、复现环境

| 组件 | 版本/位置 | 用途 |
|---|---|---|
| Python | 3.13（`python`） | 日志/缓存/资源包解析脚本 |
| 7-Zip | 26.00 | 解包 7z/zip |
| REA MCP | rea-agents 6.8.0 | PE 导出/导入/资源/objdump 检查 |
| Ghidra | 12.1.4（临时安装于系统盘临时目录，产物写入 `work/ghidra_out`） | 原生反编译 |
| Zulu JDK | 25.0.2 | Ghidra 运行时 |
| Node.js | 系统自带 | 运行/阅读 mq_server 逻辑（未执行目标） |

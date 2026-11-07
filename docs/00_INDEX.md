# E听说 PC 学生端 逆向报告 · 00 总览与导航

> **前置条件**：Windows 10/11 x64；Python 3.10+；可选 Node.js 18+（阅读/运行 `mq_server` 与前端 JS）；可选 7-Zip（解包 zip/7z）。
> **如何复现**：在仓库根目录执行 `python scripts/<脚本名>.py`；机读数据在 `data/`，运行时证据在 `runtime/`；分析对象为只读安装副本 `<ETS_INSTALL_DIR>`（全程不修改其中文件）。
> **占位符**：`<ETS_INSTALL_DIR>`=目标程序安装目录；`<APPDATA_ETS>`=`%APPDATA%\ETS`；`<WORK_DIR>`=原分析工作区；`<BUILD_ROOT>`=厂商构建机路径前缀（二进制/日志内嵌字符串原文，仅作证据）。

> 目标目录：`<ETS_INSTALL_DIR>`（667 个文件，347.14 MB）
> 分析日期：2026-11-06
> 分析方式：静态逆向（文件/二进制/日志/缓存/资源包）+ 有限运行时证据（历史日志中记录的完整网络流量与插件调用）
> 分析对象全程只读、未做任何修改；仓库只发布脱敏后的报告与机读数据。

---

## 一、一句话结论

`ETS` 不是普通 Electron 应用，而是 **讯飞自研 STIC（V3.0.76）CEF 壳 + 9 个 C++ 原生插件（`.pln`）+ 远程加载的 Vue3 SPA + Node.js WebSocket 日志总线（mq_server）+ 独立更新器** 组成的 5 层异构客户端。

业务逻辑 90% 以上在前端 JS；原生层是 10 个左右能力模块（HTTP、文件、音频、SQLite、7z、窗口、外壳、签名工具）；**真正的业务协议几乎"白送"**——目标自身的历史日志 `<ETS_INSTALL_DIR>\logs\ets_*.log` 里保存了 340 条完整请求 + 341 条响应明文（含 `head.sign`），`mq_server\main.js` 是纯明文源码。

| 项目 | 值 |
|---|---|
| 产品 | 讯飞易听说「E听说」学生端 PC 版（E听说） |
| 客户端版本 | **5.7.9**（`localdata\ETS.db` → `System/C_Version`；`Update_Version=5079`） |
| 外壳 | `ETSShell.exe` **5.0.91.329**，产品名 `CCS`，公司 `iflytek` |
| 壳框架 | **STIC V3.0.76**（自研，源码路径 `<BUILD_ROOT>\STIC\stic-pro_ets\...`，PDB `ETSShell.pdb`） |
| 浏览器内核 | CEF **91.1.22** / Chromium **91.0.4472.124**（`README.txt` + `libcef.dll` 版本资源） |
| 前端 | **Vue 3 + Element Plus** SPA，远程加载 `https://statics.ets100.com/ets-student-pc-web/index.html`（`shell.ini`） |
| 进程 | 1 个 browser 进程 + GPU/utility/renderer 子进程（历史日志中 15 个 ETSShell 进程），外加 `ets_mq_server.exe`（Node.js SEA） |
| 网络 | `api.ets100.com`（业务 API）、`statics.ets100.com`（前端）、`cdnfei.ets100.com`/`ets60.ets100.com`（资源/OSS）、阿里云 SLS 日志 |
| 本地数据 | SQLite（ETS.db、Cookies、Databases.db、BuryPoint.db）、LevelDB（Local Storage / IndexedDB / Session Storage）、Chromium Simple Cache、zip 资源包、音频 xml+mp3+spx |

---

## 二、仓库目录结构

```
ETS100-source/
├─ docs/        14 篇中文报告（本文件是导航；从 REPORT.md 开始读）
├─ data/        脱敏后的机读分析数据
│  ├─ api/      端点清单、签名样本、签名参考实现、运行时/更新器签名证明
│  ├─ frontend/ 路由、action、端点、在线 chunk 清单、插件 JS 权威 action 表
│  ├─ native/   14 个原生 PE 的导出/导入/分发统计、插件 ABI
│  └─ db/       ETS.db 全表结构与 Config 数据
├─ runtime/     运行时证据：插件 JS 封装层（plugin_js_stubs）、活体请求元数据
├─ scripts/     全部分析脚本（缓存解码、签名验证、密钥流、题库包解密、CDP 抓取…）
├─ reimpl/      可运行的参考客户端（Python 后端 + 原生 Web UI，见 12_reimplementation.md）
└─ native-replica/ 同架构原生复刻（C++20/WebView2 + 插件 DLL + Vue3，见 13_native_replica.md）
```

`scripts/` 已把绝对路径归一化为仓库相对约定：需要目标文件的脚本默认读取仓库根下的 `ETS/`（把你的 ETS 安装目录放/软链到这里），数据文件在 `data/`、运行时证据在 `runtime/`；详见 `scripts/README.md`。

---

## 三、快速开始（外部读者 5 分钟）

```powershell
# 0) 环境：Windows 10/11 x64 + Python 3.10+（可选 Node.js 18+、7-Zip）
python --version
node --version      # 可选：跑 CDP/前端相关脚本时需要

# 1) API 请求签名：MD5(pid + time + base64(body) + 内嵌密钥流)，期望 333/334
#    注：仓库内 sign_samples.json 已脱敏，只有部分样本可直接复核；完整复现需用脚本从自己的日志重建
python scripts\sign_verify_all.py

# 2) 更新器签名：MD5("grlx" + time秒 + base64(body) + key)，期望 3/3（仓库证明文件含 3 组样本）
python scripts\update_sign_verify.py

# 3) 密钥流复算：从 etshelper.pln 的 .rdata 表提取并做 FNV-1a 校验，期望 MATCH
python scripts\keystream.py

# 4) 登录字段 AES-128-ECB 解密验证，期望 3/3
python scripts\aes_check.py

# 5) 前端缓存提取：解析 Chromium blockfile 缓存并导出可读 bundle
python scripts\work_frontend_scripts_1_parse_cache.py

# 6) 题库包解密：ZipCrypto 口令由包尾口令块 MD5(MD5(pwd)) 派生，期望 24/24 解包
python scripts\work_data__scripts_extract_content.py

# 7) 运行时抓取（可选）：对已打开的 CDP 端口抓 script source / 网络 / 截图
node scripts\dump_cdp.js

# 8) 参考客户端：可真实登录、浏览真实作业/套卷/题库内容（详见 docs/12_reimplementation.md）
#    凭据只放在仓库外的 <WORK_DIR>/secrets/，不要提交
python reimpl\server.py            # 打开 http://127.0.0.1:8787/
python reimpl\tools\smoke_test.py  # 只读接口自动验收（16/16）
```

> 脚本 1、2、3、4 依赖原安装副本或历史日志中的原始样本；仓库内 `data/api/` 提供已脱敏的样本与签名证明，可用于复核端点清单与算法结论；其中 `sign_samples.json` 为脱敏版，只有部分样本可直接复算签名，完整 334 组需用 `scripts/extract_sign.py` 从自己的日志重建。脚本 5、6 的输入同样来自 `<ETS_INSTALL_DIR>` 或 `<WORK_DIR>`，按脚本顶部常量调整后即可复跑。

---

## 四、报告导航

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
| [11 运行时验证（Live）](11_runtime_live.md) | 真实运行实例 CDP 抓取、在线前端全量 chunk、插件 JS 权威 action 表、活体协议验证、Frida 原生 hook |
| [12 参考客户端](12_reimplementation.md) | 可运行的 ETS 复刻原型：架构映射、已实现/未实现矩阵、运行方式 |
| [13 原生同架构复刻](13_native_replica.md) | C++20+WebView2 壳、7 插件 DLL、Vue3 前端、Node mq_server：映射、验证与限制 |

---

## 五、数据可用性约定

- `data/`、`runtime/`、`scripts/` 为随仓库发布的脱敏机读数据与脚本。
- 原始安装副本、原始日志、原始前端 bundle、大体积反编译产物（`decompiled.c` 等）、壳层时间线与部分逐二进制中间产物**未随仓库发布**；文档中对应位置以“（未随仓库发布）”标注。
- 需要这些中间产物时，按各篇文档给出的脚本与方法，从自己的只读安装副本重建。
- 文档中的证据位置统一写作 `日志名:行号`（如 `ets_2026-10-28.log:131`），原始日志位于 `<ETS_INSTALL_DIR>\logs\`。

---

## 六、证据等级约定

本文档体系严格区分三类陈述：

- **【观察】** 直接来自文件字节、日志原文、工具输出，可复现。
- **【推断】** 由观察经合理推理得出，标注推理链。
- **【未知】** 当前证据不足，列入 [10_unknowns.md](10_unknowns.md) 并给出建议验证方法。

静态分析**不建立运行时执行事实**；本文引用的“运行时”信息全部来自目标自身写下的历史日志（`logs\`），并非执行目标所得。仅 [11_runtime_live.md](11_runtime_live.md) 描述了一次在隔离分析副本上主动启动实例后的 CDP 观察，并已明确标注。

## 七、脱敏与合规

- 日志中含真实账号 JWT、手机号、学校/班级、阿里云 STS 临时凭证（均已过期）等敏感数据。所有交付物**一律脱敏**：PII → `***`，token/密钥只保留结构与长度，不保留原值。
- 本报告用于架构学习、互操作性研究、安全评估与自有环境排障；不包含绕过付费/评分/考试、伪造成绩、破解授权的能力性内容。
- 对第三方软件的逆向可能受 EULA/著作权约束，使用前请自行确认授权范围。

## 八、复现环境（推荐）

| 组件 | 版本 | 用途 |
|---|---|---|
| Windows | 10/11 x64 | 目标为 32 位 PE / CEF 客户端 |
| Python | 3.10+（原分析用 3.13） | 日志/缓存/资源包解析脚本 |
| 7-Zip | 24+（原分析用 26.00） | 解包 7z/zip |
| Node.js | 18+（可选） | 阅读/运行 `mq_server` 逻辑、CDP 抓取脚本 |
| Ghidra | 12.1.4 + JDK 21+（可选） | 原生反编译；反编译产物未随仓库发布 |

> 原分析还使用了 REA（逆向分析 MCP）做 PE 导出/导入/证书检查；这些检查的结论已写入报告，读者用任意 PE 工具（如 `pefile`、DIE、objdump）均可复核。

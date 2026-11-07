# E听说 PC 学生端 · 全量逆向总报告

> **前置条件**：Windows 10/11 x64；Python 3.10+；可选 Node.js 18+（阅读/运行 `mq_server` 与前端 JS）；可选 7-Zip（解包 zip/7z）。
> **如何复现**：在仓库根目录执行 `python scripts/<脚本名>.py`；机读数据在 `data/`，运行时证据在 `runtime/`；分析对象为只读安装副本 `<ETS_INSTALL_DIR>`（全程不修改其中文件）。
> **占位符**：`<ETS_INSTALL_DIR>`=目标程序安装目录；`<APPDATA_ETS>`=`%APPDATA%\ETS`；`<WORK_DIR>`=原分析工作区；`<BUILD_ROOT>`=厂商构建机路径前缀（二进制/日志内嵌字符串原文，仅作证据）。
> **总报告**：各专题细节见 `docs/01`–`docs/11`；快速开始与目录结构见仓库 `README.md`。

> 目标：`<ETS_INSTALL_DIR>`（E听说学生端 PC 5.7.9，STIC/CEF 壳，667 个文件 / 347 MB）
> 方式：静态逆向 + 目标自身历史日志/缓存证据（**未执行目标、未连接厂商服务器**）
> 产物：仓库内为 `docs/` 报告体系、`data/` 机读数据、`runtime/` 运行时证据与 `scripts/` 脚本；原分析工作区 `<WORK_DIR>` 的中间产物不随仓库发布。分析对象 `<ETS_INSTALL_DIR>` 全程只读未改。

---

## 一、摘要

这是一套 **5 层异构客户端**：STIC（讯飞自研）CEF 91 壳 → 9 个 C++ 原生插件 → 远程 Vue3 SPA → Node.js WebSocket 日志总线 → 独立更新器/崩溃上报/音频链。**业务逻辑 90% 在前端 JS**；原生层是能力模块；服务端协议几乎完整暴露在客户端自写日志里。

本次逆向完成了从"文件清单"到"**可复现的签名/加密算法**"的贯通，主要可验证成果：

| # | 成果 | 验证状态 |
|---|---|---|
| 1 | **`head.sign` 签名算法完整还原**：`MD5(pid + time + base64(body) + 内嵌密钥流)` | **333/334 组真实 API 请求精确命中**（唯一不中为脱敏登录） |
| 1b | **更新器签名同样还原**：`MD5("grlx"+time秒+base64(body)+"555ff…ab8")` | **3/3 组真实更新请求精确命中** |
| 2 | **登录手机号/密码字段加密还原**：AES-128-ECB + 硬编码 `k_serves` 密钥 | 日志密文 3/3 解密出明文（已脱敏展示） |
| 3 | **前端全量 bundle 提取**：Chromium Simple Cache blockfile 格式解码 | 353/353 缓存条目（URL/头/体）还原，209 个资源落盘 |
| 4 | **题库内容包 ZipCrypto 口令算法** | 24/24 content 包成功解密并解包 |
| 5 | **mq_server 日志总线完整协议**（144 行明文 Node 源码） | 与真实日志逐条比对一致 |
| 6 | **插件 ABI / 117 个原生 action 面 / 9 插件职责** | 导出表 + 前端调用点 + 日志三方交叉 |
| 7 | **原生反编译**（Ghidra 12.1.4）：etshelper / appcontroller / filehelper 全量；ETSShell / EtsUpdate 等批量产出 | 见 `09_decompiled.md` |
| 8 | **本地数据全解**：SQLite/LevelDB/IndexedDB/Cookies、资源包、评测 XML | 见 `06_data.md` |
| 9 | **壳层/更新/音频链**：启动链、进程模型、更新协议、转码链 | 见 `07_shell_update.md` |
| 10 | **运行时验证（2026-11-06 live）**：CDP 抓取真实运行实例、补齐全部 188 个在线 chunk、插件 JS 权威 action 表、活体请求签名 68/68 | 见 `11_runtime_live.md` |

---

## 二、交付物清单

### 文档（`docs/`）

| 文件 | 内容 |
|---|---|
| [00_INDEX.md](00_INDEX.md) | 总览、导航、证据等级、合规声明 |
| [01_target_and_inventory.md](01_target_and_inventory.md) | 产品识别、目录树、667 文件清单、关键指纹 |
| [02_architecture.md](02_architecture.md) | 5 层架构、进程模型、启动链、JS↔Native 桥、scheme、数据流 |
| [03_api_protocol.md](03_api_protocol.md) | mq_server 协议、HTTP 信封、51 个 API 路径、鉴权链、AI 评测/OSS/SLS |
| [04_frontend.md](04_frontend.md) | 缓存格式解码、91 路由、20 store、118 端点、117 action、录音评测链 |
| [05_native.md](05_native.md) | 14 个原生 PE 的身份/导出/导入/字符串/能力面（原生层分析产出） |
| [06_data.md](06_data.md) | DB/存储/资源包/评测 XML 全解 |
| [07_shell_update.md](07_shell_update.md) | 壳层、窗口桥、更新、崩溃上报、音频/7z 链 |
| [08_signature.md](08_signature.md) | **签名算法 + 字段加密 + 验证** |
| [09_decompiled.md](09_decompiled.md) | Ghidra 反编译关键函数摘录与解读 |
| [10_unknowns.md](10_unknowns.md) | 未知项、限制、后续验证 |
| [11_runtime_live.md](11_runtime_live.md) | 运行时验证：Live CDP、全量 chunk、插件 JS 权威 action 表、活体协议 |

### 机读数据/脚本（仓库内）

| 路径 | 内容 |
|---|---|
| `data/inventory_hashes.json` | 关键文件的 SHA-256；完整 667 文件清单未随仓库发布 |
| `data/api/` | `endpoints.csv`、`sign_samples.json`（334 组）、`ets_sign.py`（参考实现）、`update_sign_proof.json` |
| `data/frontend/` | `routes.json`、`action_keys.json`、插件 JS 权威 action 表、在线 chunk 清单 |
| `data/native/` | 14 个二进制的导出/导入/分发统计与插件 ABI 汇总 |
| `data/db/` | ETS.db 全表结构与 Config 数据 |
| `runtime/` | 插件 JS 封装层、活体请求元数据 |
| `scripts/` | 本次全部可复现脚本（缓存解码、签名验证、密钥流提取、AES 验证、PE 解析…） |
| 未随仓库发布 | 原始 bundle、存储/题库包/评测 XML 导出、反编译产物、壳层时间线等中间产物 |

---

## 三、目标识别（一句话画像）

| 项 | 值 |
|---|---|
| 产品 | 讯飞易听说「E听说」学生端 PC 版（CCS / iflytek） |
| 客户端 | **5.7.9**（`ETS.db` `C_Version`），更新号 5079，正式环境 |
| 壳 | `ETSShell.exe` 5.0.91.329 / **STIC V3.0.76**，源码残留 `<BUILD_ROOT>\STIC\stic-pro_ets\` |
| 内核 | CEF **91.1.22** / Chromium 91.0.4472.124 |
| 前端 | Vue3 + Element Plus + Pinia + Vue Router + axios，远程 `statics.ets100.com` |
| 原生 | 9 个 `.pln`（32 位 MSVC，无壳无混淆），统一 4 导出 ABI |
| 附属 | `ets_mq_server.exe`（Node SEA，WS 40001 日志总线）、`EtsUpdate.exe`、`bugreport.exe`、`ffmpeg/lame` |
| 数据 | SQLite、LevelDB(LocalStorage/IndexedDB)、Simple Cache、zip 资源包、mp3+spx+xml |

---

## 四、核心成果详解

### 4.1 签名算法（价值最高，已可复现）

```
sign = MD5( PID_PREFIX + time_ms + base64(JSON.stringify([{r,params}])) + KEY )
v2: PID_PREFIX="pcWin", KEY="94cfbda3fbfef02b93693f8bc153be82", 返回 {pid,key_id:"202608",sign_version:"2"}
v1: PID_PREFIX="grlx",  KEY="355ffbe95ccf4e9535a110170b445ab8"
```

- 由 `plugins\etshelper\etshelper.pln` 的 `OnEncodeAPIBody`（`0x1000a410`）实现；MD5 组装函数 `0x10014110`、密钥派生 `0x10013e00`/`0x10013d30`。
- 密钥不是明文常量：藏在 `.rdata` 的两张 4 字节表 + 32 个索引中，经"查表/旋转/减/XOR"派生，并用 FNV-1a 自校验（0x32A7B273 / 0xB9EF3CD1）。本报告用 PE 直接提取并重算，校验值完全一致。
- **333/334 真实请求命中**；唯一不中的是 `/user/login`（日志脱敏把 `password` 置空，签名原文不可见）。
- 参考实现与验证脚本：`data/api/ets_sign.py`、`scripts/sign_verify_all.py`。

### 4.2 字段级加密与内置私钥（安全问题）

- 前端 `encrypt$1`：**AES-128-ECB + PKCS7**，密钥硬编码 `k_serves="f05323cb91d422b2"`（上传）/ `k="ldlflfgirerjfkcf"`（本地）。
- 日志中 `phone`/`password` 密文用 `k_serves` 解密成功（3/3），格式为 Base64(16/32 字节)。
- `envConfig("RSA_PUBLIC_KEY")` 实际返回一段 **`BEGIN RSA PRIVATE KEY` PEM**，被 `rsaEncrypt()` 使用——客户端内置私钥。

### 4.3 前端全量提取

- 缓存格式：Chromium **blockfile**（index magic `0xC103CAC3`，块文件 `0xC104CAC3`，block size 从头部读取；EntryStore 字段偏移 + `addr>>28==8 → f_%06x` 外部文件）。
- 结果：353 条缓存条目 100% 还原；209 个资源落盘（139 个可读化）；91 条路由、20 个 Pinia store、118 个前端 API 端点、117 个原生 action。

### 4.4 题库内容包解密

- `content_<stid>.zip` 为 **ZipCrypto**，包尾 336 字节含 `MSTCHINA`/`1.0`/`pwd`/`EPLAT`/`keySerialNum`/`thisAnswer`；口令 = `MD5(pwd).upper() + MD5(MD5(pwd).upper()).upper()`（64 hex）。
- 24/24 content 包解密解包；结构 `content.json`/`content2.json`/`info.json`/`material`；三类题型 `collector.read/dialogue/picture` 字段表已还原。

### 4.5 日志总线（全部协议证据的来源）

- `mq_server\main.js`（144 行明文）：WS 服务 40001（占用则 +1 并写 `packages\app.json`），收到任意消息 → `log4js` 写 `logs\ets_YYYY-M-D.log` 并广播；连接回 `hello mq_server!`。
- 因此 `logs\ets_*.log` 保存了 **340 请求/341 响应/2026 条插件与业务日志**明文；这是本次协议还原的基础。

### 4.6 原生层

- 统一 ABI：每个 `.pln` 导出 `PlnInitiliaze`（厂商拼写）、`PlnOnProcessMessage`、`PlnSetParam`、`PlnUnInitialize`；`soundhelper` 额外 29 个 `snd*`（共 33 导出）。
- 装载：壳 `StiCorePlnManager` 用 `GetProcAddress` 取三个 Pln* 函数，并注入宿主回调 `LOG` / `WLOG` / `EXEC_CALLBACK`（`appcontroller::PlnSetParam` 中三个 `strcmp` 实证）。
- action 分发 = 字符串比较（action 名先做小写归一化）+ JSON 参数；所有 action 名可在二进制 `.rdata` + 前端 `action_keys.json` + 运行日志三方交叉验证。逐插件 action 数：filehelper 30、shellhelper 20、soundhelper 17、appcontroller 15、etshelper 12、httphelper 10、window_control 9、sqlitepln 6、sevenzip 2。
- `etshelper` 的 MD5 为**内联实现**（IV 表 RVA `0x6A540`，常量 0x67452301…），无 crypt32/OpenSSL 导入；签名前有本地限流闸门（1024 次 / 16 MB 上限 + 1000 ms 节流）。
- shell 注入 renderer 的 JS 桥共 17 个 native function，全文见 `壳注入 JS 桥全文（未随仓库发布）`。
- Ghidra 反编译产物（未随仓库发布）见 `09_decompiled.md`。

### 4.7 运行时验证（2026-11-06）

用户在分析副本上启动了真实实例（CDP 10086 开放）。通过 CDP + 在线 CDN 完成了静态阶段的补全：

- **在线前端全量 chunk**：下载 188 个 JS chunk（旧 routes 191 个中 186 个按基名映射成功，其余 5 个为 Vue SFC 虚拟模块名）；补齐 Word/PKMatch/readAloud/readSentence 等 14 个此前缺失模块 → 未知项 U1 解决。
- **在线版本与缓存版本**：主 bundle 同为 3,481,698 B，仅懒加载 chunk 哈希重新打包；签名密钥、AES 密钥、RSA 私钥、协议结构逐字一致。
- **活体协议验证**：新会话 72 请求/75 响应，带签名请求 **68/68** 命中 08 的公式；发现 4 条 GET 直连请求（token 在 query，无签名）。
- **插件 JS 封装层**：9 个通道、115 个 (plugin, action) 的权威清单，精确 pluginKey 为 `EtsHelper`/`FileHelper`/`HttpHelper`/`SevenZip`/`ShellHelper`/`SysConfig`（首字母大写）与 `appcontroller`/`soundhelper`/`sqlitepln`（小写）。
- **原生 oracle**：在真实页面直接调用 `EtsHelper.encode_api_body_v2`，原生返回的 sign 与 08 的公式**逐字节一致**（`data/api/sign_oracle.json`）；并对 `getpcinfo/getconfig/getvolume/checkadapter/getroomid/get_appdata_path/check_update` 等只读 action 做了运行时探针（参数 schema 与真实返回已记录）。
- **Frida 实机观测（2026-11-07）**：附着 CEF browser 进程，捕获 9 个插件的 `PlnOnProcessMessage` 分发（arg2=action、arg3=UTF-16 JSON），以及 `etshelper` 签名函数的真实入参；由此闭合**响应签名**公式 `MD5(pid + resp_b64 + KEY + sn)`（`6d3d8217…` 逐字节命中）。详见 `11_runtime_live.md` §十一。
- 详见 `11_runtime_live.md`。

### 4.8 源码仓库（GitHub）

本报告体系与脱敏后的机读样本发布在 GitHub 仓库 `hhz-or/ETS100-source`（不含原始日志、PII、大体积二进制/反编译产物）。

---

## 五、分层结论（摘要，细节见对应文档）

| 层 | 关键结论 | 详见 |
|---|---|---|
| 壳/进程 | `Ets.exe`(preshell) 读 shell.ini → `ShellExecuteExW` 拉起 ETSShell → CEF browser+GPU+utility+renderer；插件仅在 browser 进程加载；自定义 scheme `stic://`（shell/file/rpk/cpk/upk/wpk）；单实例互斥；清单要求管理员 | 02/07 |
| 前端 | 远程 SPA，本地缓存可得全量；API 统一信封 + v2 签名；117 action；录音→ISE 双通道评测→OSS 上传 | 04 |
| API/协议 | 51 条业务 API 路径 + 12 条非 api 端点；4 类凭证（登录 JWT / 资源平台 RS256 JWT / AI accessToken / 阿里云 STS）；AI 评测 `wss://oe-pub.eduaiplat.com` | 03 |
| 原生 | 9 插件能力面：etshelper 签名、httphelper HTTP/OSS、filehelper 文件/MD5、soundhelper 录音播放评测、sqlitepln、sevenzip、shellhelper 进程、window_control、appcontroller | 05/09 |
| 数据 | ETS.db 7 行配置；鉴权 token 在 IndexedDB `login.token`；LocalStorage 存 OSS STS/资源 token；Cookie 全 DPAPI 无身份 | 06 |
| 更新 | `EtsUpdate.exe` → `http://api.ets100.com` `r=client/mobile-update`，`pid=grlx` + base64 body；版本相等即"不需要更新"退出码 1；安装面含备份/复制/RunOnce/重启 | 07 |
| 音频 | record → `public_<32hex>_<ms>.mp3/.spx/.xml` 三件套；lame 3.100、ffmpeg 4.2；xml 为讯飞 ISE 评分（read_sentence/simple_expression_ufi/topic） | 06/07 |

---

## 六、统计一览

| 指标 | 数值 |
|---|---|
| 文件 / 体积 | 667 / 347.14 MB |
| 原生 PE（分析范围） | 14 个（壳/启动器/更新器/9 插件/崩溃器/mq_server SEA） |
| 历史日志 | 6 份（ets/cef/shell × 2），含 340 请求 + 341 响应 |
| API 路径（日志实测） | 51 条（+12 非 api 端点） |
| 前端路由 | 91 条（191 个懒加载 chunk 引用，缓存命中 69） |
| 前端 API 端点（bundle 内） | 118 个 |
| 原生 action | 115 静态 + 2 动态 = 117（9 个通道） |
| Pinia store | 20 个 |
| 缓存资源 | 353 条 / 209 文件（100% 还原） |
| 题库内容包 | 24 个（全解密）+ 模板包 3 份同 hash |
| 评测音频 | 36 组三件套 |
| 签名验证 | API 333/334 + 更新器 3/3 |
| **运行时（live 2026-11-06）** | 72 请求/75 响应；**活体签名 68/68**；在线 chunk **188 个**（覆盖 100%）；页面标题 E听说V5.7.9版 |
| Ghidra 反编译 | **9 个二进制、48,487 函数（31,141 已反编译，约 41 MB C 伪代码）**：ETSShell 5966/9109、EtsUpdate 7611/9646、shellhelper 8279/12320、filehelper 2738、appcontroller 2030、etshelper 1801、window_control 1630、sevenzip 1890、sqlitepln 1196 |

---

## 七、安全与合规

1. **客户端不具备真正的秘密**：签名密钥、AES 密钥、RSA 私钥都能从客户端提取——它们只能防"随手改包"。
2. **壳放宽了 Web 安全**：`ETSShell.exe` 启用 `ignore-certificate-errors` / `disable-web-security` / `allow-running-insecure-content`。
3. **完整性缺口**：9 个 `.pln` 插件**全部未签名**；壳 `ETSShell.exe` 的签名证书已于 2026-05-09 过期；`Ets.exe` 签名正常（iFLYTEK / GlobalSign R45）。
4. **日志总线暴露面**：`mq_server` 监听 `0.0.0.0:40001`、无鉴权、把含 STS 凭证/token 的日志广播给所有连接。
5. **无主动反调试**：仅 CRT `IsDebuggerPresent` 引用，未发现反 VM/反调试逻辑，逆向门槛低。
6. **隐私面大**：日志含真实学生/教师账号、手机号、密码密文、JWT、班级学校、过期 STS 凭证；本地有完整录音与评测结果。交付物已脱敏。
7. **合规红线**：本报告不提供绕过付费/考试/评分、伪造成绩、破解授权或批量刷课的方法；仅用于架构学习、互操作性研究、安全评估与自有环境排障。
8. 第三方软件逆向可能受 EULA/著作权约束，使用前请自行确认授权。

---

## 八、复现指南

```powershell
# 在仓库根目录执行；需要本地存在只读安装副本 <ETS_INSTALL_DIR> 时，
# 请把脚本顶部的输入路径常量指向该副本。

# 1) 重建 API 样本与签名验证（只读日志）
python scripts\extract_sign.py
python scripts\sign_verify_all.py      # 333/334

# 2) 提取缓存资源（只读缓存）
python scripts\work_frontend_scripts_1_parse_cache.py   # 其余前端脚本见 scripts/

# 3) 密钥流复算（只读 PE）
python scripts\keystream.py             # FNV MATCH

# 4) 字段加密验证（只读日志）
python scripts\aes_check.py

# 5) 题库包解密（只读 zip）
python scripts\work_data__scripts_extract_content.py
```

Ghidra 复跑：`-import <binary> -postScript DumpDecomp.java <outRoot>`（Ghidra 12.1.4 + JDK 21+；导出脚本未随仓库发布，可按 `09_decompiled.md` §7 的说明自行实现）。

---

## 九、结论

- **"看懂这个 App"**：已完成且证据闭环（架构、协议、前端、数据、更新、音频）。
- **"能自己造接口/复刻核心流程"**：客户端侧已具备条件——签名算法、字段加密、信封格式、鉴权链、OSS 直传均已还原并验证。
- **"全功能等价复刻"**：不建议；服务端业务逻辑（判分、题库下发、班级/作业规则）不在客户端，需要服务端授权与合作。

未解问题与后续验证建议见 [10_unknowns.md](10_unknowns.md)。

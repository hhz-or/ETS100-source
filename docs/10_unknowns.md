# 10 未知项、限制与后续验证

> **前置条件**：Windows 10/11 x64；Python 3.10+；可选 Node.js 18+（阅读/运行 `mq_server` 与前端 JS）；可选 7-Zip（解包 zip/7z）。
> **如何复现**：在仓库根目录执行 `python scripts/<脚本名>.py`；机读数据在 `data/`，运行时证据在 `runtime/`；分析对象为只读安装副本 `<ETS_INSTALL_DIR>`（全程不修改其中文件）。
> **占位符**：`<ETS_INSTALL_DIR>`=目标程序安装目录；`<APPDATA_ETS>`=`%APPDATA%\ETS`；`<WORK_DIR>`=原分析工作区；`<BUILD_ROOT>`=厂商构建机路径前缀（二进制/日志内嵌字符串原文，仅作证据）。
> **使用方法**：表中每条未知项都给出了可执行的验证路径；标注（未随仓库发布）的产物需从自有安装副本重建。

本报告的目标是"尽可能完整"，但静态分析有明确边界。以下按"影响大小"列出仍未解决的问题，并给出可执行的验证路径。

---

## 一、仍未覆盖的代码/数据

| # | 未知项 | 影响 | 现状与原因 | 建议验证 |
|---|---|---|---|---|
| U1 | 前端未缓存 chunk | 中 | **已解决（2026-11-06 运行时）**：在线 CDN 可直连，已下载全部 **188 个 chunk**（旧 routes 191 个中 186 个按基名映射成功，其余 5 个为 Vue SFC 虚拟模块名，内联在其它 chunk）；含此前缺失的 Word/PKMatch/readAloud 等 14 个模块。详见 `11_runtime_live.md` | —（`runtime/chunks_full/（未随仓库发布）`） |
| U2 | 服务端业务逻辑（判分、班级、作业下发规则） | 中 | 黑盒，仅见请求/响应 | 需授权账号做受控请求记录；本报告只还原客户端 |
| U3 | `encode_api_resp` 响应校验 | 低 | **已解决（2026-11-07）**：Frida 实机 hook + oracle 双重验证，v2 响应签名 = `MD5("pcWin" + base64(response) + KEY_V2 + sn)`（sn 观测为 `test`，逐字节命中）；前端无调用点，服务端响应校验未启用 | — |
| U4 | v1 签名路径（`pid=grlx`）的运行时样本 | 低 | 本安装全部走 v2；v1 仅代码路径存在 | 强制让 `encode_api_body_v2` 失败（如改插件）观察降级 |
| U5 | 更新器 `EtsUpdate.exe` 的下载包校验 | 中 | **签名已解决**：`MD5("grlx"+time秒+base64(body)+"555ffbe95ccf4e9535a110170b445ab8")`，3/3 真实样本命中（`08_signature.md` §五）；**仍未知**：下载的 exe/update.dat 是否做 MD5/数字签名校验 | 反编译 `EtsUpdate.exe` 的下载/安装分支（产物已有）；或触发一次真实更新观察 |
| U6 | `bugreport.exe` 上传地址/协议 | 低 | 二进制内无明文 URL（可能运行时拼接/加密） | 字符串+反编译；或断网抓包 |
| U7 | `stic://` 自定义 scheme 的完整 host→路径映射 | 低 | 已确认 `shell`/`file`/`rpk`/`cpk` 等 host 与 `file` 直接映射绝对路径；边界规则未全验证 | 反编译 `client_schema.cpp` 对应函数（ETSShell 反编译产物中） |
| U8 | `soundhelper` 33 个 `snd*` 导出语义 | 中 | 已从日志还原录音/播放/评测主流程；导出函数逐个语义未标注 | 反编译 + 日志行号交叉 |
| U9 | `.spx` 真实容器格式 | 低 | 16 组 `.mp3.spx` 熵≈7.97、无标准魔数、ffmpeg 不识别；推断 Speex 宽带裸流 | 用 Speex 解码器尝试；或对比 `hd_stic_record_enable_speex=1` 分支 |
| U10 | 前端 `RSA_PUBLIC_KEY`（实为私钥 PEM）的实际调用点 | 低-中 | 已定位常量与 `rsaEncrypt()`，未定位业务调用 | 搜索 `rsaEncrypt(` 调用点；或看某接口字段 |
| U11 | DPAPI 加密的 Cookie 值 | 低 | 11 条 Cookie 均为 v10(DPAPI)，脱离原用户不可解；且无身份 Cookie（登录态在 IndexedDB） | 非必要 |
| U12 | IndexedDB 的 dbid→存储名全量映射 | 低 | 200,945 条、13 存储；键前缀编码只解到部分 | 用 Chromium 源格式或浏览器打开 profile |
| U13 | 客户端是否启用完整性/反篡改校验 | 中 | 未发现主动反调试（`IsDebuggerPresent` 等为 CRT 引用）；未验证文件哈希校验/签名校验 | 修改副本中的插件/资源后启动观察；检查壳日志 |
| U14 | 壳的自动升级通道（`shell::upgrade` / `upgrade\UpdateProduct.exe` / `.upk`） | 低 | 仅字符串证据，本安装未触发 | 反编译 ETSShell 的 upgrade 函数 |
| U15 | `SQL\ETS.db.sql` 为 0 字节 | 低 | 原文件为空；已从 `EtsUpdate.exe` 内嵌 SQL 还原等价语句 | — |
| U16 | `temp\update\...\update.dat` 缺失 | 低 | 本副本未保留 | 触发一次真实更新后观察 |
| U17 | 127（旧评估）vs 117（本次）actionKey 差额 | 低 | 旧评估可能把重复/动态 action 计入；本次精确统计 115 静态 + 2 动态 = 117 | 对照 `data/frontend/action_keys.json` 与旧清单 |

---

## 二、方法学限制

1. **静态分析不建立运行时事实**。本报告引用的"运行时"信息来自目标自己写下的历史日志（`<ETS_INSTALL_DIR>\logs\*`）与本地缓存，**本次未执行目标程序**，也没有连接厂商服务器。
2. **网络不可达**：`api.ets100.com` / `statics.ets100.com` 在当前网络不可直连（分流到保留地址），因此无法在线复核服务端行为。
3. **历史日志的时间点**：2026-10-28 与 2026-11-04 两次会话；版本 5.7.9（2024-04 构建的客户端 + 2026 年在线前端）。前端可能已更新，而本地缓存是当时版本。
4. **重打包/完整性**：Ghidra 反编译产物是**分析辅助**，不是原始源码；函数名多为 `FUN_xxx`，变量名由反编译器生成。
5. **PII**：日志中含真实学生/教师账号、手机号、密码密文、JWT、过期 STS 凭证。本报告与所有产物均已脱敏；`data/api/sign_samples.json` 为签名验证保留了请求 `body` 的原文结构，其中敏感字段已替换为 `***`。

---

## 三、建议的后续验证（按性价比排序）

1. **动态复核签名（0.5 天）**：复制 `<ETS_INSTALL_DIR>\` 到隔离目录，用 Frida attach `ETSShell.exe`，hook `etshelper.pln!PlnOnProcessMessage`，打印 `encode_api_body_v2` 入参/出参，与本报告公式逐字节比对。
2. **补全前端（0.5 天）**：副本实例开放 CDP 10086，登录后遍历路由，导出全部 chunk（解决 U1）。
3. **完成原生反编译解读（1–2 天）**：ETSShell/EtsUpdate/httphelper/shellhelper/soundhelper 已/将反编译，逐插件整理 action 语义（解决 U5/U7/U8/U14）。
4. **更新器验证（0.5 天）**：改本地 `Update_Version` 制造"可更新"状态，观察下载/校验/安装与 `update.dat`（解决 U5/U16）。
5. **安全评估（1 天）**：验证是否存在完整性校验（U13）；评估内置 RSA 私钥（U10）与可提取签名密钥的实际风险面。

---

## 四、明确不做的范围

- 不提供绕过付费/考试/评分、伪造成绩、破解授权或批量刷课的方法。
- 不提供可直接对生产服务端发起写操作的脚本。
- 不公开未脱敏的账号凭证与个人信息。

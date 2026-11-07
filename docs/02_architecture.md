# 02 系统架构

> **前置条件**：Windows 10/11 x64；Python 3.10+；可选 Node.js 18+（阅读/运行 `mq_server` 与前端 JS）；可选 7-Zip（解包 zip/7z）。
> **如何复现**：在仓库根目录执行 `python scripts/<脚本名>.py`；机读数据在 `data/`，运行时证据在 `runtime/`；分析对象为只读安装副本 `<ETS_INSTALL_DIR>`（全程不修改其中文件）。
> **占位符**：`<ETS_INSTALL_DIR>`=目标程序安装目录；`<APPDATA_ETS>`=`%APPDATA%\ETS`；`<WORK_DIR>`=原分析工作区；`<BUILD_ROOT>`=厂商构建机路径前缀（二进制/日志内嵌字符串原文，仅作证据）。
> **相关脚本**：`scripts/` 下的日志/桥接分析脚本；本文结论以静态文件与历史日志为依据。

## 一、总体架构

```
┌───────────────────────────────────────────────────────────────────────────┐
│ L5 业务前端：Vue3 SPA（远程 https://statics.ets100.com/ets-student-pc-web/）│
│     Vue3 + Element Plus + Pinia + Vue Router + axios                      │
│     88+ 懒加载 chunk；业务逻辑 90% 在此                                      │
└───────────────┬───────────────────────────────────────────────────────────┘
                │ ① JS 桥：cef.message.sendMessage(uid, pluginKey, actionKey, args)
                │    回调：cef.message.setMessageCallback(uid, cb)
┌───────────────▼───────────────────────────────────────────────────────────┐
│ L4 壳：ETSShell.exe（STIC V3.0.76 / CEF 91.1.22，多进程）                    │
│     · CEF browser 进程内加载 STIC 核心：StiCore / StiCorePlnManager        │
│     · 自定义 scheme handler：rpk / cpk / upk / wpk（本地加密包协议）         │
│     · V8 扩展注入 cef.message / cef.fs（见 §四）                            │
│     · 插件加载与消息路由（PlnInitiliaze / PlnOnProcessMessage / ...）        │
└───────────────┬───────────────────────────────────────────────────────────┘
                │ ② 统一插件 ABI：4 个导出函数 + action 字符串分发
┌───────────────▼───────────────────────────────────────────────────────────┐
│ L3 原生插件：9 个 .pln（32 位 MSVC C++ / MFC+STL，未加壳）                    │
│  etshelper(API 签名)  httphelper(HTTP/OpenSSL)  filehelper(文件/MD5/OSS)    │
│  soundhelper(录音/播放/评测音频)  sqlitepln(SQLite)  sevenzip(7z)           │
│  shellhelper(进程/外壳)  window_control(窗口)  appcontroller(窗口 JS 容器)   │
└──────┬──────────────────────────────────────────┬─────────────────────────┘
       │ ③ HTTP(S)（明文 JSON + head.sign）        │ ④ 子进程 / 本地 IO
┌──────▼───────────────────────────┐   ┌──────────▼─────────────────────────┐
│ L2 服务端                        │   │ L2' 本地进程/文件                    │
│ api.ets100.com                   │   │ ets_mq_server.exe（Node.js SEA）     │
│ statics/cdnfei/ets60.ets100.com  │   │   └ WebSocket 40001（日志总线）       │
│ 阿里云 SLS（日志） / OSS（上传）   │   │ EtsUpdate.exe（更新）                │
└──────────────────────────────────┘   │ bugreport.exe / ffmpeg / lame       │
                                       └────────────────────────────────────┘
┌───────────────────────────────────────────────────────────────────────────┐
│ L1 本地数据：ETS.db(SQLite) · Cookies · LocalStorage/IndexedDB(LevelDB)     │
│     Chromium Simple Cache · temp/resources/*.zip · soundfiles/*.xml+mp3+spx │
└───────────────────────────────────────────────────────────────────────────┘
```

## 二、进程模型【观察】

来自 `logs\shell_2026-11-4.log`（GBK）中 `shell::main】processName:` 记录与 `logs\ets_*.log` 的 pid：

| 进程 | 数量 | 命令行特征 | 职责 |
|---|---|---|---|
| ETSShell.exe（browser） | 2（两次启动） | 无 `--type` 参数 | 主进程：CEF browser、插件宿主、窗口、scheme |
| ETSShell.exe（GPU） | 2 | `--type=gpu-process` | GPU 进程（配置了 `DisableGPU=1`，仍拉起） |
| ETSShell.exe（utility） | 5 | `--type=utility` | 工具进程（音频/网络等 Chromium utility） |
| ETSShell.exe（renderer） | 6 | `--type=renderer` | 渲染进程（每个页面/iframe 一个） |
| ets_mq_server.exe | 1 | Node.js SEA（12 MB） | WebSocket 日志总线，端口 40001 |

- 主进程 PID 10296、33796、2600、4320、26640…（日志内），进程名可通过 `OnProcessExist:ets_mq_server.exe` 与 `filehelper` stat 调用交叉验证。
- **插件只在 browser 进程加载**（`StiCorePlugin.log starting` × 9，紧跟在 browser 启动后）。
- `Temp\Cache_ETSShell\DevToolsActivePort` 内容为 `10086` + `/devtools/browser/<guid>`，说明该副本历史运行时开启过 **`--remote-debugging-port=10086`**（CEF 调试端口，可用于 CDP 挂载）。

## 三、启动链【观察 + 推断】

```
Ets.exe（"preshell"，<BUILD_ROOT>\STIC\preshell_2\Release\preshell.pdb）
  │ 读取 .\shell.ini（ShellConfig）
  │ 计算屏幕缩放 GetScreenScale device width=...（写 WindowScale）
  │ ShellExecuteExW → 拉起 shell.exe（ETSShell.exe）
  ▼
ETSShell.exe --shell-app-...（STIC 壳）
  │ StiAdapter::CreateMainBrowser → 创建浏览器主窗口
  │ StiAdapter::RunMessageLoop → CefMessageLoop
  │ StiCorePlnManager 加载 plugins\*\*.pln（9 个，各写一份 StiCorePlugin.log）
  │ 注册自定义 scheme（rpk/cpk/upk/wpk）
  │ 打开 shell.ini 的 HomeUrl（远程 SPA）
  ▼
CEF renderer 加载 https://statics.ets100.com/ets-student-pc-web/index.html
  │ 前端通过 cef.message.sendMessage 调用原生插件
  ▼
插件按需拉起：ets_mq_server.exe（shellhelper:startprocess）等
```

- `Ets.exe` 的关键字符串：`ShellConfig`、`.\shell.ini`、`ShellExecuteExW`、`GetScreenScale device width=`、`preshell.pdb`、`--shell-app-`、`no child process`/`no such process`。→ 它是"预启动器/DPI 适配器"，不是业务逻辑。
- `mq_server` 由 `shellhelper` 插件的 `startprocess` action 拉起：`shellhelper.cpp(32) action->startprocess`、`OnStartProcess reStart: true`、`OnProcessExist:ets_mq_server.exe`。

## 四、JS ↔ Native 桥

`ETSShell.exe` 内嵌一段 **2130 字节的 V8 扩展 JS**（提取件：`壳内嵌 JS 前导提取件（未随仓库发布）`），注册 `cef.message` 与 `cef.fs`：

```js
cef.message.sendMessage(uid, pluginKey, actionKey, args)   // 发消息（异步，结果走回调）
cef.message.setMessageCallback(uid, callback)              // 注册回调
cef.message.openFile(uid, pluginKey, actionKey, args)      // 打开文件对话框
cef.message.openFileCallback(uid, callback)
cef.message.removeMessageCallback(uid)
cef.message.createGuid()                                   // 生成 uid
cef.message.getExePath() / getAppConfig() / getHomeUrl()
cef.message.setRpkPwd(pwd) / setRpkInfo(path,code,salt) / setRpkInfoList(list)
cef.message.setCpkPwd(pwd)
cef.message.setProxy(server)
cef.message.setZoomLevel(val) / getZoomLevel()
cef.message.releaseAllDb3()
```

调用约定【观察 + 推断】：
1. JS 用 `createGuid()` 生成 `uid`，`setMessageCallback(uid, cb)` 注册回调，再 `sendMessage(uid, pluginKey, actionKey, args)`。
2. 原生 `StiCore::OnTaskAction` 依据 `pluginKey` 找到插件实例，调用其 `PlnOnProcessMessage(actionKey, args)`。
3. 插件异步完成后以 `uid` 回调 JS（回调数据即 `cb(data)`）。
4. 前端日志中可见的 action 形如：`encode_api_body_v2`、`encode_api_resp_v2`、`getmd5`、`execquery`/`execdml`、`downloadresource`、`checkvoice`、`combineandconvertwavtomp3`、`getuniqueid`、`startprocess`、`onprocessexist`、`stopprocess`、`existfileorfolder` 等（大小写混用）。

## 五、自定义 scheme（本地加密包）

`ETSShell.exe` 字符串：`rpk`/`cpk`/`upk`/`wpk` 相关 API 与域名：

| 名称 | 域名 | 用途 |
|---|---|---|
| `rpk` | `//rpk.iflytek.com/` | 资源包（Resource Package） |
| `cpk` | `//cpk.iflytek.com/` | 内容包（Content Package） |
| `upk` | `upk.client.iflytek.com` / `upk.monitor.iflytek.com` / `\packages\default.upk` / `\Modules\Default.upk` | 更新包/模块包（Update Package） |
| `wpk` | `test.wpk`、`GetFileContent_WPK fail:` | 加密资源包（WPK） |

相关类：`Sti::Adapter::ClientSchemeHandler`、`UTClientSchemeHandler`、`ClientSchemeHandlerFactory`、`UTClientSchemeHandlerFactory`；密码相关：`SetRpkPwd/setRpkPwd`、`SetCpkPwd/setCpkPwd`、`rpkPath/rpkUid/rpkSalt`。
→ 该安装形态**未实际使用**这些本地包（`packages\` 下只有明文 `app.json`/`appcontroller.js`；资源包在 `temp\resources` 以明文 zip 下发），但壳具备该能力。【观察 + 推断】

## 六、插件职责（9 个）

| 插件 | 文件大小 | 主要职责 | 依据 |
|---|---|---|---|
| `etshelper` | 497 KB | **API 签名/加密工具**：`encode_api_body_v2`、`encode_api_resp_v2`、`getmd5`、`getuniqueid` 等 | actionKey、`etshelper.cpp` 日志、`Head.sign` |
| `httphelper` | 1.73 MB | HTTP(S) 客户端：请求发送、下载、OSS 上传（含 OpenSSL） | `HttpProvider.cpp`、`httphelper.cpp` 日志、`downloadresource` |
| `filehelper` | 674 KB | 文件系统：存在性/读写/删除/拷贝、MD5、OSS 直传准备 | `filehelper.cpp`、`OnExistFileOrFolder` |
| `soundhelper` | 3.18 MB | 音频：录音、播放、WAV/MP3/SPEEX 转码、评测音频处理（导出 33 个 `snd*` 函数） | `sndUtilImpl.cpp`（8284 行日志）、`soundhelper.cpp`、`spxFile.cpp` |
| `sqlitepln` | 345 KB | SQLite 封装：`execQuery`/`execDML` | `sqlitepln.cpp`、`sqlite3.dll` |
| `sevenzip` | 467 KB | 7z 解压/压缩 | `sevenzip.cpp`、`7z.dll` |
| `shellhelper` | 2.12 MB | 进程/外壳：`startprocess`/`stopprocess`/`onprocessexist`、打开外部程序、注册表等 | `shellhelper.cpp`、`OnStartProcess` |
| `window_control` | 437 KB | 窗口控制（最大化/最小化/全屏/位置） | 插件名、`appcontroller.js` 回调 |
| `appcontroller` | 552 KB | JS 注入的窗口容器（`AppController` 类）与壳窗口交互 | `packages\default\appcontroller.js`、`appcontroller.cpp` |

插件日志源文件（`shell_*.log` 中出现次数）：`sndUtilImpl.cpp` 8284、`filehelper.cpp` 798、`HttpProvider.cpp` 738、`etshelper.cpp` 398、`GeneralImpl.cpp` 252、`httphelper.cpp` 226、`soundhelper.cpp` 159、`appcontroller.cpp` 97、`shell.cpp` 79、`spxFile.cpp` 72、`sevenzip.cpp` 68、`client_schema.cpp` 67、`shellhelper.cpp` 57、`StiCorePlugin.h` 45、`StiAdapter.cpp` 5、`shell_utils.cpp` 4、`sqlitepln.cpp` 4、`client_handler.cpp` 3、`UpdateAPI.cpp` 2。【观察】

## 七、数据流（一次 API 请求）

```
Vue 组件 → axios 封装（前端）
  → cef.message.sendMessage(uid, "etshelper", "encode_api_body_v2", {body, ...})
  → etshelper.pln 计算 head.sign（v2 协议，见 08_signature.md）
  → cef.message.sendMessage(uid2, "httphelper", "send", {url, body, ...})
  → httphelper.pln 发出 HTTPS 请求（api.ets100.com）
  → 响应回到 httphelper → 回调 JS
  → 前端解析 {msg, code, body}
  → 同时全链路日志经 WebSocket 40001 发到 mq_server → logs\ets_*.log
```

**日志总线**（`mq_server`）：`main.js` 144 行，明文 Node.js 源码：监听 40001（被占用则端口 +1，并写回 `packages\app.json` 的 `suspensionBallPort`），收到任意消息即 `log4js` 写入 `../logs/ets_YYYY-M-D.log` 并**广播给所有客户端**；连接建立时回发 `hello mq_server!`。这就是历史日志能完整保存请求/响应明文的原因；任何本地进程连上 40001 都可订阅到全部日志流量。【观察】

## 八、网络端点

| 域名 | 用途 | 证据 |
|---|---|---|
| `api.ets100.com` | 业务 API（HTTPS，42+ path） | `ets_*.log` 请求行 |
| `statics.ets100.com` | 前端 SPA 静态资源 | `shell.ini`、缓存 `IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb` |
| `cdnfei.ets100.com` | CDN 文件（安装包、PDF、视频、图片） | 系统配置返回的 URL |
| `ets60.ets100.com` / `ets60.oss-cn-hangzhou.aliyuncs.com` | OSS 桶 `ets60`（录音/文件上传） | 日志中 STS Token 与 OSS 配置 |
| `file.fei.ets100.com` | 网络测速 | `[MISC] 测试当前网络的 URL` |
| `*.log.aliyuncs.com`（SLS） | 阿里云日志服务（`ets-vpc-log` / `evaluation-sdk-log`） | 日志中 STS + logstore 配置 |

## 九、关键设计观察

1. **业务在云端**：真正的题库、评测、作业数据全部来自 API；本地只有缓存与模板。
2. **签名是唯一"信任锚"**：前端不掌握签名密钥，签名由 `etshelper.pln` 完成（详见 08）。
3. **插件即能力白名单**：前端只能调用插件暴露的 action，因此 action 清单等于"客户端能力面"。
4. **日志是全量"自白"**：mq_server 广播 + 明文落盘，等于给逆向者提供了完整协议抓包（本报告大量证据来源）。
5. **壳与业务解耦**：壳只负责窗口/CEF/插件/更新/自定义协议，换皮成本低。
6. **壳默认放宽 Web 安全**：`ETSShell.exe` 中可见 Chromium 开关 `ignore-certificate-errors`、`disable-web-security`、`allow-running-insecure-content` — 这是为兼容旧 HTTP 资源而保留的高风险配置。
7. **日志总线对外暴露**：`mq_server` 监听 `0.0.0.0:40001` 且**无鉴权**，任何同机或局域网客户端连上即可接收全部日志广播（日志中含 STS 凭证、token、账号信息）。
8. **签名/加密不构成安全边界**：签名密钥、AES 密钥、RSA 私钥均可从客户端提取（见 08）。

## 十、安全观察（汇总）

| 项 | 观察 | 影响 |
|---|---|---|
| 插件签名 | 9 个 `.pln` **全部未签名** | 可被同名替换（本地提权/注入面） |
| 壳签名 | `ETSShell.exe` 签名者 广州讯飞易听说（Sectigo R36），**证书 2026-05-09 已过期** | 证书链告警 |
| 启动器签名 | `Ets.exe` 签名者 iFLYTEK（GlobalSign R45） | 正常 |
| CEF 开关 | `ignore-certificate-errors` / `disable-web-security` / `allow-running-insecure-content` | 中间人/跨域风险 |
| mq_server | `0.0.0.0:40001` 无鉴权、日志全量广播 | 日志/凭证泄露面 |
| 前端内置密钥 | AES 密钥明文、RSA **私钥** PEM、签名密钥表 | 客户端秘密不可保护 |
| 反调试 | 未发现主动反调试（仅 CRT `IsDebuggerPresent`） | 逆向门槛低 |


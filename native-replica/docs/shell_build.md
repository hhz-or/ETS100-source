# Shell 构建与运行说明（native-replica/shell）

本文档对应 `native-replica/shell/**`（`EtsReplica.exe`，C++20 + Win32 + WebView2）。
内容：构建命令、实测结果、运行方式、shell.ini、各模块职责、已验证行为、已知限制。

---

## 1. 构建（Windows / MSVC 14.51 / CMake + Ninja）

> 注意：`C:\rea_tools\pylibs\bin\cmake.exe` 是不可用的 Python shim，
> 必须使用 `<CMAKE>`。
> `ninja` 用 WinGet Links 下的 `ninja.exe`（`Get-Command ninja`）。

```bat
:: 1) 配置（一次即可；CMakeLists.txt 由 Lead 维护，本目录不修改）
cmd /c "call \"<VS_BUILDTOOLS>\Common7\Tools\VsDevCmd.bat\" -arch=x64 >nul && ^
  \"<CMAKE>\" -S <REPO_ROOT>\native-replica -B <BUILD_DIR> -G Ninja ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_MAKE_PROGRAM=\"<NINJA>\""

:: 2) 只构建壳目标（插件由其他开发线实现，可能暂时编译失败，不影响壳验证）
cmd /c "call \"<VS_BUILDTOOLS>\Common7\Tools\VsDevCmd.bat\" -arch=x64 >nul && ^
  \"<CMAKE>\" --build <BUILD_DIR> --target EtsReplica --parallel"
```

PowerShell 等价写法：

```powershell
$vs    = '<VS_BUILDTOOLS>\Common7\Tools\VsDevCmd.bat'
$cmake = '<CMAKE>'
$ninja = '<NINJA>'
cmd /c "call `"$vs`" -arch=x64 >nul && `"$cmake`" -S <REPO_ROOT>\native-replica -B <BUILD_DIR> -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM=`"$ninja`""
cmd /c "call `"$vs`" -arch=x64 >nul && `"$cmake`" --build <BUILD_DIR> --target EtsReplica --parallel"
```

### 实测结果（2026-11-07）

- 配置：`-- Configuring done` / `-- Generating done`，`WEBVIEW2_SDK=<WEBVIEW2_SDK>`。
- 构建：`--target EtsReplica --parallel` 退出码 **0**；7 个 TU（config/main/core_api/bridge/
  plugin_manager/media_server/ws_log）全部重新编译、链接成功，shell 源文件 **0 error / 0 warning**。
- 产物：`<BUILD_DIR>\bin\EtsReplica.exe`（约 352 KB，静态链接 WebView2LoaderStatic，无额外 DLL 依赖）。
- 工具链：MSVC 19.51.36260 x64（VS 18 BuildTools），CMake ≥3.25，Ninja。
- 编译选项由根 `CMakeLists.txt` 统一提供：`/utf-8 /W3`、`UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN`。

---

## 2. 运行

```powershell
<BUILD_DIR>\bin\EtsReplica.exe
```

运行时期望的目录布局（`build.ps1` 负责生成 assets/web、plugins/、mq_server/）：

```
<BUILD_DIR>\bin\
├─ EtsReplica.exe
├─ shell.ini                 # 可选，见 §3
├─ assets\web\index.html     # 前端构建产物（虚拟主机 https://app.ets.local/）
├─ plugins\etshelper\etshelper.dll
├─ plugins\filehelper\filehelper.dll
├─ plugins\httphelper\httphelper.dll
├─ plugins\sqlitepln\sqlitepln.dll
├─ plugins\shellhelper\shellhelper.dll
├─ plugins\sevenzip\sevenzip.dll
├─ plugins\sysconfig\sysconfig.dll
└─ mq_server\main.js         # Node 日志中间件（缺失则跳过 node 子进程）
```

数据目录（默认 `%APPDATA%\ETS-Replica`）：

```
%APPDATA%\ETS-Replica\
├─ WebView2\            # WebView2 user data
├─ cache\               # 媒体缓存根目录（media_server 只服务此目录下文件）
└─ logs\
   ├─ ets_YYYY-M-D.log   # 协议/插件日志（WS 不可用时本地降级；WS 可用时由 mq_server 落盘）
   └─ shell_YYYY-M-D.log # 壳自身诊断日志
```

---

## 3. shell.ini

放在 exe 同目录，缺失即用默认值；支持 `#`、`;` 注释与 `[section]`（忽略），键名不区分大小写，
值两侧空白与成对引号会被去掉，`%VAR%` 会展开。

| 键 | 默认值 | 说明 |
|---|---|---|
| `AppName` | `E听说 · 复刻版` | 窗口标题（UTF-8） |
| `HomeUrl` | 空 | 远程页面地址；非空且 host 不是 `app.ets.local` 时直接导航到该 URL（可用于 Vite dev server），否则加载虚拟主机页面 |
| `WindowWidth` / `WindowHeight` | 1280 / 800 | 窗口初始尺寸（clamp 到屏幕范围） |
| `DataDir` | `%APPDATA%\ETS-Replica` | 数据根目录；相对路径相对 exe 目录解析 |
| `LogLevel` | 1 | 0 DEBUG / 1 INFO / 2 WARN / 3 ERROR |

示例：

```ini
AppName=E听说 · 复刻版
# HomeUrl=http://127.0.0.1:5173/
WindowWidth=1440
WindowHeight=900
LogLevel=1
```

---

## 4. 模块与职责（shell/）

| 文件 | 职责 |
|---|---|
| `main.cpp` | Win32 窗口 + WebView2 环境/控制器创建、虚拟主机映射、注入 JS shim、`WM_APP+1` 回调分发、生命周期与退出 |
| `bridge.h/.cpp` | 解析页面消息 `{uid,plugin,action,args}`；`__core` 直接处理；其余交给 PluginManager 在工作线程调用；回调统一经 `PostMessage` 回到 UI 线程再 `PostWebMessageAsJson` |
| `plugin_manager.h/.cpp` | 扫描 `plugins/<name>/<name>.dll`（大小写不敏感）、`LoadLibrary` + 4 个导出、构造 `PlnHost`、`PlnSetParam("LOG"/"WLOG")`、退出时 `PlnUnInitialize` + `FreeLibrary`；每插件互斥串行、回调 uid 路由 |
| `config.h/.cpp` | `shell.ini` 解析、目录解析与创建、本地/远程 HomeUrl 判定 |
| `core_api.h/.cpp` | `__core` 动作 `info` / `media_url` / `log` / `open_external`（JS 桥与插件 `PlnHost::Exec` 共用） |
| `media_server.h/.cpp` | Winsock 本地 HTTP：`127.0.0.1:<random>`，`GET /media?p=<urlencoded 相对 CacheDir 路径>`，路径越界拦截、按扩展名 Content-Type、单区间 Range/206、`/health` |
| `ws_log.h/.cpp` | `CreateProcessW node mq_server/main.js`（cwd=exeDir，缺 node/main.js 则跳过）；WinHTTP WebSocket 连 `ws://127.0.0.1:40001`（10 次 ×300ms），日志 JSON 行上报；失败降级本地 `logs/ets_YYYY-M-D.log`；同时写 `logs/shell_YYYY-M-D.log` |

### 关键实现说明

- **JS shim**：`AddScriptToExecuteOnDocumentCreated` 注入 CONTRACT §4 的 `window.cef.message`
  （`sendMessage/setMessageCallback/removeMessageCallback/createGuid` + 兼容空实现），
  `createGuid` 优先 `crypto.randomUUID()`，回退 UUID v4 模板；`chrome.webview` 消息回调按 `uid →
  CEF_CB[uid]` 路由。
- **线程模型**：UI 线程独占 WebView2 COM；插件调用在 `std::thread(detach)` 中执行并在每插件互斥下串行；
  插件回调（任意线程）→ `PostMessage(WM_APP+1)` → UI 线程 `PostWebMessageAsJson('{"type":"callback","uid","data"}')`。
  回调按 uid 一次性消费（先摘除再调用），重复/未知 uid 记 WARN 丢弃。
- **退出顺序**：`WM_CLOSE` 销毁窗口 → 消息循环结束后：detach bridge → 移除事件 handler → `controller->Close()`
  → 释放 webview/controller/environment → 插件 `PlnUnInitialize`+`FreeLibrary` → 停媒体服务 → 停止 WS/日志 →
  终止 node 子进程。实测退出码 0。
- **路径安全**：`media_server` 同时做 `..`/`:` 组件拒绝与 `weakly_canonical` 前缀校验，越界返回 403；
  实测 `..\..\windows\win.ini` → **403**。

---

## 5. 已验证行为（本机实测）

| 项目 | 结果 |
|---|---|
| 编译 `--target EtsReplica` | 退出码 0，0 error / 0 warning（shell 源） |
| 启动 / 窗口标题 | 窗口正常显示，标题 `E听说 · 复刻版`（来自默认 AppName） |
| WebView2 初始化 + 虚拟主机 | `CreateCoreWebView2Environment` → controller → `https://app.ets.local/index.html` 导航 `hr=0` |
| 插件装载 | 8/8 全部 LoadLibrary + PlnInitiliaze 成功（日志 `loaded plugin keys: ...`） |
| JS↔宿主 `__core` | `info` / `media_url` / `log` 全部回调正确（页面 selftest 回写日志验证） |
| JS↔插件 | `ShellHelper.getconfig`、`EtsHelper.get_appdata_path`、`FileHelper.existfileorfolder` 在工作线程执行并正确回调 |
| 媒体服务 | `GET /media?p=probe.txt` → 200 正文一致；`Range: bytes=0-4` → 206 + `Content-Range: bytes 0-4/13`；越界路径 → 403；`/health` → 200 |
| WS 日志 | 连接 `ws://127.0.0.1:40001` 成功；连接前日志按 `[ts] [LEVEL] mq_server - received: <json>` 落本地 `ets_*.log` |
| node 子进程 | `bin\mq_server\main.js` 存在时成功 `CreateProcessW` 启动（日志记录 pid），退出时终止、无残留 |
| 优雅退出 | `CloseMainWindow` → 退出码 `0x00000000`，`shutdown complete` 落盘，无 WER 崩溃事件 |

> 说明：若 `assets\web\index.html` 尚未构建，导航会记录 `navigation completed with error status=9`
> （虚拟主机 404），属预期；前端产物就位后即消失。

---

## 6. 已知限制 / 注意事项

1. **WebView2 控制器是借用引用（本机运行时实测）**：`CreateCoreWebView2Controller` 回调收到的
   `ICoreWebView2Controller*` 在回调返回后会被运行时销毁，必须 `AddRef()` 保留（否则退出时
   `Close()` 访问悬空指针导致 0xC0000005）。`shell/main.cpp` 已按此处理并注释说明。
2. **插件由其他开发线实现**：DLL 缺失/导出不全时壳不崩溃，装载失败记 WARN，JS 调用返回
   `{"code":-1,"msg":"plugin not loaded: <key>"}`；插件在 worker 中抛异常时返回
   `{"code":-1,"msg":"plugin exception"}`。插件回调若超过 5s 未返回，退出时等待超时会记 WARN 并继续卸载。
3. **WS 端口固定 40001**：按要求 10 次 ×300ms 重试，不读取 mq_server `app.json` 的端口递增结果；
   若 40001 被占用且 mq_server 改端口，则壳降级为仅本地日志（不影响功能）。
4. **本机未发现 `mq_server/main.js` 时不启动 node 子进程**，仅做 WS 连接重试；缺失/失败都只降级日志，不崩溃。
5. **`__core/log` 级别映射**：`0 debug / 1 info / 2 warn / ≥3 error`（也接受 `"debug"|"info"|"warn"|"error"` 字符串）。
6. **`open_external`** 仅允许 `http(s)://` / `mailto:`，通过 `ShellExecuteW("open")` 交给系统浏览器；
   页面内 `target=_blank`/`window.open` 走同一逻辑。
7. **JS shim 的 `getExePath()/getAppConfig()/getHomeUrl()`** 按 CONTRACT §4 返回 `""`/`"{}"`/`""`
   （异步协议下无法同步取值；需要真实信息时用 `__core.info` 异步获取）。
8. **媒体服务**：只读、仅监听 loopback、无鉴权（本机进程即信任边界）；支持单区间 Range，多区间按 200 全量返回；
   大文件按 64KB 流式发送；不支持目录列表。
9. **远程 HomeUrl**（如 Vite dev server）下页面来源不再是 `app.ets.local`，媒体 URL 仍是
   `http://127.0.0.1:<port>`；Chromium 将 loopback 视为可信来源，`<audio>/<img>` 不受混合内容阻断。
10. 本目录未修改 `shared/`、`plugins/`、`frontend/`、`mq_server/`、`CMakeLists.txt`、`build.ps1`
    （如需 `/MAP`、`/utf-8` 等编译选项由 Lead 在根 CMakeLists 统一处理）。

---

## 7. 排查

- 启动即弹「WebView2 运行时初始化失败」：确认已安装 Microsoft Edge WebView2 Runtime
  （本机 156/157 可用），或检查 `%APPDATA%\ETS-Replica\WebView2` 是否可写。
- 页面空白/导航 status=9：`bin\assets\web\index.html` 未构建；先跑前端构建或 `build.ps1`。
- 插件调用返回 `plugin not loaded`：检查 `bin\plugins\<name>\<name>.dll` 是否存在且导出
  `PlnInitiliaze/PlnOnProcessMessage`（DLL 名与目录名大小写不敏感）。
- 日志：先看 `%APPDATA%\ETS-Replica\logs\shell_YYYY-M-D.log`；协议/插件日志看
  `ets_YYYY-M-D.log`（WS 已连时由 mq_server 落盘，因此该文件可能只包含启动初期行）。

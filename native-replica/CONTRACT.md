# ETS 原生复刻 · 架构与接口契约（v1）

> 目标：用**与原作相同的分层架构**（嵌入式 Chromium 壳 + 插件 DLL + Web 前端 + Node 日志中间件）复刻 ETS 客户端；
> 语言/框架/库允许使用本机或现代版本：**C++20 + MSVC 14.51 + WebView2（现代 Chromium）** 替代 CEF 91；
> 前端 **Vue3 + Element Plus + Vite + Pinia + Router**；中间件 **Node 24 + ws**。
> Python 版 `reimpl/` 保留，用于逻辑/架构研究与文档。

## 1. 总体架构

```
┌────────────────────────────────────────────────────────────────────┐
│ Frontend (Vue3 SPA, 构建产物 assets/web)                            │
│  通过注入的 window.cef.message.* 调用原生（与原作同名 API）          │
└───────────────┬────────────────────────────────────────────────────┘
                │ chrome.webview.postMessage JSON
┌───────────────▼────────────────────────────────────────────────────┐
│ EtsReplica.exe (C++20, Win32 + WebView2)                            │
│  · Bridge：JS→host→plugin；plugin 回调→host→JS                      │
│  · PluginManager：LoadLibrary + 4 个导出（PlnInitiliaze 等）        │
│  · 内置 pluginKey="__core"：media_url / log / open_external / info  │
│  · 本地媒体 HTTP 服务（127.0.0.1:随机端口）→ 供 <audio>/<img> 使用  │
│  · 日志：WinHTTP WebSocket → mq_server:40001 + 本地 logs/*.log      │
│  · 启动子进程：node mq_server/main.js；WebView2 虚拟主机映射前端     │
└───────┬────────────────────────────────┬───────────────────────────┘
        │ 4 导出 ABI                      │ ws://127.0.0.1:40001
┌───────▼──────────────────────┐  ┌──────▼───────────────────────────┐
│ plugins/<小写插件名>/<小写插件名>.dll（EtsHelper→etshelper、FileHelper→filehelper、HttpHelper→httphelper、SQLitePln→sqlitepln、ShellHelper→shellhelper、SevenZip→sevenzip、SysConfig→sysconfig）     │  │ mq_server (Node 24 + ws)         │
│  EtsHelper/FileHelper/        │  │  端口探测、日志落盘、广播          │
│  HttpHelper/SQLitePln/        │  └──────────────────────────────────┘
│  ShellHelper/SevenZip/SysConfig│
└──────────────────────────────┘
```

## 2. 目录

```
native-replica/
├─ CMakeLists.txt
├─ build.ps1                # 一键构建（MSVC + CMake/Ninja + 前端构建）
├─ CONTRACT.md              # 本文件
├─ third_party/             # json.hpp / miniz.c/h / sqlite3.c/h（vendored）
├─ shared/
│  ├─ stic_plugin.h         # 插件 ABI（4 导出 + 宿主回调结构）
│  └─ common.h/.cpp         # JSON、UTF-8/宽字符、日志、base64、文件工具
├─ shell/                   # C++ 壳（exe）
│  ├─ main.cpp              # Win32 窗口 + WebView2 + 虚拟主机 + 消息循环
│  ├─ bridge.h/.cpp         # JS<->host<->plugin 消息路由
│  ├─ plugin_manager.h/.cpp # 插件装载/映射/卸载
│  ├─ config.h/.cpp         # shell.ini
│  ├─ media_server.h/.cpp   # 本地媒体 HTTP 服务
│  └─ ws_log.h/.cpp         # WinHTTP WebSocket 日志客户端（连 mq_server）
├─ plugins/<Name>/          # 各插件 DLL（实现 4 导出）
├─ frontend/                # Vue3 源码（Vite 构建到 assets/web）
├─ mq_server/               # Node 日志中间件（main.js + package.json）
├─ assets/web/              # 前端构建产物（由 build.ps1 复制）
└─ docs/                    # 复刻说明（架构映射、构建、运行、能力矩阵）
```

## 3. 插件 ABI（必须逐字实现）

`shared/stic_plugin.h`：

```cpp
typedef void (__stdcall *PLN_CALLBACK)(const char* uid, const char* data); // data=JSON 结果字符串
typedef void (__stdcall *PLN_LOG)(int level, const char* msg);
typedef void (__stdcall *PLN_EXEC)(const char* action, const char* args, PLN_CALLBACK cb, const char* uid);
typedef struct PlnHost {
  unsigned int size;
  PLN_LOG Log;          // 普通日志
  PLN_LOG WLog;         // 警告/错误日志
  PLN_EXEC Exec;        // 请求宿主内置能力（如 media_url）
  const char* AppDir;   // exe 所在目录（UTF-8）
  const char* DataDir;  // %APPDATA%/ETS-Replica
  const char* CacheDir; // DataDir/cache
  const char* HomeUrl;  // shell.ini 的 HomeUrl
} PlnHost;
extern "C" {
  __declspec(dllexport) void PlnInitiliaze(PlnHost* host);   // 注意原版拼写
  __declspec(dllexport) void PlnSetParam(const char* key, void* fn);
  __declspec(dllexport) void PlnOnProcessMessage(const char* action, const char* argsJson, PLN_CALLBACK cb, const char* uid);
  __declspec(dllexport) void PlnUnInitialize(void);
}
```

约定：
- 字符串一律 **UTF-8**；JSON 用 `nlohmann::json`（`third_party/include/json.hpp`）。
- `PlnOnProcessMessage` 可能在**工作线程**执行；完成后必须调用 `cb(uid, resultJson)` **恰好一次**（成功/失败都返回 JSON，失败用 `{"code":-1,"msg":"..."}`）。
- 参数为空时 `argsJson` 可能是 `""` 或 `"{}"`。
- 插件不得阻塞超过数秒；耗时操作自行开线程（也可以同步，由壳在 worker 调用）。

宿主注入回调（`PlnSetParam`）：`"LOG"`、`"WLOG"` 两个 `PLN_LOG`，用于统一日志。`"EXEC_CALLBACK"` 可选。

## 4. JS ↔ Host 桥

壳在页面创建时注入（`AddScriptToExecuteOnDocumentCreated`）：

```js
window.cef = window.cef || {};
cef.message = {
  sendMessage(uid, pluginKey, actionKey, args) {
    chrome.webview.postMessage(JSON.stringify({uid, plugin: pluginKey, action: actionKey, args: args ?? ""}));
  },
  setMessageCallback(uid, cb) { CEF_CB[uid] = cb; },
  removeMessageCallback(uid) { delete CEF_CB[uid]; },
  createGuid() { /* uuid v4 */ },
  getExePath() { return ""; }, getAppConfig() { return "{}"; }, getHomeUrl() { return ""; },
  openFile(){}, openFileCallback(){}, setRpkPwd(){}, setRpkInfo(){}, setRpkInfoList(){},
  releaseAllDb3(){}, setZoomLevel(){}, getZoomLevel(){}, setCpkPwd(){}, setProxy(){}
};
window.chrome.webview.addEventListener('message', ev => {
  const m = typeof ev.data === 'string' ? JSON.parse(ev.data) : ev.data;
  if (m.type === 'callback') { const cb = CEF_CB[m.uid]; if (cb) cb(m.data); }
});
```

- 页面→壳：`{"uid","plugin","action","args"}`（字符串 JSON）。
- 壳→页面：`{"type":"callback","uid","data"}`；`data` 为插件返回的 JSON 字符串。
- `createGuid()` 返回值必须唯一（壳不参与）。
- 兼容原版语义：`uid` 由前端生成，回调按 `uid` 路由；前端可自行加 `@suffix`。

## 5. 内置 pluginKey `__core`

| action | args | 返回 |
|---|---|---|
| `info` | `{}` | `{"appDir","dataDir","cacheDir","homeUrl","version"}` |
| `media_url` | `{"path":"<绝对或相对 cache 路径>"}` | `{"url":"http://127.0.0.1:<port>/media?p=<urlencoded rel>"}` |
| `log` | `{"level":1,"tag":"...","msg":"..."}` | `{"ok":true}` |
| `open_external` | `{"url":"https://..."}` | `{"ok":true}` |

## 6. 插件与 action 清单（最小对等集）

pluginKey → DLL：`EtsHelper`→etshelper、`FileHelper`→filehelper、`HttpHelper`→httphelper、`SQLitePln`→sqlitepln（前端用小写 `sqlitepln` 也可，壳映射不区分大小写）、`ShellHelper`→shellhelper、`SevenZip`→sevenzip、`SysConfig`→sysconfig。

### EtsHelper（C++，BCrypt）
| action | args | 返回 |
|---|---|---|
| `encode_api_body_v2` | `{"body":"<base64>","time":"<ms>"}` | `{"pid":"pcWin","key_id":"202608","sign":"<md5hex>","sign_version":"2"}`；签名=`MD5("pcWin"+time+body+KEY_V2)` |
| `encode_api_body` | 同上 | `"<md5hex>"`（v1：`grlx`+KEY_V1） |
| `encode_api_resp_v2` | `{"response":"<base64>","time":"..."}` | `{"pid","key_id","sign","sign_version"}`；`MD5("pcWin"+response+KEY_V2+"test")` |
| `aes_ecb_encrypt` | `{"plain":"..."}` | `{"b64":"..."}`（AES-128-ECB/PKCS7，KEY=k_serves=`f05323cb91d422b2`） |
| `aes_ecb_decrypt` | `{"b64":"..."}` | `{"plain":"..."}` |
| `get_appdata_path` | `""` | `"%APPDATA%"`（纯字符串 JSON 或文本均可，前端兼容） |
| `log_data` | `{"tag","msg"}` | `{"ok":true}` |
| `check_update` | `""` | `{"rncode":0,"rnmsg":"no newer version"}`（复刻桩） |

KEY_V2=`94cfbda3fbfef02b93693f8bc153be82`；KEY_V1=`355ffbe95ccf4e9535a110170b445ab8`；k_serves=`f05323cb91d422b2`。

### HttpHelper（WinHTTP）
- `request`：`{"url","method":"GET|POST","body":"<string>","headers":{...},"timeoutMs":30000}` → `{"status":200,"body":"<text>","headers":{...}}`
- `download`：`{"url","filePath":"<abs>"}` → `{"code":0,"filePath","size"}`
- `upload`、`downloadresource`、`downloadsdk`、`monitornetspeed`、`isrpkexist`、`stopdownload`：返回未实现 JSON。

### FileHelper
- `readfile` `{"filePath"}` → `{"content":"..."}`
- `readbinaryfile` `{"filePath"}` → `{"base64":"..."}`
- `writefile` `{"filePath","content"}` → `{"code":0}`
- `writefilewithbinary` `{"filePath","base64"}` → `{"code":0}`
- `existfileorfolder` `{"filePath"}` → `{"result":true,"size":123}`
- `deletefileordirectory` `{"filePath"}` → `{"code":0}`
- `createfolder` `{"filePath"}` / `copyfileordirectory` `{"src","dst"}` / `removefiletootherpath` `{"src","dst"}` → `{"code":0}`
- `getmd5` `{"filePath"}` → `{"md5":"..."}`
- `getbase64` `{"filePath"}` → `{"base64":"..."}`
- `getfoledersize` `{"filePath"}` → `{"errorCode":0,"errorMsg":"get dir size ok","size":N}`
- 其它（对话框等）返回未实现。

### SQLitePln（sqlite3 amalgamation）
- `connect` `{"dbPath"}` → `{"code":0}`
- `execQuery` `{"dbPath","sql","params":[]}` → `{"rows":[{...}]}`
- `execDML` `{"dbPath","sql","params":[]}` → `{"changes":N}`
- `disconnect` `{}` → `{"code":0}`

### ShellHelper
- `getpcinfo` → 设备信息 JSON（字段可简化：AppTitle/ClientType/CopyRight/Name/computername/OsBit/SystemVersion/ProcessName/DwNum/HDD/IP2/Version…）
- `getconfig` → 壳配置 JSON
- `getvolume`/`setvolume` `{"volume":0-100}`
- `checkadapter` → `{"rncode":1,"rnmsg":"网卡正常."}`
- `getuniqueid` → `{"id":"..."}`（MachineGuid 的 SHA1 或 MAC 派生）
- `startprocess`/`stopprocess`/`processexist` `{"process_list":[...]}` / `{"name":"..."}`
- `cmd`/`gettoken`/`initActAuth` 等返回未实现。

### SevenZip（miniz + ZipCrypto）
- `unzip` `{"zipPath","outDir"}` → `{"code":0,"files":N}`；支持 ZipCrypto（口令推导：包尾 336B `MSTCHINA/EPLAT` → `MD5(MD5(pwd))` 64位大写 hex，见 docs/06_data.md §4.2）
- `zip`/`test` 可简化/未实现。

### SysConfig
- `init` → `{"ok":true}`（桩）

## 7. 前端要求

- Vue3 + `<script setup>` + Vite + Pinia + Vue Router + Element Plus。
- 页面：登录、首页（三卡+模块卡）、作业列表/详情、套卷列表、同步课程、练习页（read/dialogue/picture + 音频）、错题本、设置/关于。
- API 层：`sendMessage` 封装（Promise + uid）；登录流程严格按：
  `aes_ecb_encrypt(phone/password)` → 组 `[{r,params}]` → `btoa` UTF-8 base64 → `EtsHelper.encode_api_body_v2` → `HttpHelper.request` `https://api.ets100.com/<r>`（body=`{"body":b64,"head":{...}}`）。
- 内容：`HttpHelper.download` → `SevenZip.unzip` → `FileHelper.readfile` 读取 `content.json`；音频路径经 `__core.media_url` 转 url。
- 样式参考原作（左侧导航/顶栏/卡片），不要求像素级一致。
- 构建命令：`pnpm install && pnpm build`（Vite 输出 dist/）。

## 8. mq_server（Node 24 + ws）

- `main.js`：尝试 40001 起 WebSocket；端口占用则 +1；收到消息写 `logs/ets_YYYY-M-D.log` 并广播；连接回 `hello mq_server!`；端口写 `app.json`。
- 壳启动时 `CreateProcessW node mq_server/main.js`，并连 `ws://127.0.0.1:40001` 上报日志。

## 9. 构建

`build.ps1` 流程：
1. `call "<VS>\Common7\Tools\VsDevCmd.bat" -arch=x64`
2. `cmake -S . -B <BUILD_DIR> -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM=<NINJA>`
3. `cmake --build <BUILD_DIR>`
4. `pnpm -C frontend install` + `pnpm -C frontend build`
5. 复制 `frontend/dist` → `assets/web`；插件 DLL → `plugins/<Name>/`
6. 产物：`<BUILD_DIR>\bin\EtsReplica.exe`

## 10. 约束

- 不修改 `ETS/`、`docs/`、`publish/`、`repo/`、`reimpl/`、`work/`。
- 凭据只从 `<WORK_DIR>/secrets/account.json` 读取，不得写入源码/提交（前端只输入，不硬编码）。
- 第三方库已 vendored：`third_party/`（json.hpp、miniz、sqlite3）。
- 未实现能力必须显式返回 `{"code":-2,"msg":"not implemented"}` 或 UI 标注，不伪造。


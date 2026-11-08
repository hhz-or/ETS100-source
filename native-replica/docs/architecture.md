# 原生复刻版（native-replica）· 架构说明

> 本目录是「E听说 PC 学生端」的**同架构复刻**：嵌入式浏览器壳 + 插件 DLL + Web 前端 + Node 日志中间件。
> 与原作的区别仅在于**具体技术选型使用本机可用的现代版本**：
>
> | 层 | 原作（5.7.9） | 本复刻 |
> |---|---|---|
> | 浏览器壳 | CEF 91 + STIC V3.0.76 壳 | **WebView2（现代 Chromium，Windows 内建运行时）** |
> | 原生语言/编译器 | C++/MSVC（VS2019 时代） | **C++20 / MSVC 14.51（VS2026 BuildTools）** |
> | 插件机制 | 9 个 `.pln` DLL + 4 导出 ABI | 同样 4 导出 ABI（`PlnInitiliaze/PlnSetParam/PlnOnProcessMessage/PlnUnInitialize`），8 个插件 DLL（7 业务 + `soundhelper`） |
> | 前端 | Vue3 + Element Plus + Pinia + Router（远程 SPA） | **Vue3 + Element Plus + Pinia + Vue Router + Vite（本地打包）** |
> | 日志中间件 | `mq_server`（Node + ws，40001） | **Node 24 + ws，40001** |
> | JS↔Native 桥 | `cef.message.sendMessage/setMessageCallback` | 同名 API（`window.cef.message` shim），底层走 WebView2 `postMessage` |
> | 签名/加密 | 原生插件 + 内嵌密钥流 | 同算法，C++（BCrypt）实现 |
> | 题库包 | ZipCrypto + 7z | 同格式，miniz + ZipCrypto 实现 |

保留 `reimpl/`（Python 版）作为**逻辑/协议研究参考**：它把签名、API、解包、页面数据流都实现了一遍，便于对照阅读；原生版负责验证"同架构也能跑"。

## 1. 分层

```
┌──────────────────────────────────────────────────────────────────┐
│ frontend/  Vue3 SPA（Vite 构建 → assets/web）                     │
│   src/bridge.js   window.cef.message.*（与原作同名）               │
│   src/api.js      登录/只读接口（aes→btoa→encode_api_body_v2→http）│
└──────────────┬───────────────────────────────────────────────────┘
               │ chrome.webview.postMessage(JSON)
┌──────────────▼───────────────────────────────────────────────────┐
│ shell/  EtsReplica.exe（C++20 / Win32 / WebView2）                │
│   main.cpp          窗口 + WebView2 + 虚拟主机 + 注入 shim          │
│   bridge.cpp        JS→host→plugin；回调→UI线程→JS                 │
│   plugin_manager    LoadLibrary + 4 导出 + PlnHost 注入            │
│   config            shell.ini（AppName/HomeUrl/窗口/DataDir）      │
│   media_server      127.0.0.1:随机端口，服务 CacheDir（音频/图片）  │
│   ws_log            WinHTTP WebSocket → mq_server:40001            │
│   内置 __core       info / media_url / log / open_external         │
└───────┬──────────────────────────────────────┬────────────────────┘
        │ 4 导出 ABI                            │ ws://127.0.0.1:40001
┌───────▼───────────────────────┐   ┌──────────▼───────────────────┐
│ plugins/<name>/<name>.dll     │   │ mq_server（Node + ws）        │
│  etshelper  filehelper        │   │  端口探测/日志落盘/广播        │
│  httphelper sqlitepln         │   └──────────────────────────────┘
│  shellhelper sevenzip sysconfig│
└───────────────────────────────┘
```

## 2. 插件 ABI

见 `shared/stic_plugin.h` 与 `CONTRACT.md` §3。插件必须导出：

```cpp
void PlnInitiliaze(PlnHost* host);
void PlnSetParam(const char* key, void* fn);
void PlnOnProcessMessage(const char* action, const char* argsJson, PLN_CALLBACK cb, const char* uid);
void PlnUnInitialize(void);
```

宿主通过 `PlnHost` 注入日志与内置能力；`PlnOnProcessMessage` 可在工作线程执行，完成后以 JSON 字符串回调一次。

## 3. JS ↔ Native 桥

页面只会看到 `window.cef.message`（与原作同名）：

```js
cef.message.sendMessage(uid, "EtsHelper", "encode_api_body_v2", '{"body":"...","time":"..."}');
cef.message.setMessageCallback(uid, data => { /* data: JSON 字符串 */ });
```

壳负责把消息路由到插件 DLL，并把插件结果回投到页面。

## 4. 能力范围（对等目标）

已实现（目标）：
- 登录（AES 字段加密 + 请求签名 + HttpHelper）
- 首页、作业列表/详情、套卷、同步课程、错题本
- content 包下载→ZipCrypto 解压→read/dialogue/picture 渲染→音频播放
- 配置查看、E 卡信息

不实现（与原作一致或刻意不做）：
- STIC 壳/反调试/完整性校验（复刻不需要）
- 录音采集、ISE/AI 评测、考试提交、OSS/SLS 上传、自动更新器
- 付费/授权相关逻辑

## 5. 构建与运行

见 `docs/BUILD.md`。核心：

```powershell
pwsh -File native-replica\build.ps1          # MSVC + CMake + Vite 一键构建
<BUILD_DIR>\bin\EtsReplica.exe         # 运行
```

## 6. 与 Python 版的关系

| 关注点 | Python 版 `reimpl/` | 原生版 `native-replica/` |
|---|---|---|
| 目的 | 协议/逻辑验证，改起来快 | 同架构复刻，验证 C++/插件/桥可行性 |
| 运行 | `python reimpl/server.py` | `EtsReplica.exe` |
| 前端 | 原生 HTML/JS | Vue3 + Element Plus |
| API 调用 | Python 进程内 | 经 `HttpHelper` 插件 DLL |
| 数据/解密 | Python zipfile | C++ miniz + ZipCrypto |
| 保留 | ✅（长期保留） | ✅ |

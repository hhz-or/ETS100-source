# 13 原生同架构复刻（native-replica）

> 目标：用**与原作相同的分层架构**——嵌入式 Chromium 壳 + 插件 DLL + Web 前端 + 日志中间件——复刻 ETS 学生端；
> 具体技术选型使用本机可用的现代版本（WebView2 / C++20 / Vue3 / Node 24）。
> Python 版 `reimpl/` 保留，作为协议与逻辑的研究参考。

## 1. 与原作的映射

| 层 | 原作 5.7.9 | native-replica |
|---|---|---|
| 浏览器壳 | CEF 91 + STIC 3.0.76 | **WebView2**（Chromium 157，Windows 内建运行时） |
| 原生语言/编译器 | C++ / MSVC(VS2019 时代) | **C++20 / MSVC 14.51** |
| 插件机制 | 9 个 `.pln` DLL，4 导出 ABI | 同样 4 导出 ABI（`PlnInitiliaze/PlnSetParam/PlnOnProcessMessage/PlnUnInitialize`），7 个 DLL |
| JS↔Native 桥 | `cef.message.sendMessage / setMessageCallback / createGuid` | **同名 API**（注入 shim，底层 WebView2 `postMessage`） |
| 前端 | Vue3 + Element Plus + Pinia + Router | **Vue3 + Element Plus + Pinia + Vue Router + Vite** |
| 日志中间件 | `mq_server`（Node + ws :40001） | **Node 24 + ws**（端口探测，写 app.json） |
| 签名/加密 | 原生插件 + 内嵌密钥流 | 同算法，C++ BCrypt（MD5 / AES-128-ECB） |
| 题库包 | ZipCrypto + 7z | miniz + 自实现 ZipCrypto 解包 |

## 2. 结构

```
native-replica/
├─ CMakeLists.txt / build.ps1      # MSVC + CMake/Ninja + Vite 一键构建
├─ CONTRACT.md                     # 开发契约：ABI、桥协议、action 表
├─ shared/                         # 插件 ABI + 公共库（JSON/UTF-8/Base64/MD5/AES/文件）
├─ shell/                          # C++ 壳：窗口、WebView2、bridge、插件管理、媒体服务、WS 日志
├─ plugins/                        # 7 个插件 DLL
│  ├─ etshelper/  filehelper/  httphelper/  sqlitepln/
│  └─ shellhelper/ sevenzip/ sysconfig/
├─ frontend/                       # Vue3 SPA（Vite 构建到 assets/web）
├─ mq_server/                      # Node 日志中继
├─ third_party/                    # json.hpp / sqlite3 / miniz（vendored）
└─ docs/                           # 架构、构建、验证、前端/插件/壳实现说明
```

## 3. 已实现并实测

| 能力 | 证据 |
|---|---|
| WebView2 壳启动、窗口、虚拟主机 `app.ets.local`、注入 `cef.message` | 运行日志 hr=0；页面正常渲染 |
| 7/7 插件加载、4 导出 ABI、worker 线程回调 | 壳日志 `loaded 7/7` |
| JS→插件→回调（EtsHelper/FileHelper/ShellHelper/HttpHelper/SevenZip…） | 运行期探针全部返回 |
| **真实 HTTPS 调 API**（HttpHelper + 签名） | `system/config` 返回 `code=0`、真实配置 |
| 登录态 API（token） | `user/info` 返回 `code=0`，真实昵称/年级 |
| 首页/作业/套卷/课程/错题/设置页面渲染 | 注入有效 token 后全部页面加载 |
| 题库包解包（ZipCrypto） | 24 个真实 `content_*.zip` 全解，111 文件与 Python zipfile 逐字节一致（插件单测） |
| 媒体服务 | `media_url` → `http://127.0.0.1:<port>/media?...`，GET 200 / Range 206 / 越界 403 |
| mq_server WebSocket 日志中继 | 壳连上副本 mq_server（端口探测 40001→40002/40003） |
| 优雅退出 | 关窗 exit 0，无崩溃 |

## 4. 已知限制（与本轮未完成项）

| 项 | 说明 |
|---|---|
| 作业列表数据 | 前端 `g/homework/list` 的 `parent_account_id` 取值链路仍有一处未对齐（页面出现"没有找到有效班级"）；插件与接口本身已验证可用，属前端数据装配待修 |
| 录音 / ISE 评测 / 考试提交 / OSS / SLS / 更新器 | 与 Python 版一致：未实现，UI 明确标注 |
| 壳的日志端口 | 已支持读 `mq_server/app.json` 端口；早期构建曾固定连 40001（会写进官方客户端日志），当前已修 |
| 前端 mock | 浏览器直接打开 `dist/` 可用 mock 数据预览；WebView2 内自动走原生桥 |

## 5. 构建与运行

```powershell
cd native-replica
pwsh -File build.ps1            # MSVC + CMake + Vite；产物 .-build\bin\EtsReplica.exe
.-build\bin\EtsReplica.exe
```

前置与排错见 `native-replica/docs/BUILD.md`；壳/插件/前端实现细节见 `native-replica/docs/{shell,plugins,frontend}_build.md`。

## 6. 与 Python 版对照

| 关注点 | Python 版 `reimpl/` | 原生版 `native-replica/` |
|---|---|---|
| 目的 | 协议/逻辑验证，迭代快 | 同架构验证：CEF→WebView2、插件 ABI、JS 桥 |
| 前端 | 原生 HTML/JS | Vue3 + Element Plus |
| 网络/解密 | Python 进程内 | 分别由 `httphelper` / `sevenzip` DLL 承担 |
| 状态 | 完整可用（读写只读业务） | 架构闭环 + 主要页面可用，个别数据装配待修 |

两版共享同一套协议结论（`docs/03`、`docs/06`、`docs/08`），可互相印证。

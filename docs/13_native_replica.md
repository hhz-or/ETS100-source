# 13 原生同架构复刻（native-replica）

> 目标：用**与原作相同的分层架构**——嵌入式 Chromium 壳 + 插件 DLL + Web 前端 + 日志中间件——复刻 ETS 学生端；
> 具体技术选型使用本机可用的现代版本（WebView2 / C++20 / Vue3 / Node 24）。
> Python 版 `reimpl/` 保留，作为协议与逻辑的研究参考。

## 1. 与原作的映射

| 层 | 原作 5.7.9 | native-replica |
|---|---|---|
| 浏览器壳 | CEF 91 + STIC 3.0.76 | **WebView2**（Chromium 157，Windows 内建运行时） |
| 原生语言/编译器 | C++ / MSVC(VS2019 时代) | **C++20 / MSVC 14.51** |
| 插件机制 | 9 个 `.pln` DLL，4 导出 ABI | 同样 4 导出 ABI（`PlnInitiliaze/PlnSetParam/PlnOnProcessMessage/PlnUnInitialize`），8 个 DLL（7 个业务插件 + `soundhelper` 录音编码） |
| JS↔Native 桥 | `cef.message.sendMessage / setMessageCallback / createGuid` | **同名 API**（注入 shim，底层 WebView2 `postMessage`） |
| 前端 | Vue3 + Element Plus + Pinia + Router | **Vue3 + Element Plus + Pinia + Vue Router + Vite** |
| 录音/评测 | `soundhelper` + 前端 XRTC/ISE WebSocket | `soundhelper`（speex 编码）+ 前端 protobuf/WebSocket（`src/ise.js`） |
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
├─ plugins/                        # 8 个插件 DLL（含 soundhelper：speex 编码/mp3）
│  ├─ etshelper/  filehelper/  httphelper/  sqlitepln/
│  └─ shellhelper/ sevenzip/ sysconfig/ soundhelper/
├─ frontend/                       # Vue3 SPA（Vite 构建到 assets/web）
│  └─ src/ise.js, practiceFlow.js, recorder.js   # 评测 / 上传回传 / 录音采集
├─ mq_server/                      # Node 日志中继
├─ third_party/                    # json.hpp / sqlite3 / miniz / speex（vendored）
└─ docs/                           # 架构、构建、验证、前端/插件/壳实现说明
```

## 3. 已实现并实测

| 能力 | 证据 |
|---|---|
| WebView2 壳启动、窗口、虚拟主机 `app.ets.local`、注入 `cef.message` | 运行日志 hr=0；页面正常渲染 |
| 7/7 业务插件 + soundhelper 加载、4 导出 ABI、worker 线程回调 | 壳日志 `loaded 8/8` |
| JS→插件→回调（EtsHelper/FileHelper/ShellHelper/HttpHelper/SevenZip/soundhelper…） | 运行期探针全部返回 |
| **真实 HTTPS 调 API**（HttpHelper + 签名） | `system/config` 返回 `code=0`、真实配置 |
| **UI 登录**（页面输入手机号/密码→提交） | 跳转 `#/home`，token 长度 160，提示"登录成功" |
| 设备指纹复用 | 官方账号有设备绑定；设置页填写 `device_code/device_name/local_ip` 后可免验证登录 |
| 首页 | 真实昵称/年级/学校/学习卡剩余天数；1 份待完成作业、9 道待订正错题 |
| 作业 | 待完成 1 / 已完成 3 / 已过期 0，可进入详情与开始练习 |
| 套卷 / 同步课程 / 错题本 | 栏目 16 套、教材列表、错题 9 条（参数已对齐） |
| 题库内容 + 音频 | 下载→ZipCrypto 解包→读 `content.json`→渲染朗读题；音频 `HTTP 200 / 127,362 B` |
| 媒体服务 | `media_url` → `http://127.0.0.1:<port>/media?...`，GET 200 / Range 206 / 越界 403 |
| **录音 + ISE 评测** | 麦克风（WebView2 授权）→ speex 16k（106B/帧）→ protobuf WebSocket → XML 分数；页面实测 2.6s 返回 |
| **speex 编码 / mp3 生成** | `soundhelper.encode_speex`（405 帧/8.1s，247ms）；`encode_mp3` 调 ffmpeg 生成 24kbps mp3 |
| **OSS 上传 + 成绩回传** | STS → 三文件表单上传（public-read，GET 200）→ `/m/audio/sync-v2`；前端 404ms 完成三传 |
| mq_server WebSocket 日志中继 | 壳连上副本 mq_server（端口探测，读 `app.json`） |
| 优雅退出 | 关窗 exit 0，无崩溃 |

## 4. 已知限制

| 项 | 说明 |
|---|---|
| 设备绑定 | 官方账号首次登录会提示"设备需要绑定免验证"；在设置页填入官方客户端的 `device_code` 即可，值只存本机 localStorage |
| 单会话 | 副本登录会顶掉官方客户端会话（反之亦然），这是服务端策略 |
| 录音 / ISE 评测 | ✅ 已实现并验证协议；真实麦克风完整回归仍需一次人工练习（自动化测试不向评测服务发送环境音）。见 docs/15。 |
| 上传 / 回传 | ✅ 已实现：ffmpeg 生成 mp3 → OSS 三文件上传 → sync-v2；mp3 需要 `ffmpeg.exe`（`<appDir>\tools\ffmpeg.exe` 或环境变量 `ETS_FFMPEG`）。 |
| SLS / 更新器 | 未实现（与练习主链路无关） |
| 评分口径 | `real_score = total_score × question_type_score` 为按抓包/接口样本推断，服务端可能二次计算；以服务端返回的 `point/complete` 为准 |
| 前端 mock | 浏览器直接打开 `dist/` 可用 mock 数据预览；WebView2 内自动走原生桥 |

## 5. 构建与运行

```powershell
cd native-replica
pwsh -File build.ps1            # MSVC + CMake + Vite；默认产物 <BUILD_DIR>\bin\EtsReplica.exe
<BUILD_DIR>\bin\EtsReplica.exe  # 运行（需要 WebView2 运行时；首次登录见设置页设备信息）
```

- 构建前置：MSVC x64、CMake 3.25+、Ninja、Node 18+ + pnpm、WebView2 SDK（NuGet）；speex 已 vendored（`third_party/speex`），无需联网。
- 录音上传需要 `ffmpeg.exe`：放到 `bin\tools\ffmpeg.exe`、或用 `ETS_FFMPEG` 指向安装目录自带 ffmpeg；不配置时录音/评测仍可用，仅“上传并回传成绩”会提示缺失。
- 前置与排错见 `native-replica/docs/BUILD.md`；壳/插件/前端实现细节见 `native-replica/docs/{shell,plugins,frontend}_build.md`。

## 6. 与 Python 版对照

| 关注点 | Python 版 `reimpl/` | 原生版 `native-replica/` |
|---|---|---|
| 目的 | 协议/逻辑验证，迭代快 | 同架构验证：CEF→WebView2、插件 ABI、JS 桥 |
| 前端 | 原生 HTML/JS | Vue3 + Element Plus |
| 网络/解密 | Python 进程内 | 分别由 `httphelper` / `sevenzip` DLL 承担 |
| 录音/评测/上传 | `ets_ise.py`（ISE 回放验证）、`practice.py`（STS/OSS/sync） | 前端 + `soundhelper` + `httphelper`（完整 UI 链路） |
| 状态 | 完整可用（只读业务 + 参考写链路） | 架构闭环 + 主要页面 + 录音评测上传回传可用 |

两版共享同一套协议结论（`docs/03`、`docs/06`、`docs/08`、`docs/15`），可互相印证。

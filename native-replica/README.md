# native-replica · ETS 同架构复刻（C++ / WebView2 / Vue3）

本目录用**与原作相同的分层架构**复刻「E听说 PC 学生端」：

- **壳**：C++20 + Win32 + **WebView2**（现代 Chromium；原作是 CEF 91）
- **插件**：8 个 DLL（7 个业务插件 + `soundhelper`），保留原作 4 导出 ABI（`PlnInitiliaze/PlnSetParam/PlnOnProcessMessage/PlnUnInitialize`）
- **前端**：Vue3 + Element Plus + Pinia + Vue Router + Vite（原作也是 Vue3）
- **日志中间件**：Node 24 + ws（对应原作 `mq_server`，40001）

保留仓库内 `reimpl/`（Python 版）作为协议/逻辑研究参考；本目录负责验证“同架构复刻也能跑真实业务”。

## 文档

| 文件 | 内容 |
|---|---|
| [CONTRACT.md](CONTRACT.md) | 分层、插件 ABI、JS 桥协议、插件 action 表（开发契约） |
| [docs/architecture.md](docs/architecture.md) | 与原作的逐层映射、能力范围 |
| [docs/BUILD.md](docs/BUILD.md) | 已验证的工具链、构建、运行、排错 |
| [docs/VERIFY.md](docs/VERIFY.md) | 验证矩阵：登录/业务/媒体/录音评测/上传回传 |
| [docs/15 练习协议](../docs/15_practice_protocol.md) | ISE protobuf、speex 参数、OSS、sync-v2 |

## 快速开始

```powershell
cd native-replica
pwsh -File build.ps1          # MSVC + CMake/Ninja + Vite；产物 <BUILD_DIR>\bin\EtsReplica.exe
<BUILD_DIR>\bin\EtsReplica.exe
```

前置：VS BuildTools（C++ 桌面负载）+ Windows SDK；CMake≥3.25、Ninja；Node 18+ / pnpm；WebView2 Runtime（Win10/11 一般已内建）。
WebView2 SDK 与第三方库（json/sqlite/miniz/speex）的获取方式见 `docs/BUILD.md`；speex 已 vendored，无需联网。

录音/评测的“上传并回传成绩”需要 `ffmpeg.exe`：放到 `<BUILD_DIR>\bin\tools\ffmpeg.exe`，或设置环境变量
`ETS_FFMPEG=<ffmpeg.exe 路径>`（也可使用官方客户端安装目录自带的 ffmpeg）。未配置时录音与评测仍可用，仅上传会提示。

## 能力范围

- ✅ 登录（AES 字段加密 + 请求签名 + HTTPS）
- ✅ 首页 / 作业 / 套卷 / 同步课程 / 错题本
- ✅ content 包下载 → ZipCrypto 解压 → read/dialogue/picture 渲染 → 音频播放
- ✅ 配置查看、E 卡信息
- ✅ **录音采集**（WebView2 自动授权麦克风）→ **speex 16k 编码**（106B/帧、212B/WS 块）→ **ISE 评测**（protobuf WebSocket）→ XML 分数/逐词反馈
- ✅ **mp3 生成** → **OSS 三文件上传**（STS/public-read）→ **`/m/audio/sync-v2` 成绩回传**（含错题/用时）
- ❌ SLS 日志上传、自动更新器
- ❌ STIC 壳/反调试/完整性校验（复刻不需要）

## 免责声明

仅用于架构学习、互操作性研究与自有环境排障；不用于绕过付费/评分/授权。凭据只从仓库外读取，不写入源码或提交。

# native-replica · ETS 同架构复刻（C++ / WebView2 / Vue3）

本目录用**与原作相同的分层架构**复刻「E听说 PC 学生端」：

- **壳**：C++20 + Win32 + **WebView2**（现代 Chromium；原作是 CEF 91）
- **插件**：7 个 DLL，保留原作 4 导出 ABI（`PlnInitiliaze/PlnSetParam/PlnOnProcessMessage/PlnUnInitialize`）
- **前端**：Vue3 + Element Plus + Pinia + Vue Router + Vite（原作也是 Vue3）
- **日志中间件**：Node 24 + ws（对应原作 `mq_server`，40001）

保留仓库内 `reimpl/`（Python 版）作为协议/逻辑研究参考；本目录负责验证"同架构复刻也能跑真实业务"。

## 文档

| 文件 | 内容 |
|---|---|
| [CONTRACT.md](CONTRACT.md) | 分层、插件 ABI、JS 桥协议、插件 action 表（开发契约） |
| [docs/architecture.md](docs/architecture.md) | 与原作的逐层映射、能力范围 |
| [docs/BUILD.md](docs/BUILD.md) | 已验证的工具链、构建、运行、排错 |

## 快速开始

```powershell
cd native-replica
pwsh -File build.ps1          # MSVC + CMake/Ninja + Vite
C:\ets-rea-build\bin\EtsReplica.exe
```

前置：VS2022/2026 BuildTools（C++ 桌面负载）+ Windows SDK；CMake≥3.25、Ninja；Node 18+ / pnpm；WebView2 Runtime（Win10/11 一般已内建）。
WebView2 SDK 与第三方库（json/sqlite/miniz）的获取方式见 `docs/BUILD.md`。

## 能力范围

- ✅ 登录（AES 字段加密 + 请求签名 + HTTPS）
- ✅ 首页 / 作业 / 套卷 / 同步课程 / 错题本
- ✅ content 包下载 → ZipCrypto 解压 → read/dialogue/picture 渲染 → 音频播放
- ✅ 配置查看、E 卡信息
- ❌ 录音采集、ISE/AI 评测、考试提交、OSS/SLS 上传、自动更新器（与原作一致，标注"未实现"）
- ❌ STIC 壳/反调试/完整性校验（复刻不需要）

## 免责声明

仅用于架构学习、互操作性研究与自有环境排障；不用于绕过付费/评分/授权。凭据只从仓库外读取，不写入源码或提交。

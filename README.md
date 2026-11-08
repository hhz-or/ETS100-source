# ETS100 逆向工程资料（E听说 PC 学生端）

本仓库是对 **讯飞易听说「E听说」学生端 PC 版 5.7.9**（STIC 3.0.76 / CEF 91 壳）的逆向分析资料集合：架构、协议、前端、原生层、本地数据、更新链、运行时验证，以及两个可运行的复刻实现——Python 参考客户端（`reimpl/`）与同架构原生复刻（`native-replica/`）。

> 分析对象为自有软件副本；结论来自静态分析、目标自身产生的日志/缓存，以及主动启动实例后的 CDP/Frida 运行时观察。仓库不包含原始安装包、原始日志、个人信息或大体积反编译产物。

## 目录

```
docs/                 16 篇中文报告（00–15 + REPORT；从 docs/REPORT.md 开始）
data/                 脱敏后的机读数据
  api/                端点清单、签名样本（已脱敏）、签名参考实现、运行时/更新器签名证明
  frontend/           路由、action 清单、插件 JS 权威 action 表、在线 chunk 清单
  native/             14 个原生 PE 的导出/导入/插件 ABI/能力面
  db/                 本地 SQLite 配置库数据
runtime/              运行时验证证据：插件 JS 封装层、活体请求元数据、Frida 抓取记录
scripts/              分析脚本（缓存解码、签名验证、密钥流、题库包解密、CDP 抓取等）
capture/              练习抓包工具（CDP WebSocket / Frida 插件调用 / 日志 / 文件监听 + 汇总）
reimpl/               可运行的参考客户端（Python 后端 + 原生 Web UI）
  ets_ise.py          ISE 评测参考实现（protobuf + WebSocket，纯标准库）
  practice.py         STS / OSS 上传 / sync-v2 / 错题 / 用时（默认 dry-run）
native-replica/       同架构原生复刻（C++20 + WebView2 壳 / 8 插件 DLL / Vue3 前端 / Node mq_server）
```

## 核心成果

| # | 成果 | 验证 |
|---|---|---|
| 1 | API 请求签名 `MD5(pid + time + base64(body) + 内嵌密钥流)` | 历史日志 333/334 + 运行时 68/68 + 原生 oracle |
| 2 | 响应签名 `MD5(pid + resp_b64 + KEY + sn)` | Frida 实机输入 + oracle 逐字节命中 |
| 3 | 更新器签名 `MD5("grlx" + time秒 + base64(body) + key)` | 3/3 |
| 4 | 登录字段 AES-128-ECB 加密与硬编码密钥 | 3/3 密文解密 |
| 5 | 前端 Chromium blockfile 缓存解码 / 在线全量 chunk（188 个） | 100% 覆盖 |
| 6 | 题库包 ZipCrypto 口令算法 | 24/24 解包 |
| 7 | 插件 ABI（4 导出）、9 通道 115 个 action、壳自定义 scheme | 三方交叉 + Frida 实机 |
| 8 | Python 参考客户端（真实登录 / 首页 / 作业 / 套卷 / 题库练习 / 错题） | 16/16 API + 21/21 前端交互 |
| 9 | **练习协议全链路**：ISE WebSocket protobuf、speex 16k 编码（106B/帧）、OSS 上传、sync-v2 回传 | 抓包回放 + 实测上传 |
| 10 | **原生复刻的录音/评测/上传**：麦克风 → speex → ISE → 分数 → mp3+OSS+回传 | 页面内端到端实测 |

## 快速开始

```bash
# 1) 验证签名算法（用仓库内脱敏样本，期望 333/334）
python scripts/sign_verify_all.py

# 2) 密钥流复算（需要 ETS 安装目录，见 scripts/README.md）
python scripts/keystream.py

# 3) 参考客户端（凭据放在仓库外，不提交）
python reimpl/server.py            # http://127.0.0.1:8787/
python reimpl/tools/smoke_test.py  # 只读接口验收 16/16

# 4) 练习协议：用抓包回放验证 ISE；查看上传/回传链路（默认 dry-run）
python reimpl/ets_ise.py --capture-run <抓包目录> --spx <文件.spx>
python reimpl/practice.py sts

# 5) 原生复刻：构建后运行，作业 → 进题 → “录音评测” → “上传并回传成绩”
#    需要 MSVC + CMake/Ninja + WebView2 SDK + Node/pnpm；录音上传另需 ffmpeg.exe
#    （放到 <build>/bin/tools/ffmpeg.exe 或设置 ETS_FFMPEG）

# 6) 练习抓包（可选）：官方客户端登录后运行，做一次真实练习，回车停止并汇总
pwsh -File capture/run_capture.ps1
python capture/summarize.py capture/runs/<时间戳>
```

## 报告导航

| 文档 | 内容 |
|---|---|
| [REPORT.md](docs/REPORT.md) | 总报告：成果、统计、复现指南 |
| [00_INDEX.md](docs/00_INDEX.md) | 总览与导航 |
| [01_target_and_inventory.md](docs/01_target_and_inventory.md) | 目标识别、667 文件清单、指纹 |
| [02_architecture.md](docs/02_architecture.md) | 5 层架构、进程模型、消息流、安全观察 |
| [03_api_protocol.md](docs/03_api_protocol.md) | mq_server 协议、HTTP API、鉴权链 |
| [04_frontend.md](docs/04_frontend.md) | 缓存解码、路由、action、录音评测链 |
| [05_native.md](docs/05_native.md) | 原生 PE 的 ABI/导出/导入/能力面 |
| [06_data.md](docs/06_data.md) | DB/存储/题库包/评测 XML |
| [07_shell_update.md](docs/07_shell_update.md) | 壳层、更新、崩溃上报、音视频链 |
| [08_signature.md](docs/08_signature.md) | API/更新器签名 + 字段加密（均已验证） |
| [09_decompiled.md](docs/09_decompiled.md) | Ghidra 反编译关键函数摘录 |
| [10_unknowns.md](docs/10_unknowns.md) | 未知项、限制与验证建议 |
| [11_runtime_live.md](docs/11_runtime_live.md) | 运行时验证：CDP、全量 chunk、插件 action 表、活体协议 |
| [12_reimplementation.md](docs/12_reimplementation.md) | Python 参考客户端：架构映射、实现矩阵、运行方式 |
| [13_native_replica.md](docs/13_native_replica.md) | 原生同架构复刻：WebView2/插件/Vue3、录音评测、构建运行 |
| [15_practice_protocol.md](docs/15_practice_protocol.md) | 真实练习抓包：ISE protobuf、speex 参数、OSS 上传、sync-v2 |

## 数据与路径约定

- `data/`、`runtime/`、`scripts/`、`capture/` 为随仓库发布的脱敏数据、脚本与工具。
- 原始安装副本、原始日志、原始前端 bundle、反编译产物等未发布；文档中以“（未随仓库发布）”标注，可按报告中的脚本与方法从自有安装副本重建。
- 文档中的证据位置统一写作 `日志名:行号`；原始日志位于目标安装目录的 `logs/`。
- 占位符：`<ETS_INSTALL_DIR>`=目标程序安装目录；`<BUILD_DIR>`=复刻构建输出目录；`<REPO_ROOT>`=仓库根目录；`<WORK_DIR>`=分析工作区。

## 免责声明

- 本项目仅用于**架构学习、互操作性研究、安全评估与自有环境排障**；不得用于绕过付费/考试评分、伪造成绩、破解授权或其他侵害他人权益的行为。
- 第三方软件、商标、代码片段（如 `runtime/plugin_js_stubs/` 中的前端插件封装代码）版权归原权利人所有，此处引用仅用于协议互操作性说明；如权利人提出异议将立即移除。
- 仓库数据已脱敏：`data/api/sign_samples.json` 保留请求结构用于验证签名，敏感字段已替换为 `***`；`runtime/live_requests.json` 仅保留请求元数据。

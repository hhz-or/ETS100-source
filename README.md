# ETS100 逆向工程资料（E听说 PC 学生端）

本仓库是对 **讯飞易听说「E听说」学生端 PC 版 5.7.9**（STIC 3.0.76 / CEF 91 壳）的逆向分析资料集合：架构、协议、前端、原生层、本地数据、更新链、运行时验证，以及一个**可运行、功能接近的参考客户端**（`reimpl/`）。

> 分析对象为自有软件副本；结论来自静态分析、目标自身产生的日志/缓存，以及主动启动实例后的 CDP/Frida 运行时观察。仓库不包含原始安装包、原始日志、个人信息或大体积反编译产物。

## 目录

```
docs/                 15 篇中文报告（从 docs/REPORT.md 开始）
data/                 脱敏后的机读数据
  api/                端点清单、签名样本（已脱敏）、签名参考实现、运行时/更新器签名证明
  frontend/           路由、action 清单、插件 JS 权威 action 表、在线 chunk 清单
  native/             14 个原生 PE 的导出/导入/插件 ABI/能力面
  db/                 本地 SQLite 配置库数据
runtime/              运行时验证证据：插件 JS 封装层、活体请求元数据、Frida 抓取记录
scripts/              分析脚本（缓存解码、签名验证、密钥流、题库包解密、CDP 抓取等）
reimpl/               可运行的参考客户端（Python 后端 + 原生 Web UI）
native-replica/       同架构原生复刻（C++20 + WebView2 壳 / 插件 DLL / Vue3 前端 / Node mq_server）
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
| 8 | 可运行参考客户端（真实登录 / 首页 / 作业 / 套卷 / 题库练习 / 错题） | 16/16 API + 21/21 前端交互 |

## 快速开始

```bash
# 1) 验证签名算法（用仓库内脱敏样本，期望 333/334）
python scripts/sign_verify_all.py

# 2) 密钥流复算（需要 ETS 安装目录，见 scripts/README.md）
python scripts/keystream.py

# 3) 参考客户端（凭据放在仓库外，不提交）
python reimpl/server.py            # http://127.0.0.1:8787/
python reimpl/tools/smoke_test.py  # 只读接口验收 16/16
```

## 免责声明

- 本项目仅用于**架构学习、互操作性研究、安全评估与自有环境排障**；不得用于绕过付费/考试评分、伪造成绩、破解授权或其他侵害他人权益的行为。
- 第三方软件、商标、代码片段（如 `runtime/plugin_js_stubs/` 中的前端插件封装代码）版权归原权利人所有，此处引用仅用于协议互操作性说明；如权利人提出异议将立即移除。
- 仓库数据已脱敏；`data/api/sign_samples.json` 为验证签名保留了请求结构，敏感字段已替换为 `***`。

# 12 参考客户端：可运行的 ETS 复刻原型

> 目标：用逆向得到的协议知识，实现一个**能真实登录、能读取真实业务数据、能浏览与练习题库内容**的客户端，验证"逆向结论足以复刻一个功能接近的客户端"。
> 位置：仓库 `reimpl/`。技术栈刻意保持简单：Python 标准库 + 可选 `requests`/`cryptography`，前端原生 HTML/CSS/JS（无构建、无 CDN）。

---

## 1. 为什么它能"几乎一样"

原客户端是「CEF 壳 + 9 个原生插件 + 远程 Vue3 SPA」。参考客户端用**等价能力的最小组合**替代：

| 原作层 | 原作实现 | 参考客户端实现 |
|---|---|---|
| 壳/窗口 | ETSShell（STIC + CEF） | 浏览器 + 本地 HTTP 服务（`127.0.0.1:8787`） |
| JS↔Native 桥 | `cef.message.sendMessage(uid, plugin, action, args)` | `/api/*` REST + 同步函数调用 |
| `EtsHelper` 签名 | `encode_api_body_v2`（MD5 + 内嵌密钥流） | `ets_client.sign()`（公式见 `08_signature.md`，333/334 验证） |
| `EtsHelper` 字段加密 | AES-128-ECB / k_serves | `ets_client.aes_ecb_b64()`（同算法同密钥） |
| `HttpHelper` | HTTP(S) + 下载 | `requests`/`urllib` + 签名信封 |
| `FileHelper` / `SevenZip` | 文件、MD5、解压 | Python 文件操作 + `zipfile` + ZipCrypto 解密（`06_data.md` §4.2） |
| 前端 SPA | Vue3 + Element Plus | 原生 JS 单页，布局/信息架构对齐原作 |
| 日志总线 mq_server | WebSocket 40001 | 本地控制台日志（非必需） |

**结论**：业务协议 90% 以上在 HTTP JSON + 签名；客户端骨架可以用任意 HTTP 客户端替代。真正无法替代的是**服务端**（判分、AI 评测、题库下发规则）与**录音/评测链路**。

---

## 2. 已实现（真实接口、真实数据）

| 模块 | 对应原作能力 | 验证 |
|---|---|---|
| 登录 | `POST user/login`（AES 手机号/密码 + 签名） | 真实账号 `code=0`，token 持久化 |
| 会话/身份 | `user/info`、`m/ecard/list` | 真实昵称/年级/学校/E 卡 |
| 首页 | `system/config`、`g/homework/list`、`m/mistake/summary`、`m/advertisement/list` | 三卡数据、配置 497 项 |
| 作业 | `g/homework/list`（待完成/已完成/过期） | 真实 1 待完成 + 3 已完成 |
| 套卷/同步课程 | `g/set/list`、`g/set/unit-list`、`g/set/unit-info`、`g/set/module-list`、`g/set/column-v2` | 118/113/111 套、23 教材 |
| 题库内容 | 资源包下载 + **ZipCrypto 解密**（包尾 336B 口令块） | `content_1010510` 解密成功；read/dialogue/picture 三类渲染 |
| 音频 | 包内 `material/*.mp3` + 评测结果音频 | 127,362 B MP3 可播放 |
| 错题本 | `m/mistake/summary` + 历史录音/XML | 真实 9 条 |
| 系统信息 | `system/config`、`system/time`、`fluent` 配置查看 | 与官方一致 |
| 账号信息 | E 卡列表、绑定信息 | 脱敏展示 |

自动化验收：`reimpl/tools/smoke_test.py` → **16/16 PASS**；`reimpl/tools/cdp_probe.js` 前端交互 → **21/21 PASS**（无 console error）。

---

## 3. 未实现（UI 中明确标注，不伪造）

| 能力 | 原因 |
|---|---|
| 录音（麦克风采集 / `soundhelper.record`） | 需要原生音频栈；浏览器 MediaRecorder 无法等价 |
| ISE / AI 双通道评测（`wss://oe-pub.eduaiplat.com`） | 需要评测服务与音频格式（spx/双通道 40ms 帧） |
| 考试提交 / 作业完成上报 | 写接口会产生真实业务数据，参考实现只做只读浏览 |
| OSS / SLS 上传 | 依赖 STS 凭证与签名策略 |
| 自动更新器（EtsUpdate.exe） | 与客户端功能无关 |
| 读写模拟题型 | 服务端返回的 `rw_data` 与 content 包结构不同 |
| 生词本、预测分 | 需更多写接口/评测数据 |

---

## 4. 运行

```bash
# 前置：Python 3.10+；可选 pip install requests cryptography（缺省自动回退纯 stdlib 实现）
# 凭据：<WORK_DIR>/secrets/account.json = {"phone":"...","password":"...","device_name":"...","device_code":"...","local_ip":"..."}
#       或 <WORK_DIR>/secrets/app_token.txt 直接复用现有 token

python reimpl/server.py            # http://127.0.0.1:8787/
python reimpl/server.py --port 8790 --open
python reimpl/tools/smoke_test.py  # 只读接口验收
```

**单会话行为**：同一账号在服务端是单会话。参考客户端登录会顶掉官方客户端（或反之），这是服务端策略而非实现缺陷；README 已说明如何切换 token。

---

## 5. 安全与边界

- 凭据只从仓库**之外**的 `secrets/` 读取，不写入任何将提交的文件；`.state/`（token、缓存、浏览器 profile）已 gitignore。
- 只调用**只读**接口；不提交考试、不写作业、不上传音频。
- 本地服务只监听 `127.0.0.1`，无对外暴露。
- 参考实现用于验证逆向结论与学习，不用于绕过任何付费/评分/授权机制。

---

## 6. 目录

```
reimpl/
├─ ets_client.py        # 协议库：签名/AES/信封/登录/token/25 个只读接口/资源包解密/音频缓存
├─ server.py            # 本地 HTTP 服务 + 静态 UI + /api/*
├─ static/
│  ├─ index.html
│  ├─ css/app.css
│  └─ js/app.js         # 原生 SPA（登录/首页/作业/套卷/课程/练习/错题/配置）
├─ tools/
│  ├─ smoke_test.py     # 只读 API 验收
│  └─ cdp_probe.js      # CDP 前端交互验收
├─ README.md            # 前置条件、运行、验收、实现矩阵
└─ .gitignore
```

## 7. 与原作的功能对照结论

- **能复刻的**：登录、会话、首页、作业/套卷/课程结构、题库内容与音频、错题摘要、E 卡/配置——已用真实账号跑通。
- **不能复刻的**：原生音频采集与评测、写业务（考试/作业提交）、自动更新、OSS/SLS 上传——这些依赖服务端或原生栈，不属于"客户端协议"范畴。
- 因此"功能几乎一样"在本项目中定义为：**客户端侧的信息架构与只读业务能力等价**；这一点已达成并可复现。

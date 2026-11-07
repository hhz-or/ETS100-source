# E 听说（学生端 PC）参考客户端

一个用于验证逆向结论、可本地运行的 **Python 后端 + 原生 Web UI** 参考客户端。
它直接调用 `https://api.ets100.com` 的真实只读接口，使用真实登录 token、真实作业/套卷/题库资源包与音频，
界面按原作（讯飞 E 听说 V5.7.9）的导航与页面结构做轻量复刻。

> 定位：逆向研究 / 互操作性验证的原型，**不是官方客户端**。只读、只在本机运行；不实现录音、评测、提交、上传。
> 所有页面只展示真实接口数据，不伪造分数；未实现能力在 UI 中明确标注“参考客户端未实现”。

---

## 1. 前置条件

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 10/11（也可在 macOS/Linux 运行，路径用环境变量覆盖） |
| Python | 3.10+（实测 3.13） |
| 依赖 | 纯标准库即可运行；安装了 `requests` / `cryptography` 时自动优先使用（AES 有内置纯 Python 实现，二者均可选） |
| 浏览器 | Chrome / Edge / Firefox 等现代浏览器 |
| 凭据 | `D:\ets-rea\secrets\account.json`（账号登录）或 `D:\ets-rea\secrets\app_token.txt`（复用官方客户端 token） |
| 网络 | 可访问 `api.ets100.com` / `cdnsubject.ets100.com` / `cdnfeis.ets100.com` / `ets60.ets100.com` |

> **凭据不进入 `reimpl/`**：`reimpl/` 内没有账号、密码、token 副本；后端只在运行时从 `secrets/` 读取。
> `reimpl/.state/token.json` 是运行期 token 缓存（已 `.gitignore`，删除后回退到 `secrets/app_token.txt`）。

### 1.1 凭据文件格式（放在 `reimpl/` 之外，不要提交）

`D:\ets-rea\secrets\account.json`：

```json
{
  "phone": "{{手机号}}",
  "password": "{{密码}}",
  "device_name": "{{机器名，例如 PC}}",
  "device_code": "{{16 位大写十六进制设备码}}",
  "local_ip": "{{本机 IP，例如 127.0.0.1}}"
}
```

`D:\ets-rea\secrets\app_token.txt`：文件内容为官方客户端当前登录 token（一行 160 字符 JWT，无引号）。

可用环境变量覆盖路径：

| 环境变量 | 作用 |
|---|---|
| `ETS_ACCOUNT_FILE` | 账号 JSON 路径 |
| `ETS_APP_TOKEN_FILE` | 官方 token 文件路径 |
| `ETS_REIMPL_STATE_DIR` | 运行期状态目录（默认 `reimpl/.state`） |
| `ETS_API_BASE` | API 域名（默认 `https://api.ets100.com`） |
| `ETS_REIMPL_PORT` | 默认端口（默认 8787） |

---

## 2. 运行步骤

```powershell
cd D:\ets-rea

# 1) 启动本地服务器（默认 127.0.0.1:8787，只监听本机）
python reimpl\server.py

# 可选：指定端口并自动打开浏览器
python reimpl\server.py --port 8790 --open
```

浏览器打开 <http://127.0.0.1:8787/>，按页面提示三选一登录：

1. **本机账号登录** —— 读取 `secrets/account.json`，按原作 `user/login` 现场做字段 AES 加密 + 请求签名；
2. **官方客户端 token** —— 读取 `secrets/app_token.txt`，复用官方客户端当前会话（最不容易互踢）；
3. **粘贴 token** —— 手动粘贴一个有效 token（仅保存到 `reimpl/.state/token.json`）。

### 2.1 单会话行为（重要）

账号是**单会话**的：官方客户端正在运行时，新的 `user/login` 可能返回 `code 20004`（账号已在别处登录），
也可能把官方客户端顶下线。因此：

- 验收 / 日常使用建议**先完全退出官方客户端**，再使用“本机账号登录”；
- 若要保持官方客户端在线，优先使用“官方客户端 token”（`secrets/app_token.txt`），它复用现有会话、不触发新登录；
- 测试过登录后，若旧 token 失效，可重新用官方客户端登录生成新 token，或删除 `reimpl/.state/token.json` 回退到 `secrets/app_token.txt`；
- 登录失败时页面会给出可读提示（单会话冲突 / token 失效 / 未绑定班级等），不会崩溃。

---

## 3. 页面与路由

| 路由 | 页面 | 数据来源 |
|---|---|---|
| `#/home` | 学习中心首页（三卡 / 模块卡 / 同步课程 / 作业预览） | `/api/home` 聚合 |
| `#/homework?tab=todo\|done\|overtime\|all` | 班级练习列表 | `g/homework/list` |
| `#/homeworkDetail/<id>` | 作业详情：试卷结构（template res.json）+ 题目列表 | `g/homework/list` + 模板包 |
| `#/sets/<column_id>` | 套卷目录（听说/读写/听力模拟等） | `g/set/list` |
| `#/setDetail/<column_id>/<set_id>` | 套卷详情 | `g/set/list` + 模板包 |
| `#/practice/homework/<id>`、`#/practice/set/<column>/<id>` | 练习页：read / dialogue / picture（bonus: choose）渲染 + 示范音频 + 答案/解析 | content_*.zip 本地解密 |
| `#/courses` | 同步课程（教材 / 单元 / 模块列表） | `g/resource/*` + `g/set/unit-list` / `module-list` |
| `#/mistakes`、`#/mistake/<id>` | 错题本统计/明细 + 历史评测录音与 XML | `m/mistake/summary` + `m/mistake/list` |
| `#/ecards` | 我的 E 卡（敏感字段服务端遮蔽） | `m/ecard/list` |
| `#/config` | 系统配置只读检索（约 497 个 key） | `system/config` |
| `#/expand` | 能力拓展 / 功能开关 | `g/set/column-v2` + `g/resource/expand-module` |
| `#/words` | 生词本（未实现，明确标注） | — |
| `#/about` | 关于 / 已实现与未实现矩阵 / 只读接口清单 | 本地静态 |

顶栏包含原作风格的 E 听说 V5.7.9 标识、用户信息、服务端时钟与窗口装饰（装饰不可操作）。
左侧导航：学习中心 / 能力拓展 / 班级练习 / 错题本 / 生词本 / 同步课程 / 我的 E 卡 / 系统配置 / 关于。

---

## 4. 已实现 / 未实现矩阵

### 4.1 已实现（真实接口 / 真实数据）

- [x] **请求签名**：`sign = MD5("pcWin" + time_ms + base64(body_json) + "94cfbda3…")`（v2）
- [x] **请求信封**：`{body: base64([{r, params}]), head:{version:"1.0", sign, pid:"pcWin", time, time_second}}`
- [x] **字段加密**：AES-128-ECB / PKCS7 / `k_serves`，用于登录 phone/password（内置纯 Python AES 兜底）
- [x] **登录**：`user/login`，token 持久化 `.state/token.json`（已 gitignore），也支持 `secrets/app_token.txt`
- [x] **23 个实测只读接口 + 2 个 bonus**（见 `/api/about` 或 §6）
- [x] **首页聚合**：user/info + homework/list + mistake/summary + advertisement + column-v2 + system/time
- [x] **作业**：多状态列表（待完成/已完成/已逾期/全部）、详情、套卷结构
- [x] **套卷目录**：听说模拟（118 套）、读写模拟（113 套目录）、听力模拟（111 套）
- [x] **同步课程**：教材 23 本 / 单元 / 模块目录
- [x] **题库资源包**：`cdnsubject.ets100.com/made/<md5>.zip` 下载 → 包尾 336B（MSTCHINA/EPLAT）派生 ZipCrypto 口令 → 本地解密解压 → 缓存
- [x] **练习页**：`collector.read` / `collector.dialogue` / `collector.picture` / bonus `collector.choose` 渲染；示范音频 `<audio>`；题干 / 解析 / 参考答案 / 关键词 / 范文
- [x] **音频**：包内音频、评测录音（ets60.ets100.com）本地缓存 + Range 流式返回
- [x] **错题本**：统计 + 明细 + 真实历史评测分数、录音回放、XML 原始结果
- [x] **E 卡 / 账号信息**：卡片、班级、有效期、引擎配置；password / 手机号 / 机器码等在服务端遮蔽
- [x] **系统配置查看**：497 个 key 的搜索 / 分页 / 展开
- [x] **错误处理**：接口错误统一 JSON（不再崩溃）；单会话 code 20004 / token 失效 30001 给可读提示
- [x] 纯本地 Web UI：原生 HTML/CSS/JS，无构建、无外部 CDN、无第三方运行时

### 4.2 未实现（UI 中明确标注，不伪造）

- [ ] **录音采集**（麦克风 / SndHelper）
- [ ] **ISE / AI 评测**（`wss://oe-pub.eduaiplat.com`，双通道、评分回写）
- [ ] **考试提交 / 作业完成上报**（`m/audio/sync-v2`、`g/homework/checkstart`、`m/homework/set-use-time` 等写接口）
- [ ] **阿里云 OSS / SLS 上传**（录音 mp3/spx/xml、埋点日志）
- [ ] **自动更新器**（`EtsUpdate.exe` / `client/mobile-update`）
- [ ] **读写模拟题型渲染**（服务端 `rw_data` 只有目录信息，无 content 包）
- [ ] 生词本（只读接口清单未覆盖用户词表读写）
- [ ] 预测分（原作成长接口未开放；首页显示“— 不伪造”）

> 未实现 ≠ 不知道怎么做：签名、字段加密、资源包口令、评测链路、OSS 上传参数均已在逆向文档中还原，
> 本参考客户端刻意**只读**，避免向 ETS 账号写入任何数据。

---

## 5. 目录结构

```
reimpl/
├─ ets_client.py            # 纯逻辑库：签名 / AES / 信封 / 登录 / token / 25 个只读接口 / 资源包下载与 ZipCrypto 解密 / 音频缓存
├─ server.py                # ThreadingHTTPServer 127.0.0.1:8787：静态 UI + /api/* + 错误 JSON + Range 音频
├─ static/
│  ├─ index.html            # 单页入口（顶栏 / 侧边导航 / 内容区 / toast / modal）
│  ├─ css/app.css           # 原作风格视觉（蓝色主题、卡片、响应式）
│  └─ js/app.js             # 原生 SPA：hash 路由 + 各页面渲染 + 事件委托 + 练习页
├─ tools/
│  ├─ smoke_test.py         # 只读 API 验收（16 项；不触发登录）
│  └─ cdp_probe.js          # 可选的前端交互自测（需 Node 22+ 与 CDP Chrome；21 项）
├─ README.md
├─ .gitignore               # .state/、__pycache__/
└─ .state/                  # 运行期（gitignore）：token.json / cache/ 资源包与音频缓存 / 日志
```

代码规模：`ets_client.py` 约 1000 行、`server.py` 约 1200 行、`static/js/app.js` 约 1750 行、`app.css` 约 630 行。

---

## 6. 关键实现说明

### 6.1 协议

- 签名：`MD5(PID + time_ms + base64(body_json) + KEY_V2)`，`PID=pcWin`，`KEY_V2=94cfbda3fbfef02b93693f8bc153be82`（docs/08_signature.md）
- 信封：`{body: <base64 的 [{r,params}] 紧凑 JSON>, head:{version:"1.0", sign, pid, time, time_second}}`
- 响应：`[{msg, code, body}]`；`code != 0` → 抛 `EtsError`，server 转成 JSON 错误并映射 20004/30001 可读提示
- 公共参数：`sign_response:1, sn:"test", system:4, global_client_version:"5.7.9"`，除登录/公告/配置外附 `token`
- 登录字段：`phone/password` 用 AES-128-ECB(`k_serves`) + Base64；再整体签名

### 6.2 资源包解密（docs/06_data.md §4.2）

1. 从 `struct.contents[].url`（或 `template.url`）得到 `<md5>.zip`，下载自 `https://cdnsubject.ets100.com/made/<md5>.zip`；
2. 读取包尾 336 字节：`company[0:8]=MSTCHINA`、`pwd[16:144]`、`productid[144:176]=EPLAT`；
3. `m = MD5(pwd_text).upper()`，ZipCrypto 口令 = `m + MD5(m).upper()`（64 位大写 hex）；
4. Python 标准库 `zipfile.ZipFile.setpassword()` 解密并逐个 `read()` 校验 CRC，安全解压到 `reimpl/.state/cache/content/<stid>/`；
5. 模板包通常不加密，同一流程自动识别（无 MSTCHINA 尾块则不设口令）。

### 6.3 音频

- 包内音频（`material/content.mp3`、`ques1askaudio.mp3` 等）→ `/api/audio/<stid>/<相对路径>`，支持 Range，便于音频拖动；
- 评测录音 URL（`https://ets60.ets100.com/ugc/...`）→ `/api/remote-audio?url=...`，只允许 `ets60.ets100.com`，本地 SHA-256 命名缓存；
- 图片 → `/api/asset/<stid>/<相对路径>`；模板音频 → `/api/template-audio/<template_id>/<路径>`。

### 6.4 安全与凭据边界

- 服务只监听 `127.0.0.1`，不对外网卡开放；
- `reimpl/` 目录不含真实账号/密码/token 字面量；`account.json` / `app_token.txt` 始终在 `secrets/`；
- token 缓存写 `reimpl/.state/token.json`（`.gitignore`），退出登录只删除该文件，不碰 `secrets/`；
- 返回浏览器的数据统一遮蔽 `password / raw_phone / bind_mobile / teacher_phone / family_phone / mobile / machine_code` 等字段；
- 资源包文件名、stid、媒体路径均做白名单 / 路径穿越校验；远程媒体只允许指定域名。

---

## 7. API 清单（本地服务）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/status` | 登录态、token 来源（脱敏）、用户/E 卡摘要、服务端时间 |
| POST | `/api/login` | `{mode:"account"\|"token"\|"auto", token?}` |
| POST | `/api/logout` | 清除 `.state/token.json`（不删 secrets） |
| GET | `/api/home` | 首页聚合 |
| GET | `/api/homework?tab=&offset=&limit=` | 作业列表（含真实结构） |
| GET | `/api/homework/<id>` | 作业详情 + template 结构 |
| GET | `/api/modules` | 模块卡计数 + expand 开关 |
| GET | `/api/sets?column_id=&offset=&limit=&q=` | 套卷目录 |
| GET | `/api/sets/detail?column_id=&set_id=` | 套卷详情 |
| GET | `/api/courses?book_id=&unit_id=` | 教材 / 单元 / 模块 |
| GET | `/api/content?stid=&zip=` | 下载 + 解密 content 包，返回 JSON 与媒体 URL |
| GET | `/api/template?template_id=&zip=` | 模板结构（res/info/audio） |
| GET | `/api/config` | system/config 只读 |
| GET | `/api/mistakes`、`/api/mistake/<id>` | 错题统计 / 明细（含真实评测与录音代理 URL） |
| GET | `/api/ecards` | E 卡（敏感字段遮蔽） |
| GET | `/api/about` | 实现矩阵 / 只读接口清单 |
| GET | `/api/audio/<stid>/<path>`、`/api/asset/<stid>/<path>`、`/api/template-audio/<tid>/<path>` | 本地缓存媒体（Range 支持） |
| GET | `/api/remote-audio?url=` | 评测录音/XML 代理缓存（仅 ets60.ets100.com） |

已封装的 ETS 只读接口（`ets_client.READONLY_ENDPOINTS`，25 个）：
`system/config`、`system/time`、`user/info`、`user/get-record`、`announcement/list`、`m/ecard/list`、
`m/advertisement/list`、`m/mistake/summary`、`m/mistake/list`、`g/homework/list`、`g/resource/grade-list`、
`g/resource/book-list`、`g/resource/expand-module`、`g/resource/priority-instruction-book`、`g/set/unit-list`、
`g/set/unit-info`、`g/set/module-list`、`g/set/list`、`g/set/column-v2`、`file/download`、`g/data/sls-config`、
`p1/student/ability/sls/slsAppConfig`、`config/config/getResourcePlatformToken`、`ai/aiplat/getaitoken`、
`p1/student/config/config/ossEvaluateUploadStsToken`。

> `work/reimpl_probe` 中的 23 个真实响应样本全部对应（`m/mistake/list` 与 OSS STS 为额外 bonus）。

---

## 8. 验收自测（已实际运行）

### 8.1 启动与 HTTP 自检

```powershell
cd D:\ets-rea
python reimpl\server.py
# 另开终端：
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8787/
curl.exe -s http://127.0.0.1:8787/api/status
curl.exe -s http://127.0.0.1:8787/api/home
curl.exe -s "http://127.0.0.1:8787/api/homework?tab=todo"
curl.exe -s "http://127.0.0.1:8787/api/sets?column_id=1&limit=5"
curl.exe -s http://127.0.0.1:8787/api/modules
curl.exe -s http://127.0.0.1:8787/api/mistakes
curl.exe -s http://127.0.0.1:8787/api/config
```

实测结果（2026-11-07，真实账号 token）：

- `GET /` → **200**，返回 5.6 KB HTML；
- `/api/status` → `loggedIn=true`，token 来源 `app_token.txt`（首次实测；完成 §8.5 登录测试后为 `account`，页面只显示脱敏前缀），用户/年级/E 卡为真实数据；
- `/api/home` → 待完成 1 / 已完成 3 / 已逾期 1，模块计数 听说 104 / 读写 113 / 听力 111，错题 9；
- `/api/homework?tab=todo` → 1 条真实作业（set_id 958806，6 道子题）；
- `/api/sets?column_id=1` → 118 套；`/api/courses` → 23 本教材 / 7 个单元；`/api/config` → 497 个 key；
- 全部只读接口 `code=0`。

### 8.2 自动化验收脚本（推荐）

```powershell
# 只读 API 验收（不触发登录，不写 ETS 账号数据）
python -X utf8 reimpl\tools\smoke_test.py
```

实测输出：

```
== E 听说参考客户端验收：http://127.0.0.1:8787 ==
[PASS] GET / 返回 HTML
[PASS] GET /api/status
[PASS] GET /api/home
[PASS] GET /api/homework?tab=todo
[PASS] GET /api/homework?tab=done
[PASS] GET /api/modules
[PASS] GET /api/sets?column_id=1
[PASS] GET /api/sets?column_id=88
[PASS] GET /api/courses
[PASS] GET /api/mistakes
[PASS] GET /api/ecards
[PASS] GET /api/config
[PASS] GET /api/about
[PASS] GET /api/homework/<id>
[PASS] GET /api/content（下载 + ZipCrypto 解密）
[PASS] GET /api/audio（MP3 播放）
合计：16/16 通过
```

### 8.3 内容包 / 音频实测

```powershell
# 取待完成作业的第一道朗读题（stid=1010510，真实 content 包）
curl.exe -s "http://127.0.0.1:8787/api/content?stid=1010510&zip=1a642a08389a0a4db01a976c10d599ee.zip"
# 返回 structure_type=collector.read，material[0].url=/api/audio/1010510/material/content.mp3
curl.exe -s -o test.mp3 "http://127.0.0.1:8787/api/audio/1010510/material/content.mp3"
# test.mp3：127,362 B，MP3（ID3 头），浏览器 <audio> 可直接播放
```

- 资源包来源 `https://cdnsubject.ets100.com/made/1a642a08389a0a4db01a976c10d599ee.zip`；
- 包尾 `MSTCHINA/EPLAT` 口令块 → 派生 64 位 ZipCrypto 口令 → 本地解密；
- 首次下载后缓存到 `reimpl/.state/cache/content/1010510/`，再次打开毫秒级返回。

### 8.4 前端交互自测（可选，需 Node 22+）

```powershell
# 先以调试端口启动 Chrome（任选一个）：
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --remote-debugging-port=9222 --user-data-dir="$env:TEMP\ets-ref-chrome" about:blank
# 再运行：
node reimpl\tools\cdp_probe.js
```

实测输出（21/21）：

```
[PASS] 首页渲染 / 统计卡 / 模块卡
[PASS] 作业列表 tabs / 卡片
[PASS] 作业详情 / 试卷结构 / 题目列表
[PASS] 练习页 rail / read 题干 / 示范音频
[PASS] 展开答案与解析 / 解析文本
[PASS] 下一题切换
[PASS] 错题本统计与列表 / 系统配置表
[PASS] 模块卡 → 套卷目录、作业卡 → 详情、题目行 → 练习页、错题行 → 错题详情
[PASS] 无页面 console error / 未捕获异常
合计：21/21 通过
```

### 8.5 独立登录流程验证

> 注意：账号单会话。官方客户端在跑时，独立登录可能返回 `code 20004` 或顶掉官方客户端；只测一次，不反复登录。

`POST /api/login {"mode":"account"}` 会读取 `secrets/account.json`，按原作 `user/login` 加密签名。

**登录测试记录（2026-11-07 14:58，仅执行一次）**

- `POST /api/login {"mode":"account"}` → **HTTP 200 / code=0 / loggedIn=true**，`tokenSource=account`，
  新 token 保存到 `reimpl/.state/token.json`（页面只显示脱敏前缀）；
- 登录后 `GET /api/home` → 待完成 1 / 已完成 3，真实作业与用户数据正常；
- 登录后旧的 `secrets/app_token.txt` 调用 `user/info` 返回 **`code 30001`（账号或密码不正确）**——
  实测验证了**单会话互踢**：新登录会让官方客户端 token 失效（官方客户端需重新登录）；
- 当前后端使用 `.state/token.json` 中的新 token。若要改回官方 token：先让官方客户端重新登录生成新 token，
  删除 `reimpl/.state/token.json` 后重启服务器即可回退到 `secrets/app_token.txt`。

恢复方式：优先使用 `secrets/app_token.txt`；如 token 已失效，重新用官方客户端登录生成新 token，
或删除 `reimpl/.state/token.json` 后重启服务器。

---

## 9. 常见问题

| 现象 | 原因 / 解决 |
|---|---|
| 页面提示“无法连接本地后端” | `server.py` 未启动；或端口被占用。运行 `python reimpl\server.py --port 8790` |
| 登录提示 code 20004 | 账号已在官方客户端登录（单会话）。退出官方客户端再登录，或改用 `secrets/app_token.txt` |
| 登录提示 code 30001 | token 失效 / 账号密码错误。重新获取 token 或检查 `secrets/account.json` |
| 官方客户端被顶下线 | 单会话限制；重新登录官方客户端即可。参考客户端不写任何业务数据 |
| 首页/作业为空 | 账号未绑定有效班级 / E 卡；或该账号确实没有作业。接口会返回真实空列表 |
| 资源包下载失败 | 检查网络与 `cdnsubject.ets100.com` 可达性；删除 `reimpl/.state/cache` 重试 |
| 音频不能拖动 | 浏览器需 Range 支持；服务端已实现 `Range: bytes=`，若仍异常请刷新页面 |
| 读写模拟没有题目 | `rw_data` 只有目录信息，参考客户端未实现读写题型渲染（已在页面标注） |
| 预测分为“—” | 原作成长/预测分接口未开放，参考客户端不伪造分数 |
| 端口/路径不同 | 用 `--port`、`ETS_REIMPL_STATE_DIR`、`ETS_ACCOUNT_FILE`、`ETS_APP_TOKEN_FILE` 覆盖 |

---

## 10. 证据与延伸阅读

- `docs/08_signature.md` —— 签名算法、密钥流、字段加密（v1/v2）
- `docs/03_api_protocol.md` —— 信封、51 个 API 路径、鉴权链、评测/OSS 链路
- `docs/06_data.md` §4 —— content 包 ZipCrypto 口令与结构、template 包、音频
- `docs/04_frontend.md` —— 原作 91 条路由、9 条通道、录音评测链
- `work/scripts/probe_api.py` / `probe_endpoints.py` —— 真实登录与 23 个只读接口实测脚本
- `work/reimpl_probe/*.json` —— 23 个接口真实响应样本
- `work/data/_scripts/extract_content.py` —— 本地资源包解密参考实现

---

## 11. 免责声明

本项目仅用于**自有授权环境下的互操作性研究与教学**。请勿用于绕过服务端鉴权、批量抓取、侵犯他人账号或商业用途。
参考客户端不实现任何写操作（录音评测、考试提交、OSS 上传），不会修改 ETS 账号数据。

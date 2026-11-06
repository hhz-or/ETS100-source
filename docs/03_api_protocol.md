# ETS 学生端 PC（STIC/CEF 壳）API 与协议分析（03）

- 版本：v1.0（2026-11-06）
- 分析对象：`D:\ets-rea\ETS`（只读）
- 分析者：api-analyst（Team Lead：lead）
- 数据来源：`ETS/mq_server/main.js`（明文 Node 源码）、`ETS/packages/app.json`、`ETS/packages/default/appcontroller.js`、`ETS/logs/ets_2026-10-28.log`、`ets_2026-11-4.log`、`cef_2026-10-28.log`、`cef_2026-11-4.log`、`shell_2026-10-28.log`、`shell_2026-11-4.log`
- 配套产物：`work/api/endpoints.csv`、`work/api/sign_samples.json`、`work/api/endpoint_samples.json`、`work/api/reports/`（证据报表）

标注约定：**【观察】**=日志/源码直接可见；**【推断】**=由多处观察推导，未直接证实；**【未知】**=现有数据不足。

---

## 0. 结论摘要

1. **mq_server 不是命令型服务，而是无协议的“日志回传中继”**：`main.js` 只有 144 行，作用是把任意 WebSocket 客户端发来的文本**原样广播给所有连接**，并把每条收到的消息写入 `logs/ets_<年-月-日>.log`。**没有** log/config 等消息类型分发逻辑（任务书假设的“命令类型”不存在）。【观察】
2. **端口 40001 起自增探测**，并把最终端口写回 `packages/app.json` 的 `suspensionBallPort` 字段；前端页面实际连接 `ws://127.0.0.1:40001/`。【观察】
3. **前端→HTTP API 采用统一信封**：`{body:[{r,params}], head:{version,sign,pid,time,time_second}}`，`head.sign` 为 32 位小写十六进制（MD5 形态），签名协议版本 `v2`；签名代码在 **ETSShell.exe 原生层**（`etshelper/encode_api_body_v2`）。**签名算法本身尚未还原**，已准备 334 组“原文 body + sign + time + path”样本供验证。【观察 + 未知】
4. 日志内共还原 **51 个 api.ets100.com 路径**（其中 2 个为仅出现在 cef 网络日志的点服 GET 路径），另有 **12 条非 api 主机端点**（collect 埋点 1 条 + CDN/OSS/SLS/第三方/静态页面 11 条）。全部业务 API 走 HTTPS；响应为 `[{msg,code,body}]` 信封，观察到的 335 个业务响应 `code` 全为 0。【观察】
5. **鉴权链有 4 套独立凭证**：①登录 JWT（160 字符，HS256，`params.token`）；②资源平台 JWT（504 字符，RS256，`qm-ets-key`，走 URL query，用途未见）；③AI 评测 accessToken（137 字符，HS256，`aid=ksyyyxx-etszx`）；④阿里云 STS（OSS 直传 / SLS 日志）。【观察】
6. **日志编码重要更正**：`ets_*.log`、`cef_2026-10-28.log` 为纯 UTF-8（0 个 U+FFFD、0 个“锟斤拷”）；`shell_*.log` 为 GB18030；`cef_2026-11-4.log` 仅 1 行非 UTF-8。此前看到的 `�ɹ�` 是 PowerShell 控制台/管道按 cp936 解码造成的显示假象，**不是数据本身损坏**，不要对 ets 日志做 GBK 二次解码（会破坏 sign 原文）。【观察】

---

## 1. 数据源与统计口径

| 文件 | 大小 | 行数 | 编码 | 内容 |
|---|---|---|---|---|
| `ETS/logs/ets_2026-10-28.log` | 6,910,058 B | ≈1,979 | UTF-8 | mq_server 落盘日志（前端上报） |
| `ETS/logs/ets_2026-11-4.log` | 5,255,123 B | ≈3,023 | UTF-8 | 同上（另一次启动/会话） |
| `ETS/logs/cef_2026-10-28.log` | 15,703,293 B | 115,951 | UTF-8 | Chromium CEF 详细日志（含全部 URL 请求、无障碍树） |
| `ETS/logs/cef_2026-11-4.log` | 1,407,391 B | 10,868 | UTF-8（1 行例外） | 同上 |
| `ETS/logs/shell_2026-10-28.log` | 519,301 B | 6,727 | GB18030 | ETSShell.exe 原生日志（含 encode_api_body_v2） |
| `ETS/logs/shell_2026-11-4.log` | 1,437,761 B | 19,496 | GB18030 | 同上 |

日志核心计数（两文件合计）：

| 指标 | 数量 | 说明 |
|---|---|---|
| mq_server 落盘行 | 5,002 | 其中 16 行为服务端自身事件，其余 4,986 行是 `received:` |
| 带 `[I]/[E] [TAG]` 的上报消息 | 4,986 | 见 §2.5 标签表 |
| `[API_ETS] ets request` | 342 | 151（10-28）+ 191（11-4） |
| `[API_ETS] ... ets response` | 341 | 150 + 191，1 个请求在日志边界处缺响应 |
| 带 `head.sign` 的请求 | 334 | 100% 提供 `param_json_exact` 与逐字节一致的 `body_json_exact` |
| 不同 api 路径（归一化 `//`） | 51 | 见 `endpoints.csv` |
| 业务响应 `code` 分布 | `0`×335、空串×6 | 空串为 point-service `""` 响应 |

---

## 2. mq_server（WebSocket 日志中继）完整协议

源码：`ETS/mq_server/main.js`（144 行，明文）；`package.json` 声明依赖 `ws@^8.17.0`，但 `ETS/mq_server/node_modules` 中实际存在 **log4js 0.6.38** 与 **ws 1.1.2**（旧版）；`ets_mq_server.exe`（12,080,168 B）为 pkg 打包产物、内部字符串不可见，运行时真正打包的版本【未知】。配置 `ETS/packages/app.json`，运行期内容恒为 `{"suspensionBallPort":40001}`。【观察】

### 2.1 启动与端口探测

```text
createWebSocketServer("demo.log")        // main.js:11 参数被忽略（函数无参）main.js:12
  port = 40001                            // main.js:13
  findAvailablePort()                     // main.js:61-70, 143
    checkPort(port)                       // main.js:15-32  net.createServer().listen(port,"0.0.0.0")
      listen 成功 → close() → resolve(false)  → createWebSocketServerWithPort(port)
      listen EADDRINUSE → resolve(true)   → port++ → 递归 findAvailablePort()
      其它 error → resolve(false)  → 直接 createWebSocketServerWithPort(port)
```

- 监听地址为 **`0.0.0.0`**（不是 127.0.0.1），端口从 40001 单调 +1 探测；**没有上限检查**，若 40001–65535 全部占用会一直递归到 `listen` 抛 `EADDRINUSE`/`ERR_SOCKET_BAD_PORT`（异常路径）。【观察（代码）】
- `wss = new WebSocketServer({port})` 省略 host，`ws` 库同样绑定全部网卡；**无鉴权、无来源校验**。【观察（代码）】
- 端口确定后：`log4js.configure(...)`（main.js:90-99，`appenders` 用**数组**写法，与 `node_modules` 中 log4js 0.6.38 的 API 一致）、随后 `logger.info("mq_server running! port is " + port)`（main.js:101）。
- 实测日志：`mq_server running! port is 40001`（`ets_2026-10-28.log:1`、`ets_2026-11-4.log:1`、`ets_2026-11-4.log:26`）。【观察】

### 2.2 与 `packages/app.json` 的关系（端口注册表）

`main.js:6` `configUrl = "../packages/app.json"`（相对 mq_server 的工作目录，即 `ETS/packages/app.json`）。

```text
readAppConfig()  // main.js:34-49  读取失败/空 → "{}"；JSON.parse 异常也 resolve({})
  config = {} 时 config 为真 → flag1 = config.suspensionBallPort 存在且 != port
                             flag2 = !config.suspensionBallPort
  if (flag1 || flag2) { config.suspensionBallPort = port; writeAppConfig(config) }
  else 分支（writeAppConfig({suspensionBallPort:port})）实际不可达（{} 也为真）
writeAppConfig() // main.js:51-59  JSON.stringify 后覆盖写入（无缩进）
```

实测对应日志（首次启动，app.json 缺失/无端口）：

```text
ets_2026-10-28.log:1  mq_server running! port is 40001
ets_2026-10-28.log:2  read_app_config_fail {}          // readFile 失败（当时文件不存在）
ets_2026-10-28.log:3  update port to 40001
ets_2026-10-28.log:4  write_app_config_success {"suspensionBallPort":40001}
ets_2026-11-4.log:2   read_app_config_success {"suspensionBallPort":40001}   // 已存在 → 不重写
```

- `read_app_config_fail` 后的第二参数实际被 log4js 打印为 `{}`（`err || !data ? "{}" : data`，main.js:37-40）。【观察】
- 谁消费这个端口：`shell_2026-10-28.log:84` 出现 `ClientAppHandler.h(112) josn::parse app.json, error: 2`（首次启动时 app.json 尚不存在，error 2=文件不存在），说明 **ETSShell.exe 原生层读取/解析 app.json**【观察】；同日志 `shellhelper::PlnOnProcessMessage action->getconfig`（`shell_2026-10-28.log:73`）表明 JS 通过 CEF 桥 `shellhelper/getconfig` 取配置【推断：端口即由该 action 返回】；页面实际连接 `ws://127.0.0.1:40001/`（`cef_2026-10-28.log:205`、`cef_2026-11-4.log:149`、`cef_2026-11-4.log:419`）。若端口被占用升到 40002，本数据集未观察到，客户端如何跟随【未知】。

进程生命周期（原生日志）：

```text
shell_2026-10-28.log:67/72  existfileorfolder ...\mq_server\ets_mq_server.exe (stat-size 12080168)
shell_2026-10-28.log:75     action->processexist
shell_2026-10-28.log:76     OnProcessExist:ets_mq_server.exe
shell_2026-10-28.log:80     action->startprocess
shell_2026-10-28.log:81     OnStartProcess reStart: true
shell_2026-10-28.log:6718   OnStopProcess stop process, {"process_list":["ets_mq_server.exe"]}
```

即由 ETSShell.exe 负责“检查是否存在→启动→退出时杀掉” mq_server。【观察】

### 2.3 日志文件命名与落盘

`getLogFileName()`（main.js:72-85）：`"../logs/ets_" + 年 + "-" + 月 + "-" + 日 + ".log"`，其中月/日 **不补零**（补零代码被注释，main.js:79-80）。因此实际文件名为 `ets_2026-10-28.log`、`ets_2026-11-4.log`（不是 `11-04`）——与目录内文件名完全吻合，可反证该代码路径生效。【观察】

- log4js appender：`console` + `file`（filename=上面的路径，category=`mq_server`）；`logger = log4js.getLogger("mq_server")`。落盘格式：`[YYYY-MM-DD HH:mm:ss.SSS] [INFO|ERROR] mq_server - <message>`。【观察】
- 文件按“进程启动日”命名（不是按每条消息日期滚动），跨午夜不切换。【推断（代码）】

### 2.4 连接处理与消息中继

```text
wss.on("connection", ws => {                       // main.js:116
  logger.info("new connection: %s", ws)            // → "new connection: [object Object]"
  ws.on("message", message => {                    // main.js:118
    logger.info("received: %s", message)           //   原样落盘（Buffer→字符串按 %s）
    wss.broadcast(message)                         //   广播给全部 client（含发送者自己）
  })
  ws.on("open", ...)                               // main.js:122-124  ← 服务端 socket 无 open 事件，死代码（日志中从未出现 "open..."）
  ws.on("close", (code,reason)=> logger.info("close, code : %s, reason: %s", ...))   // main.js:125-127
  ws.on("error", err => logger.error("error: %s", err))                               // main.js:128-130
  ws.send("hello mq_server!")                      // main.js:132 连接建立后服务端唯一主动下行
})
wss.broadcast = data => wss.clients.forEach(c => c.send(data))   // main.js:135-139
```

要点：

- **无消息类型/命令分发**：`message` 回调不解析内容，不做 log/config/... 分支；`demo.log` 参数、`getLogFileName` 之外的“config 交互”都发生在服务端自身（app.json 读写），与客户端消息无关。【观察】
- **广播即回显**：`clients.forEach` 包含发送方，客户端会收到自己刚发出的消息；`ws.send` 未检查 `readyState`。【观察（代码）】
- **无心跳/无超时/无重连逻辑**；连接断开由客户端负责重连（本数据集未观察到重连消息）。【观察 + 未知】
- 连接握手：服务端下行 `hello mq_server!`（明文文本帧），随后客户端首条上行是**不带 `[TAG]` 前缀**的握手文本 `ets_mq_server.exe连接成功，端口号:40001`，之后才是带前缀的业务日志。【观察】

### 2.5 WebSocket 消息格式（应用层）

上行文本格式（唯一格式）：

```text
[<级别>] [<TAG>] <payload>
级别：I（Info）/ E（Error）—— 本数据集仅见这两种
TAG ：MISC / API_ETS / FLOW_PRAC / PLG_STIC / H5_SOUND / ENG_SCORE / UI_PAGE
payload：纯文本，或 JSON 对象文本（部分 TAG 混用）
```

`payload` 是**自由文本**：服务器不解析，落盘后直接可读；`}`/`{` 出现在 payload 中不转义，单条消息为一行（payload 内不含裸换行）。【观察】

标签统计（两日志合计 4,986 条）：

| 级别 | TAG | 条数 | payload 形态（观察） |
|---|---|---|---|
| I | `MISC` | 1779 | 纯文本（含少量 JSON 片段），业务提示/网络/设备/配置刷新 |
| I | `API_ETS` | 913 | 纯文本：`ets request ...` / `ets response ...` / 上传提示（见 §4.1） |
| I | `FLOW_PRAC` | 632 | 混合：233 条 JSON（套题流程 exam_step）、400 条纯文本（播放/录音流程） |
| I | `PLG_STIC` | 594 | 混合：453 条纯文本（下载/解压/录音）、240 条 JSON（`optype` 操作与回调） |
| I | `H5_SOUND` | 478 | 纯文本：`播放前：原地址...`、`onplay/onpause/onend` |
| I | `ENG_SCORE` | 420 | 纯文本：AI 评测连接/开始帧/结果/错误（含大 JSON） |
| I | `UI_PAGE` | 46 | 纯文本：`从<from> 页面跳转: <to>` |
| E | `PLG_STIC` | 99 | 同 PLG_STIC（多为 ExistFileOrFolder result=false） |
| E | `MISC` | 19 | `SlsUtils credentials还没有值`、`测试URL ... 失败` 等 |
| E | `ENG_SCORE` | 3 | `recorder iseManager.onerror失败 ...`/评测失败 |
| E | `API_ETS` | 2 | `获取不到token的情况 ... sessionToken: null` |
| E | `FLOW_PRAC` | 1 | `录音评测任务处理完 , 失败任务...` |
| — | **合计** | **4986** | — |

代表性消息（含 file:line 证据）：

| TAG | 示例（脱敏） | 证据 |
|---|---|---|
| 握手（无 TAG） | `ets_mq_server.exe连接成功，端口号:40001` | `ets_2026-10-28.log:6`、`ets_2026-11-4.log:4` |
| API_ETS | `ets_sign_protocol_selected protocol=v2, pid=pcWin` | `ets_2026-10-28.log:7`、`ets_2026-11-4.log:5` |
| API_ETS | `ets request $api_name=https://api.ets100.com/system/config param={...}` | `ets_2026-10-28.log:11` |
| API_ETS | `154ms ets response $api_name=... requestId=... return=[{...}]` | `ets_2026-10-28.log:16` |
| API_ETS | `ets request {"url":"http://collect.ets100.com/log_collector","method":"post","data":"type=Event_Startup&..."}` | `ets_2026-10-28.log:95` |
| MISC | `测试当前网络的 URL：http://file.fei.ets100.com/network_test, 网络状态: 正常, ...1.25MB/s` | `ets_2026-10-28.log:18` |
| MISC | `windows操作系统版本 env type: Microsoft Windows 11; device_name: D7480; device_code: 4437...; local_ip: ...` | `ets_2026-10-28.log:21` |
| MISC | `当前资源平台token已过期；开始请求配置数据` | `ets_2026-10-28.log:55`、`ets_2026-11-4.log:66` |
| MISC | `AI引擎token已过期；开始请求配置数据` | `ets_2026-10-28.log:163` |
| MISC | `当前配置已过期；开始请求oss的配置数据` | 同日志多处（MISC 子类统计见 `reports/keywork_and_misc.txt`） |
| UI_PAGE | `从/app-start 页面跳转: /auth/login` | `ets_2026-10-28.log:17` |
| PLG_STIC | `start download file: {"url":"https://cdnfeis.../file/...zip","local_file":"clear_cache.zip",...}` | `ets_2026-10-28.log:15` |
| PLG_STIC | `{"optype":"ExistFileOrFolder","path":"...","result":false,"size":0}` | `ets_2026-10-28.log:397` |
| H5_SOUND | `播放前：原地址： stic://file.iflytek.com/C:\...\1_desc.mp3, 播放地址：...` | `ets_2026-10-28.log:428` |
| ENG_SCORE | `id: 1793186560729, sdk:AI2 , 评测发送开始帧：{...}` | `ets_2026-10-28.log:479` |
| FLOW_PRAC | `{"title":"套题流程: ","set_id":"...","entity_id":"...","order":"...","log_name":"exam_step"}` | `ets_2026-10-28.log:420` |

> 注：`[API_ETS]` 一条“记录”可能是 request / response / 上传提示等不同语句，共 913 条（10-28 与 11-4 累计），其子类型统计见 §4.1。

### 2.6 典型时序（一次启动）

```mermaid
sequenceDiagram
    participant S as ETSShell.exe
    participant M as ets_mq_server.exe
    participant P as CEF 前端页面
    S->>S: 启动、etshelper/filehelper/httphelper init
    S->>S: shellhelper/getconfig（读 packages/app.json，首次 error:2）
    S->>S: existfileorfolder mq_server/ets_mq_server.exe
    S->>M: startprocess（reStart:true）   [shell_2026-10-28.log:80-81]
    M->>M: 端口探测 40001 → ws Server
    M->>S: write_app_config_success {"suspensionBallPort":40001}  [ets_2026-10-28.log:4]
    P->>M: WS 连接 ws://127.0.0.1:40001/   [cef_2026-10-28.log:205]
    M->>P: "hello mq_server!"              [main.js:132]
    P->>M: "ets_mq_server.exe连接成功，端口号:40001"  [ets_2026-10-28.log:6]
    M->>M: log4js 落盘
    P->>M: "[I] [API_ETS] ets request ..."
    M->>M: received + broadcast（回显给所有客户端）
    ... 运行期持续 ...
    M->>M: close, code : 1006（客户端异常退出） [ets_2026-10-28.log:1979]
    S->>M: stop process ets_mq_server.exe  [shell_2026-10-28.log:6718]
```

异常路径（日志实证）：

| 场景 | 观察 | 证据 |
|---|---|---|
| 客户端“正常/异常”断开 | `close, code : 1006, reason:`（1006=abnormal closure，无 close 帧，多为进程被杀/崩溃） | `ets_2026-10-28.log:1979`、`ets_2026-11-4.log:3023` |
| 服务端启动时 app.json 不存在 | `read_app_config_fail {}` 后仍写入端口 | `ets_2026-10-28.log:2-4` |
| 端口占用 | 代码设计为 +1 重试；本数据集未出现 | `main.js:61-70` |
| `ws.on("open")` | 永不触发（服务端无 open 事件），日志无 `open...` | `main.js:122-124` |
| 广播异常 | 未检查 readyState；无 error 日志出现 | `main.js:135-139` |

---

## 3. 前端 HTTP API 协议（api.ets100.com 统一信封）

### 3.1 请求信封

`[API_ETS] ets request $api_name=<URL> param=<JSON>`（`ets_2026-10-28.log:8/10/11`…）【观察】

```json
{
  "body": [
    {
      "r": "user/info",
      "params": {
        "sign_response": 1,
        "sn": "test",
        "system": 4,
        "global_client_version": "5.7.9",
        "token": "***",
        "...": "业务参数"
      }
    }
  ],
  "head": {
    "version": "1.0",
    "sign": "0123456789abcdef0123456789abcdef",
    "pid": "pcWin",
    "time": "1793184960949",
    "time_second": 1793184960949
  }
}
```

- `api_name` 是完整 URL；`r` 是相对路由（与 URL 路径一致，但有的模块会自带前导 `/`，导致实际 URL 出现 **`//`**，如 `https://api.ets100.com//m/audio/sync-v2`、`//announcement/list`、`//g/set/mark-txt`、`//m/homework/info`、`//m/set/column`、`//g/pk/summary-word`、`//config/config/getResourcePlatformToken`）。同一接口在另一模块下又会以单斜杠出现（例：`/g/set/mark-txt` 15 次、`//g/set/mark-txt` 14 次，业务语义相同）。服务端接受双斜杠。【观察】
- `head.time` 为毫秒时间戳**字符串**，`time_second` 为同值**数字**；`head.version` 恒 `"1.0"`，`pid` 恒 `"pcWin"`；`head` 5 个字段 100%（334/334 带 sign 的请求）。【观察】
- 无 sign 的请求只有两类：`point-service/account/trail`（`param={}`，GET 型）与 `log_collector`（`param={"url","method","data"}` 非信封格式）。【观察】
- **HTTP 方法**：RPC 类请求的方法日志中未直接出现，按“body+head 信封、axios 直接请求记录”推断为 **POST+JSON**；`announcement.txt` 为 **GET**、`log_collector` 为 **POST form-urlencoded**（二者由 axios `config` 直接记录）。【推断 + 观察】

公共参数（多接口复用）：

| 参数 | 观察值/形态 | 出现范围 |
|---|---|---|
| `sign_response` | 恒 `1` | 全部业务请求 |
| `sn` | 恒 `"test"` | 全部业务请求 |
| `system` | 恒 `4`（PC 端） | 全部业务请求 |
| `global_client_version` | 恒 `"5.7.9"` | 全部业务请求 |
| `token` | 登录 JWT（160 字符，`***`） | 除登录/验证码/公告/配置外 |
| `checkToken` | `false`（免登录接口：`system/config`、`/announcement/list`） | 部分 |
| `use_https` | `1` | `file/download`、`g/set/list`、`g/homework/list`、`g/set/mark-txt` |
| `key` | `"pc_stic_tools"` | `file/download` |
| `version` | `1` | 多接口 |
| `parent_account_id` | 子账号 id（如 `***`） | 学习/作业/错题类 |

### 3.2 响应信封

`<N>ms ets response $api_name=<URL> requestId=<uuid> return=<JSON>`（`ets_2026-10-28.log:12-16`）【观察】

```json
[{"msg": "成功", "code": 0, "body": { /* 业务体 */ }}]
```

- `requestId` 形如 `5da4b73c-2ab7-9a3b-88a5-16f3ce4d9e56`，341 个响应 requestId 全部唯一。【观察】
- 耗时 `<N>ms` 分布：min 28 / max 4512 / avg 167（`reports/stats.txt`）。【观察】
- 335 个响应 `code=0,msg="成功"`；6 个 `point-service/account/trail` 响应体为空字符串 `""`。【观察】
- 直接文件型请求的响应不是信封，而是 axios response 结构 `{data,status,statusText,headers,config}`（例：`https://cdnfei.ets100.com/system/announcement.txt`、`http://collect.ets100.com/log_collector`）。【观察】

### 3.3 签名（sign）协议 v2

- 启动即声明：`ets_sign_protocol_selected protocol=v2, pid=pcWin`（`ets_2026-10-28.log:7`）。【观察】
- `head.sign`：32 位小写 hex（MD5 长度），334 个请求全部存在且各不相同形态；样本见 `work/api/sign_samples.json`。【观察】
- 签名由**原生层**生成：`shell_2026-11-4.log` 中 `[etshelper::PlnOnProcessMessage] action->encode_api_body_v2` 出现 192 次、`[etshelper::OnEncodeAPIBody] success` 192 次；`shell_2026-10-28.log` 分别 157 次。与同日 ets 日志请求数（151 / 191）近似 1:1（差值可能为失败重试/未落盘请求）。【观察 + 推断】
- **签名原文/算法未还原**：已按任务要求准备 **334 组**样本，字段：
  - `body_json_exact`：从日志 `param` 中按括号配对**逐字节截取**的 `"body":[...]` 原文（334/334 与 `json.dumps(json.loads(...))` 无空格重序列化**完全一致**，可安全当原文用）；
  - `param_json_exact`：整个 `param` 原文；
  - `head_json_exact`、`sign`、`time`、`time_second`、`url`、`path`、`host`、`route`。
  - 校验：`work/api/sign_samples.json` 每条均带 `body_exact_roundtrip: true`（334/334），即 `body_json_exact` 与按 JSON 重序列化结果逐字节一致。
- 建议 Lead 验证方向（仅假设，未证实）：`md5(body_raw)` / `md5(body_raw+time)` / `md5(url+body_raw+time+密钥)` 等；`head.time` 与 `time_second` 同值说明参与签名的很可能是毫秒时间戳本身。【未知】

### 3.4 直接 HTTP（非信封）请求

| 请求 | 方法 | 请求头（观察） | 说明 | 证据 |
|---|---|---|---|---|
| `https://cdnfei.ets100.com/system/announcement.txt` | GET | `Accept: application/json, text/plain, */*`、`Cache-Control: no-cache`、`Pragma: no-cache` | 62 B 静态 JSON：`{"1":{},"2":{},"4":{},"8":{},"16":{},"32":{},"64":{},"128":{}}`；响应 `Server: AliyunOSS` + CDN 头 | `ets_2026-10-28.log:9`、`ets_2026-11-4.log:7`；`reports/axios_configs.json` |
| `http://collect.ets100.com/log_collector` | POST | `Content-Type: application/x-www-form-urlencoded`、`Accept: application/json, text/plain, */*` | 启动埋点：`type=Event_Startup&version=5.7.9&system=Microsoft Windows 11&account_id=***&date_time=YYYY-MM-DD HH:mm:ss`；响应 `success\n` | `ets_2026-10-28.log:95/103`、`ets_2026-11-4.log:101/109` |
| `http://file.fei.ets100.com/network_test` | GET | — | 网络连通/测速探针；因页面为 https，Chromium 报 Mixed Content（`cef_2026-10-28.log:118`、`cef_2026-11-4.log:78`） | `ets_2026-10-28.log:18` |
| `https://ets60.oss-cn-hangzhou.aliyuncs.com` | POST 表单 | `Content-Type: multipart/form-data`（OSS PostObject） | 录音 mp3/spx/xml 直传，见 §6 | `ets_2026-10-28.log:514` 等 |

---

## 4. API 清单（按业务域）

> 完整机读清单见 `work/api/endpoints.csv`（63 行 = 51 个 api.ets100.com 路径 + 1 个 collect.ets100.com 埋点 + 11 条 CDN/OSS/SLS/第三方/静态页面端点；`//` 前缀已归一化为 `/`，原文双斜杠见 §3.1）。
> 请求/响应示例（已脱敏）见 `work/api/endpoint_samples.json`；证据区号为 `日志名:行号`。

### 4.1 [API_ETS] 子类型统计

| 子类型 | 条数 | 例 |
|---|---|---|
| `ets request $api_name=... param=...` | 340 | `ets_2026-10-28.log:8` |
| `ets request {"url":...}`（log_collector） | 2 | `ets_2026-10-28.log:95` |
| `ets response ... return=...` | 341 | `ets_2026-10-28.log:12` |
| 上传提示：`<file>上传文件请求地址：..., 表单数据： {...}` | 约 108（每次 3 文件） | `ets_2026-10-28.log:514/517/519` |
| 上传结果：`<file>上传文件成功： "{\"rncode\":0,...}"` | 约 108 | `ets_2026-10-28.log:520` |
| `ets_sign_protocol_selected protocol=v2, pid=pcWin` | 2 | `ets_2026-10-28.log:7` |
| `获取不到token的情况... sessionToken: null` | 2 | `ets_2026-10-28.log:36/39` |

### 4.2 业务端点总表

> 完整机读清单见 `work/api/endpoints.csv`；下表按业务域分组，次数为两日日志中 `[API_ETS] ets request` 计数（cef URL 计数见 CSV 的 `cef_url_count` 列）。

**登录与账号**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/user/get-record` | api.ets100.com | 6 | 学习记录(按 resource_id/type) | `ets_2026-10-28.log:130` |
| POST | `/account/get-bind-info` | api.ets100.com | 3 | 账号绑定信息(手机/邮箱/学校/地区) | `ets_2026-10-28.log:30` |
| POST | `/user/info` | api.ets100.com | 3 | 用户资料(账号id/学校/班级/年级/手机) | `ets_2026-10-28.log:109` |
| POST | `/user/user/getLoginInfo` | api.ets100.com | 2 | 登录信息/账号类型(accountType) | `ets_2026-10-28.log:28` |
| POST | `/code/send` | api.ets100.com | 1 | 发送短信验证码(phone 加密串) | `ets_2026-10-28.log:37` |
| POST | `/user/login` | api.ets100.com | 1 | 账号密码登录(device_name/device_code/local_ip) | `ets_2026-11-4.log:55` |
| POST | `/user/register-or-login` | api.ets100.com | 1 | 注册或登录(手机号+验证码/密码) | `ets_2026-10-28.log:40` |
| POST | `/user/set-recent-resource` | api.ets100.com | 1 | 设置最近使用资源 | `ets_2026-10-28.log:56` |

**启动引导（资源包下载 / 公告）**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/file/download` | api.ets100.com | 7 | 按 key 取文件/资源包(clear_cache.zip/common.zip)，返回 CDN url | `ets_2026-10-28.log:8` |
| POST | `/announcement/list` | api.ets100.com | 3 | 公告列表(detail/title) | `ets_2026-10-28.log:10` |

**系统与配置**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/system/config` | api.ets100.com | 56 | 系统配置(开关/文案/白名单/引擎策略)，keywork 可按关键字拉取 | `ets_2026-10-28.log:11` |
| POST | `/system/time` | api.ets100.com | 4 | 服务器时间校准(与 head.time 对应) | `ets_2026-10-28.log:138` |

**凭证与云资源**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/p1/student/config/config/ossEvaluateUploadStsToken` | api.ets100.com | 5 | 获取 OSS STS + 上传路径(mp3/spx/xml/photoRead) | `ets_2026-10-28.log:60` |
| POST | `/g/data/sls-config` | api.ets100.com | 4 | SLS 日志服务凭证(evaluation-sdk-log) | `ets_2026-10-28.log:58` |
| POST | `/p1/student/ability/sls/slsAppConfig` | api.ets100.com | 4 | SLS 日志服务凭证(app-general-log) | `ets_2026-10-28.log:59` |
| POST | `/ai/aiplat/getaitoken` | api.ets100.com | 2 | 获取 AI 评测引擎 accessToken(expiresIn) | `ets_2026-10-28.log:168` |
| POST | `/config/config/getResourcePlatformToken` | api.ets100.com | 2 | 获取资源平台 JWT(token/expireAt/timeout) | `ets_2026-10-28.log:61` |

**资源目录（年级/书本/模块）**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/g/resource/grade-list` | api.ets100.com | 14 | 年级列表 | `ets_2026-10-28.log:80` |
| POST | `/g/resource/expand-module` | api.ets100.com | 7 | 功能模块开关表 | `ets_2026-10-28.log:125` |
| POST | `/g/resource/priority-instruction-book` | api.ets100.com | 6 | 优先指导书 | `ets_2026-10-28.log:128` |
| POST | `/g/resource/book-list` | api.ets100.com | 4 | 教材/书本列表 | `ets_2026-10-28.log:98` |

**套题 / 栏目 / 单元**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/g/set/mark-txt` | api.ets100.com | 14 | 标注文本(mark_txt) | `ets_2026-10-28.log:364` |
| POST | `/g/set/ppr-res` | api.ets100.com | 14 | 套题资源详情(批量 batch) | `ets_2026-10-28.log:362` |
| POST | `/g/set/column-v2` | api.ets100.com | 12 | 栏目列表(v2) | `ets_2026-10-28.log:134` |
| POST | `/g/set/module-list` | api.ets100.com | 10 | 模块列表 | `ets_2026-10-28.log:142` |
| POST | `/g/set/unit-info` | api.ets100.com | 9 | 单元详情 | `ets_2026-10-28.log:108` |
| POST | `/g/set/list` | api.ets100.com | 7 | 套题列表(按 column/book) | `ets_2026-10-28.log:129` |
| POST | `/g/set/unit-list` | api.ets100.com | 6 | 单元列表 | `ets_2026-10-28.log:102` |

**作业**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/g/homework/list` | api.ets100.com | 29 | 作业列表(状态/分页/计数/结构) | `ets_2026-10-28.log:131` |
| POST | `/g/homework/checkstart` | api.ets100.com | 7 | 作业开始校验(解锁/服务端时间) | `ets_2026-10-28.log:353` |
| POST | `/g/homework/plan-list` | api.ets100.com | 1 | 作业计划列表 | `ets_2026-11-4.log:269` |

**学习与激励（PK/单词/健康平台）**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/g/pk/count` | api.ets100.com | 1 | PK 次数统计 | `ets_2026-11-4.log:267` |
| POST | `/g/pk/summary-word` | api.ets100.com | 1 | PK 单词总结 | `ets_2026-11-4.log:275` |
| POST | `/g/user/jkpt-info` | api.ets100.com | 1 | 健康平台(jkpt)绑定信息 | `ets_2026-10-28.log:263` |
| POST | `/g/word/new-notebook` | api.ets100.com | 1 | 新建单词本 | `ets_2026-11-4.log:276` |

**评测与作业记录**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/m/audio/sync-v2` | api.ets100.com | 36 | 录音评测结果同步(核心业务上报, 评分/上传id) | `ets_2026-10-28.log:525` |
| POST | `/m/homework/info` | api.ets100.com | 11 | 作业详情/最近完成记录 | `ets_2026-10-28.log:354` |
| POST | `/m/homework/set-use-time` | api.ets100.com | 4 | 作业用时上报(user_time) | `ets_2026-10-28.log:1879` |

**错题**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/m/mistake/summary` | api.ets100.com | 7 | 错题统计 | `ets_2026-10-28.log:126` |
| POST | `/m/mistake/check` | api.ets100.com | 4 | 错题检查 | `ets_2026-10-28.log:399` |
| POST | `/m/mistake/update` | api.ets100.com | 3 | 错题更新(同步 timestamp) | `ets_2026-10-28.log:1865` |
| POST | `/m/mistake/list` | api.ets100.com | 1 | 错题列表(含 score_detail) | `ets_2026-11-4.log:223` |

**学习卡/广告/商品/资讯/配音**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| POST | `/m/advertisement/list` | api.ets100.com | 7 | 广告位列表 | `ets_2026-10-28.log:127` |
| POST | `/m/ecard/list` | api.ets100.com | 7 | 电子卡/学习卡列表 | `ets_2026-10-28.log:44` |
| POST | `/m/set/column` | api.ets100.com | 2 | 栏目列表 | `ets_2026-10-28.log:520` |
| POST | `/m/dub/list` | api.ets100.com | 1 | 配音/朗读作品列表 | `ets_2026-11-4.log:273` |
| POST | `/m/info/list` | api.ets100.com | 1 | 资讯列表 | `ets_2026-11-4.log:271` |
| POST | `/m/product/list` | api.ets100.com | 1 | 商品/权益列表 | `ets_2026-10-28.log:201` |
| POST | `/m/resource/add-v2` | api.ets100.com | 1 | 添加资源(账号+学校层级+教材) | `ets_2026-10-28.log:47` |

**积分服务（独立服务，JWT 走 URL）**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| GET | `/point-service/account/trail` | api.ets100.com | 6 | 积分服务试用账号(URL query 携带 JWT) | `ets_2026-10-28.log:165` |
| GET | `/point-service/homework/rank/list` | api.ets100.com | 0 | 作业排行榜(URL query 携带 JWT) | `cef_2026-10-28.log:108683` |

**埋点 / 静态 / 直传 / 第三方**

| 方法 | 路径 | host | 次数 | 用途（推断） | 示例证据 |
|---|---|---|---|---|---|
| GET | `/ets-student-pc-web/index.html` | statics.ets100.com | 8903 | 前端 SPA 入口(?tdt=时间戳) | `cef_2026-10-28.log:17` |
| GET | `/network_test` | file.fei.ets100.com | 1111 | 网络连通性/测速探针 | `ets_2026-10-28.log:18` |
| GET | `/common/pc-listen.html` | statics.ets100.com | 459 | 前端跟读页面(?token=JWT&time=) | `cef_2026-10-28.log:8627` |
| POST | `/logstores/app-general-log` | ets-vpc-log.cn-hangzhou.log.aliyuncs.com | 288 | 阿里云 SLS 应用日志上报 | `cef_2026-10-28.log(URL)` |
| POST(multipart) | `/` | ets60.oss-cn-hangzhou.aliyuncs.com | 216 | OSS 直传录音(mp3/spx/xml)，表单含 STS/policy/signature/key | `ets_2026-10-28.log:514` |
| GET | `/common/pc-listen-answer.html` | statics.ets100.com | 158 | 前端答题页面(?token=JWT&time=) | `cef_2026-10-28.log` |
| POST | `/ai-thor-data-collector/feedback/batchUpload` | ai-thor.eduaiplat.com | 151 | AI 数据反馈批量上传(评测反馈) | `cef_2026-10-28.log(URL)` |
| POST | `/logstores/evaluation-sdk-log` | ets-vpc-log.cn-hangzhou.log.aliyuncs.com | 76 | 阿里云 SLS 评测 SDK 日志上报 | `cef_2026-10-28.log(URL)` |
| GET/POST | `/app/h5/v1` | jic.talkingdata.com | 6 | TalkingData 埋点(appid=495EB...) | `cef_2026-11-04.log:928` |
| POST | `/log_collector` | collect.ets100.com | 2 | 启动埋点上报(Event_Startup, form-urlencoded) | `ets_2026-10-28.log:95` |
| GET | `/system/announcement.txt` | cdnfei.ets100.com | 2 | 公告墙静态 JSON(62B) | `ets_2026-10-28.log:9` |
| GET | `/dcp-config/getJsConfig` | dcp.changyan.com | 2 | 畅言评论组件配置(自带 appid/timestamp/sign) | `cef_2026-10-28.log:182` |

### 4.3 典型请求/响应样例（脱敏）

登录（`user/register-or-login`，`ets_2026-10-28.log:40-41`）：

```json
/* request.params */
{"sign_response":1,"sn":"test","system":4,"global_client_version":"5.7.9",
 "phone":"***","password":"***","code":"***","device_name":"D7480","device_code":"***","account":"***","name":"***"}
/* response.body（节选字段名，值脱敏） */
{"recent_account_id":"***","user_type":0,"school_year_id":0,"school_year_name":"","grade_id":0,"name":"***",
 "phone":"***","raw_phone":"***","bind_mobile":"***","token":"***","expire":1794395112,"newUser":false,"partner":"common"}
```

用户资料（`user/info`，`ets_2026-10-28.log:109`）：`body` 含 `recent_account_id / user_type / school_year_id / grade_id / grade_name / class(id) / province_id / city_id / name / phone / cover / partner / push_switch` 等。

录音评测结果同步（`/m/audio/sync-v2`，36 次，核心写接口，`ets_2026-10-28.log:525`）：

```json
/* request.params（节选） */
{"sign_response":1,"sn":"test","system":4,"global_client_version":"5.7.9","token":"***",
 "set_id":"747726","entity_id":"811865","homework_id":"110271129","resource_id":"363",
 "score":...,"real_score":...,"point":...,"score_detail":"...","dimension_score":...,
 "upload_file_id":"583126840053","spx_file_url":"https://ets60.ets100.com/ugc/evaluate/speex/...",
 "detail_file_url":"...","mark_trace_id":"tencentyun@...","mark_service":...,"version":...}
/* response.body */
{"practise_count":1,"detail_file_id":"583101376047","point":0.38,"total_point":10,"complete":8,
 "avg_point":76,"pass":1,"dimension_score":{"fluency_score":0,"integrity_score":0,"accuracy_score":0,"stress_pronunciation_score":0},
 "entity_id":"811865","upload_file_id":"583126840053","receive_time":"1793186566.3280","token":"***",
 "base":{"ip":"","pid":"","ets_app":0,"uid":0,"system":0,"request_id":"","global_client_version":"","sn":""}}
```

系统配置（`system/config`，56 次，最大响应 ~174 KB）：`body` 为扁平 `key→string` 字典（值多为 JSON 字符串），覆盖开关、文案、白名单、引擎策略等；支持 `keywork` 参数按关键字子集拉取：

```text
keywork = ["engine_sdk_config","engine_sdk_config_primary","special_word_list_for_color","res_color_adjust",
"word_color_rule","res_score_adjust","pc_enable_ailib","pc_web_enable_aimix","pc_force_record_vol_100",
"mutil_dimension_adjust","jiyan_code_verify","homework_rank_rate","disable_total_score_adjust"]
```

`system/time`：`{"date":"2026-10-28 19:05:22","time_stamp":1793185522}`（用于校正 `head.time`）。【观察】

### 4.4 cef 网络日志补充（含未在前端日志出现的端点/资源）

- 全部 `NetworkDelegate::NotifyBeforeURLRequest:` 行已抽取：`cef_2026-10-28.log` / `cef_2026-11-4.log` 共 1,036 条 api.ets100.com URL；其中 **`/point-service/homework/rank/list?homework_id=...&token=***`** 只出现在 cef（`cef_2026-10-28.log:108683`），前端日志未捕获 → 补入 `endpoints.csv`。【观察】
- 页面/资源主机分布（按 URL 出现次数）：`statics.ets100.com`（SPA，8,903 次，`/ets-student-pc-web/index.html?tdt=<时间戳>`）、`cdnfei.ets100.com`（图片/PDF/安装包/zip）、`cdnfeis.ets100.com`（会话级 CDN 路径 `/<YYYYMMDDHHmm>/<hash>/file/<hash>.zip`）、`cdnsubject.ets100.com`（套题资源 `zip/`、`made/`）、`cdn.fei.ets100.com`（图片）、`file.fei.ets100.com`（network_test）、`ets60.oss-cn-hangzhou.aliyuncs.com`（OSS 直传）、`ets60.ets100.com`（评测音频/XML 公开 URL，`/ugc/evaluate/...`）、`ets-vpc-log.cn-hangzhou.log.aliyuncs.com`（SLS）、`ai-thor.eduaiplat.com`（AI 反馈批量上传）、`dcp.changyan.com`（畅言评论）、`jic.talkingdata.com`（埋点）、`static.geetest.com`/`gcaptcha4.geetest.com`（验证码）、`teacher/hdteacher/koukao/www.ets100.com`（外链页面）。完整清单 `reports/urls_all.txt`。【观察】
- 前端页面本身通过 `statics.ets100.com/ets-student-pc-web/common/pc-listen.html?token=***&time=...`、`pc-listen-answer.html?token=***&time=...` 打开听说练习子页，JWT 走 query。【观察】

---

## 5. 会话与鉴权链

### 5.1 凭证清单（4 类：登录 JWT / 资源平台 JWT / AI accessToken / 阿里云 STS）

| 凭证 | 形态/长度 | 结构与观察值 | 携带位置 | 来源接口 | 有效期 |
|---|---|---|---|---|---|
| 登录 token | JWT HS256，160 字符 | header `{"typ":"JWT","alg":"HS256"}`；payload `{"create":<epoch秒>,"id":"<uid>","login":"***"}` | `params.token`、`pc-listen*.html?token=`、`point-service/*?token=` | `/user/login`、`/user/register-or-login` 的 `body.token` | 响应 `body.expire`（epoch 秒，≈14 天） |
| 资源平台 token | JWT RS256，504 字符 | header `{"alg":"RS256"}`；payload `{"iat":...,"exp":...,"iss":"rop","sub":"rop","app":"qm-ets-key","uid":"1234","pcode":"ets"}` | 日志中未观察到使用点 | `/config/config/getResourcePlatformToken` → `body.token` | `exp-iat=1209600`（14 天）；响应另有 `expireAt/timeout` |
| AI 评测 accessToken | JWT HS256，137 字符 | header `{"alg":"HS256","typ":"JWT"}`；payload `{"aid":"ksyyyxx-etszx","exp":"<epoch秒>"}` | AI 评测 WS 握手（sdk 内部使用） | `/ai/aiplat/getaitoken` → `body.accessToken` | `expiresIn=2592000`（30 天） |
| OSS STS | `accessKeyId`=`STS.`+24 字符；`accessKeySecret` 44 字符；`securityToken` ≈1180 字符 | 阿里云 STS 临时凭证 + PostObject policy/signature | OSS 直传表单 | `/p1/student/config/config/ossEvaluateUploadStsToken` | `expiration` 距请求 ≈19 分钟（`timeout:1159` 秒） |
| SLS STS | `access_key_id`=`STS.`+…；`access_key_secret` 44 字符；`security_token` 长串 | 阿里云 SLS 临时凭证 | SLS SDK 上报 | `/p1/student/ability/sls/slsAppConfig`、`/g/data/sls-config` | `expiration_time`（≈1 小时） |

### 5.2 登录链（观察）

```text
页面流程：/app-start → /auth/login → (eCard 登录) /auth/eCardLogin → /ecardBind → /startup → /main/home
          另一会话直接 /auth/login → /startup（UI_PAGE 日志）

1) code/send        （手机号加密串，用途 use=1/class_id=0）        ets_2026-10-28.log:37-38
2) user/register-or-login（phone/password/code/device_*）→ body.token   :40-41
   或 user/login（phone/password/device_name/device_code/local_ip）→ body.token  ets_2026-11-4.log:55-56
3) 后续请求把 body.token 放进 params.token（160 字符 JWT）        ets_2026-10-28.log:44 起
4) user/user/getLoginInfo → accountType                            :28-29
5) account/get-bind-info ×2（先用 account，再带 password）          :30-33
6) user/info（带 token，取 uid/学校/班级/年级）                      :109-110
7) 请求资源平台 token / OSS STS / SLS 凭证：
   //config/config/getResourcePlatformToken → {token(504 RS256), expireAt, timeout}   :61-62
   ossEvaluateUploadStsToken → {upload:{...}, mp3Path/spxPath/xmlPath/photoReadPath, timeout}  :60-61
   g/data/sls-config、p1/student/ability/sls/slsAppConfig → SLS STS
8) 登录 token 有效期来自响应 body.expire（epoch 秒），例如 1794395112 / 1795001715（≈14 天）
```

- **登录 token**：160 字符 JWT，header `{"typ":"JWT","alg":"HS256"}`，payload `{"create":<epoch秒>,"id":"<uid>","login":"<手机号>"}`；同一账号两次会话 `id` 相同、`create` 不同；被用于 `params.token`（268 个请求）、`pc-listen*.html?token=` 与 `point-service/*?token=`（cef 日志中 HS256 JWT 共出现 298/325 次，含上述两类 URL）。【观察】
- **资源平台 token**：504 字符 JWT，header `{"alg":"RS256"}`（无 typ），payload `{"iat":...,"exp":...,"iss":"rop","sub":"rop","app":"qm-ets-key","uid":"1234","pcode":"ets"}`，`exp-iat=1209600`（14 天）；接口返回 `expireAt`（毫秒）与 `timeout`（≈5512140 s）。**该 token 在日志中未被任何请求使用**。【观察 + 未知】
- **AI accessToken**：137 字符 JWT，`{"alg":"HS256","typ":"JWT"}`，payload `{"aid":"ksyyyxx-etszx","exp":"<epoch秒>"}`；`expiresIn=2592000`（30 天）。用于 AI 评测 WS 握手。【观察】
- **OSS/SLS STS**：见 §6、§7。**【观察】**
- **刷新机制**（日志文案实证）：`当前资源平台token已过期；开始请求配置数据`（`ets_2026-10-28.log:55`、`ets_2026-11-4.log:66`）、`AI引擎token已过期；开始请求配置数据`（`ets_2026-10-28.log:163`）、`当前配置已过期；开始请求oss的配置数据`（MISC 多处）→ 三类短时凭证都是**过期后按需重新拉取**；登录 token 过期的处理未在日志中出现（无 401/relogin 记录），机制【未知】。【观察 + 未知】
- 免登录接口：`system/config`、`/announcement/list` 带 `checkToken:false`；`file/download` 用 `key:"pc_stic_tools"`、无 token（首次启动即调用）。【观察】
- **Cookie**：cef 仅有 `Cookie.*` histograms（`cef_2026-10-28.log:110407` 起），**未观察到任何 Set-Cookie 或 Cookie 请求头**；鉴权均走 body/URL。**【未知/未观察到】**

### 5.3 设备/版本/身份字段

| 字段 | 观察值 | 来源 |
|---|---|---|
| `head.pid` | `pcWin` | 全部请求 |
| `global_client_version` | `5.7.9`（= PC 客户端版本，MISC: `stic version: 5.7.9`） | 全部请求 |
| `system` | `4` | 全部请求 |
| `device_name` | 机器名（日志中为 `D7480`，脱敏为 `***`） | `user/login`、`register-or-login` |
| `device_code` | 16 位大写十六进制（如 `4437D19B6B29BEEA`） | 同上 |
| `local_ip` | 客户端本地 IP（日志示例为 `198.18.0.1`） | `user/login` |
| `uid` | 平台账号 id（AI 评测 extra、OSS 对象路径） | ENG_SCORE extra、OSS key |
| `parent_account_id` / `account_id` / `sub_account_ids` | 学校/家长/子账号 ID（如 `275389912`、`275389909`…） | `user/info`、`m/resource/add-v2` |
| `class_id` / `school_id` / `grade_id` / `regionId` / `stageId` | 班级/学校/年级/考区（AI extra） | ENG_SCORE 开始帧 |
| `engine_area` / `tpl_region` | 例如 `shanghai` | 作业/套题响应、AI extra |
| `sn` / `sign_response` | `test` / `1`（PC 端固定） | 全部请求 |

---

## 6. 评测链路：AI 评测 WebSocket（wss://oe-pub.eduaiplat.com）

`[ENG_SCORE]` 日志完整记录了评测客户端（AI2 dualChannelManager）的协议参数与结果。【观察】

- 连接前：`获取AI引擎 Token 成功`（accessToken 来自 `/ai/aiplat/getaitoken`）。
- 握手/开始帧（`ets_2026-10-28.log:479`，原文，敏感值脱敏）：

```json
{"timeout":90000,"connectTimeout":60000,"language":"en","isPsc":false,
 "engineParam":{"category":"read_sentence","paperId":"<res_id>","region":"shanghai","group":"",
   "parsePaper":"false","audioStorage":"true","resultStorage":"true"},
 "isEndFlag":false,"aioeFlag":3,"version":"ets_70","transFormat":"speex","sendInterval":40,
 "extra":{"uid":"***","regionId":"5269,5270,0","schoolId":"***","classId":"***","gradeId":"***",
   "stageId":"0","tpl_region":"shanghai","scene_type":"homework","scene_id":"***","module":"1",
   "plat_type":"Web","plat_ver":"5.7.9"},
 "host":"wss://oe-pub.eduaiplat.com"}
```

- 音频：本地 `soundfiles/<public|分片>_<录音id>.mp3` + `.spx`（speex），`sendInterval:40ms`、`isSpeex:true`、`wss超时时间 60000`（ENG_SCORE 初始化行）；结束帧 `isEndFlag:true`（`评测发送结束帧`）。
- 结果（`ets_2026-10-28.log:493`）：`statusBean{code:"000000",msg:"请求成功",traceId:"tencentyun@...",requestId:...}`、`data:{xml:true}`、`channelType:"zhishu"`。
- XML 结果解析（`ets_2026-10-28.log:512`）：

```json
{"sdk_recode":"000000","engine_recode":"0","total_score":"2.762908","is_rejected":"false",
 "sid":"tencentyun@...","mark_trace_id":"tencentyun@...",
 "wav_url":"https://ets60.ets100.com/ugc/evaluate/mp3/middleApp/pc/2026/10/28/<uid>/public_<id>_<ts>.mp3",
 "spx_url":"https://ets60.ets100.com/ugc/evaluate/speex/...mp3.spx",
 "xml_url":"https://ets60.ets100.com/ugc/evaluate/xml/...xml"}
```

- 错误码实测：`1004 Websocket超时异常`（连接/等待超时，重试 `retryCount:1` 后仍失败；`ets_2026-10-28.log:719/740/741`）；`评测错误码命中规则 [rule=3] shouldZero=true ... engine_code= except_info=28673/28676 is_rejected=true`（拒评时总分置 0）。【观察】
- 评测完成后：本地 mp3+spx+xml 上传 OSS（§7），再调 `/m/audio/sync-v2` 上报评分与上传 id。【观察】

---

## 7. 录音/评测文件上传：阿里云 OSS 直传（PostObject 表单）

- STS 凭证来自 `/p1/student/config/config/ossEvaluateUploadStsToken`（5 次），响应体：

```json
{"upload":{"securityToken":"***","accessKeyId":"***","bucket":"ets60","accessKeySecret":"***",
  "endpoint":"oss-cn-hangzhou.aliyuncs.com","prefix":"https://","cname":"https://ets60.ets100.com",
  "expiration":"2026-10-28T11:24:42Z","region":"cn-hangzhou","object":""},
 "mp3Path":"ugc/evaluate/mp3/middleApp/pc/2026/10/28/<uid>/",
 "spxPath":"ugc/evaluate/speex/middleApp/pc/2026/10/28/<uid>/",
 "xmlPath":"ugc/evaluate/xml/middleApp/pc/2026/10/28/<uid>/",
 "photoReadMp3Path":"ugc/photoRead/mp3/...","photoReadImgPath":"ugc/photoRead/img/...",
 "timeout":1159}
```

- 上传动作日志（`ets_2026-10-28.log:514`）：`<file>上传文件请求地址： https://ets60.oss-cn-hangzhou.aliyuncs.com, 表单数据： {...}`，表单字段（观察）：

| 字段 | 值/格式 |
|---|---|
| `OSSAccessKeyId` | `STS.` + 24 字符 |
| `policy` | base64(JSON)：`{"expiration":"...","conditions":[["content-length-range",0,524288000],["eq","$bucket","ets60"],["eq","$key","ugc/evaluate/mp3/middleApp/pc/2026/10/28/<uid>/public_<id>_<ts>.mp3"]]}` |
| `signature` | base64（OSS 签名） |
| `x-oss-security-token` | STS securityToken（长字符串） |
| `key` | `ugc/evaluate/{mp3,spx,xml,photoRead}/middleApp/pc/<YYYY>/<MM>/<DD>/<uid>/public_<md5>_<epochms>.<ext>` |
| `file` | 文件二进制（multipart） |

- 每次评测固定 3 个对象：`*.mp3`、`*.mp3.spx`、`*.xml`；上传结果日志 `<file>上传文件成功： "{\"rncode\":0,\"rnmsg\":\"uploadFile success.\"}"`（`ets_2026-10-28.log:520`）。上传成功的对象可经 `https://ets60.ets100.com/ugc/...` 公开读取（评测结果里的 `wav_url/spx_url/xml_url`）。【观察】
- OSS STS 有效期：`expiration` 与请求时间差 ≈ 19 分钟（`timeout:1159` 秒），过期前重新拉取（MISC: `当前配置已过期；开始请求oss的配置数据`）。【观察】

---

## 8. 日志与监控链路

| 链路 | 端点 | 说明 |
|---|---|---|
| 前端运行日志 | `ws://127.0.0.1:40001/` → mq_server → `logs/ets_<date>.log` | §2 |
| 启动埋点 | `POST http://collect.ets100.com/log_collector`（form-urlencoded） | `type=Event_Startup&version&system&account_id&date_time` |
| 阿里云 SLS（应用） | `POST https://ets-vpc-log.cn-hangzhou.log.aliyuncs.com/logstores/app-general-log` | STS 来自 `p1/student/ability/sls/slsAppConfig`（`access_key_id/security_token/access_key_secret/expiration_time/project/logstore`） |
| 阿里云 SLS（评测 SDK） | `POST .../logstores/evaluation-sdk-log` | STS 来自 `g/data/sls-config` |
| AI 数据反馈 | `POST https://ai-thor.eduaiplat.com/ai-thor-data-collector/feedback/batchUpload`（151 次 URL） | 与 AI 评测配套的反馈上报 |
| TalkingData | `https://jic.talkingdata.com/app/h5/v1?appid=495EB536B2694258A6DA406D98F9E230` | 第三方埋点 |
| 畅言评论 | `GET https://dcp.changyan.com/dcp-config/getJsConfig?...&appid=OsoL5ESKO835&timestamp=<ms>&sign=<32hex>` | 第三方评论组件配置，**自带**另一套 sign（MD5 形态），与本 App 的 `head.sign` 不同源 |
| 验证码 | `static.geetest.com` / `gcaptcha4.geetest.com` | 极验验证码（`hd_login_captcha_threshold=3` 等配置控制） |

---

## 9. CEF / 原生桥（与 HTTP 协议并列的另一套“协议”）

`ETS/packages/default/appcontroller.js`（明文）给出 JS↔原生消息格式：

```js
cef.message.setMessageCallback(callback_id, fn)                    // 注册回调
cef.message.sendMessage(callback_id, 'appcontroller', 'init', JSON.stringify(info))
//                            ↑回调id      ↑模块          ↑action   ↑JSON 参数
cef.message.createGuid() / removeMessageCallback()
```

- 窗口控制 action（`appcontroller.js`）：`init/close/maximize/minimize/restore/move/fullscreen/reduction/hide/show/get_win_pos/set_win_pos/startapp/idg_exist`；`startapp` 附带 `apprun_callback_id`/`appexit_callback_id`。【观察】
- 原生侧模块/action（shell 日志实证）：`etshelper(init/get_appdata_path/encode_api_body_v2/check_update)`、`filehelper(existfileorfolder/getbase64/getmd5)`、`soundhelper(record/setsound…；`saveSpxFile`)、`shellhelper(getvolume/getconfig/processexist/getpcinfo/startprocess/executecmd/setvolume)`、`httphelper(init/download/upload)`、`sqlitepln`、`appcontroller`。消息统一形如 `[<module>::PlnOnProcessMessage] action-><action>`，参数为 JSON（`appcontroller.cpp:150` `[appcontroller::SetWinPos] utf8_args {...}`）。【观察】
- **`encode_api_body_v2` 就是 §3.3 的签名入口**（etshelper.cpp:522/499）；`httphelper/upload` 走 libcurl（`HttpProvider::uploadRequest`，`curl_easy_getinfo code:200`）。【观察】
- 本地文件伪协议：页面音频地址 `stic://file.iflytek.com/<绝对路径>`，由原生 `client_schema.cpp` 解析（`shell_2026-11-4.log:763` `domain_name size: ... //file.iflytek.com/C:\...`）。【观察】

---

## 10. 资源包/内容下载链路（cef + ets 观察）

```text
1) file/download（key=pc_stic_tools）→ body.url = https://cdnfeis.ets100.com/<YYYYMMDDHHmm>/<hash>/file/<hash>.zip
   PLG_STIC: "start download file: {url, local_file: clear_cache.zip, exists:{...}}"     ets_2026-10-28.log:15
   → 下载 → "下载成功：1个, 进度100%" → "解压成功" → 本地 %APPDATA%\ETS\clear_cache     ets_2026-10-28.log:24-27
2) 套题内容：g/set/list 的 link 字段 = https://cdnsubject.ets100.com/zip/<hash>.zip
   g/homework/list 的 zip_url / struct.template.url、base_url=https://cdnsubject.ets100.com/made/
   cef 侧同源请求：/zip/<hash>.zip、/made/<hash>.zip、/entity/<hash>/content2.json（cdn.subject.ets100.com）
3) 静态图片/PDF/安装包：cdnfei.ets100.com/img|file|package/...、cdn.fei.ets100.com/img/...
4) 评测音频/XML：ets60.ets100.com/ugc/evaluate/{mp3,speex,xml}/middleApp/pc/<YYYY>/<MM>/<DD>/<uid>/...
5) 前端页面：statics.ets100.com/ets-student-pc-web/{index.html?tdt=<ms>, assets/*.js, common/pc-listen*.html?token=...&time=...}
```

- `file/download` 每次启动调用（7 次），`key:"pc_stic_tools"` 固定；返回 URL 含部署时间戳（`202610281856`），说明 CDN 目录按发布批次生成。【观察】
- `g/homework/list` 返回 `base_url`、`zip_url`、`template.url` 等下载入口；`cdnsubject.../made/` 在响应中出现 3 次。【观察】

---

## 11. 异常路径与错误处理（汇总）

| 现象 | 证据 | 结论 |
|---|---|---|
| mq_server 客户端断开 `1006` | `ets_2026-10-28.log:1979`、`ets_2026-11-4.log:3023` | 进程被杀/崩溃导致无 close 帧；服务端仅记录，不做清理逻辑 |
| 网络探测失败 | `ets_2026-10-28.log:695-697`：`测试URL http://file.fei.ets100.com/network_test 失败` → `cdn.fei.ets100.com/network_test` 失败 → `网络状态: 异常（所有URL都请求失败）` | 双 URL 回退，均失败则判定断网 |
| AI 评测 WS 超时 | `ets_2026-10-28.log:719/740/741`（code 1004） | 评测重试 1 次后置失败，`data.xml=false` |
| 评测被拒 | `评测错误码命中规则 [rule=3] ... except_info=28673/28676 is_rejected=true` | `total_score=0`，仍走后续上报 |
| SLS 凭证缺失/过期 | `ets_2026-10-28.log:51/53`（`credentials还没有值`）、`1637-1657`（`凭证过期`） | 初始化早于凭证获取；过期后自动重取 |
| 登录 token 缺失 | `ets_2026-10-28.log:36/39` `获取不到token的情况 ... sessionToken: null`（E 级） | 【推断】code/send、register-or-login 阶段尚无 sessionToken，属预期路径（E 级但非致命） |
| 免登录接口 | `checkToken:false`（system/config、announcement/list） | 启动早期在登录前调用 |
| 资源 file 缺失 | `filehelper::OnGetMd5 file is not exist`（`shell_2026-10-28.log:95`） | 首次启动 clear_cache.zip 不存在，随后下载 |
| 上传失败重传 | MISC：`自动扫描是否存在上传失败的评测文件`（236 次）/`autoReUpload`（236 次）/`录音评测任务处理完 , 失败任务recordFiledTasks：1个`（`ets_2026-10-28.log:1822`） | 本地失败任务队列 + 自动重传机制 |

---

## 12. 证据索引（关键行号）

| 主题 | 证据 |
|---|---|
| mq_server 源码 | `ETS/mq_server/main.js:6,11-13,15-32,34-59,61-70,72-85,87-141,143` |
| 端口写入 app.json | `ets_2026-10-28.log:1-4`、`ets_2026-11-4.log:1-2,26-27` |
| app.json 被原生解析 | `shell_2026-10-28.log:84`（`josn::parse app.json, error: 2`）、`:73`（`action->getconfig`） |
| mq_server 进程管理 | `shell_2026-10-28.log:67,72,75-76,80-81,6718` |
| WS 连接 URL | `cef_2026-10-28.log:205`、`cef_2026-11-4.log:149,419`（`ws://127.0.0.1:40001/`） |
| 连接建立/断开 | `ets_2026-10-28.log:5-6,1979`、`ets_2026-11-4.log:3-4,3023` |
| 签名协议声明 | `ets_2026-10-28.log:7`、`ets_2026-11-4.log:5`（`protocol=v2, pid=pcWin`） |
| 签名原生实现 | `shell_2026-10-28.log:82-83` 等（`encode_api_body_v2`/`OnEncodeAPIBody success`）；全文件各 157/192 次 |
| 登录 token 签发 | `ets_2026-10-28.log:41`（register-or-login）、`ets_2026-11-4.log:56`（user/login） |
| token 使用 | `ets_2026-10-28.log:44` 起 `params.token`；cef `pc-listen.html?token=`（`cef_2026-10-28.log:8627`） |
| 资源平台 token | `ets_2026-10-28.log:61-62,71-72`（`getResourcePlatformToken` 响应/成功文案） |
| AI token | `ets_2026-10-28.log:168-169,185-186`（请求/`获取AI引擎token数据成功`） |
| AI 评测开始帧/结果 | `ets_2026-10-28.log:479,493,512` |
| AI 评测错误 | `ets_2026-10-28.log:719,740,741` |
| OSS STS 响应 | `ets_2026-10-28.log:69` |
| OSS 上传表单/结果 | `ets_2026-10-28.log:514,517,519,520` |
| SLS 凭证 | `ets_2026-10-28.log:67-68,73-74`；响应 `g/data/sls-config`、`p1/.../slsAppConfig` |
| 埋点上报 | `ets_2026-10-28.log:94-95,103` |
| 直接 API 的请求头 | `reports/axios_configs.json`（源自 `ets_2026-10-28.log:9,103`、`ets_2026-11-4.log:7,109`） |
| 网络探测 | `ets_2026-10-28.log:18,695-697`；`cef_2026-10-28.log:118`（Mixed Content） |
| cef URL 全集 | `reports/urls_all.txt`；单端点见 `cef_2026-10-28.log:106-108683` |
| 点服 rank/list（仅 cef） | `cef_2026-10-28.log:108683` |
| 启动序列 | `shell_2026-10-28.log:59-110`；`ets_2026-10-28.log:1-27` |
| 资源包下载/解压 | `ets_2026-10-28.log:14-27` |
| UI 路由流程 | `ets_2026-10-28.log:17,34,42,49,111,199` |
| 设备/版本信息 | `ets_2026-10-28.log:19-21` |

---

## 13. 未解问题（供 Lead 决策）

1. **sign v2 算法未还原**：签名原文/算法在 ETSShell.exe（`etshelper::OnEncodeAPIBody`）。已备 334 组逐字节原文样本；需要 Lead 用样本反推（或由 native 队友反编译 `etshelper.cpp`/`encode_api_body_v2` 的 MD5 入参拼接顺序与密钥）。
2. **RPC 接口 HTTP 方法**：日志未记录方法（只有 URL/body），`endpoints.csv` 标为“推断 POST”。
3. **资源平台 token（504 RS256）用途**：日志中未见任何消费点（可能被原生或未记录的子系统使用）。
4. **登录 token 过期后的刷新/重登流程**：无 401/relogin 观察；配置项 `relogin_if_no_common` 暗示存在重登策略，未见触发。
5. **手机号/密码加密**：`code/send` 的 `phone` 为 base64 密文（`...==`），`getLoginInfo` 的 `phone/password` 亦为密文；加密算法（AES/密钥）未分析，需 native/前端补位。
6. **mq_server 是否有其它命令**：源码层面确认没有；但“`suspensionBallPort` 之外是否还有隐藏配置”取决于客户端读取逻辑（`shellhelper/getconfig` 的实现未反编译）。
7. **Cookie 机制**：cef 只有 histogram，无实际 Cookie 头；是否完全不用 Cookie 需结合前端 bundle 确认。
8. **双斜杠路径成因**：不同前端模块拼接 `baseURL(以/结尾)+path(以/开头)` 导致；服务端兼容，但作为还原细节保留。
9. **`/system/config` 全量语义**：响应为 174 KB、数百个扁平键，本文只列关键项；完整键值需另做配置字典（可与 frontend 队友的代码分析对照）。
10. **部分端点语义为推断**：如 `g/user/jkpt-info`（健康平台）、`m/product/list`（权益商品）、`point-service/account/trail`（积分试用）等，依据字段名与调用时机推断。

---

## 14. 产物与脱敏说明

`work/api/`：

| 文件 | 内容 |
|---|---|
| `endpoints.csv` | 63 行端点清单：`path,method,host,count,cef_url_count,example_ref,example_requestId,purpose_inferred,confidence,method_evidence` |
| `sign_samples.json` | **334 组**签名样本：`url/host/path/route/head_version/pid/time/time_second/sign/body_json_exact/head_json_exact/param_json_exact/body_reparsed`，`body_json_exact` 全部与重序列化逐字节一致 |
| `endpoint_samples.json` | 52 个端点的请求/响应样例（`params_masked`、`head_masked`、响应体抽样，敏感值 `***`） |
| `reports/` | 证据报表：`mq_server_lines.txt`、`stats.txt`、`urls_all.txt`、`resp_fields.txt`、`token_kinds.txt`、`axios_configs.json`、`errors.txt`、`eng_score.txt`、`oss_upload.txt`、`keywork_and_misc.txt`、`api_paths_union.txt`、`cef_shell_shapes.txt` 等 |
| `raw/` | 中间解析目录（大响应已裁剪；`responses_trimmed.json`/`summary.txt`）。原始 `requests.json`/`responses.json` 等大文件已清理以减小体积；需要时运行 `work/api/extract.py` 从只读日志重建（`raw/` 为输出目录）。 |

脱敏处理：doc/CSV/`endpoint_samples.json`/`reports/` 中姓名、手机号、账号、学校名、班级名、token/JWT、cookie、OSS/SLS 凭证、password 均替换为 `***`（保留字段名与格式）。**例外**：`sign_samples.json` 按任务要求保留“原始 body 字符串”（签名验证需要原文），其中可能包含请求参数原值（含 token、密文手机号、password 等）；该文件仅用于算法验证，勿对外传播。

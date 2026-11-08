# 15 真实练习抓包分析：录音 / ISE 评测 / 上传 / 同步

> 数据来源：一次真实作业练习（作业 111203417，套卷 958806，10 道听说题，含 10 次录音评测）。
> 采集方式：`capture/`（CDP 抓 WebSocket + 渲染进程 HTTP、Frida 抓插件调用、日志跟随、文件监听）。
> 本文只记录协议与格式，不含账号、token、录音等个人信息。

## 1. 一次练习的完整时序

```
进入作业
 ├─ POST g/homework/list                  （刷新作业列表）
 ├─ POST g/homework/checkstart            homework_id=111203417 → 返回 begin/server_datetime
 ├─ POST /m/homework/info                 → 练习状态、submit、上次完成信息
 ├─ POST g/homework/list                  （再次刷新，all_count 变化）
 ├─ POST g/set/ppr-res                    batch: entity_id+order → res_id（题目资源 id）
 ├─ POST /g/set/mark-txt                  question[].key = "<entity_id>_<order>"
 ├─ POST m/mistake/check                  entity_id[] → 是否错题
 │
 ├─ 逐题循环（每题一次）：
 │   ├─ 下载 content zip（HttpHelper.download）→ 解压 → 朗读/答题
 │   ├─ 录音 → 本地生成 <id>.mp3 / <id>.mp3.spx / <id>.xml
 │   ├─ ISE WebSocket 评测（wss://oe-pub.eduaiplat.com/ws/v2/ise）
 │   │    ← 返回评测 XML（与本地 .xml 同格式）
 │   ├─ 3 个文件上传阿里云 OSS（mp3 / spx / xml，public-read）
 │   └─ POST /m/audio/sync-v2              携带成绩与 3 个 OSS URL → 返回 point/dimension_score
 │
 ├─ POST m/mistake/update                 （全部完成后）
 ├─ POST m/homework/set-use-time          use_time=582 秒
 └─ POST /m/homework/info                 （刷新最终状态；最后一条 sync-v2 会置 submit_time / is_complete_and_udpated=1）
```

- 评测结果除了回传前端，还以 `[ENG_SCORE]` 行写日志：
  `[ENG_SCORE] id: <ts>, sdk:AI2 , 评测请求成功..., {"statusBean":{"code":"000000","msg":"请求成功","traceId":"tencentyun@…","requestId":"…"},"responseFinish":true,...}`

## 2. ISE 评测 WebSocket

- 端点：`wss://oe-pub.eduaiplat.com/ws/v2/ise`
- 传输：**全部为 binary 消息**，内容为 protobuf（无 JSON 文本帧）。
- 一次评测一个连接：先发 init，再连续发音频块，最后发结束帧；服务端回一帧结果后关闭。

### 2.1 音频格式

| 项 | 值 |
|---|---|
| 采样率 | 16000 Hz |
| 编码 | speex（初始化消息中 `codec="speex"`） |
| 每块 | 212 字节（≈40ms：2×20ms speex 帧，约 42kbps） |
| 本地 `.spx` | 就是所有音频块按顺序拼接（例如 42400B = 200×212，约 8s） |
| 本地 `.mp3` | 同一段录音的 mp3 版本（如 24300B，约 3s @24kbps；用于回放/上传） |
| 本地 `.xml` | 评测结果 XML（与 WS 返回内容一致） |

### 2.2 Protobuf 消息（按 wire 字段号）

**init（首帧，约 900B）**

```
f1  (message) SessionInfo
    f1 = clientId            "ksyyyxx-etszx"        # SDK/client id
    f2 = accountId           "275389912"
    f3 = mac                 "00-00-00-00-00-00"
    f4 = appId               "ets_70"
    f5 = sdkKey              "SDK_pY1wOPU8"
    f6 = requestId           32 位 hex（每次随机）
    f7 = accessToken         JWT（HS256，payload {"aid":"ksyyyxx-etszx","exp":...}）
    f8 = ""（空）
    f9 (repeated) map entry: f1=key, f2=value
        uid=33888750, regionId=5269,5270,0, schoolId=7729, classId=1155123,
        gradeId=90329, stageId=263833, tpl_region=shanghai,
        scene_type=homework, scene_id=<homework_id>, module=1,
        plat_type=Web, plat_ver=5.7.9
f2  = "en"                   # 语言
f3  = ""（空）
f4  = 1                      # 音频格式/通道相关常量（实测传 0/1/2 服务端均按 speex 处理）
f5  = <212B 音频块>          # 第一块音频直接放在 init 里
f6  = 16000                  # 采样率
f7  = "speex"                # 编码
f8  = 0
f9  = 0
f10 = 0
f11 (repeated) map entry: f1=key, f2=value
        category=read_sentence, paperId=<res_id>, region=shanghai,
        group="", parsePaper=false, audioStorage=true, resultStorage=true
f12 = ""（空）
f13 = 3                      # 编码/质量相关常量
```

**音频帧（每个 224B）**

```
f5 = <212B speex chunk>
f7 = "speex"
f8 = 0
```

**结束帧（21B）**

```
f5 = 10 个 0 字节
f7 = "speex"
f8 = 1
```

**结果帧（约 1–13KB）**

```
f1 = "00000"                 # 状态码（成功）
f2 = "请求成功"
f3 = "tencentyun@<traceId>"
f4 = (message) { f1="result", f2=<XML 字符串> }
```

- 评测结果 XML 根节点 `<xml_result>`，按题型不同为 `<read_sentence>` / `<read_word>` 等；
  关键属性：`accuracy_score`、`fluency_score`、`integrity_score`、`standard_score`、`total_score`、
  `is_rejected`、`except_info`、`content`、`word_count`；
  子节点：`<sentence>` → `<word>`（含 pitch）→ `<syll>` → `<phone>`（`phone_total_score`、`gwpp`）。
- 评测服务会把结果同时写回 OSS（客户端上传 xml）与 HPS 平台。

### 2.3 accessToken 获取

`POST https://api.ets100.com/ai/aiplat/getaitoken`（普通签名信封 + 登录 token）→

```json
{"expiresIn":"2592000","accessToken":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.…"}
```

- `expiresIn=2592000`（30 天），`accessToken` 即 init 里的 f1.f7。

## 3. 录音文件上传（阿里云 OSS）

- 地址：`https://ets60.oss-cn-hangzhou.aliyuncs.com`（POST 表单，multipart）
- 字段：

| 字段 | 说明 |
|---|---|
| OSSAccessKeyId / policy / signature / x-oss-security-token | STS 临时凭证（来自 `p1/student/config/config/ossEvaluateUploadStsToken`） |
| key | `ugc/evaluate/{mp3|speex|xml}/middleApp/pc/YYYY/MM/DD/<account_id>/<uuid>_<ts>.mp3[.spx|.xml]` |
| x-oss-object-acl | `public-read` |
| submit | `Submit` |
| success_action_status | `200` |
| localFile | 本机文件路径（插件读取后上传） |

每题上传 3 个文件：mp3（回放）、spx（speex 原始流）、xml（评测结果），返回的公网 URL 用于下一步 sync。

## 4. 成绩回传 `/m/audio/sync-v2`

参数（节选）：

```json
{
  "resource_id": "239", "set_id": "958806", "entity_id": "1010510", "order": "1",
  "real_score": 0, "score": 0,
  "upload_file_url": "https://ets60.ets100.com/ugc/evaluate/mp3/....mp3",
  "spx_file_url":   "https://ets60.ets100.com/ugc/evaluate/speex/....mp3.spx",
  "detail_file_url":"https://ets60.ets100.com/ugc/evaluate/xml/....xml",
  "mark_trace_id": "tencentyun@…",           // ISE 结果 traceId
  "score_detail": "{\"accuracy_score\":0,\"fluency_score\":0,\"integrity_score\":0,\"standard_score\":0,\"total_score\":0,\"real_score\":0,\"category\":\"read_sentence\",\"rate_scale\":1}",
  "homework_id": "111203417", "first_column_id": "1", "question_type_score": "0.5",
  "rate_scale": 1, "graduation": "0.125",
  "client_time": "2026-11-08 15:09:08",
  "mark_service": 1, "version": "2"
}
```

响应含 `point`、`dimension_score`（fluency/integrity/accuracy/stress_pronunciation）、
`is_complete_and_udpated`（最后一题完成后为 1 且带 `submit_time`）、`upload_file_id`。

完成全部题目后：
- `POST m/mistake/update`（homework_id/set_id/type/resource_id）
- `POST m/homework/set-use-time`（use_time 秒、correct）
- `POST /m/homework/info`（刷新最终成绩/提交状态）

## 5. 对复刻版的意义

- 录音链路 = **浏览器/原生采 16k PCM → speex 编码（每块 212B）→ WS 流式评测**；
  评测结果 XML 可解析为分数与逐词反馈。
- 写接口与上传链路参数已完全明确，可在 `reimpl/`（Python）与 `native-replica/`（C++ + Vue）中实现。
- 未解：speex 编码器的精确参数（quality/frame 组合）需实测匹配；评测服务对音频内容敏感，
  复刻实现应使用真实麦克风输入而非伪造音频。

---

## 6. 编码参数实测（speex）

用标准 speex 1.2.1（浮点、WB）解码/编码对比，确定客户端的编码参数：

| 参数 | 值 | 验证 |
|---|---|---|
| 模式 | speex wideband（16 kHz） | 帧长 320 samples（20 ms） |
| quality | 10 | — |
| VBR | 关闭 | — |
| bitrate | **84800** | 每帧恒为 **106 字节** |
| 每个 WS 音频块 | 2 帧 = **212 字节** | 与抓包 200 块×212B 完全一致 |
| 本地 .spx | 所有块顺序拼接 | 42400B = 200×212 |

- `SPEEX_SET_BITRATE=84800` + `SPEEX_SET_VBR=0` 时，speex 编码器输出固定 106B/帧；
  两个帧拼成一个 212B 块正好匹配抓包。
- 实测：把同一段录音（mp3 解码为 16k PCM）用该参数重新编码，再走 ISE 评测，
  返回结构/时长/逐词结果与原始评测一致（分数差异来自 mp3 有损回环）。
- 复刻实现：`native-replica/plugins/soundhelper`（C++/speex）提供 `encode_speex`；
  `native-replica/frontend/src/ise.js` 负责 protobuf + WebSocket + 结果解析；
  `reimpl/ets_ise.py` 为同协议的 Python 参考实现（已用抓包 spx 回放验证）。

## 7. 复刻实现状态

| 能力 | 状态 |
|---|---|
| ISE WebSocket 协议（init/音频/结束/结果） | ✅ 前端 JS + Python 均跑通 |
| speex 编码（16k/106B 帧/212B 块） | ✅ C++ 插件编码，评分链路验证 |
| 麦克风采集（16k PCM） | ✅ WebView2 内 getUserMedia + 权限自动授予 |
| 录音→编码→评测→显示分数 | ✅ Practice 页已接入 |
| OSS 上传（STS 表单） | ✅ Python 参考实现验证（可直传 public-read） |
| `/m/audio/sync-v2` 成绩回传 | ✅ 参数已还原；前端接入待完成 |
| mp3 生成（上传所需） | ⏳ 需 ffmpeg/lame（可用安装目录自带工具） |
| 真实麦克风完整练习回归 | ⏳ 待用真实录音验证（避免自动化测试往评测服务发送环境音） |

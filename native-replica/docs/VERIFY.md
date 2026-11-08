# 运行期验证记录（native-replica）

> 环境：Windows 10 19045 x64；WebView2 Runtime 157.0.4341.42；MSVC 14.51；构建产物 `EtsReplica.exe`（C++20）。
> 验证方式：启动副本 + WebView2 远程调试（`ETS_REPLICA_DEBUG_PORT`）+ 页面真实输入/点击 + JS 桥探针。

## 1. 壳、桥与插件

| 检查 | 结果 |
|---|---|
| 窗口标题 | `E听说 · 复刻版`（读 shell.ini） |
| WebView2 环境/控制器 | 初始化成功，`navigate https://app.ets.local/index.html hr=0` |
| 插件加载 | `plugin host initialized (loaded 7/7)`：EtsHelper、FileHelper、HttpHelper、SQLitePln、ShellHelper、SevenZip、SysConfig |
| `__core.info` | 返回 appDir/cacheDir/dataDir/mediaPort/platform=webview2/version |
| `__core.media_url` | 返回 `http://127.0.0.1:<port>/media?...`；GET 200、Range 206、越界 403 |
| 签名 | `EtsHelper.encode_api_body_v2` 与 Python/历史日志逐字节一致 |
| `ShellHelper.getpcinfo` | 返回设备信息 JSON |
| `FileHelper` / `SevenZip` | 解包真实 `content_*.zip`，`FileHelper.readfile` 读回 JSON |
| mq_server | 副本 Node 中继起来（40001 被官方占用时自动 +1），壳按 `app.json` 端口连接 |

## 2. 端到端（页面真实输入，非注入 token）

| 检查 | 结果 |
|---|---|
| **UI 登录** | 登录页输入手机号/密码 → 回车 → 跳转 `#/home`，token 长度 160，提示"登录成功" |
| 设备绑定 | 首次登录返回"设备需要绑定免验证"；在设置页填写官方客户端的 `device_code/device_name/local_ip`（localStorage `ets_device_override`）后登录成功 |
| 首页 | 真实昵称/年级/学校/学习卡剩余天数；1 份待完成作业、9 道待订正错题 |
| 作业 | `g/homework/list` 待完成 1 / 已完成 3 / 已过期 0；列表可进入详情/开始练习 |
| 套卷 | `g/set/column-v2` + `g/set/list`：栏目 16 套（默认 resource_id=363） |
| 同步课程 | `g/resource/book-list`/`grade-list` → 教材列表；单元/模块参数已对齐 |
| 错题本 | `m/mistake/summary` + `m/mistake/list`：听说 9 条 |
| 题库内容 | 作业"开始练习" → `HttpHelper.download` 下载 content zip → `SevenZip.unzip` 4 文件 → `FileHelper.readfile` 读 `content.json` → 渲染朗读题（题干/参考原文/解析） |
| 音频 | `<audio>` 指向 `http://127.0.0.1:<port>/media?p=practice/1010510/material/content.mp3`，HTTP **200 / 127,362 B** |

## 3. 数据兼容修复（本轮）

- `m/ecard/list` 的 `body` 在不同服务端版本下可能是 `{data:[...]}` / `{data:{"0":{...}}}` / `{"0":{...}}`；前端已统一归一化为数组，并持久化 `parent_account_id`。
- 作业/错题接口补齐 `parent_account_id` 等必需参数；套卷/课程补齐 `resource_id/book_id/unit_id`。
- content 包素材实际位于 `material/`，音频 URL 解析已改为「先探测存在再生成 media_url」。

## 4. 结论

- "CEF→WebView2、STIC 插件→4 导出 DLL、远程 SPA→本地 Vue3、mq_server→Node" 的同架构复刻**跑通**；
- 登录、首页、作业、套卷、同步课程、错题、题库内容、音频均以真实账号/真实接口验证；
- 未实现：录音采集、ISE/AI 评测、考试提交、OSS/SLS 上传、自动更新器（UI 已标注）。
- 单会话说明：副本登录会顶掉官方客户端会话；反之亦然。设备指纹可在设置页填写以复用官方绑定。

> 截图与运行日志含账号信息，未随仓库发布；本文件只保留可公开的验证结论。

## 5. 录音 / ISE 评测（新增，2026-11-08）

基于真实练习抓包（docs/15_practice_protocol.md）实现并验证：

| 检查 | 结果 |
|---|---|
| speex 编码器参数 | 16k WB、quality 10、VBR off、bitrate=84800 → **106B/帧**，2 帧=212B 块（与抓包一致） |
| C++ `soundhelper.encode_speex` | 通过桥调用编码 8.1s PCM（259200B）→ 405 帧 / 106B / 42930B spx，耗时 158ms |
| ISE 评测（Python 参考实现） | 用抓包 spx 回放 → `code=000000`，逐词结果与原评测一致（accuracy 0.0609 vs 0.0609） |
| ISE 评测（复刻前端 JS） | WebView2 页面内：media PCM → `soundhelper` 编码 → 浏览器 WebSocket protobuf → 返回 XML/分数（2.7s） |
| 麦克风权限 | WebView2 自动授予：`getUserMedia` 打开 "麦克风阵列 (Realtek Audio)"，随后立即关闭 |
| Practice 页录音评测 | 已接入：开始录音 → 停止并评测 → 显示准确度/流利度/完整度/总分与逐词颜色 |

未完成：mp3 生成（上传所需，可调用安装目录 ffmpeg/lame）、OSS 上传与 `sync-v2` 的前端接入（Python 参考实现已验证 OSS 上传）。

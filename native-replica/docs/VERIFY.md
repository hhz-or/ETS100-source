# 运行期验证记录（native-replica）

> 环境：Windows 10 19045 x64；WebView2 Runtime 157.0.4341.42；MSVC 14.51；构建产物 `EtsReplica.exe`（C++20）。
> 验证方式：启动副本 + WebView2 远程调试（`ETS_REPLICA_DEBUG_PORT`）+ JS 桥探针；token 复用官方客户端当前会话（只读）。

## 1. 壳与桥

| 检查 | 结果 |
|---|---|
| 窗口标题 | `E听说 · 复刻版`（读 shell.ini） |
| WebView2 环境/控制器 | 初始化成功，`navigate https://app.ets.local/index.html hr=0` |
| 插件加载 | `plugin host initialized (loaded 7/7)`：EtsHelper、FileHelper、HttpHelper、SQLitePln、ShellHelper、SevenZip、SysConfig |
| `__core.info` | 返回 appDir/cacheDir/dataDir/mediaPort/platform=webview2/version |
| `__core.media_url` | 返回 `http://127.0.0.1:<port>/media?...`；GET 200、Range 206、越界 403 |
| `EtsHelper.encode_api_body_v2` | 与 Python/历史日志逐字节一致（同一 body/time 得到同一 sign） |
| `ShellHelper.getpcinfo` | 返回设备信息 JSON |
| `FileHelper` / `SevenZip` | 解包真实 `content_*.zip`，`FileHelper.readfile` 读回 JSON |
| mq_server | 副本 Node 中继起来（40001 被官方占用时自动 +1），壳按 `app.json` 端口连接 |

## 2. 真实 API（经 HttpHelper 插件、HTTPS）

| 接口 | 结果 |
|---|---|
| `POST /system/config` | `code=0`，返回真实配置 JSON（插件 WinHTTP + 签名链路） |
| `POST /user/info`（token） | `code=0`，返回真实昵称/年级/城市（token 来自官方客户端会话） |
| `POST /m/ecard/list` | `code=0`，返回学习卡数据 |
| `POST /g/homework/list` | 参数已对齐后仍有一处前端装配未通（见 docs/13 §4），插件与接口通道正常 |

## 3. 页面（注入有效 token 后）

`/home`、`/homework`、`/sets`、`/courses`、`/mistakes`、`/practice`、`/settings` 均渲染；
主页显示真实用户昵称/年级/城市与学习卡入口；mock 模式（浏览器直接打开 `dist/`）可离线预览。

## 4. 结论

- "CEF→WebView2、STIC 插件→4 导出 DLL、远程 SPA→本地 Vue3、mq_server→Node" 的同架构复刻**跑通**；
- 插件 ABI、JS 桥、签名、HTTPS、ZipCrypto、媒体服务均以真实数据验证；
- 剩余差距集中在少数前端数据装配（作业列表 parent_account_id）与非客户端能力（录音/评测/上传/更新），已在文档标注。

> 截图与运行日志含账号信息，未随仓库发布；本文件只保留可公开的验证结论。

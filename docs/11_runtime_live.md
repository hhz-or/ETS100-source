# 11 运行时验证（Live Instance + 在线前端全量获取）

> **前置条件**：Windows 10/11 x64；Python 3.10+；可选 Node.js 18+（阅读/运行 `mq_server` 与前端 JS）；可选 7-Zip（解包 zip/7z）。
> **如何复现**：在仓库根目录执行 `python scripts/<脚本名>.py`；机读数据在 `data/`，运行时证据在 `runtime/`；分析对象为只读安装副本 `<ETS_INSTALL_DIR>`（全程不修改其中文件）。
> **占位符**：`<ETS_INSTALL_DIR>`=目标程序安装目录；`<APPDATA_ETS>`=`%APPDATA%\ETS`；`<WORK_DIR>`=原分析工作区；`<BUILD_ROOT>`=厂商构建机路径前缀（二进制/日志内嵌字符串原文，仅作证据）。
> **本文复核**：`node scripts/dump_cdp.js`、`python scripts/download_chunks.py`、`python scripts/plugin_stubs.py`（需在测试机上启动一个只读分析副本）。

> 触发：在测试机上启动了 `<ETS_INSTALL_DIR>\ETSShell.exe`（即本报告的分析副本），并开放了 CDP。
> 方法：CDP(10086) 动态抓取 + 实时日志 + 在线 CDN 直取；**未修改目标文件、未注入代码**。
> 结论：静态分析的关键结论在真实运行环境中全部复现；并补齐了静态阶段缺失的 122 个 chunk 与插件 JS 封装层。

---

## 一、运行环境（观察）

| 项 | 值 |
|---|---|
| 启动路径 | `<ETS_INSTALL_DIR>\ETSShell.exe --shell-app-pull_params=`（从分析副本启动） |
| 进程 | browser(20896) + 2 renderer + gpu + 2 utility + `ets_mq_server.exe`（Node SEA） |
| CDP | **127.0.0.1:10086**（browser 监听；renderer 参数含 `--remote-debugging-port=10086`） |
| Profile | `<ETS_INSTALL_DIR>\temp\Cache_ETSShell`（本次运行刷新：Cache 102 文件/23 MB） |
| 日志 | `logs\ets_2026-11-6.log`（469 KB，本次会话）；cef/shell 日志本次为 0 字节 |
| 页面 | `https://statics.ets100.com/ets-student-pc-web/index.html?tdt=…#/main/home`，标题「E听说」，右上角显示 **E听说V5.7.9版** |
| 子进程参数 | `--no-sandbox`、`--ignore-certificate-errors`、`--use-gl=swiftshader-webgl`、`--register-pepper-plugins=plugins/pepflash/mpvjs.node;application/x-mpvjs`、`--disable-features=NetworkService,OutOfBlinkCors,SameSiteByDefaultCookies` |
| 其它 | `plugins\pepflash\mpvjs.node` **实际不存在**（声明了但未随包分发，播放器可能是可选组件） |

CDP 返回 `Chrome/91.0.4472.124`、协议 1.3，与 `libcef.dll` 版本一致。

---

## 二、在线前端版本（与本地缓存的差异）

| 项 | 本地缓存（10-28/11-04 会话） | 在线（11-06 会话） |
|---|---|---|
| 主 bundle | `assets/index-dc0257dd.js` 3,481,698 B | `assets/index-e7d07c24.js` 3,481,698 B |
| SHA-256 | `d87e84c9…` | `11ab53fd…` |
| 差异 | — | **仅懒加载 chunk 的内容哈希被重新打包**（文件名 `<Component>-<hash>` 全变），主 bundle 内核心代码逐字一致 |

核心常量逐一比对（live vs 旧缓存，计数完全相同）：`f05323cb91d422b2`（k_serves）、`ldlflfgirerjfkcf`（k）、`encode_api_body_v2`、`sign_protocol_selected`、`BEGIN RSA PRIVATE KEY`、`key_id`/`sign_version`、`grlx`、`EtsSignatureAdapter`、`wss://`/`eduaiplat`/`api.ets100.com`。
→ **签名算法、AES 密钥、RSA 私钥、协议结构均未变化**，08/03 的结论继续适用。

补充：主 bundle 中可见回退版本字符串 `"5.7.3"`，但外观版本（标题栏/日志）为 5.7.9；该字符串可能是前端资源的兼容标记，非客户端版本。

---

## 三、前端全量 chunk（补齐静态阶段的 122 个缺口）

方法：
1. CDP `Debugger.getScriptSource` 抓当前页已加载脚本（36 个）；
2. 在线 CDN 现已可直连（本次 `statics.ets100.com` → 198.18.0.86，HTTP 200），从主 bundle 提取全部动态 import 名称并批量下载；
3. 与旧 `routes.json` 按「组件基名」对齐（哈希已变）。

结果（`runtime/chunks_full/（未随仓库发布）`，4.6 MB）：

| 指标 | 数值 |
|---|---|
| 下载文件 | **188 个 JS chunk**（+ index.html、主 bundle） |
| 旧 routes 引用的 191 个 chunk | **186 个按基名映射成功**；其余 5 个是 Vue SFC 虚拟模块名（内联在其它 chunk，非独立文件）→ 实际 **100% 覆盖** |
| 新发现模块（旧缓存缺失） | `WordList`、`WordPractice`、`WordPracticeResult`、`WordQuestion`、`WordQuestionResult`、`PKMatch`、`readAloud`、`readSentence`、`readSentenceScoreInfo`、`networkSpeedWorker`、`textInfo` 等 14 个 |
| 映射结果 | `data/frontend/routes_live.json`（91 路由 → 在线 chunk 名） |

→ **未知项 U1（122 个未缓存 chunk）已解决**。

---

## 四、插件 JS 封装层（权威 action 表 + pluginKey 精确名称）

在线前端把 9 个原生插件封装为独立 JS（`/ets-student-pc-web/plugins/stic/*.js`，共 12 个文件），可直接读出**精确的 pluginKey、action、参数序列化方式、超时**。修正了此前按日志推断的名称大小写：

| pluginKey（精确） | 文件 | action 数 | 备注 |
|---|---|---|---|
| `appcontroller` | appcontroller.js | 14 | init/close/maximize/minimize/restore/move(×2)/fullscreen/reduction/hide/show/get_win_pos/set_win_pos/startapp/idg_exist |
| `EtsHelper` | etshelder.js | 11 | **大写 E/H**；含 `encode_api_body(_v2)`、`encode_api_resp(_v2)`、`dub_merge`、`log_data`、`check_update(_force)`、`run_update`、`open_url_by_def_browser`、`test_crash`、`get_appdata_path` |
| `FileHelper` | filehelper.js | 24 | readfile/readbinaryfile/writefile/writefilewithbinary/savefiledialog/openfiledialog/existfileorfolder/copyfileordirectory/deletefileordirectory/getfoledersize/createfolder/renamefolder/removefiletootherpath/ergodicfiles/savefiledialog/readrpk_kqlx/getbase64/getmd5/aliyun_oss_md5/getcode/closeshell/ncttools/openbrowsedialog/cleardir |
| `HttpHelper` | httphelper.js | 8 | init/upload/download/isrpkexist/downloadresource/downloadsdk/monitornetspeed/stopdownload |
| `SevenZip` | sevenzip.js | 4 | init/unzip/zip/test |
| `ShellHelper` | shellhelper.js | 33 | init/getroomid/executecmd/executeexe/executebat/startprocess/stopprocess/processexist/CheckAudio/setvolume/getvolume/setmute/checkadapter/getpcinfo/getconfig/cmd/netcheck/padkeyboardup/closewin7padkeyboardup/getuniqueid/initActAuth/unInitActAuth/actauth/getactauth/gettoken/destroy/setsuspensionballconfig/getsysytemlocalpath/clipboard… |
| `soundhelper` | sndhelper.js | 14 | record/play/pause/continue/stop/convertfile/aqcwavfile/combineandconvertwavtomp3/checkvoice/checkwovfile/trace/loadfile/init/destroy |
| `sqlitepln` | sqlitepln.js | 6 | connect/disconnect/execQuery/execDML/init/destroy |
| `SysConfig` | sysconfig.js | 1 | init |

协议细节（观察）：
- 统一形式：`uid = cef.message.createGuid()+"@"+action`；`setMessageCallback(uid, cb)`；`sendMessage(uid, "PluginKey", "action", JSON.stringify(args) 或 "")`；回调后 `removeMessageCallback`。
- 部分 action（如 `encode_api_body_v2`、`encode_api_resp_v2`）走通用封装，带 **800 ms 超时**（超时回调空串）。
- 9 个通道合计 **115 个不同 (plugin, action) 对**（与静态 bundle 提取的 117 差异来自动态 action 与重复调用，见 `data/frontend/plugin_stubs_analysis.json`）。

---

## 五、运行时协议验证

本次会话日志（21:16–21:20）：**72 条请求 / 75 条响应**，25 个不同 path。

- **签名**：对 68 条带 `head.sign` 的请求用 08 的公式复算，**68/68 命中**（0 失败）→ 签名算法在在线版本上依然成立。
- **GET 直连**：4 条 `GET /point-service/account/trail?resource_id=…&id=…&token=<JWT>` **不带 `head`/`sign`**，直接以 URL 参数携带登录 JWT。说明协议存在两类调用：
  1. 业务 POST：`{body: base64([{r,params}]), head:{version,sign,pid,time,time_second}}`
  2. 轻量 GET：query 直传（token 在 URL 中）
- 25 个 path 全部落在既有清单内（`//announcement/list`、`//config/config/getResourcePlatformToken` 为旧清单中双斜杠写法）。
- 资源链（`PLG_STIC`）：启动时检查/下载 `common.zip`（`https://cdnfeis.ets100.com/202611062116/9e29…/file/ebce…zip`）→ 解压到 `%APPDATA%\ETS\common`；检查 `clear_cache`、`pc_xst_dict`；与 06/07 的资源链一致。

---

## 六、运行时页面状态（鉴权与存储确认）

`Runtime.evaluate` 直接读取（值已脱敏）：

| 存储 | 键（18/8 个） | 说明 |
|---|---|---|
| localStorage | `appLogin`、`appConfig`、`appOssStore`、`resourcePlatformStore`、`userInfo`、`clientConfig`、`systemConfig`、`homeworkStore`、`mediaSetting`、`appTranslateSettingStore`、`syncLessionStore`、`specialStore`… | 账号+混淆密码、OSS STS、资源平台 token、系统配置 |
| sessionStorage | `__aiplat_token_config`（AI accessToken + expiresIn）、`allEcardList`、`mistakeManagerStore`、`winConfig`、`previousPath`… | AI 评测 token 与本次会话状态 |
| `cef.message` | 17 个方法（sendMessage/setMessageCallback/createGuid/getAppConfig/setProxy…） | 与 `壳内嵌 JS 前导提取件（未随仓库发布）` 完全一致 |
| inline script | 17 个 | 壳注入 + 页面内联 |

> 登录态 token 的长期存储仍在 IndexedDB（06 已确认），本次运行未改变该结论。

---

## 七、方法与可复现

| 脚本 | 作用 |
|---|---|
| `scripts/dump_cdp.js` | 连接 10086，reload 后抓全部 script source / 网络响应体 / 页面状态 / 截图 |
| `scripts/route_nav.js` | 按 91 条路由逐一切换 hash，抓新加载 chunk（**注：约 40 秒后可能因某个大 chunk 的 `getScriptSource` 无响应而挂起，正式版应加超时；本次改用在线 CDN 直取完成覆盖**） |
| `scripts/download_chunks.py` | 从在线 CDN 批量下载全部 chunk（188 个）+ 生成 manifest |
| `scripts/live_log.py` | 解析本次会话日志，验证签名（68/68） |
| `scripts/plugin_stubs.py` | 从插件 JS 封装提取权威 action 表 |
| `scripts/version_diff.py` | 在线 vs 缓存主 bundle 差异对照 |
| `scripts/map_live_routes.py` | 旧 routes → 在线 chunk 映射 |

产物：`runtime/` 下的证据文件（含 `runtime/live_requests.json` 等；chunk 全量、截图等大文件未随仓库发布）。

---

## 八、对既有结论的修正/补充

1. **pluginKey 大小写**：正确值为 `EtsHelper`、`FileHelper`、`HttpHelper`、`SevenZip`、`ShellHelper`、`SysConfig`（首字母大写），`appcontroller`、`soundhelper`、`sqlitepln` 为小写；此前文档按 action 记录，未强调通道名。
2. action 总数：在线权威表 **115 对**（覆盖 9 通道），静态 bundle 统计 117 对；差异来自动态 action 与重复调用。
3. 新增模块：Word 系列、PKMatch、readAloud/readSentence、networkSpeedWorker、textInfo（此前缓存缺失）。
4. GET 直连路径携带 token，不参与签名。
5. `mpvjs.node` pepper 插件被声明但文件不存在（不影响主流程）。

---

## 九、补齐的模块说明（此前缓存缺失）

在线 chunk 全量下载后，新增可分析的模块（`data/frontend/new_modules_analysis.json`）：

| 模块 | 大小 | 功能（依据页面文案与 API 调用） |
|---|---|---|
| `WordList` | 5.2 KB | 单元单词列表：全部/已掌握/未掌握、单词设置、重新练习提示、单元掌握完成提示、单词 PK 入口 |
| `WordPractice` | 4.1 KB | 单词学习：单词认识、例句、认识/不认识、上一词/下一题 |
| `WordQuestion` | 8.0 KB | 单词练习四题型：词义辨析、单词听说、单词拼写；音效开关；退出保存进度 |
| `WordPracticeResult` / `WordQuestionResult` | 0.9/2.2 KB | 练习结束页：掌握单词数、继续练习未掌握单词 |
| `PKMatch` | 3.9 KB | 单词 PK 匹配：资源版取题、匹配/重新匹配、对手被抢、不对齐拦截 |
| `readAloud` | 35.3 KB | 全文朗读练习：录音、评分中、原文试听、拉伸后/原始录音时长、补交与截止限制 |
| `readSentence` + `readSentenceScoreInfo` + `textInfo` | 21.2/9.8/18.5 KB | 逐句跟读：完整度/准确度/流畅度评分说明、单句重做限制、原文/分句试听、提交确认 |
| `networkSpeedWorker` | 0.6 KB | 网络测速 Web Worker |
| `index-62bff6b1` / `index-85cbaae4` | 7.0/5.1 KB | 模块索引（完成度、数据异常兜底） |

在线路由表复核：主 bundle 可解析出 **69 条带 component 的路由**，与缓存 `routes.json` 的路径集合**无新增差异**；另有 6 个壳级路径（`/app-start`、`/startup`、`/error`、`/system-message`、`/bypass`、`/:catchAll(.*)`）。→ 路由结构稳定，变化只在打包哈希与 chunk 拆分。

---

## 十、原生 action 运行时探针（cef.message 直调）

方法：在页面 `Runtime.evaluate` 中直接用 `cef.message.createGuid / setMessageCallback / sendMessage` 对**只读** action 发起调用（2–2.5 s 超时），不依赖前端封装模块。脚本：`scripts/probe_native.js`、`probe_native2.js`；原始返回：`运行时探针原始返回（未随仓库发布）`。

### 10.1 签名 oracle（决定性运行时证据）

| 调用 | 入参 | 原生返回 | 结论 |
|---|---|---|---|
| `EtsHelper.encode_api_body_v2` | `{body:"W3siciI6InN5c3RlbS90aW1lIiwicGFyYW1zIjp7InNuIjoidGVzdCJ9fV0=", time:"1793971732563"}` | `{"key_id":"202608","pid":"pcWin","sign":"7960a6bda26ffa4b2ec84725036488e0","sign_version":"2"}` | 与公式 `md5("pcWin"+time+body_b64+"94cf…")` **完全一致**（`data/api/sign_oracle.json`，match=true） |
| `EtsHelper.encode_api_body`（v1） | 同上 | 32 hex `b0eb949d3f1bc869751594fc013099cb` | v1 为遗留路径，输入拼接未闭合（本客户端不使用） |
| `EtsHelper.encode_api_resp_v2` | `{response:"W10=", time:"…"}` | `{"key_id":"202608","pid":"pcWin","sign":"6d3d82172ce30999a4b3890a022619bb","sign_version":"2"}` | 响应签名**确实存在**；但前端无调用点，canonical 拼接未匹配（U3） |
| `EtsHelper.encode_api_resp`（v1） | 同上 | 32 hex `086a94f6c8b8638b93c02023336ec2f2` | 同上 |

> 这是比"日志回放"更强的证据：请求-响应对由本次实时调用产生，公式逐字节吻合。

### 10.2 只读能力探针（节选，真实值已脱敏）

| 插件.action | 返回（摘要） | 说明 |
|---|---|---|
| `ShellHelper.getpcinfo` | 30+ 字段设备指纹：`AppTitle/ClientType/CopyRight/CPU/内存/物理内存/磁盘总量与剩余/HDD 卷/网卡 MAC/内网 IP/系统版本/输入输出设备/WPS/Python/防火墙/投屏` | 用于客户端环境采集与上报 |
| `ShellHelper.getconfig` | 壳配置：`AppTitle/ClientType/CopyRight/FullScreen/HDSerial/LogoTitle/Name/OS/OSBit/Version` | OS 固定返回 "Microsoft Windows 8"（实际 Win11，兼容字段）；MAC 归零 |
| `ShellHelper.getvolume` / `setvolume` | `{"volume":70}` / 设置成功 | 探针曾设为 50，已还原 70 |
| `ShellHelper.getroomid` | `{rncode:0, rnmsg:"{\"roomId\":\"\"}"}` | 录播/直播房间号 |
| `ShellHelper.checkadapter` | `{rncode:1, rnmsg:"网卡正常."}` | 网络适配器自检 |
| `EtsHelper.get_appdata_path` | `%APPDATA%` | 用户数据根 |
| `EtsHelper.check_update` | `{rncode:0, rnmsg:"no newer version"}` | 更新检查 |
| `FileHelper.getfoledersize` | `{errorCode:0, errorMsg:"get dir size ok", flag:…}` | 接受 `{filePath}` |
| `FileHelper.getbase64` | `"ok"` | 读取并转 Base64（参数 schema 待定） |
| `HttpHelper.isrpkexist` | `{code:0, filePath:""}` | 本地 rpk 包检查 |
| `appcontroller.get_win_pos` | 字段值异常（win_width 负数） | 需先 `init` 建立窗口上下文 |
| `SysConfig.init` | `"OnTaskAction InteralErr。"` | 厂商拼写错误原样；需特定参数 |

### 10.3 参数 schema 观察

- 绝大多数 action 期望 **JSON 字符串**；`get_appdata_path`、`check_update`、`getpcinfo`、`getvolume`、`checkadapter`、`getroomid` 可传空串或 `{}`。
- `getfoledersize` 接受 `{"filePath":"..."}`；但 `existfileorfolder` 用 `{path}` / `{filePath}` 均返回空 path/false，说明其 JSON 结构还有额外字段（待定，见 U8）。
- 部分 action 依赖前置状态（`appcontroller` 需 init；`SysConfig.init` 需要配置对象）。

### 10.4 副作用与还原

- 探针仅调用只读 action；唯一写操作是 `setvolume`（系统音量 70→50），已立即 `setvolume(70)` 还原。
- 未写文件、未发起业务写请求、未修改页面状态。

### 10.5 运行时 HTTP 头（观察）

对 `api.ets100.com` 的业务 POST 请求，CDP 捕获到的请求头只有：

```
Content-Type: application/json
Accept: application/json, text/plain, */*
User-Agent: Mozilla/5.0 (Windows NT 6.2; WOW64) ... Chrome/91.0.4472.124
Referer: https://statics.ets100.com/
sec-ch-ua / sec-ch-ua-mobile
```

- **没有 `Authorization`、没有自定义鉴权头**：登录态 token 放在请求体 `params.token` 内（与 `03_api_protocol.md` 的信封一致），并由 `head.sign` 保护完整性。
- GET 直连请求（`/point-service/account/trail`）把 `token` 放在 URL query 中。
- 未捕获到 `ws://127.0.0.1:40001` 的 WebSocket 帧事件（CEF 91 的 CDP Network 域未上报该本地 WS；不影响结论，帧格式已由 `mq_server/main.js` 明文确定）。

---

## 十一、Frida 原生运行时观测（2026-11-07）

在官方客户端运行中，用 Frida 17 附着到 CEF browser 进程，对 `etshelper.pln` 的签名函数与 9 个插件的 `PlnOnProcessMessage` 导出做**只读** Interceptor 观测（不修改参数/返回值）。脚本：`scripts/frida_ets2.js`、`frida_ets3.js`、`frida_ets4.js`、`frida_md5.js`、`frida_runner.py`。

> 说明：Frida 17 移除了 `Memory.readPointer` 等全局读函数，改用 `NativePointer.readU32()/readPointer()/readUtf8String()/readUtf16String()`；插件参数为 **UTF-16** 字符串。

### 11.1 插件分发 ABI（实机确认）

每次前端 `sendMessage(uid, pluginKey, action, args)` 都会在原生侧命中：

```
PLN <Module>.pln  arg2=<actionKey>  arg3={"..." JSON 参数}
```

- 模块名：`EtsHelper.pln`、`FileHelper.pln`、`HttpHelper.pln`、`ShellHelper.pln`、`SevenZip.pln`、`sqlitepln.pln`、`appcontroller.pln`（**首字母大小写与前端 pluginKey 一致**，仅 `soundhelper` 未见独立消息）。
- `PlnOnProcessMessage` 的第 1 个参数（ecx）为宿主上下文，第 2 个（edx/arg2）为 action 字符串，第 3 个（arg3）为 UTF-16 JSON 参数；与 `05_native.md` 的静态 ABI 结论一致。

### 11.2 签名函数实机输入（决定性证据）

| 动作 | 捕获到的原生入参 | 输出 |
|---|---|---|
| `encode_api_body_v2` | `OnEncodeAPIBody sel=1 {body:b64,time:ms}` → `sign_body sel=1 A="pcWin" B=time C=b64` | 与本报告公式 `MD5(A+B+C+KEY_V2)` **逐字节一致**（运行时 oracle，见 `runtime/sign_oracle.json`） |
| `encode_api_body`（v1） | `sel=0 A="grlx" B=time C=b64` | 返回 32 hex；v1 拼接未完全对齐（遗留路径，客户端不调用） |
| `encode_api_resp_v2` | `OnEncodeAPIResp sel=1 {response:b64,time}` → `sign_resp sel=1 A="pcWin" B=b64 C="test"` | `MD5(A+B+KEY_V2+C)` = `6d3d8217…` **逐字节一致**（响应签名由此闭合） |
| `encode_api_resp`（v1） | `sel=0 A="grlx" B=b64 C="test"` | 32 hex（同上，遗留路径） |

由 `sign_body` / `sign_resp` 的参数序可确认原生实现的拼接顺序：

- 请求：`MD5(pid + time + body_b64 + KEY)`
- 响应：`MD5(pid + resp_b64 + KEY + sn)`（`sn` 观测为 `test`，密钥流插在最后一段之前）

### 11.3 观测的边界与副作用

- 仅安装 Interceptor 读取参数，未修改行为；每次观测结束后 `detach`。
- 对全部插件导出做"任意指针探测"的重型 hook 会显著拖慢原生分发（表现为插件调用超时），建议只 hook 目标函数；本次已改用精简 hook 完成最终取证。
- 观测期间未影响客户端正常功能与登录态。

### 11.4 产物

`runtime/frida_events.jsonl`、`runtime/frida_paired.jsonl`、`runtime/frida_md5.jsonl`、`runtime/v1_oracle.json`、`runtime/sign_oracle.json`。

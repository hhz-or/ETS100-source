# 11 运行时验证（Live Instance + 在线前端全量获取）

> 触发：用户在本机启动了 `D:\ets-rea\ETS\ETSShell.exe`（即本报告的分析副本），并开放了 CDP。
> 方法：CDP(10086) 动态抓取 + 实时日志 + 在线 CDN 直取；**未修改目标文件、未注入代码**。
> 结论：静态分析的关键结论在真实运行环境中全部复现；并补齐了静态阶段缺失的 122 个 chunk 与插件 JS 封装层。

---

## 一、运行环境（观察）

| 项 | 值 |
|---|---|
| 启动路径 | `D:\ets-rea\ETS\ETSShell.exe --shell-app-pull_params=`（用户从分析副本启动） |
| 进程 | browser(20896) + 2 renderer + gpu + 2 utility + `ets_mq_server.exe`（Node SEA） |
| CDP | **127.0.0.1:10086**（browser 监听；renderer 参数含 `--remote-debugging-port=10086`） |
| Profile | `D:\ets-rea\ETS\temp\Cache_ETSShell`（本次运行刷新：Cache 102 文件/23 MB） |
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

结果（`work/runtime/chunks_full/`，4.6 MB）：

| 指标 | 数值 |
|---|---|
| 下载文件 | **188 个 JS chunk**（+ index.html、主 bundle） |
| 旧 routes 引用的 191 个 chunk | **186 个按基名映射成功**；其余 5 个是 Vue SFC 虚拟模块名（内联在其它 chunk，非独立文件）→ 实际 **100% 覆盖** |
| 新发现模块（旧缓存缺失） | `WordList`、`WordPractice`、`WordPracticeResult`、`WordQuestion`、`WordQuestionResult`、`PKMatch`、`readAloud`、`readSentence`、`readSentenceScoreInfo`、`networkSpeedWorker`、`textInfo` 等 14 个 |
| 映射结果 | `work/runtime/routes_live.json`（91 路由 → 在线 chunk 名） |

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
- 9 个通道合计 **115 个不同 (plugin, action) 对**（与静态 bundle 提取的 117 差异来自动态 action 与重复调用，见 `work/runtime/plugin_stubs_analysis.json`）。

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
| `cef.message` | 17 个方法（sendMessage/setMessageCallback/createGuid/getAppConfig/setProxy…） | 与 `work/lead/shell_bridge_prelude.js` 完全一致 |
| inline script | 17 个 | 壳注入 + 页面内联 |

> 登录态 token 的长期存储仍在 IndexedDB（06 已确认），本次运行未改变该结论。

---

## 七、方法与可复现

| 脚本 | 作用 |
|---|---|
| `work/scripts/dump_cdp.js` | 连接 10086，reload 后抓全部 script source / 网络响应体 / 页面状态 / 截图 |
| `work/scripts/route_nav.js` | 按 91 条路由逐一切换 hash，抓新加载 chunk（**注：约 40 秒后可能因某个大 chunk 的 `getScriptSource` 无响应而挂起，正式版应加超时；本次改用在线 CDN 直取完成覆盖**） |
| `work/scripts/download_chunks.py` | 从在线 CDN 批量下载全部 chunk（188 个）+ 生成 manifest |
| `work/scripts/live_log.py` | 解析本次会话日志，验证签名（68/68） |
| `work/scripts/plugin_stubs.py` | 从插件 JS 封装提取权威 action 表 |
| `work/scripts/version_diff.py` | 在线 vs 缓存主 bundle 差异对照 |
| `work/scripts/map_live_routes.py` | 旧 routes → 在线 chunk 映射 |

产物：`work/runtime/{scripts,net,chunks_full,screenshot.png,page_state.json,live_requests.json,plugin_stubs_analysis.json,routes_live.json,chunks_manifest.json}`。

---

## 八、对既有结论的修正/补充

1. **pluginKey 大小写**：正确值为 `EtsHelper`、`FileHelper`、`HttpHelper`、`SevenZip`、`ShellHelper`、`SysConfig`（首字母大写），`appcontroller`、`soundhelper`、`sqlitepln` 为小写；此前文档按 action 记录，未强调通道名。
2. action 总数：在线权威表 **115 对**（覆盖 9 通道），静态 bundle 统计 117 对；差异来自动态 action 与重复调用。
3. 新增模块：Word 系列、PKMatch、readAloud/readSentence、networkSpeedWorker、textInfo（此前缓存缺失）。
4. GET 直连路径携带 token，不参与签名。
5. `mpvjs.node` pepper 插件被声明但文件不存在（不影响主流程）。

# 04 前端逆向分析（E 听说学生端 PC）

> **前置条件**：Windows 10/11 x64；Python 3.10+；可选 Node.js 18+（阅读/运行 `mq_server` 与前端 JS）；可选 7-Zip（解包 zip/7z）。
> **如何复现**：在仓库根目录执行 `python scripts/<脚本名>.py`；机读数据在 `data/`，运行时证据在 `runtime/`；分析对象为只读安装副本 `<ETS_INSTALL_DIR>`（全程不修改其中文件）。
> **占位符**：`<ETS_INSTALL_DIR>`=目标程序安装目录；`<APPDATA_ETS>`=`%APPDATA%\ETS`；`<WORK_DIR>`=原分析工作区；`<BUILD_ROOT>`=厂商构建机路径前缀（二进制/日志内嵌字符串原文，仅作证据）。
> **本文复核**：`python scripts/work_frontend_scripts_1_parse_cache.py` 等（缓存解析/导出/路由/action 提取脚本均在 `scripts/`）。

> 目标：`<ETS_INSTALL_DIR>`（只读）。远程 SPA：`https://statics.ets100.com/ets-student-pc-web/`（Vue3 + ElementPlus，Vite 构建）。
> 数据来源：CEF/Chromium 磁盘缓存的离线解析（`<ETS_INSTALL_DIR>\temp\Cache_ETSShell\Cache`），**未联网、未执行目标代码**。
> 产物：已发布的机读数据在 `data/frontend/`（路由、action、端点、在线 chunk 清单等 JSON）；原始 bundle、可读化 bundle 与提取中间产物未随仓库发布，解析脚本在 `scripts/`。
> 生成时间：2026-11-06。

---

## 0. 结论摘要（先看这里）

| 项目 | 结果 |
|---|---|
| 缓存条目（URL 资源）总数 | **353** 条（`index` 文件头声明 353，与解析一致） |
| 可提取资源 | **353/353** 全部成功（0 失败）；去重后 **209** 个唯一文件，约 **10.5 MB** |
| 类型分布（按条目） | bin=2, css=10, gif=3, html=84, jpg=64, js=116, json=13, png=60, txt=1 |
| gzip 解压条目 | 106 条（Chromium 缓存的是网络原始字节，部分为 `Content-Encoding: gzip`） |
| 路由 | **91** 条（模块路由 65 + 主路由 26），含 path/name/component/chunk/meta |
| 懒加载 chunk 引用 | **191** 个不同文件名；本次缓存命中 **69** 个，缺 **122** 个（未被访问过，标“未知”） |
| cef.message 桥 action | **120** 处 `sendMessage` 调用点 / **115** 个不同 `插件.action` + 2 个动态 action（encode_api_body_v2 / encode_api_resp_v2），共 **117** 个原生 action；旧评估 127 的差异见 §7.5 |
| 桥通道（plugin channel） | 9 个：EtsHelper, FileHelper, HttpHelper, SevenZip, ShellHelper, SysConfig, appcontroller, soundhelper, sqlitepln |
| API 端点 | **118** 个（另有 1 个正则误报已剔除），全部走统一信封 + 签名 |
| Pinia store | **20** 个，见 §5 |
| 核心链路 | 路由守卫→API 签名（v1/v2）→录音（原生 SndHelper）→流式评测（双通道 ISE/AI2）→OSS 直传→评分同步 `/m/audio/sync-v2`；日志三路（本地 WS→mq_server 写 logs、阿里云 SLS、log_collector） |

关键“首次还原”内容：

1. **Chromium blockfile 缓存格式**（`data_0..3` 块文件 + `index` + `f_*` 外部文件）被完整解码，所有 URL、响应头、响应体可还原（§1.2）。之前“f_ 文件只能靠魔数猜类型”的做法不再必要。
2. **API 签名协议** v1/v2（`EtsSignatureAdapter`）：body 先 `JSON.stringify` 再 base64，`head.sign/pid/time` 由原生 `EtsHelper.encode_api_body[_v2]` 生成；v2 返回 `{pid,key_id,sign,sign_version:"2"}`，签名为 32 位 hex。实测日志显示当前客户端走 **v2、pid=pcWin**（§6.3）。
3. **录音→评测链路**：录音由原生 `soundhelper` 完成（`record` 的 `recordTime` 单位为 0.1s，`dataStreamType` 为 `"10"` 或 `"spx"`），音频通过 `datastream_callback` 以 **40ms/6400B** 分片推给评测 SDK；引擎由 `ecard.engine_config` 规则表选择（AI2/AI_2MIX/AI_2INS/AI_2EXAM），结果写回 `/m/audio/sync-v2`（§8）。
4. **日志/埋点三路**：`LoggerUtils` → 本地 `ws://127.0.0.1:<suspensionBallPort|40001>` → `ets_mq_server.exe` → `<ETS_INSTALL_DIR>\logs\ets_*.log`；阿里云 SLS `WebTrackerBrowser`（STS 凭证来自 `g/data/sls-config`）；`log_collector` 表单上报；崩溃/日志 zip 经 OSS 上传（§9）。

---

## 1. 数据来源与缓存提取

### 1.1 缓存目录结构

`<ETS_INSTALL_DIR>\temp\Cache_ETSShell\Cache\`：

| 文件 | 大小 | 含义 |
|---|---|---|
| `index` | 262,512 | 缓存条目索引（magic `0xC103CAC3`），头部含 `num_entries=0x161=353` |
| `data_0` | 45,056 | 块文件 #0（block size 36，基本空闲） |
| `data_1` | 270,336 | 块文件 #1（block size **256**）——**EntryStore（条目元数据）全部在此**，也存小数据块 |
| `data_2` | 1,056,768 | 块文件 #2（block size **1024**）——内联响应体 |
| `data_3` | 4,202,496 | 块文件 #3（block size **4096**）——内联响应体/响应头（HTTP 头流几乎都在这里） |
| `f_000001..f_000030` | 17 KB–3.4 MB | **外部文件**：>16KB 左右的响应体单独成文件（gzip 或原始字节） |
| `Code Cache\js` | — | V8 字节码缓存，仅作辅助，本报告不依赖 |

### 1.2 格式解码方法（可复现）

块文件（blockfile）头部（小端）：

```
+0  u32 magic = 0xC104CAC3
+4  u16 version(=0) / u16 (=2)
+8  u16 this_file / u16 next_file
+12 u32 block_size     // data_0=36, data_1=256, data_2=1024, data_3=4096
+16 u32 max_entries
...
数据区起点 = 8192（前两块为头部/位图）
```

`data_1` 中按 **256 字节对齐**扫描得到 EntryStore（353 条，与 index 声明一致）：

```
+0   u32 key_hash
+4   u32 next
+8   u32 rankings_node
+12  i32 reuse_count
+16  i32 refetch_count
+20  i32 state
+24  u64 creation_time      // 1601 起的微秒数（已校验：= 2026 年）
+32  i32 key_len
+36  u32 long_key           // 0 或外部文件地址
+40  i32 data_size[4]       // 4 个流：0=响应头(Pickle) 1=响应体 2/3 备用
+56  u32 data_addr[4]
+72  u32 tag
+96  char key[key_len]      // URL；key_len>160 时走 long_key
```

`data_addr` 解码（本次逆向出的规则，已对全部流做一致性校验）：

```
file_type = addr >> 28
  == 0x8 : 外部文件，文件号 = addr & 0xFFFFFF  ->  f_%06x
  != 0x8 : 块文件，file_number = (addr >> 16) & 0xFF  (0..3 -> data_0..3)
            start_block  = addr & 0xFFFF
            文件偏移 = 8192 + start_block * block_size(file_number)
高位字节 0xA0..0xC3 是分配尺寸档位（随流大小分档），不参与定位。
```

流 0（响应头）是 Chromium 的 `HttpResponseInfo` Pickle：`u32 payload_len`、`u32 flags`、`u64 request_time`、`u64 response_time`、`u32 headers_len`，随后是 NUL 分隔的原始响应头（含 `HTTP/1.1 200 OK`、`Content-Length` 等）。据此可获得 URL 的 MIME、编码与缓存时间。

校验结果：353 个条目中 340 个响应头流地址按上式命中（其余 13 条指向 `data_1` 已淘汰/覆写的旧块，标“未知”）；48 个外部文件地址全部命中 `f_000001..f_000030`。

解析脚本（均位于 `scripts/`）：`work_frontend_scripts_1_parse_cache.py`（解析）、`work_frontend_scripts_2_extract.py`（导出）、`work_frontend_scripts_4_dedupe.py`（去重）、`work_frontend_scripts_5_pretty.py`（格式化）、`work_frontend_scripts_12d_routes.py` / `work_frontend_scripts_30_routes_final.py`（路由）、`work_frontend_scripts_31_action_keys.py`（桥）、`work_frontend_scripts_22_api_stores.py`（API/store）、`work_frontend_scripts_40_make_doc.py`（本文生成）。
证据：缓存条目清单（353 条原始条目：URL、hash、地址、大小、响应头；该清单未随仓库发布）。

### 1.3 提取产物

- **前端原始 bundle**（未随仓库发布）：**209** 个唯一文件，命名 `NNN_<host>__<path>.<ext>`；`NNN` 是缓存条目序号（与 manifest 对应）。
- **前端资源清单**（`data/frontend/manifest.json`，未随仓库发布）：353 条清单，字段 `index/url/file/duplicate_of/cache_file/stored_size/size/gzip/sha256/type/content_type/status/headers/pretty/pretty_lines`。
- **前端可读化 bundle**（未随仓库发布）：139 个文本资源的“可读/可引用行号”版本（仅在 `; { }` 后插入换行，**不改变字符序列**，因此可按行号引用；原始文件仍是单行 minified）。
- 抓到的资源按 host 分布：

| host | 条目数 |
|---|---|
| statics.ets100.com | 228 |
| dcp.changyan.com | 63 |
| static.geetest.com | 19 |
| teacher.ets100.com | 18 |
| static.ets100.com | 11 |
| cdn.subject.ets100.com | 6 |
| cdnfeis.ets100.com | 5 |
| api.ets100.com | 1 |
| cdnfei.ets100.com | 1 |
| www.ets100.com | 1 |

> 说明：`pc-listen.html`、`pc-listen-answer.html`、`pc-entity.html` 等同一 URL 在缓存中重复多次（不同 token/时间），去重后只保留一份。

### 1.4 外部文件（f_*）完整映射（48 个）

| 缓存文件 | URL | 存储大小 | 解压后 |
|---|---|---|---|
| `f_000029` | http://cdn.subject.ets100.com/entity/0729fb93c5da69ae6508aaf107c98b97/content2.json | 24482 | 24482 |
| `f_00002f` | https://cdnfeis.ets100.com/202611041936/516f0a808b190ff161b667fc76418efc/dub/1a9e21cdb46 | 19166 | 19166 |
| `f_00002e` | https://cdnfeis.ets100.com/202611041936/7c409436087e4abfe1f149452da4da33/dub/7aa960721b6 | 21396 | 21396 |
| `f_00002d` | https://cdnfeis.ets100.com/202611041936/99215c850071ec5664ce9b960cf6a6aa/dub/41cb4fbfb34 | 23554 | 23554 |
| `f_00002c` | https://cdnfeis.ets100.com/202611041936/a7a161161221211ae5f991bdb00e8bf9/dub/bae4f84c695 | 17653 | 17653 |
| `f_000030` | https://cdnfeis.ets100.com/202611041936/f2824b42e81c50613cb9d7cb3e48f0dc/dub/b560f6594fa | 19075 | 19075 |
| `f_000005` | https://dcp.changyan.com/dcp-js/analysis.js?sdk_ver=1.0.8 | 38772 | 110563 |
| `f_000004` | https://dcp.changyan.com/dcp-js/entry.js | 20329 | 54444 |
| `f_000026` | https://static.ets100.com/teacherend/dist/js/default-c2034ffd72.js | 47133 | 152356 |
| `f_000024` | https://static.ets100.com/teacherend/dist/plugin/bluebird.min.js | 27277 | 81530 |
| `f_000027` | https://static.ets100.com/teacherend/dist/plugin/collect-rangers-v5.2.6.js | 78495 | 254425 |
| `f_000022` | https://static.ets100.com/teacherend/dist/plugin/jquery.min.js | 34774 | 89500 |
| `f_000025` | https://static.ets100.com/teacherend/dist/plugin/lodash.min.js | 28861 | 73539 |
| `f_000028` | https://static.ets100.com/teacherend/dist/plugin/opencc/full.js | 504142 | 1121163 |
| `f_000023` | https://static.ets100.com/teacherend/dist/plugin/vue-1.min.js | 29693 | 76275 |
| `f_00001f` | https://static.geetest.com/captcha_v4/policy/bed23a191d3a4dcc89404cda5d10a527/slide/3337 | 36215 | 36215 |
| `f_000021` | https://static.geetest.com/captcha_v4/policy/bed23a191d3a4dcc89404cda5d10a527/slide/3337 | 54135 | 54135 |
| `f_000020` | https://static.geetest.com/captcha_v4/policy/bed23a191d3a4dcc89404cda5d10a527/slide/3337 | 61195 | 61195 |
| `f_000008` | https://static.geetest.com/pictures/v4_pic/slide_2021_07_14/cartoon5/bg/dc52460454c2442d | 26610 | 26610 |
| `f_000009` | https://static.geetest.com/pictures/v4_pic/slide_2021_07_14/cartoon6/bg/ce990b6a41f344fd | 28162 | 28162 |
| `f_00000a` | https://static.geetest.com/pictures/v4_pic/slide_2024_09_02/26a347846f/bg/2d3c54cbcee746 | 63854 | 63854 |
| `f_000007` | https://static.geetest.com/v4/static/v1.9.8-0d53fd/js/gcaptcha4.js | 156698 | 1081659 |
| `f_00001e` | https://static.geetest.com/v4/static/v1.9.9-53b07e/js/gcaptcha4.js | 157562 | 1072828 |
| `f_000006` | https://statics.ets100.com/ets-student-pc-web/assets/Bg_Login-a010bcd9.png | 86879 | 86879 |
| `f_00000d` | https://statics.ets100.com/ets-student-pc-web/assets/Bg_Startup-15b3ca81.png | 32546 | 32546 |
| `f_00000e` | https://statics.ets100.com/ets-student-pc-web/assets/Home-12e1deb4.js | 37318 | 37318 |
| `f_000016` | https://statics.ets100.com/ets-student-pc-web/assets/HomeworkList-df5198bc.js | 27145 | 27145 |
| `f_000015` | https://statics.ets100.com/ets-student-pc-web/assets/Icon_Download-ab29f0ef.gif | 20629 | 20629 |
| `f_000017` | https://statics.ets100.com/ets-student-pc-web/assets/MockExamDetails-169bf8a1.js | 23461 | 23461 |
| `f_000012` | https://statics.ets100.com/ets-student-pc-web/assets/MyEcard-643f2bcd.js | 22563 | 22563 |
| `f_000014` | https://statics.ets100.com/ets-student-pc-web/assets/MyProfile-cb4bd67a.js | 28958 | 28958 |
| `f_00000f` | https://statics.ets100.com/ets-student-pc-web/assets/SyncSelectBookDialog-89a14887.js | 23276 | 23276 |
| `f_000019` | https://statics.ets100.com/ets-student-pc-web/assets/adjustWordColor-74ceaab6.js | 18303 | 18303 |
| `f_00000c` | https://statics.ets100.com/ets-student-pc-web/assets/ecard_bg-992eeb92.png | 79246 | 79246 |
| `f_000013` | https://statics.ets100.com/ets-student-pc-web/assets/ecard_junior-4c1d9cbd.png | 67217 | 67217 |
| `f_000011` | https://statics.ets100.com/ets-student-pc-web/assets/home_bg_tsmn_short-5c562c88.png | 32294 | 32294 |
| `f_000010` | https://statics.ets100.com/ets-student-pc-web/assets/home_icon_speaking-39074861.png | 29722 | 29722 |
| `f_000002` | https://statics.ets100.com/ets-student-pc-web/assets/index-dc0257dd.js | 3481698 | 3481698 |
| `f_00000b` | https://statics.ets100.com/ets-student-pc-web/assets/province_city_id-b8413979.js | 57502 | 57502 |
| `f_000001` | https://statics.ets100.com/ets-student-pc-web/assets/style-e20d0142.css | 375097 | 1150090 |
| `f_00002b` | https://statics.ets100.com/ets-student-pc-web/assets/tuozhan_BG_PK-5de005b1.png | 20996 | 20996 |
| `f_00002a` | https://statics.ets100.com/ets-student-pc-web/assets/tuozhan_BG_yuedu_chang-85b0a125.png | 17216 | 17216 |
| `f_000018` | https://statics.ets100.com/ets-student-pc-web/assets/useExamStepper-b3594738.js | 19556 | 19556 |
| `f_00001c` | https://statics.ets100.com/ets-student-pc-web/common/js/jquery.min_9455e8c5.js | 93861 | 93861 |
| `f_00001d` | https://statics.ets100.com/ets-student-pc-web/common/js/pc-listen-data_da18ccbb.js | 38007 | 38007 |
| `f_00001b` | https://statics.ets100.com/ets-student-pc-web/common/js/pc-listen-fn_d312fa32.js | 21913 | 21913 |
| `f_00001a` | https://statics.ets100.com/ets-student-pc-web/common/js/vue.min_90bc3805.js | 75514 | 75514 |
| `f_000003` | https://statics.ets100.com/ets-student-pc-web/plugins/crypto-js.js | 48929 | 48929 |

---

## 2. SPA 入口与运行时骨架

入口 `index.html`（可读化 bundle 的 `000_...index.html`，未随仓库发布；共 39 行）：

- `<title>E听说</title>`（L7）；启动占位屏 `#placeholderScreen`（L17-20，文案“程序正在启动中…”）→ 由 `page/splashScreen.js` 移除。
- L13：`<script type="module" crossorigin src="./assets/index-dc0257dd.js">` —— SPA 主 bundle（3,481,698 B，缓存中为**未压缩原始 JS**，即 `f_000002`）。
- L14：`<link rel="stylesheet" href="./assets/style-e20d0142.css">`（1,150,090 B，gzip `f_000001`）。
- L22-35：**在 module 前后加载 14 个 classic 脚本**（挂 window 全局，供 SPA 调用原生能力）：`page/refreshPage.js`、`plugins/stic/{appcontroller,shellhelper,sqlitepln,filehelper,sevenzip,sndhelper,httphelper,sysconfig,etshelper}.js`、`plugins/clientDB.js`、`plugins/crypto-js.js`、`plugins/gt4.js`。加载顺序即依赖顺序（`cef.message` 由 CEF 注入，见 §7）。
- 启动流程：`refreshPage.js` 读取 `localStorage.clientConfig`（含 `EnvType`、`C_Version`、`Port` 等）与 `sessionStorage` → `splashScreen.js` 调 `ShellHelper.getconfig` 取窗口配置、移除占位屏 → SPA 挂载 `#app`（L36）。

版本/环境线索：`envConfig` 内 `version$4="3.9.3"`（B:18387，构建版本字面量）；实际客户端版本来自 `clientConfig.C_Version`，函数 `envConfig("VITE_CLIENT_VERSION")`（B:18356-18362）；真实运行日志 `<ETS_INSTALL_DIR>\logs\ets_2026-11-4.log` 中 `global_client_version` 为 **5.7.9**。

运行时全局：`EXE_PATH = cef.message.getExePath()`、`STIC_PATH="stic://file.iflytek.com/"`（B:50812）——本地资源（packages、soundfiles）通过自定义 scheme 访问。

---

## 3. Vue3 路由表（`routes.json`）

### 3.1 结构与守卫

- Router 创建：`moduleRoutes=getModuleRoutes(), router=createRouter({history:createWebHashHistory(), routes:[...主路由, ...moduleRoutes]})`（B:56369-56463）——**hash 模式**（`/#/main/home`）。
- 模块路由：`import.meta.glob("./modules/*.ts")` 的 16 个模块（B:56363）：`home.ts, homework.ts, listeningSpeakingSynchronous.ts, login.ts, mockExam.ts, personalCenter.ts, phonetic.ts, phoneticNew.ts, pk.ts, recommDub.ts, referenceBook.ts, speakListenLesson.ts, special.ts, studyPlan.ts, textCourse.ts, words.ts`；`getModuleRoutes()` 拼接所有模块数组（B:56361-56366）。每个模块数组变量在 B:823k-858k 区间（`home=[...]`、`homework=[...]` …），路由对象的行号见下表 `module` 列。
- 守卫（B:56464）：`router.beforeEach(permissionInterceptor)`、`keepAliveInterceptor`、`pageInterceptor`，`router.afterEach(resetStoreAfterRouteInterceptor)`（守卫函数体未逐行展开，职责：权限跳转、KeepAlive 名单、页面标题/头部配置、路由后重置部分 store）。
- `RouteNames` 枚举（B:16608）：`login / appStart / startup / home / error / systemMessage / myProfile / mockExamResult / mockExamDetail`。
- 每个懒加载组件写法：`component:async()=>await __vitePreload(()=>import("./X-hash.js"),["./X-hash.js",...依赖 chunk],import.meta.url)`；`__vitePreload` 的数组即该路由的全部依赖 chunk（可用于还原 chunk 图）。

### 3.2 全量路由（91 条）

列说明：`line` = 可读化 bundle 的 `001_...index-dc0257dd.js` 行号（可读化 bundle 未随仓库发布）；`module` = 来源模块数组（`main-router` 为主路由表）；`component` 为该路由组件 chunk；`meta` 为 `meta:{...}` 中的关键项（keepAlive/header 等）。

| line | full_path | name | component | meta | module |
|---|---|---|---|---|---|
| 18488 | `/jkPage` | `jkPage` | JKPage-861491af.js |  | home |
| 18494 | `/homeworkList` | `homeworkList` | HomeworkList-df5198bc.js | showMax=False | homework |
| 18504 | `/listeningSpeakingSynchronousDetail` | `listeningSpeakingSynchronousDetail` | Practice-2b728a44.js | showMax=True, showFont=True | listeningSpeakingSynchronous |
| 18510 | `/listeningSpeakingSynchronousComprehensive` | `listeningSpeakingSynchronousComprehensive` | Comprehensive-100472e4.js | showMax=True, showFont=True | listeningSpeakingSynchronous |
| 18520 | `/eduLogin` | `eduLogin` | EduLogin-3bfdb22f.js |  | login |
| 18522 | `/eduSwLogin` | `eduSwLogin` | EduSwLogin-bcd4e9c2.js |  | login |
| 18528 | `/mockExamList` | `mockExamList` | MockExamList-27b58c1c.js | keepAlive=True, showMax=True | mockExam |
| 18534 | `/mockExamDetail` | `mockExamDetail` | MockExamDetails-169bf8a1.js | showMax=True, showFont=True | mockExam |
| 18540 | `/mockExamResult` | `mockExamResult` | MockExamResult-8829504e.js | showMax=True, showFont=True | mockExam |
| 18546 | `/modelTestMode` | `modelTestMode` | Examine-9688cb21.js |  | mockExam |
| 18548 | `/readingWritingList` | `readingWritingList` | ReadingWritingList-d3d94c69.js | keepAlive=True, showMax=True | mockExam |
| 18554 | `/readingWritingStart` | `readingWritingStart` | ReadingWritingStart-4c32dd2f.js |  | mockExam |
| 18560 | `/readingWritingDetails` | `readingWritingDetails` | ReadingWritingDetails-157ff9c5.js | keepAlive=False, showMax=True, showFont=True | mockExam |
| 18566 | `/readingWritingResult` | `readingWritingResult` | ReadingWritingResult-74759f6d.js |  | mockExam |
| 18576 | `/ecard-list` | `ecardList` | EcardList-b62523e6.js | showMax=True, show=True, handleZoom=True, title=获取E卡 | personalCenter |
| 18582 | `/ecard-parent-buy` | `ecardParentBuy` | EcardParentBuy-c56c9074.js | title=父母代买 | personalCenter |
| 18588 | `/ecard-introduce` | `ecardIntroduce` | EcardIntroduce-612b4099.js | showMax=True, show=True, handleZoom=True, title=E卡升级 | personalCenter |
| 18598 | `/phonetic` | `phonetic` | PhoneticView-ded1a214.js | showMax=True, show=True, handleZoom=True | phonetic |
| 18604 | `/phoneticDetail` | `phoneticDetail` | PhoneticDetailView-219cc676.js | showMax=True, show=True, handleZoom=True | phonetic |
| 18610 | `/phoneticPractice` | `phoneticPractice` | PhoneticPracticeView-ce205a45.js | showMax=True, showFont=True, show=True, handleZoom=False | phonetic |
| 18620 | `/phoneticNew` | `phoneticNew` | PhoneticNewView-6333efec.js | keepAlive=True, showMax=True, show=True, handleZoom=True | phoneticNew |
| 18626 | `/phoneticNewDetail` | `phoneticNewDetail` | PhoneticNewDetailView-fd1142ca.js | showMax=True, show=True, handleZoom=True | phoneticNew |
| 18632 | `/phoneticNewFinished` | `phoneticNewFinished` | PhoneticNewFinishedView-0b8f4467.js | showMax=True, show=True, handleZoom=True | phoneticNew |
| 18638 | `/phoneticNewPractice` | `phoneticNewPractice` | PhoneticNewPracticeView-351bdd16.js | showMax=True, showFont=True, show=True, handleZoom=False | phoneticNew |
| 18644 | `/phoneticNewResult` | `phoneticNewResult` | PhoneticNewResultView-efb17f91.js | showMax=True, show=True, handleZoom=True | phoneticNew |
| 18654 | `/pkMatch` | `pkMatch` | PKMatch-91ae4c7e.js | show=True | pk |
| 18660 | `/pkMatch_resource` | `pkMatch_resource` | PKMatch-bf8a5a48.js | show=True | pk |
| 18666 | `/pk` | `pk` | PK-acffe1fc.js | showMax=True, show=True | pk |
| 18672 | `/pkRank` | `pkRank` | PKRank-273268fa.js | showMax=True, show=True | pk |
| 18678 | `/pkResult` | `pkResult` | PKResult-82a2ad12.js | keepAlive=True, showMax=True, show=True | pk |
| 18688 | `/recommendDub` | `recommendDub` | DubHomePage-60e00138.js | keepAlive=True, showMax=True, show=True, handleZoom=True | recommDub |
| 18694 | `/dubDetailPage` | `dubDetailPage` | DubDetailPage-92ff010f.js | keepAlive=True, showMax=True, show=True, handleZoom=False | recommDub |
| 18700 | `/dubPlayingPage` | `dubPlayingPage` | DubPlayingPage-54c0f7f9.js | showMax=True, show=True, handleZoom=False | recommDub |
| 18706 | `/dubFinishSavePage` | `dubFinishSavePage` | DubFinishSavePage-efacb6b9.js | showMax=True, show=True, handleZoom=False | recommDub |
| 18716 | `/referenceBookList` | `referenceBookList` | ReferenceBookList-09eb5c58.js | showMax=False, show=True, handleZoom=True | referenceBook |
| 18722 | `/referenceBookDetail` | `referenceBookDetail` | ReferenceBookDetail-bcced0a9.js | showMax=False, show=True, handleZoom=True | referenceBook |
| 18728 | `/referenceBookTopicPreview` | `referenceBookTopicPreview` | ReferenceBookTopicPreview-c52cee99.js | showMax=False, show=True, handleZoom=True | referenceBook |
| 18738 | `/speakListenLesson` | `speakListenLesson` | index-14285fc6.js | showMax=True, showFont=True, handleZoom=False | speakListenLesson |
| 18748 | `/specialList` | `specialList` | SpecialListView-a8cb20ae.js | keepAlive=True, showMax=True | special |
| 18754 | `/specialReadingWritingStart` | `specialReadingWritingStart` | SpecialReadingWritingStart-b7da82a3.js | showMax=True | special |
| 18764 | `/studyPlanDetail` | `studyPlanDetail` | studyPlanDetail-0a1cc619.js | showMax=False | studyPlan |
| 18770 | `/studyPlanHistoryDetail` | `studyPlanHistoryDetail` | studyPlanDetail-0a1cc619.js | showMax=False | studyPlan |
| 18780 | `/textCourse` | `textCourse` | index-6d498c80.js |  | textCourse |
| 18782 | `/textInfo` | `textInfo` | textInfo-48051e73.js |  | textCourse |
| 18784 | `/readSentence` | `readSentence` | readSentence-31452861.js |  | textCourse |
| 18786 | `/readSentenceScoreInfo` | `readSentenceScoreInfo` | readSentenceScoreInfo-380b0a06.js |  | textCourse |
| 18788 | `/readAloud` | `readAloud` | readAloud-4045e1f4.js |  | textCourse |
| 18790 | `/textCourse_resource` | `textCourse_resource` | index-67ed0db1.js |  | textCourse |
| 18792 | `/textInfo_resource` | `textInfo_resource` | textInfo-5b689998.js |  | textCourse |
| 18794 | `/readSentence_resource` | `readSentence_resource` | readSentence-13b2dc83.js |  | textCourse |
| 18796 | `/readSentenceScoreInfo_resource` | `readSentenceScoreInfo_resource` | readSentenceScoreInfo-31bd9273.js |  | textCourse |
| 18798 | `/readAloud_resource` | `readAloud_resource` | readAloud-98c3add0.js |  | textCourse |
| 18804 | `/wordStudy` | `wordStudy` | WordStudy-ff81a63b.js |  | words |
| 18806 | `/wordPractice` | `wordPractice` | WordPractice-95bc42e3.js | showMax=True, show=True, handleZoom=True | words |
| 18812 | `/wordPracticeResult` | `wordPracticeResult` | WordPracticeResult-933df161.js | showMax=True, show=True, handleZoom=True | words |
| 18818 | `/wordQuestion` | `wordQuestion` | WordQuestion-e237c73e.js | showMax=True, show=True, handleZoom=True | words |
| 18824 | `/homeworkWordQuestion` | `homeworkWordQuestion` | HomeworkWordQuestion-fb8193a7.js | showMax=True, show=True, handleZoom=True | words |
| 18830 | `/homeworkWordQuestionResult` | `homeworkWordQuestionResult` | HomeworkWordQuestionResult-ab061cff.js |  | words |
| 18836 | `/wordQuestionResult` | `wordQuestionResult` | WordQuestionResult-5db8ab59.js | showMax=True, show=True, handleZoom=True | words |
| 18842 | `/wordList` | `wordList` | WordList-a0c54070.js |  | words |
| 18844 | `/wordList_resource` | `wordList_resource` | WordList-e1a4f04a.js |  | words |
| 18846 | `/wordPractice_resource` | `wordPractice_resource` | WordPractice-6f534d22.js | showMax=True, show=True, handleZoom=True | words |
| 18852 | `/wordQuestion_resource` | `wordQuestion_resource` | WordQuestion-ad342ada.js | showMax=True, show=True, handleZoom=True | words |
| 18858 | `/wordQuestionResult_resource` | `wordQuestionResult_resource` | WordQuestionResult-c74e3d55.js | showMax=True, show=True, handleZoom=True | words |
| 18864 | `/wordPracticeResult_resource` | `wordPracticeResult_resource` | WordPracticeResult-7243a528.js | showMax=True, show=True, handleZoom=True | words |
| 56370 | `/` | `appStart` |  |  | main-router |
| 56386 | `/auth` | `authLayout` | Login-86ede767.js | keepAlive=True | main-router |
| 56387 | `/auth/login` | `login` | Login-86ede767.js |  | main-router |
| 56389 | `/auth/register` | `register` | Login-86ede767.js |  | main-router |
| 56391 | `/auth/verifyAccount` | `verifyAccount` | VerifyAccount-a7f4af97.js |  | main-router |
| 56393 | `/auth/verifyModel` | `verifyModel` | VerifyModel-f1ff75f3.js |  | main-router |
| 56395 | `/auth/forgetPwd` | `forgetPwd` | ForgotPwd-438d023c.js |  | main-router |
| 56397 | `/auth/eCardLogin` | `eCardLogin` | ECardLogin-48e15b75.js | keepAlive=True | main-router |
| 56401 | `/auth/selectEduSystem` | `selectEduSystem` | SelectEduSystem-25dfceac.js |  | main-router |
| 56403 | `/auth/privacy` | `privacy` | Privacy-51e0bbdb.js |  | main-router |
| 56406 | `/setGoalOne` | `setGoalOne` | SetGoalOnePage-3ad92f0d.js |  | main-router |
| 56408 | `/setGoalTwo` | `setGoalTwo` | SetGoalTwoPage-48026398.js |  | main-router |
| 56410 | `/ecardBind` | `ecardBind` | EcardBind-93a93043.js |  | main-router |
| 56412 | `/main` | `mainLayout` | Home-12e1deb4.js | keepAlive=True | main-router |
| 56413 | `/main/home` | `home` | Home-12e1deb4.js | keepAlive=True | main-router |
| 56417 | `/main/abilityExpand` | `abilityExpand` | AbilityExpand-1ce33197.js | keepAlive=True | main-router |
| 56421 | `/main/myEcard` | `myEcard` | MyEcard-643f2bcd.js | keepAlive=True | main-router |
| 56425 | `/main/words` | `words` | WordsPage-18595578.js | keepAlive=True | main-router |
| 56429 | `/main/review` | `review` | Review-1214fe06.js | keepAlive=True | main-router |
| 56433 | `/main/growthPath` | `growthPath` | growth-ccc135a6.js | keepAlive=True | main-router |
| 56437 | `/main/correctedList` | `correctedList` | CorrectedList-2752b4eb.js | back=True | main-router |
| 56443 | `/main/homework` | `homework` | Homework-d059c4e1.js | keepAlive=True | main-router |
| 56447 | `/main/addClass` | `addClass` | AddClass-1e6562b8.js |  | main-router |
| 56449 | `/main/myProfile` | `myProfile` | MyProfile-cb4bd67a.js |  | main-router |
| 56451 | `/main/accountBindPhone` | `AccountBindPhone` | AccountBindPhone-9861ce6a.js | title=绑定手机号 | main-router |
| 56456 | `/studyMaterialList` | `studyMaterialList` | StudyMaterialList-692afa8d.js | keepAlive=True, showMax=True, show=True, handleZoom=False | main-router |

> 备注：`/main` 与 `/auth` 为布局路由（`MainLayout` / auth 布局），子路由为相对路径；`/:catchAll(.*)` → `NotFound`；`/` → redirect `appStart`。
> 路由完整 chunk 依赖列表见 `routes.json → routes[].chunks` 与 `chunks` 字典（含 `present` 标记：缓存中是否抓到）。

### 3.3 页面/业务模块划分（按 modules/*.ts）

| 模块 | 路由数 | 说明 |
|---|---|---|
| home | 1 | `/jkPage`（金课/学习面板 iframe 页） |
| homework | 1 | `/homeworkList` 作业列表 |
| listeningSpeakingSynchronous | 2 | 听说同步：练习页 + 综合页 |
| login | 2 | 教育系统登录 / 单点登录 |
| mockExam | 8 | 模考：列表/详情/结果/机考模式/读写（列表/开始/详情/结果） |
| personalCenter | 3 | E 卡列表/家长购买/介绍 |
| phonetic | 3 | 音标：列表/详情/练习 |
| phoneticNew | 5 | 新音标：列表/详情/完成/练习/结果 |
| pk | 5 | PK：匹配/资源/主界面/排行/结果 |
| recommDub | 4 | 推荐配音：首页/详情/配音页/保存页 |
| referenceBook | 3 | 教材：列表/详情/单元预览 |
| speakListenLesson | 1 | 听说课 |
| special | 2 | 专项：列表/读写 |
| studyPlan | 2 | 学习计划详情/历史详情 |
| textCourse | 10 | 课文：课文/信息/朗读句子/评分信息/朗读，及 `_resource` 系列镜像路由 |
| words | 13 | 单词：学习/练习/结果/答题/作业答题/结果/词表，及 `_resource` 镜像 |
| main-router | 26 | 主表：布局(/auth,/main)、启动(/app-start,/startup,/system-message,/error,/bypass)、设置目标、E 卡绑定、学习资料列表等 |

> 观察：`*_resource` 后缀路由复用同一组件 chunk、用于“资源库”入口（同一页面，不同数据来源），是产品上的双入口设计。

---

## 4. 启动与主流程（前端口径）

1. `index.html` 注入 14 个插件脚本（原生桥封装）→ `splashScreen.js` 读窗口配置 → 主 bundle 执行。
2. 主 bundle 顺序（B 行号）：`envConfig` 环境解析（B:18354-18385）→ `BASE_URL`/`TIME_OUT`（B:18387）→ axios `HYRequest` 实例（B:56580-56610）→ `router` 创建（B:56369）→ 全局守卫。
3. 首屏跳 `appStart` → `startup`（启动页）→ 登录/校验 → `main/home`。`AppStart` 负责：读取 `clientConfig`、检查更新（`LoggerUtils.checkUpdate` → `EtsHelper.check_update[_force]`）、网络检查（`ShellUtils.networkCheck`，HEAD `http://file.fei.ets100.com/network_test`，B:50831-50840）、拉系统配置（`system/config`）与公告。

---

## 5. 状态管理（Pinia，20 个 store）

| store | 定义行（B） |
|---|---|
| `reviewStore` | 50382 |
| `userInfo` | 56702 |
| `syncLessionStore` | 56866 |
| `appConfig` | 57059 |
| `mediaSetting` | 57080 |
| `routerStore` | 57146 |
| `userSetting` | 57164 |
| `homeworkStore` | 57182 |
| `appLogin` | 57214 |
| `phonetic` | 57226 |
| `specialStore` | 57270 |
| `mistakeManagerStore` | 57679 |
| `showGrowth` | 57971 |
| `requestManager` | 57983 |
| `appTranslateSettingStore` | 57994 |
| `systemMessage` | 58011 |
| `networkInspectorStore` | 58101 |
| `deviceCheckStore` | 58129 |
| `appOssStore` | 58145 |
| `resourcePlatformStore` | 58187 |

关键 store（`userInfo`，B:56702-56720+）：

- state：`userInfo / ecardInfo / activeGradeEcardInfo / systemConfig / isEdu / isEduSw / jumpToHome / ecardList / ecardGetMsg / foshanExpand / ztUserInfo`。
- getters：`getLstToken`（token）、`getUserInfo`、`getEcardInfo`、`getSystemConfig`、`getEngineConfig`（`JSON.parse(ecardInfo.engine_config)`，评测引擎规则）、`getEcardLock`、`getDisplayName`、`getIsNonVip`、`getFoshanNonVipActive`、`isSpeexMode`（`systemConfig.stic_record_enable_speex` 且客户端版本 >=5.7.3 且非 Linux，B:56718-56720）。
- 其他 store 职责（据命名与引用）：`appConfig`（设备 MAC/OSType、clientConfig）、`mediaSetting`（音量/语速/麦克风）、`routerStore`（keepAlivePages）、`homeworkStore`、`phonetic`、`specialStore`、`mistakeManagerStore`、`requestManager`（全局 loading、登录失效弹窗状态）、`appOssStore`（OSS 上传配置）、`resourcePlatformStore`、`networkInspectorStore`、`deviceCheckStore`、`systemMessage`、`appTranslateSettingStore`、`showGrowth`、`appLogin`、`syncLessionStore`、`reviewStore`、`userSetting`。

持久化：IndexedDB（dexie，`db.wordDict / questionDetilsDb / uploadRecord / phonetic / downloadFiles / login / wordPractice / userSet` 等表，B:46619 附近一行注释列出表结构），本地 SQLite 由原生 `sqlitepln` 插件承担（`ClientDBUtils`）。

---

## 6. API 封装层与签名协议

### 6.1 环境与常量

`envConfig(key)`（B:18354-18384）：从 `localStorage.clientConfig.EnvType`（1..5）选环境数组，返回 `VITE_*` 配置；`Port` 会拼到 `VITE_BASE_URL` 后。5 个环境：

| EnvType | label | VITE_BASE_URL |
|---|---|---|
| 1 | 正式 | `https://api.ets100.com` |
| 2 | 灰度 | `https://hdapi.ets100.com` |
| 3 | 测试 | `https://testapi.ets100.com` |
| 4 | 开发 | `https://devapi.ets100.com` |
| 5 | 重构 | `http://test.api.ets100.com` |

其他关键配置（同表，B:18374-18382）：`VITE_AUDIO_UPLOAD=http://partner.ets100.com/oss/config`（OSS 上传凭证）、`VITE_log_collector=http://collect.ets100.com/log_collector`、`VITE_JK_LOGIN/VITE_JK_CALLBACK`（金课）、`VITE_EDU_LOGIN=https://pass.changyan.com/login?...product_appkey=qingdao_ets`、`VITE_announcement`、`VITE_HOMEWORK=http://teacher.ets100.com/dist/pc-entity.html`、`VITE_DUAL_CHANNEL_ISE_WSS_URL=wss://oe-pub.eduaiplat.com`、`VITE_DUAL_CHANNEL_HTTP_URL`、`VITE_DUAL_CHANNEL_AI_THOR_URL`、`VITE_EXAM_PREP_ISE_URL=wss://oe-pub.eduaiplat.com/ws/v2/exam_preparation_ise`、`VITE_TRACKER_IFLYTEK_*`（DCP 埋点 appid/secret/pubkey）、`VITE_RESOURCE_PLATFORM_URL=https://airesapi.koukao.cn`。
硬编码：`k="ldlflfgirerjfkcf"`、`k_serves="f05323cb91d422b2"`、`RSA_PUBLIC_KEY=-----BEGIN RSA PRIVATE KEY-----...`（B:18369-18371，实为私钥常量，注意安全风险）。

`BASE_URL = envConfig("VITE_BASE_URL")`、`TIME_OUT=60000`、`HEAD_VERSION="1.0"`（B:18387）。

### 6.2 请求类与拦截器

- `class HYRequest`（B:18326-18353）：包装 axios 实例；`get/post/delete/patch/request`，支持每个请求自带 `interceptors`。
- 实例（B:56580-56610）：`new HYRequest({baseURL:BASE_URL, timeout:TIME_OUT, interceptors:{ requestInterceptor, responseInterceptor, ... }})`：
  - 请求拦截：记录 `timeKey`、`LoggerUtils.logRequest`、全局 loading（`useRequestManagerStore().showGlobalRequestLoading`）。
  - 响应拦截：计算耗时 `getRequestTime`、`LoggerUtils.logResponse(e,{time,type:1})`、关 loading；错误时 `type:2` 并兜底关闭全屏 loading。
- 统一请求封装（`hyRequest`，B:56611-56693）：`postIt(url, params, showLoading)` 为核心，`getIt/get/postJoin` 为变体。

### 6.3 请求信封 + 签名（本次最关键还原）

`postIt` 实现（B:56630-56672）：

```
1) 参数对象 a = { sign_response:1, sn:"test", system:4,
                 global_client_version: envConfig("VITE_CLIENT_VERSION"),
                 token: userInfo.token || sessionStorage.token, ...params }
   （checkToken=false 时可跳过 token；拿不到 token 时按白名单 url 记日志）
2) body 数组 = [ { r: url, params: a } ]；c = JSON.stringify(数组)；c = gBase64.encode(c)
3) time = String(Date.now())
4) sign = await etsSignatureAdapter.signBody({body:c, time})
5) POST {baseURL}{url}, data={ body:c, head:{ version:"1.0", sign:sign, pid:pid,
                                             time, time_second:Number(time) } }, responseType:"text"
6) resp = JSON.parse(respText); payload = resp[0] || resp; errorHandler(payload); return payload
```

签名适配器 `EtsSignatureAdapter`（B:56480-56547）：

- 探测：先调原生 `EtsHelper.encode_api_body_v2({body,time})`；返回可解析为 `{pid,key_id,sign,sign_version:"2"}` 则锁定 **v2**；否则回落 **v1** 调 `encode_api_body`（返回 32 位 hex 签名，`pid="grlx"`，常量 `V1_PID`）。
- 失败重试：`SIGN_ATTEMPTS=3`，单次调用超时 `CALL_TIMEOUT=1200ms`（`invoke` 包 Promise + timeout）。
- 签名格式校验：`SIGN_PATTERN=/^[a-f\d]{32}$/i`（B:56465）。
- 响应签名：`signResponse(body, protocol)` → v2 走 `encode_api_resp_v2`，v1 走 `encode_api_resp`（请求里 `sign_response:1` 表示要求响应签名）。
- 协议切换会写日志 `ets_sign_protocol_selected protocol=..., pid=...`（B:56655-56656）；实测日志：`ets_sign_protocol_selected protocol=v2, pid=pcWin`（`<ETS_INSTALL_DIR>\logs\ets_2026-11-4.log`）。

错误码处理 `errorHandler`（B:56556-56579）：

- `code==20004`：登录态失效。若当前不在登录页 → 调用 `useUploadLogs().handleUploadLogs({feedback:"接口异常20004, 自动上报日志", contact:raw_phone, system_type:9})` 上报日志，弹窗“登录状态已失效，请重新登录”，确认后 `router.replace({name:RouteNames.Login})`。
- 其他 code 由调用方/业务层处理（未发现集中式错误码表；标记未知）。

### 6.4 API 端点清单（118 个，`api_endpoints.json`）

命名约定：`hyRequest.postIt("模块/动作", params)`，最终 URL = `BASE_URL + "/" + r`（r 可带前导 `/`，日志中可见双斜杠 `https://api.ets100.com//announcement/list`）。

| endpoint (r) | 分组（行号） | 定义行 |
|---|---|---|
| `g/word/new-notebook` | 作业/单词/资源(19229-19237) | 19229 |
| `g/word/add-new` | 作业/单词/资源(19229-19237) | 19229 |
| `g/set/word-list` | 作业/单词/资源(19229-19237) | 19229 |
| `g/word/master` | 作业/单词/资源(19229-19237) | 19229 |
| `g/pk/start-word-pk` | 作业/单词/资源(19229-19237) | 19229 |
| `g/word/struct` | 作业/单词/资源(19229-19237) | 19229 |
| `g/pk/submit-word` | 作业/单词/资源(19229-19237) | 19229 |
| `g/pk/ranklist` | 作业/单词/资源(19229-19237) | 19229 |
| `g/pk/count` | 作业/单词/资源(19229-19237) | 19229 |
| `g/set/material-res` | 作业/单词/资源(19229-19237) | 19229 |
| `g/word/score-report` | 作业/单词/资源(19229-19237) | 19229 |
| `m/file/pre-upload` | 作业/单词/资源(19229-19237) | 19229 |
| `g/homework/list` | 作业/单词/资源(19229-19237) | 19231 |
| `m/class/list` | 作业/单词/资源(19229-19237) | 19233 |
| `m/class/check-lock` | 作业/单词/资源(19229-19237) | 19233 |
| `m/class/add` | 作业/单词/资源(19229-19237) | 19233 |
| `m/class/change` | 作业/单词/资源(19229-19237) | 19233 |
| `/m/homework/info` | 作业/单词/资源(19229-19237) | 19235 |
| `g/homework/pk-info` | 作业/单词/资源(19229-19237) | 19237 |
| `/point-service/homework/rank/list` | 作业/单词/资源(19229-19237) | 19237 |
| `g/homework/struct` | 作业/单词/资源(19229-19237) | 19237 |
| `m/homework/struct` | 作业/单词/资源(19229-19237) | 19237 |
| `m/homework/set-use-time` | 作业/单词/资源(19229-19237) | 19237 |
| `m/homework/submit` | 作业/单词/资源(19229-19237) | 19237 |
| `m/score/detail` | 作业/单词/资源(19229-19237) | 19237 |
| `g/homework/score-sync` | 作业/单词/资源(19229-19237) | 19237 |
| `g/homework/score-detail` | 作业/单词/资源(19229-19237) | 19237 |
| `g/homework/score-drop` | 作业/单词/资源(19229-19237) | 19237 |
| `g/word/is-in-notebook` | 作业/单词/资源(19229-19237) | 19237 |
| `g/homework/checkstart` | 作业/单词/资源(19229-19237) | 19237 |
| `g/data/audio-task-submit` | 作业/单词/资源(19229-19237) | 19237 |
| `m/homework/audio-task-retry` | 作业/单词/资源(19229-19237) | 19237 |
| `m/homework/audio-task-cancel` | 作业/单词/资源(19229-19237) | 19237 |
| `file/download` | 基础/网关(24480-24512) | 24480 |
| `system/time` | 基础/网关(24480-24512) | 24482 |
| `ai/aiplat/getaitoken` | 基础/网关(24480-24512) | 24484 |
| `g/user/get-llm-access-token` | 基础/网关(24480-24512) | 24503 |
| `/user/userUnlockPhone/unlockPhone` | 基础/网关(24480-24512) | 24512 |
| `/g/set/mark-txt` | 基础/网关(24480-24512) | 24512 |
| `/proxy/phoneticForStudent/sectionList` | 拼读/资源平台(47800) | 47800 |
| `/proxy/resourcePlatformInterface/pageItems` | 拼读/资源平台(47800) | 47800 |
| `/proxy/resourcePlatformInterface/findByIds` | 拼读/资源平台(47800) | 47800 |
| `g/set/get-score` | 拼读/资源平台(47800) | 47800 |
| `g/set/report-score` | 拼读/资源平台(47800) | 47800 |
| `g/homework/get-score` | 拼读/资源平台(47800) | 47800 |
| `g/homework/report-score` | 拼读/资源平台(47800) | 47800 |
| `m/dub/list` | 配音/计划(49618) | 49618 |
| `m/info/list` | 配音/计划(49618) | 49618 |
| `g/homework/plan-list` | 配音/计划(49618) | 49618 |
| `g/resource/expand-module` | 配音/计划(49618) | 49618 |
| `g/homework/plan-detail` | 配音/计划(49618) | 49618 |
| `g/es/plan-excellent` | 配音/计划(49618) | 49618 |
| `/m/audio/sync-v2` | 考试/评分同步(50336-50369) | 50360 |
| `/m/set/get-score-detail` | 考试/评分同步(50336-50369) | 50363 |
| `/m/set/reset-score-v2` | 考试/评分同步(50336-50369) | 50365 |
| `/m/exam/struct` | 考试/评分同步(50336-50369) | 50369 |
| `/m/exam/get-score-detail` | 考试/评分同步(50336-50369) | 50369 |
| `/m/exam/sync` | 考试/评分同步(50336-50369) | 50369 |
| `/m/exam/submit` | 考试/评分同步(50336-50369) | 50369 |
| `/m/composition/save-draft` | 考试/评分同步(50336-50369) | 50369 |
| `/m/composition/recognize` | 考试/评分同步(50336-50369) | 50369 |
| `/m/composition/mark` | 考试/评分同步(50336-50369) | 50369 |
| `/score` | 考试/评分同步(50336-50369) | 50369 |
| `m/ecard/list` | E卡/通知/政策(51492-51494) | 51492 |
| `g/resource/book-list` | E卡/通知/政策(51492-51494) | 51492 |
| `g/set/unit-list` | E卡/通知/政策(51492-51494) | 51492 |
| `g/set/unit-info` | E卡/通知/政策(51492-51494) | 51492 |
| `g/set/module-list` | E卡/通知/政策(51492-51494) | 51492 |
| `g/resource/grade-list` | E卡/通知/政策(51492-51494) | 51492 |
| `g/set/column-v2` | E卡/通知/政策(51492-51494) | 51492 |
| `g/set/list` | E卡/通知/政策(51492-51494) | 51492 |
| `m/notify/list` | E卡/通知/政策(51492-51494) | 51494 |
| `m/policy/get-auth-url` | E卡/通知/政策(51492-51494) | 51494 |
| `m/policy/get-comment-url` | E卡/通知/政策(51492-51494) | 51494 |
| `m/policy/get-feedback-url` | E卡/通知/政策(51492-51494) | 51494 |
| `m/feedback/submit` | E卡/通知/政策(51492-51494) | 51494 |
| `client/mobile-update` | E卡/通知/政策(51492-51494) | 51494 |
| `m/mistake/summary` | 错题(52059) | 52059 |
| `m/mistake/list` | 错题(52059) | 52059 |
| `,prop:` | 其他(53053) | 53053 |
| `g/set/ppr-res` | 其他(53103) | 53103 |
| `m/set/column` | 其他(53103) | 53103 |
| `g/set/list-v2` | 其他(53103) | 53103 |
| `user/login` | 登录/用户(56694-56702) | 56694 |
| `/user/login-sw` | 登录/用户(56694-56702) | 56694 |
| `user/logout` | 登录/用户(56694-56702) | 56694 |
| `system/config` | 登录/用户(56694-56702) | 56696 |
| `user/info` | 登录/用户(56694-56702) | 56698 |
| `user/rebind-code` | 登录/用户(56694-56702) | 56698 |
| `user/reset-password` | 登录/用户(56694-56702) | 56698 |
| `code/send` | 登录/用户(56694-56702) | 56698 |
| `user/register` | 登录/用户(56694-56702) | 56698 |
| `user/change-info` | 登录/用户(56694-56702) | 56698 |
| `user/change-password` | 登录/用户(56694-56702) | 56698 |
| `user/change-phone` | 登录/用户(56694-56702) | 56698 |
| `user/bind-email` | 登录/用户(56694-56702) | 56698 |
| `user/close` | 登录/用户(56694-56702) | 56698 |
| `user/login-zt` | 登录/用户(56694-56702) | 56698 |
| `g/data/zt-behavior` | 登录/用户(56694-56702) | 56698 |
| `account/get-bind-info` | 登录/用户(56694-56702) | 56698 |
| `user/register-or-login` | 登录/用户(56694-56702) | 56700 |
| `m/resource/add-v2` | 登录/用户(56694-56702) | 56700 |
| `m/ecard/get` | 登录/用户(56694-56702) | 56700 |
| `m/student/change-info` | 登录/用户(56694-56702) | 56702 |
| `g/user/jkpt-info` | 登录/用户(56694-56702) | 56702 |
| `g/user/unbind` | 登录/用户(56694-56702) | 56702 |
| `g/data/sls-config` | 登录/用户(56694-56702) | 56702 |
| `g/resource/login-list` | 登录/用户(56694-56702) | 56702 |
| `user/user/getLoginInfo` | 登录/用户(56694-56702) | 56702 |
| `/user/user/getBindInfo` | 登录/用户(56694-56702) | 56702 |
| `user/user/bindMobile` | 登录/用户(56694-56702) | 56702 |
| `/m/set/column` | 作文/错题(57244-57302) | 57266 |
| `/m/composition/info` | 作文/错题(57244-57302) | 57268 |
| `m/mistake/check` | 作文/错题(57244-57302) | 57302 |
| `m/mistake/update` | 作文/错题(57244-57302) | 57302 |
| `m/mistake/detail` | 作文/错题(57244-57302) | 57302 |
| `/announcement/list` | 公告/配置(58009-58187) | 58009 |
| `/config/config/getResourcePlatformToken` | 公告/配置(58009-58187) | 58187 |

典型分组用途：
- 登录/用户：`user/login`、`/user/login-sw`、`user/logout`、`user/info`、`system/config`、`code/send`、`user/register`、`user/change-*`、`user/user/getLoginInfo`、`user/user/bindMobile`、`account/get-bind-info`、`g/user/jkpt-info`（金课）。
- 作业/单词：`g/homework/*`、`m/homework/*`、`g/word/*`、`g/pk/*`、`m/class/*`、`g/data/audio-task-submit`。
- 评分：`/m/audio/sync-v2`、`/m/set/get-score-detail`、`/m/set/reset-score-v2`、`g/set/report-score`、`/m/exam/*`、`/score`。
- 资源/文件：`file/download`、`m/file/pre-upload`、`m/resource/add-v2`、`/proxy/resourcePlatformInterface/*`、`/proxy/phoneticForStudent/sectionList`。
- 运维：`system/time`、`ai/aiplat/getaitoken`、`g/data/sls-config`、`client/mobile-update`、`m/feedback/submit`、`/announcement/list`。

---

## 7. cef.message 原生桥（actionKey 全表）

### 7.1 协议

所有原生能力由 CEF 侧注入的 `cef.message` 对象提供，插件 JS 用统一模式（示例 `ShellHelper`，`pretty/005_...shellhelper.js`）：

```js
// 1) 生成唯一回调 ID（GUID + @后缀）
var s = cef.message.createGuid() + "@getroomid";
// 2) 注册回调
cef.message.setMessageCallback(s, function (t) {
  cef.message.removeMessageCallback(s);
  cb && cb.apply(self, [t]);        // 原生返回数据（通常是 JSON 字符串）
});
// 3) 发消息：(回调ID, 插件名, 动作名, JSON.stringify(参数))
cef.message.sendMessage(s, "ShellHelper", "getroomid", "");
```

- 原生 → JS 的**事件**（如 `@recordbegin`、`@recordend`、`@waveform`、`@error`）在 `init` 时注册：`setMessageCallback(uid+"@xxx", cb)`，并把 id 放进 init 参数（`{id, error_callback_id, ...}`）。
- 返回值约定：大多数动作回调参数是 JSON 字符串（如 `record` ack：`{"data":"","errorCode":0,"errorMsg":"record ok.","flag":0}`，见日志）。
- `EtsHelper` 有一个通用发送器（`pretty/014_...etshelper.js:4-15`）：任意 action 名 + **800ms 超时兜底**，用于动态动作（`encode_api_body_v2`、`encode_api_resp_v2`）。

### 7.2 通道（plugin）与 action 统计

| 插件/通道 | action 数 |
|---|---|
| EtsHelper | 11 |
| FileHelper | 27 |
| HttpHelper | 8 |
| SevenZip | 4 |
| ShellHelper | 34 |
| SysConfig | 1 |
| appcontroller | 15 |
| soundhelper | 14 |
| sqlitepln | 6 |

总计 **120** 处调用、**115** 个不同 `插件.action`，另有 2 个动态 action（`EtsHelper.encode_api_body_v2` / `encode_api_resp_v2`）。机器可读清单：`data/frontend/action_keys.json`（含 `plugin/action/method/params文案/文件/行号`）。

### 7.3 action 全表

| action_key | JS 方法 | 参数（源码截断） | 证据 |
|---|---|---|---|
| `EtsHelper.check_update` | check_update |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:50 |
| `EtsHelper.check_update_force` | check_update_force |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:55 |
| `EtsHelper.dub_merge` | dubmerge |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:35 |
| `EtsHelper.encode_api_body` | encode_api_body |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:65 |
| `EtsHelper.encode_api_resp` | encode_api_resp |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:72 |
| `EtsHelper.get_appdata_path` | get_appdata_path |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:40 |
| `EtsHelper.init` | init |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:30 |
| `EtsHelper.log_data` | log_data |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:45 |
| `EtsHelper.open_url_by_def_browser` | open_url_by_def_browser |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:79 |
| `EtsHelper.run_update` | run_update |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:84 |
| `EtsHelper.test_crash` | test_crash |  | 014_statics.ets100.com__ets-student-pc-web__plugins__stic__etshelper.js:60 |
| `FileHelper.aliyun_oss_md5` | getaliyunmd5 |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:201 |
| `FileHelper.cleardir` | cleardir |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:234 |
| `FileHelper.closeshell` | closeshell |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:215 |
| `FileHelper.copyfileordirectory` | copyfileordirectory |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:84 |
| `FileHelper.createfolder` | createfolder |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:111 |
| `FileHelper.deletefileordirectory` | deletefileorfloder |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:93 |
| `FileHelper.ergodicfiles` | ergofile |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:138 |
| `FileHelper.ergodicfiles` | ergofile |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:147 |
| `FileHelper.existfileorfolder` | existfileorfloder |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:75 |
| `FileHelper.getbase64` | getbase64 |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:183 |
| `FileHelper.getcode` | getcode |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:210 |
| `FileHelper.getfoledersize` | getfoldersize |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:102 |
| `FileHelper.getmd5` | getmd5 |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:192 |
| `FileHelper.init` | init |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:18 |
| `FileHelper.ncttools` | getrsapubkey |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:220 |
| `FileHelper.openbrowsedialog` | openbrowsedia |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:225 |
| `FileHelper.openfiledialog` | openFileDialog |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:66 |
| `FileHelper.readbinaryfile` | readbinaryfile |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:38 |
| `FileHelper.readfile` | readfile |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:29 |
| `FileHelper.readrpk_kqlx` | readRpk |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:163 |
| `FileHelper.readrpk_kqlx` | readnpk |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:172 |
| `FileHelper.removefiletootherpath` | movefile |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:129 |
| `FileHelper.renamefolder` | renamefolder |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:120 |
| `FileHelper.savefiledialog` | saveFileDialog |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:61 |
| `FileHelper.savefiledialog` | savefiledialog |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:152 |
| `FileHelper.writefile` | writefile |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:47 |
| `FileHelper.writefilewithbinary` | writebinaryfile |  | 009_statics.ets100.com__ets-student-pc-web__plugins__stic__filehelper.js:56 |
| `HttpHelper.download` | download |  | 012_statics.ets100.com__ets-student-pc-web__plugins__stic__httphelper.js:34 |
| `HttpHelper.downloadresource` | downloadresource |  | 012_statics.ets100.com__ets-student-pc-web__plugins__stic__httphelper.js:52 |
| `HttpHelper.downloadsdk` | downloadsdk |  | 012_statics.ets100.com__ets-student-pc-web__plugins__stic__httphelper.js:61 |
| `HttpHelper.init` | init |  | 012_statics.ets100.com__ets-student-pc-web__plugins__stic__httphelper.js:24 |
| `HttpHelper.isrpkexist` | isrpkexist |  | 012_statics.ets100.com__ets-student-pc-web__plugins__stic__httphelper.js:43 |
| `HttpHelper.monitornetspeed` | monitornetspeed |  | 012_statics.ets100.com__ets-student-pc-web__plugins__stic__httphelper.js:70 |
| `HttpHelper.stopdownload` | stopdownload |  | 012_statics.ets100.com__ets-student-pc-web__plugins__stic__httphelper.js:75 |
| `HttpHelper.upload` | upload |  | 012_statics.ets100.com__ets-student-pc-web__plugins__stic__httphelper.js:29 |
| `SevenZip.init` | - |  | 010_statics.ets100.com__ets-student-pc-web__plugins__stic__sevenzip.js:18 |
| `SevenZip.test` | - |  | 010_statics.ets100.com__ets-student-pc-web__plugins__stic__sevenzip.js:33 |
| `SevenZip.unzip` | - |  | 010_statics.ets100.com__ets-student-pc-web__plugins__stic__sevenzip.js:23 |
| `SevenZip.zip` | - |  | 010_statics.ets100.com__ets-student-pc-web__plugins__stic__sevenzip.js:28 |
| `ShellHelper.CheckAudio` | CheckAudio |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:72 |
| `ShellHelper.actauth` | actAuth |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:175 |
| `ShellHelper.checkadapter` | CheckAdapter |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:113 |
| `ShellHelper.clipboard` | clipboard |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:256 |
| `ShellHelper.closewin7padkeyboardup` | closewin7padkeyboardup |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:151 |
| `ShellHelper.cmd` | cmd |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:132 |
| `ShellHelper.destroy` | destroy |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:198 |
| `ShellHelper.executebat` | executebat |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:48 |
| `ShellHelper.executecmd` | ExecCmd |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:30 |
| `ShellHelper.executeexe` | executeexe |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:39 |
| `ShellHelper.getactauth` | getActAuth |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:184 |
| `ShellHelper.getconfig` | getconfig |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:123 |
| `ShellHelper.getdeviceinfos` | queryUsb |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:214 |
| `ShellHelper.getpcinfo` | getpcinfo |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:118 |
| `ShellHelper.getroomid` | GetRoomId |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:25 |
| `ShellHelper.getserverports` | startbat |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:224 |
| `ShellHelper.getsysytemlocalpath` | getsysytemlocalpath |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:247 |
| `ShellHelper.gettoken` | getToken |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:193 |
| `ShellHelper.getuniqueid` | getuniqueid |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:156 |
| `ShellHelper.getvolume` | getvolume |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:90 |
| `ShellHelper.init` | init |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:20 |
| `ShellHelper.initActAuth` | initActAuth |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:161 |
| `ShellHelper.killagentserver` | killagentserver |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:240 |
| `ShellHelper.monitordeviceplug` | monitorUsb |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:204 |
| `ShellHelper.netcheck` | netcheck |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:141 |
| `ShellHelper.padkeyboardup` | padkeyboardup |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:146 |
| `ShellHelper.processexist` | processexist |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:67 |
| `ShellHelper.setmute` | setmute |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:99 |
| `ShellHelper.setmute` | getmute |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:108 |
| `ShellHelper.setsuspensionballconfig` | setsuspensionballconfig |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:232 |
| `ShellHelper.setvolume` | setvolume |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:81 |
| `ShellHelper.startprocess` | startprocess |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:53 |
| `ShellHelper.stopprocess` | stopprocess |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:58 |
| `ShellHelper.unInitActAuth` | unInitActAuth |  | 005_statics.ets100.com__ets-student-pc-web__plugins__stic__shellhelper.js:166 |
| `SysConfig.init` | init |  | 013_statics.ets100.com__ets-student-pc-web__plugins__stic__sysconfig.js:16 |
| `appcontroller.close` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:38 |
| `appcontroller.fullscreen` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:80 |
| `appcontroller.get_win_pos` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:100 |
| `appcontroller.hide` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:90 |
| `appcontroller.idg_exist` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:119 |
| `appcontroller.init` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:33 |
| `appcontroller.maximize` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:43 |
| `appcontroller.minimize` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:48 |
| `appcontroller.move` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:66 |
| `appcontroller.move` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:75 |
| `appcontroller.reduction` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:85 |
| `appcontroller.restore` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:53 |
| `appcontroller.set_win_pos` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:105 |
| `appcontroller.show` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:95 |
| `appcontroller.startapp` | - |  | 004_statics.ets100.com__ets-student-pc-web__plugins__stic__appcontroller.js:114 |
| `soundhelper.aqcwavfile` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:138 |
| `soundhelper.checkvoice` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:79 |
| `soundhelper.checkwovfile` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:66 |
| `soundhelper.combineandconvertwavtomp3` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:143 |
| `soundhelper.continue` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:119 |
| `soundhelper.convertfile` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:133 |
| `soundhelper.destroy` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:43 |
| `soundhelper.init` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:38 |
| `soundhelper.loadfile` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:92 |
| `soundhelper.pause` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:110 |
| `soundhelper.play` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:101 |
| `soundhelper.record` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:48 |
| `soundhelper.stop` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:128 |
| `soundhelper.trace` | - |  | 011_statics.ets100.com__ets-student-pc-web__plugins__stic__sndhelper.js:61 |
| `sqlitepln.connect` | connect |  | 007_statics.ets100.com__ets-student-pc-web__plugins__stic__sqlitepln.js:19 |
| `sqlitepln.destroy` | destroy |  | 007_statics.ets100.com__ets-student-pc-web__plugins__stic__sqlitepln.js:45 |
| `sqlitepln.disconnect` | disconnect |  | 007_statics.ets100.com__ets-student-pc-web__plugins__stic__sqlitepln.js:24 |
| `sqlitepln.execDML` | execDML |  | 007_statics.ets100.com__ets-student-pc-web__plugins__stic__sqlitepln.js:40 |
| `sqlitepln.execQuery` | query |  | 007_statics.ets100.com__ets-student-pc-web__plugins__stic__sqlitepln.js:35 |
| `sqlitepln.init` | init |  | 007_statics.ets100.com__ets-student-pc-web__plugins__stic__sqlitepln.js:14 |

### 7.4 桥的能力归类（供后续原生侧对照）

- **窗口/生命周期**（`appcontroller`×15）：init/close/maximize/minimize/restore/move/fullscreen/reduction/hide/show/get_win_pos/set_win_pos/startapp/idg_exist。
- **系统/设备**（`ShellHelper`×34）：getconfig、getroomid、getpcinfo、getuniqueid、getdeviceinfos、monitordeviceplug、CheckAudio、checkadapter、netcheck、setvolume/getvolume/setmute、clipboard、cmd/executecmd/executeexe/executebat、startprocess/stopprocess/processexist、getserverports、padkeyboardup、setsuspensionballconfig、killagentserver、actauth/getactauth/gettoken（授权码激活）、destroy。
- **文件/归档**（`FileHelper`×27、`SevenZip`×4）：读写、复制/删除/重命名、遍历、MD5、base64、打开/保存对话框、`aliyun_oss_md5`、`readrpk_kqlx`、zip/unzip。
- **网络**（`HttpHelper`×8）：download / downloadresource / downloadsdk / upload / 断点、限速、isrpkexist。
- **数据库**（`sqlitepln`×6）：connect/disconnect/execQuery/execDML。
- **音频**（`soundhelper`×14）：见 §8。
- **升级/杂项**（`EtsHelper`×11、`SysConfig`×1）：check_update、run_update、log_data、get_appdata_path、encode_api_body[_v2]、encode_api_resp[_v2]、dub_merge、open_url_by_def_browser、test_crash。

### 7.5 与旧评估“127 个 actionKey”的差异

本次精确统计：120 处字面量 `sendMessage` 调用 = **115 个不同 (plugin, action)** + 2 个动态 action = **117**。差异 **10 个**未在本次缓存的插件源码中出现，可能原因（未知，需更多版本/更多缓存对照）：旧评估把回调通道名（如 `@recordbegin`、`@init`、`@error`）也计入；或统计了其他版本 bundle/其他插件文件（当前只有 9 个插件 + `plugins/clientDB.js`）。本报告以**代码可证**的 117 个为准。

---

## 8. 录音 → 转码 → 评测 → 上传链路（前端侧）

### 8.1 总览

```
[麦克风] → 原生 soundhelper.record（STIC 音频引擎，原生侧）
   ├─ datastream_callback(data) ──→ 评测 SDK（双通道 WebSocket）分片发送
   ├─ waveform_callback("1|2|3") ─→ UI 波形
   ├─ recordbegin/recordend_callback → 计时/收尾
   ▼
本地文件 EXE_PATH\soundfiles\public_<uuid32>_<ts>.mp3（speex 流时另有 .spx）
   ├─ 在线评测：结果 → /m/audio/sync-v2（score_detail/rate_scale/graduation）
   ├─ 离线/重评：evaluateAudioFile(file) → getFileBase64 → 同一评测 SDK
   └─ 上传：uploadFile() → OSS（partner.ets100.com/oss/config 取 policy）
```

### 8.2 录音（`useRecorder`，B:54787-55069）+ 原生 SndHelper

- `useRecorder()`：`v = new SndHelper({ error_callback, datastream_callback, waveform_callback, playbegin/playend, recordbegin/recordend, aqcresult_callback })`（B:54810-54878），初始化后 `v.init()`。
- 录音参数（B:54894-54904、54927-54944）：
  - 默认录音时长 `n=100`（=10s，因为 `recordTime` 单位是 0.1s：`b(e)=(e>0?e:100)/.1`，B:54884-54885）。
  - `dataStreamType`：默认 `"10"`；`isSpeexMode` 时 `"spx"`（B:54798），并追加 `spxQuality:"10"`、`saveSpxFile:1`（B:54944）。
  - 文件：`EXE_PATH\soundfiles\public_<32位uuid>_<Date.now()><suffix>`，`DefaultRecordFile.suffix=".mp3"`（B:51232），`recordOnly` 路径是 `${a}${Date.now()}.mp3`（B:54896）。
  - 关键参数对象（B:54941-54944）：`{ recordTime, filePath, dataStreamType, [spxQuality], [saveSpxFile] }`。
- 录音前音量保障（B:54886-54892）：`systemConfig.pc_force_record_vol_100==1` → 强制麦克风 100%；否则 `useMediaSettingStore().checkMicrophone()`，低于 `pc_min_record_volume` 时强制设为该值。
- 原生 ack/事件（实测日志 `ets_2026-11-4.log`）：`sndInst.record ack（原生开始录音）, data={"data":"","errorCode":0,"errorMsg":"record ok.","flag":0}`；`recordbegin_callback`；`recordend_callback` 携带 `{"time_len":50,"media_stop":0}`（`time_len` 单位 0.1s）。
- 波形：`waveform_callback` 收到 `"a|b|c"` 字符串 → `split("|").map(Number)` → `useVolume().convertToVolume`（`Math.abs(x)/32767` 取最大值，B:55070-55078）。
- 停止（B:55003-55013）：不足 1s 不允许停止（提示“触发停止录音，不够1s, 不允停止”）；`stop()` 后原生触发 `recordend_callback`，前端 resolve 评测结果。
- 原生 `soundhelper` 动作全表（`pretty/011_...sndhelper.js`）：`init/destroy/record/trace/checkwovfile/checkvoice/loadfile/play/pause/continue/stop/convertfile/aqcwavfile/combineandconvertwavtomp3`（14 个）。其中：
  - `combineAndConvertWavToMp3`（L139-143）：多段 wav 合并转 mp3；
  - `startAQCWavFile`（L134-138）：音频质量检测（AQC）；
  - `checkWov/checkVoice`（L62-79）：录音设备/格式校验；
  - `convertfile`（L129-133）：格式转换（wav<->mp3/spx）。

### 8.3 评测（引擎选择 + 双通道 ISE）

- 引擎规则（`useRecordInit`，B:46743-46790+）：
  - 读取 `userInfo.systemConfig.engine_sdk_config`（JSON）：`global_default_rule.default_engine_sdk`、`global_default_rule.use_exam_engine`、`engine_config_list[]`（按 `parent_res_id_list` 命中用户 E 卡 `parent_resource_id`，再按 `paper_type_list.condition(or/and) + set_module_list/set_type_list` 命中具体 `category` → `engine_sdk`）。
  - `ENGINE_SDK` 枚举（B:24454）：`MSC / AI / AI2 / AI_2MIX / AI_2INS / AI_2EXAM`；`isAIMultiEngine` = AI_2MIX/AI_2INS/AI_2EXAM（B:24473-24475）。
  - 引擎连接参数（B:46778-46783）：`BASE_URL=envConfig("VITE_DUAL_CHANNEL_ISE_WSS_URL"|"VITE_DUAL_CHANNEL_ISE_TEST_WSS_URL")`、`AI_THOR_URL`、`DEVICE_ID=appConfig.MAC`、`DF="ETS_PC"`、`UID=recent_account_id`、`APPID=decrypt(ENGINE_SDK_CONFIG.AI_ID)`；`ENGINE_SDK_CONFIG` 内 AI_ID/MSC_ID/AI_KEY 为 base64 常量（B:24464-24466）。
  - 评测参数（B:54973-54979）：`{ category, res_id, region, ent:引擎配置, mark_local_file, isEtsOpen, set_id, first_column_id, aioeFlag, params }`；`region` 规则：`pprInfo.isEtsOpen` 且 `mark_region`，否则 `ecardInfo.engine_area`（AI_2MIX/AI_2INS）。
- 发送（B:54966-55002）：`v.record(N, cb)` 原生开始录音后，`iseManager.onmessage/onerror` 注册回调，`iseManager.start(params)` 建连；音频分片通过 `datastream_callback` → `iseInstance.send(e)`（B:54832-54837）。
- 双通道客户端常量（B:24480）：`WS_TIMEOUT=60000`、`audio_chunk_send_interval=40`(ms)、`pc_web_aicloud_chunk_size=6400`(B)；可在 `systemConfig` 用 `pc_web_/hd_pc_web_audio_chunk_send_interval`、`*_wss_timeout` 覆盖（B:30232）。
- 错误码（B:24450-24461）：`IseErrorCode {Success:"000000", AuthFailed:"700001", Error:"40004"}`；`ENGINE_CODE {Silent:"68673", NoData:"10118", LowVolume:"28673", Err:48205}`；`ExceptInfo`（无声类 28673/28676/28678/28680/28690/28689/28707）→ 视为 0 分（B:54990-54999）。
- 日志中实测：`sdk:AI2, category:read_sentence, region:shanghai`，`发送开始帧/结束帧`，结果含 `total_score`、`sid=tencentyun@...`、`wav_url=https://ets60.ets100.com/ugc/evaluate/mp3/...`（`ets_2026-11-4.log` 的 `[ENG_SCORE]` 行）。

### 8.4 评分结果回写

`requestAnswerLogs`（B:50336-50360）：整理 `score_detail`（JSON 串）、`rate_scale`（0.125 换算，依据 `ecardInfo.rate_scale` 与 set 列规则）、`graduation`、`client_time`、`mark_service:1`、`version:"2"` → `hyRequest.postIt("/m/audio/sync-v2", payload)`。
其他同步：`/m/set/get-score-detail`、`/m/set/reset-score-v2`、`/m/exam/sync`、`/m/exam/submit`、`g/set/report-score`、`g/homework/report-score`。

### 8.5 上传（OSS 直传）+ 断网重试

`uploadFile(filePath, {dir,index,signal})`（B:51457-51480+）：

```
1) buf=useFileManager().getFileBuffer(path); md5=getFileMD5(path); name=`${md5}.${ext}`
2) GET ${envConfig("VITE_AUDIO_UPLOAD")}?dir=${dir||"tmp"}&name=${name}
   → { accessid, signature, callback, expire, policy, dir, host }
3) POST multipart 到 host：OSSAccessKeyId / Signature / callback / expire / policy / key(=dir+name) / name / file
4) 回调返回上传结果（OSS callback 由服务端校验）
```

本地重试队列：IndexedDB `uploadRecord` 表（字段 `filePath,userId,type,preId,times`，B:46619、51636-51645、51776-51784）——录音/SLS 上传失败时落库，后续重试（`addRecord/getAll/getRecord/updateRecord/deleteRecord`）。

> **未知**：将评测文件（mp3/xml）上传到 `ets60.ets100.com/ugc/evaluate/...` 并回传 `wav_url` 的具体前端代码位于本次未缓存的懒加载 chunk（191 个引用中缺 122 个），只能由日志侧证实存在（`[ENG_SCORE] 上传本题本地录音文件/上传本题本地xml文件`），无法给出源码行号。

---

## 9. 日志与埋点上报链路

### 9.1 本地日志（→ <ETS_INSTALL_DIR>\logs）

`LoggerUtils`（B:50977-51017）：

- `logCustom(msg, {type:1|2, tag:"MISC"|"API_ETS"|"PLG_STIC"|"ENG_SCORE"})` → `EtsSeverUtils.sendMessage("[I] [tag] msg")`。
- `logRequest(config)` / `logResponse(resp, {type,url,time})` → `[I] [API_ETS] ...`（含耗时 ms）。
- 初始化 `LoggerUtils.init()` 会创建 `EtsHelper` 实例（`EtsHelper.init`），用于版本检查等。

`EtsSeverUtils`（B:50875-50960）：

- 静态 WS 客户端：`ws://127.0.0.1:${(JSON.parse(cef.message.getAppConfig())||{}).suspensionBallPort||40001}`（B:50952-50955），5s 超时重试（`retryCount=3`）。
- 进程守护：`processName = "ets_mq_server.exe"`（Windows）/`ets_mq_server`（Linux），启动路径 `EXE_PATH/mq_server/ets_mq_server.exe`，通过 `ShellHelper.processexist/startprocess` 检查并拉起（B:50905-50920）。
- `sendMessage(str)` → WS 转发；mq_server 把收到的内容落盘为 `<ETS_INSTALL_DIR>\logs\ets_<M-D>.log`（实测日志格式：`[时间] [INFO] mq_server - received: [I] [TAG] ...`）。
- 前端日志文件族：`cef_<M-D>.log`（CEF 原生）、`shell_<M-D>.log`（ETSShell）、`ets_<M-D>.log`（前端经 mq_server）。

### 9.2 阿里云 SLS 埋点

`appGeneralSlsUtils`（B:46967-47034）：

- 初始化 `getCredentials()` → `requestSlsAppConfig()`（接口 `/p1/student/ability/sls/slsAppConfig` 与 `g/data/sls-config`，实测日志两条都有）→ `body = {access_key_id, access_key_secret, security_token, endpoint, project, logstore, expiration}`。
- `new WebTrackerBrowser({host, project, logstore, time:1, count:100, topic:"topic", source:"PC", tags:{tags:"tags"}})` + `createStsPlugin({accessKeyId, accessKeySecret, securityToken, refreshSTSTokenInterval:5000, refreshSTSToken})`（B:46988-46999）。
- WebTracker 协议（B:25695-25743）：POST `${host}/logstores/${logstore}/track`，body `{__logs__:[...], __topic__, __source__, __tags__}`，批量 10 条/10s 刷新；`sendImmediate` 立即发送。
- 业务用法：`appGeneralSlsUtils.sendImmediate(getGeneralSlsParams(token, {type:"evaluateFile", subType:"record", description, level:"INFO", code: slsNormalCode.success|error}))`（B:54830、54871）；`slsNormalCode={success:1,error:-1}`、`slsFileCode={success:1,noFile:-1000,ossError:-1001}`（B:51646-51650）。
- 另一套 `SlsUtils`（旧 SLS 封装，B:27430 附近）在业务页使用，字段含 page/action 等（具体参数各页面自定，未逐一展开）。

### 9.3 log_collector / 崩溃与反馈上报

- `useLogCollector()`（B:51494-51521）：`new ClientDBUtils({dbpath:"./bugreport/localdata/BuryPoint.db"})`；`t(type, version)` 组装 `type/version/system/account_id(raw_phone)/date_time` → `axios.post(envConfig("VITE_log_collector"), form-urlencoded)`，即 `http://collect.ets100.com/log_collector`；事件类型如 `Event_Startup`、`Event_Crash_LastError`。
- 崩溃上报：`useLogCollector` 读取 `bugreport` 数据 → `uploadFile(崩溃压缩包)` → 上传 OSS，并 `requestSubmit`（`m/feedback/submit`）提交 `feedback_type/system_type:9/m_code:md5(MAC,16).toUpperCase()` 等（B:51522-51540）。
- 日志打包上传 `useUploadLogs`（B:55775 附近 + `packagingLogs/uploadLogs`，B:53413-53440）：
  - 选择日期 → 把 `EXE_PATH\logs\{cef,shell,ets}_<Y-M-D>.log` 复制到 `EXE_PATH\temp\logs\`，连同 `EXE_PATH\temp\sounds\sounds_<date>` 一起 `ZipUtils.zip`；
  - zip 命名 `log_<raw_phone>_<YYYYMMDD>_<HHmmss>.zip`；
  - `uploadFile(zip)` → OSS；上传完成后删除 `temp\sounds`。
- 第三方埋点：`VITE_TRACKER_IFLYTEK_*`（release 环境 appid `OsoL5ESKO835`，测试环境另有一套）+ `dcp.changyan.com/dcp-js/entry.js`、`analysis.js`（缓存中已抓到，见 §1.4），即讯飞 DCP 数据采集 SDK；加载点为主 bundle 内动态注入（缓存 URL 可证），具体注入代码未逐行定位（部分未知）。

### 9.4 本地存储/缓存相关

- `localStorage`：`clientConfig`（环境/版本/端口）、`os`、`linuxUpdateDetails`、`winConfig`(session)。
- `sessionStorage`：`token`、`winConfig`、`record_ready_delay`、`crash_log`、`pageHomeworkListRouterData`。
- IndexedDB（dexie）：`downloadFiles/login/wordDict/questionDetilsDb/wordPractice/uploadRecord/userSet/phonetic/...`（B:46619 一行注释列出全部表结构）。
- SQLite（原生）：`ClientDBUtils` 封装 `sqlitepln`，主要读写 `config` 表（如 `UpdateLoginInfo/LoginInfo`，B:51910-51921）。

---

## 10. 未解 / 未知（诚实标注）

1. **122 个懒加载 chunk 未抓到**（未被本次会话访问）。因此 `Practice/Comprehensive/Homework/WordsPage/...` 等页面内部逻辑、以及评测结果上传到 `ugc/evaluate` 的具体前端代码无法给出。`routes.json.chunks[*].present=false` 可精确列出。
2. **13 条缓存条目**的响应头地址指向已淘汰块（`data_1` 之外/被覆写），无法恢复响应头，但其 URL/大小仍可读；已在 `cache_entries.json` 标出（读取时返回空 headers）。
3. **权限/页面守卫函数体**（`permissionInterceptor/keepAliveInterceptor/pageInterceptor/resetStoreAfterRouteInterceptor`）未逐行展开（被压缩为常量引用处），其内部规则（白名单、跳转条件）未还原。
4. **`suspensionBallPort` 默认 40001** 之外，`cef.message.getAppConfig()` 的完整字段结构未知（只用到 `suspensionBallPort`）。
5. **V1 签名 pid="grlx"** 的语义（产品线标识）未知；**v2 `key_id` 的来源/轮换**在原生侧，前端只透传。
6. **`RSA_PUBLIC_KEY` 常量**（实为 RSA 私钥）在 main bundle 中的用途未定位（可能仅历史遗留/其他模块用），未见调用点（未知）。
7. 旧评估“127 actionKey”与本次 117 的差额原因未知（§7.5）。
8. 埋点事件全量字典（`Event_*`）位于懒加载页面代码，未全量枚举；已确认 `Event_Startup`、`Event_Crash_LastError`。
9. `data_0`（block size 36 的块文件）在此会话中基本为空，未参与资源恢复。

---

## 11. 产物与证据索引

> 下表标注（未随仓库发布）的产物不在仓库内；已发布的数据文件位于 `data/frontend/`。

| 产物 | 说明 |
|---|---|
| `data/frontend/routes.json` | 91 条路由（path/name/component/chunks/meta/module/line）+ 191 个 chunk 引用与命中情况 |
| `data/frontend/action_keys.json` | 9 通道 115 个 action（含方法名、参数文案、文件、行号） |
| 前端资源清单（未随仓库发布） | 353 条资源清单（URL/类型/大小/sha256/缓存定位/pretty 路径） |
| 前端原始 bundle（未随仓库发布） | 209 个去重后的原始资源（含 3.4MB 主 bundle、1.15MB CSS、原生插件 JS、图片等） |
| 前端可读化 bundle（未随仓库发布） | 139 个文本资源的可读版（插入换行，字符不变；用于行号引用） |
| API 端点清单（未随仓库发布） | 118 个 API 端点（`data/frontend/api_endpoints.json`） |
| Pinia store 清单（未随仓库发布） | 20 个 store（`data/frontend/stores.json`） |
| 缓存条目清单（未随仓库发布） | 353 条缓存条目原始解析结果（含响应头、地址） |
| 桥调用点清单（未随仓库发布） | 120 处 `sendMessage` 原始调用点 |
| 关键代码窗口（未随仓库发布） | 关键代码窗口（带行号，便于复核）：`routenames/logger/uploadlogs/sls/snd1-4/ise4/oss/sigreq/consts/...` |
| `scripts/work_frontend_scripts_*.py` | 全部解析/提取/统计脚本（可复现，见 §1.2） |
| 行号约定（未随仓库发布） | 所有 `文件:行号` 引用均指可读化 bundle 版本；原始 minified 为单行，行号=1 |

主要证据行号速查：

| 主题 | 证据 |
|---|---|
| 入口/脚本顺序 | `pretty/000_...index.html:13-35` |
| 路由构建/守卫 | `pretty/001_...index-dc0257dd.js:56361-56464` |
| 签名适配器 | 同上 `:56465-56547` |
| 请求信封（postIt） | 同上 `:56630-56672` |
| 错误码 20004 | 同上 `:56553-56579` |
| HYRequest/拦截器 | 同上 `:18326-18353`、`:56580-56610` |
| 环境配置表 | 同上 `:18354-18385` |
| 录音 useRecorder | 同上 `:54787-55069` |
| 引擎选择 | 同上 `:46743-46790` |
| 评测常量/错误码 | 同上 `:24450-24483` |
| 评分同步 | 同上 `:50336-50360` |
| OSS 上传 | 同上 `:51457-51480` |
| 日志 LoggerUtils | 同上 `:50977-51017` |
| 本地 WS/mq_server | 同上 `:50875-50960` |
| SLS WebTracker | 同上 `:25695-25743`、`:46967-47034` |
| 日志打包上传 | 同上 `:53413-53440`、`:55775+` |
| 桥协议示例 | `pretty/005_...shellhelper.js:21-30`、`pretty/011_...sndhelper.js:44-48` |
| 动态 action 发送器 | `pretty/014_...etshelper.js:4-15` |

---

## 12. 运行时复核（2026-11-06 live）

用户在分析副本上启动了真实实例（CDP 10086），本节记录对前端结论的在线复核与修正，详见 `11_runtime_live.md`。

| 项 | 静态阶段（缓存 bundle） | 运行时（在线） |
|---|---|---|
| 主 bundle | `index-dc0257dd.js` | `index-e7d07c24.js`（同尺寸，仅 chunk 哈希重打包；核心代码逐字一致） |
| chunk 覆盖 | 69/191（缓存命中） | **188 个在线 chunk 全部下载**（旧 191 个按基名映射 186 个，其余 5 个为 SFC 虚拟模块名） |
| 补全模块 | 缺失 | WordList/WordPractice(PK)/PKMatch/readAloud/readSentence/networkSpeedWorker/textInfo 等 14 个 |
| 插件封装 | 由 bundle 推断 action | `/plugins/stic/*.js` 给出权威 pluginKey 与 115 个 (plugin, action) |
| pluginKey | 未强调大小写 | `EtsHelper`/`FileHelper`/`HttpHelper`/`SevenZip`/`ShellHelper`/`SysConfig` 首字母大写；`appcontroller`/`soundhelper`/`sqlitepln` 小写 |
| 签名 | 333/334（历史日志） | **68/68（本次 live 日志）** |

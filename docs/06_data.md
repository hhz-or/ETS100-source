# 06 本地数据与资源分析（讯飞 E 听说 PC 学生端 5.7.9 / ETSShell）

> 范围：`D:\ets-rea\ETS` 下的本地持久化数据、Chromium（CEF）用户数据、`temp\resources` 资源包、`soundfiles` 录音与评测结果、更新/下载日志。
> 目标目录全程只读，未做任何修改；所有解包/导出产物写入 `D:\ets-rea\work\data\`（约 39 MB）。
> 脱敏约定：账号统一 `SHM*******`、手机号 `1**********`、JWT/STS/密码字段 `***REDACTED`；文中数值/时间戳保持原样。
> 证据路径均相对 `D:\ets-rea\`；`[ETS]` 表示只读源文件，`[W]` 表示本次产物。

---

## 0. 结论速览

| 块 | 结论 |
|---|---|
| SQLite 配置库 | `localdata\ETS.db` 是客户端唯一的 SQLite 配置库：**只有 1 张 `Config(Section,Entry,Value,UpdateTime,Common)` 表**，7 行；`SQL\ETS.db.sql` 在本次快照中为 **0 字节**（缺口），但其等价建库/更新 SQL 内嵌在 `EtsUpdate.exe` 中，可据此还原更新流程。 |
| 浏览器存储 | CEF 用 `temp\Cache_ETSShell` 作为用户数据目录。登录态**不在 Cookie**（11 条 Cookie 全是第三方 `v10`(DPAPI) 密文）；账号/密码（混淆）/JWT 存在 `Local Storage` 的 `appLogin` 与 IndexedDB 的 `login` 对象存储；IndexedDB 共 **200,945 条记录**、13 个对象存储（词库缓存 28,322 词、评测上传记录 396+、配置等）。 |
| 资源包 | `temp\resources` 为「套卷 set_id 目录 + 8 个 `content_<stid>.zip` + 共用 `template_686.zip`」结构；**content 包是 ZipCrypto 加密的**，密码由包尾 336 字节口令块经 `MD5(MD5(pwd))` 二级摘要得到（JS 逻辑位于缓存中的 Vite bundle），本次已成功解密并解包 **24/24** 个 content 包。 |
| 音频/评测 | `soundfiles` 每条录音三件套 `public_<32hex>_<13位毫秒>.mp3` + `.mp3.spx` + `.xml`，共 36 组。mp3 为 16 kHz 单声道 24 kbps（可上传/回放），spx 为高熵自定义/压缩副本（非标准 Ogg Speex，未确认，缺口），xml 为讯飞评测引擎返回的逐词/逐音素评分结果（read_sentence / simple_expression_ufi / topic 三类）。 |

---

## 1. 数据版图

| 路径 `[ETS]` | 大小 | 说明 | 本次产物 `[W]` |
|---|---|---|---|
| `localdata\ETS.db` | 12,288 B | SQLite 配置库，仅 `Config` 表 | `work/data/db/ETS_db_dump.json`、`ETS_db_Config_rows.json` |
| `SQL\ETS.db.sql` | **0 B** | 预期为 GBK 建库脚本，本次为空（缺口 §8） | 内嵌 SQL 证据：`work/data/db/EtsUpdate_SQL_region.txt` |
| `bugreport\localdata\BuryPoint.db` | 16,384 B | 埋点库，`BURYPOINTDATABASE` 表 0 行 | `work/data/db/BuryPoint_db_dump.json` |
| `temp\Cache_ETSShell\` | ~35 MB | CEF 用户数据（Cookie/LS/SS/IDB/Cache/Code Cache） | `work/data/storage/*.json` |
| `temp\resources\` | 3×~2.7 MB | common/clear_cache/pc_xst_dict + 3 套套卷资源 | `work/data/extracted/**`、`resources_*.json` |
| `soundfiles\` | 108 文件 | 36 组 mp3/spx/xml | `work/data/soundfiles/*.json` |
| `logs\` | 6 文件 ~30 MB | shell/ets/cef 日志（GBK/UTF-8 混合） | `work/data/logs/*.json` |
| `temp\update\log\` | 3×1,696 B | 客户端自动更新（EtsUpdate）日志 | 同上 |
| `7z.log` | 15,949 B | 7z 解包日志（记录了原始安装路径与全部解包动作） | 引用 |

工具：Python 3.13（标准库 sqlite3/json/ElementTree）、7-Zip 26.00、`ETS\ffmpeg\ffmpeg.exe`、自写纯 Python LevelDB 读取器（`work/data/_scripts/leveldb_reader.py`，含 Snappy 解压/SST/LOG 解析，**未依赖 pip**）。

---

## 2. SQLite 配置库（`localdata\ETS.db`）

### 2.1 文件级事实（证据：`work/data/db/ETS_db_dump.json`）

| 项 | 值 |
|---|---|
| 大小 / page_size | 12,288 B / 4096 |
| 编码 / journal_mode | UTF-8 / delete |
| 表 | 1 张：`Config`；索引 1 个：`unique_ley` |
| 版本 | `user_version=0`（无 schema 版本，靠 SQL 脚本增量升级） |

```sql
CREATE TABLE [Config] (
  [Section] VARCHAR(64),
  [Entry]   VARCHAR(64),
  [Value]   VARCHAR(256),
  [UpdateTime] DATETIME,
  [Common]  varchar(128)
);
CREATE UNIQUE INDEX [unique_ley] ON [Config] ([Section], [Entry]);
```

字段语义：

| 字段 | 含义 | 备注 |
|---|---|---|
| `Section` | 配置分组 | 现有 `System`、`UpdatePop`、`UpdateLoginInfo` |
| `Entry` | 配置项名 | 与 Section 组成唯一键 |
| `Value` | 配置值（字符串） | 全部以 TEXT 存储 |
| `UpdateTime` | 写入时间（本地时间） | 允许 NULL |
| `Common` | 中文说明（帮助文案） | 更新时由 SQL 写入；本库为 UTF-8 中文 |

### 2.2 全表数据（7 行，`work/data/db/ETS_db_Config_rows.json`）

| Section | Entry | Value | UpdateTime | Common（中文说明） | 用途解释 |
|---|---|---|---|---|---|
| System | `C_Version` | `5.7.9` | 2024-04-17 18:52:04 | 客户端版本号 | 客户端展示/上报用版本；`EtsUpdate` 更新成功后用 `UPDATE [Config] SET [Value]="%s" WHERE [Entry]="C_Version"` 写入 |
| System | `Update_Version` | `5079` | 2024-04-17 18:52:04 | 更新版本号 | 内部整型版本号；`EtsUpdate` 启动时 `SELECT [Value] FROM [Config] WHERE [Entry]='Update_Version'` 作为比较基准，更新后写回 |
| System | `EnvType` | `1` | 2024-04-17 18:52:04 | 1-正式, 2-灰度, 3-测试 | 环境选择；前端 `LoginView` 读取并打印环境（另见日志/JS 中 4-开发、5-重构） |
| System | `TestVersion` | `0` | 2024-04-24 10:12:07 | 测试版本号 | 测试通道版本标记 |
| System | `Port` | ``（空） | 2024-04-24 10:12:07 | 主链接端口号，默认空 | 主链接（后端）端口覆盖；空=用默认 |
| UpdatePop | `Skip` | `0` | 2024-04-17 18:52:04 | 是否跳过更新提示, 0-不跳过, 1-跳过 | 自动更新弹窗的“不再提示”开关；`EtsUpdate` 读取 `UpdatePop/Skip` |
| UpdateLoginInfo | `LoginInfo` | `xxx` | NULL | NULL | 上次登录信息位；本样本值为占位 `xxx`（疑似被样例化/脱敏），`Common` 为空 |

> 前端 JS 里还有一份**同构镜像**：`Local Storage` 的 `clientConfig` = `{"C_Version":"5.7.9","Update_Version":"5079","Skip":"0","EnvType":"1","TestVersion":"0","Port":""}`（99 B，UTF-8），即前端从 DB/接口同步后写入 localStorage，见 §3.3。

### 2.3 `SQL\ETS.db.sql` 为空时的补救证据（`EtsUpdate.exe`）

`EtsUpdate.exe` 内嵌了完整更新流程与 SQL（`work/data/db/EtsUpdate_SQL_region.txt`，GBK 区段，偏移 0x182BC0–0x182FD0 附近）：

| 证据字符串（`EtsUpdate.exe`） | 含义 |
|---|---|
| `\SQL\`、`ETS.db.sql`、`\localdata\`、`ETS.db` | 更新器从安装目录 `SQL\ETS.db.sql` 读脚本、操作 `localdata\ETS.db` |
| `[SQL ERRID:`、`更新数据库失败`、`=更新成功=`、`版本号:` | 脚本执行日志 |
| `BEGIN TRANSACTION` / `COMMIT TRANSACTION` | 多语句事务执行建库脚本 |
| `SELECT [Value] FROM [Config] WHERE [Entry]='Update_Version'` | 读取本地版本号 |
| `UPDATE [Config] SET [Value] = "%d" WHERE [Entry] = "Update_Version";` | 更新后写版本号 |
| `UPDATE [Config] SET [Value] = "%s" WHERE [Entry] = "C_Version";` | 更新后写客户端版本 |
| `select value from Config where section='%s' and entry='%s'` | 通用读配置（Skip 等） |
| `delete from Config where section='%s' and entry='%s'` / `insert into Config values ('%s','%s','%s','','')` | 配置项写入/重置 |
| `\update.dat`、`Temp/Update/update.dat`、`/Dir="%s" /CVer="%s" /UVer="%d" /Exe="%s" /File=".../update.dat" /Slient="0"` | 更新包与安装器启动参数 |
| `SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce`、`ETS_UPDATE` | 重启接续更新 |
| `QTEngine.exe`、`IFC.exe`、`ETSShell.exe`、`taskkill.exe /F /T /PID %u` | 更新前结束的进程 |
| `http://api.ets100.com`、`RequestURL`、`--AutoRun --AppName --AppTitle --AppDirectory --NetworkTimeout --DetectionTimeout --UpdateID --ForceShow` | 更新接口与命令行 |

结论：`SQL\ETS.db.sql` 的**文本未在本次快照中保留**，但更新器的执行方式、事务边界、版本号读写语句都已还原；运行库 `ETS.db` 的表结构见 §2.1（与 SQL 脚本执行后的结果一致）。

### 2.4 `bugreport\localdata\BuryPoint.db`

| 表 | 字段 | 行数 |
|---|---|---|
| `BURYPOINTDATABASE` | `ID, PROCESSNAME, TIME, LASTERR, PID` | 0 |

埋点离线队列库（进程/时间/错误/PID），运行期才会写入；本快照为空。

---

## 3. Chromium / CEF 本地存储（`temp\Cache_ETSShell`）

### 3.1 目录清单

| 路径 `[ETS]` | 大小 | 内容 |
|---|---|---|
| `Cookies` (+journal) | 20,480 B | SQLite，Chromium Cookie v14 |
| `Local Storage\leveldb\` | ~0.9 MB | LocalStorage（`*.ldb` + `*.log`） |
| `Session Storage\` | 60 KB | SessionStorage LevelDB |
| `IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb\` | ~13 MB | IndexedDB（origin=`https://statics.ets100.com`） |
| `databases\Databases.db` | 28,672 B | WebSQL/数据库跟踪库（仅 `meta`） |
| `Cache\` | 11.57 MB | HTTP 磁盘缓存：`index` 262 KB、`data_0..3` 5.7 MB、`f_000001..f_000030` 48 个数据块 |
| `Code Cache\js\` | — | 99 个 V8 编译脚本缓存 + `index/index-dir`；`wasm\` 2 文件 |
| `GPUCache\` | 0.53 MB | GPU 着色器缓存 |
| `LocalPrefs.json` | 479 B | CEF Preferences（含 `os_crypt.encrypted_key`） |
| `Network Persistent State` | 592 B | HTTP/2(SPDY) 服务器属性 |
| `Visited Links` | 131,072 B | `VLnk` v3，URL **哈希**集合（不可还原明文） |
| `QuotaManager` | 53,248 B | 存储配额管理库（SQLite） |
| `Reporting and NEL` | 36,864 B | NEL/Reporting API 持久化（SQLite） |
| `DevToolsActivePort` | 60 B | `10086\n/devtools/browser/e6be91f9-…`：**CEF 远程调试端口 10086 + 浏览器 GUID**（可 CDP 附加） |
| `CURRENT/MANIFEST-000001/000003.log/LOG/LOG.old` | — | 顶层 LevelDB（实际无业务数据，`000003.log`=0 B） |

### 3.2 Cookies（`work/data/storage/cookies.json`）

- SQLite `meta.version=14`，表 `cookies(creation_utc,host_key,name,value,path,expires_utc,is_secure,is_httponly,last_access_utc,has_expires,is_persistent,priority,encrypted_value,samesite,source_scheme,source_port,is_same_party)`，共 **11 条**。
- **`value` 全部为空**，密文在 `encrypted_value`，前缀均为 `v10`（Chromium Windows DPAPI 方案：`v10` + nonce + AES-256-GCM 密文，密钥由 `Local State/LocalPrefs.json` 的 `os_crypt.encrypted_key`（`DPAPI`+密文）解出）。
- `LocalPrefs.json` 实测：`{"os_crypt":{"encrypted_key":"RFBBUEkBAAAA…"},"profile_network_context_service":{…}}`。

| host_key | name | secure | httponly | 说明 |
|---|---|---|---|---|
| api.ets100.com | aliyungf_tc | 0 | 0 | 阿里云 WAF 风控 token |
| collect.ets100.com | aliyungf_tc | 0 | 0 | 同上（埋点域名） |
| www.ets100.com / teacher.ets100.com | aliyungf_tc | 0 | 0 | 同上 |
| dcp.changyan.com | aliyungf_tc | 0 | 0 | 畅言（讯飞）域 |
| gcaptcha4.geetest.com | captcha_v4_user | 1 | 1 | 极验验证码会话 |
| .cloud.tencent.com | qcmainCSRFToken / intl / language | 1 | 1 | 腾讯云控制台（内嵌页面产生） |
| .baidu.com | BAIDUID / BAIDUID_BFESS | 0/1 | 0 | 百度统计/跳转 |

结论：**登录态没有落在 Cookie**（无 `ets100` 域的身份 Cookie）；Cookie 侧只保留第三方风控/验证码/统计标识。DPAPI 密钥绑定 Windows 用户，离线无法解密（缺口 §8）。

### 3.3 Local Storage（`work/data/storage/local_storage.json`）

LevelDB 记录 22 条。键值编码（实测）：

- Key：`_` + `<origin>` + `0x00` + `0x01` + `<storage key>`；元数据键 `META:<origin>`；顶层 `VERSION`=`1`。
- Value：首字节为编码标记——`0x01` + UTF-8 文本，或 `0x00` + UTF-16LE 文本；值本身多为 JSON 字符串。
- 文件：`000005.ldb/000071.ldb/000073.ldb/000075.ldb/000077.ldb` + `000076.log`(414 KB)/`000078.log`；`work/data/_scripts/leveldb_reader.py` 按序列号合并取最新值。

| key（origin 均为 `https://statics.ets100.com`，另有一条 teacher 域空 META） | 值编码 | 大小 | 内容/用途 | 敏感 |
|---|---|---|---|---|
| `VERSION` | — | 1 | 本地存储格式版本 `1` | |
| `appLogin` | utf-8 | 78 | `{"phone":"***","pwd":"<8字节混淆串>","rememberPwd":true,"autoLogin":true}`：**记住密码/自动登录**（密码为应用级混淆，非明文） | ★ |
| `userInfo` | utf-16 | 378,151 | 用户信息大对象（`userInfo.recent_account_id` 等，含账号相关字段） | ★ |
| `appConfig` | utf-16 | 2,803 | 设备/环境：`AppTitle=讯飞E听说`、`ClientType`、`HDSerial`、`IP`、`MAC`、`Name`(机器名)、`OS/OSBit`、`Version=1.0.0.1` 等 | ★ |
| `clientConfig` | utf-8 | 99 | §2.2 的 `C_Version/Update_Version/Skip/EnvType/TestVersion/Port` 镜像 | |
| `systemConfig` | utf-16 | 347,669 | 服务端下发的系统配置合集（活动配置 `hd_pk_activity_config`、开关等） | |
| `resourcePlatformStore` | utf-8 | 592 | `resourceTokenConfig.token`（RS256 JWT，504 字符，`iss/sub=rop`、`app=qm-ets-key`、`uid=1234`）+ `timestamp/expireAt` | ★ |
| `appOssStore` | utf-8 | 1,913 | `ossEvaluateUploadConfig.upload`：阿里云 OSS 上传 **STS**（`securityToken` 1,180 字符、AccessKey 等，评测音频上传用） | ★ |
| `homeworkStore` | utf-16 | 22,943 | 作业列表缓存（`homework_id`、`popupArr`、`showPlanPopup`、`dataModel`） | |
| `syncLessionStore` | utf-16 | 21,559 | 同步课教材选择（`currentBook.term_name/name/resource_id/grade_name`…） | |
| `mediaSetting` | utf-8 | 52 | `{"config":{"microphone":100,"volume":10,"speed":1}}`：录音/播放参数 | |
| `os` | utf-8 | 8 | `Windows`（OS 类型） | |
| `specialStore` | utf-8 | 20 | `{"resource_id":239}`：当前专项目资源 | |
| `showGrowth` | utf-8 | 21 | 成长页开关 | |
| `grow` | utf-8 | 49 | 成长数据接口错误缓存 `{code:30001,"resource predict not open"}` | |
| `appTranslateSettingStore` | utf-8 | 22 | `{"selOpenTrans":true}` 划词翻译开关 | |
| `edu_collect_sdk_ebg_st-OsoL5ESKO835` | utf-8 | 275 | 埋点 SDK 开关（`ruleSwitch/maxExtSize/autoPageSwitch/upload…`） | |
| `edu_collect_sdk_idxId&devIdOsoL5ESKO835` | utf-8 | 79 | 埋点设备 ID（UUID）+ 当日计数 | ★ |
| `LLM_ASSISTANT_SDK_DATA_TRACK_ksyyyxx-etszx` | utf-16 | 30,777 | LLM 助手埋点队列（20 条 `sdk_request_v2` 记录，未上传） | |
| `LLM_ASSISTANT_SDK_TEST_AVAILABILITY` | — | 0 | 空 | |
| `META:https://statics.ets100.com` | — | 13 | LevelDB 层元数据（`08 9b d6 cb f4 83 c6 ef 17 10 fa a3 31`，protobuf 风格，语义未知） | |
| `META:https://teacher.ets100.com` | — | 0 | 同上（空） | |

### 3.4 Session Storage（`work/data/storage/session_storage.json`）

36 条 key，全部 **value 为空（删除/清空后的墓碑）**，说明会话级数据在退出时被清掉或只写 key。键格式（Chromium sessionStorage LevelDB）：

- `next-map-id`
- `namespace-<GUID>-<origin>/`（如 `namespace-66d5a548_d7e8_40c6_8614_8f28f01ce102-https://teacher.ets100.com/`）
- `map-<mapId>-<key>`，可见 key：`token`、`__aiplat_token_config`、`allEcardList`、`mistakeManagerStore`、`fromName`、`path`、`previousPath`、`remote_jet_lag`、`pageHomeworkListRouterData`、`requestSystemConfigByKeywordTimestamp`、`winIsMax`、`winConfig` 等。

即前端把“路由/作业列表/错题/令牌”等放进 sessionStorage 的命名空间 map，进程退出后不保留值。

### 3.5 IndexedDB（`work/data/storage/indexeddb.json`）

- 目录：`IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb\`（origin `https://statics.ets100.com`，bucket 0）；5 个 `.ldb`（~1.5–2.2 MB）+ `000090.log`(648 KB)。
- 规模：**200,945 条记录，值总字节约 13.1 MB**。
- 对象存储清单来自库内 `currentSchema` 配置记录（实测值，字段即建表字段）：

| 对象存储 | 字段 |
|---|---|
| `composition` | id, content |
| `downloadFiles` | id_++, url, filename, size, zip_file, desc_file |
| `dubVideo` | id++, userId, pre_id, videoPath, resource_id, times, dubId, md5 |
| `listeningSpeakingPracticeMode` | id++, set_id, homework_id, mock |
| **`login`** | **account, pwd, token, autoLogin, rememberMe** |
| `mockExam` | id++, set_id, entity_id, homework_id, mistake_id, order, xml, audio, upload_file_url, detail_file_url |
| `phonetic` | id, step, section |
| `questionDetilsDb` | set_id, first_column_id, set_module_id, homework_id |
| `syncLession` | id++, userUniqueId, selectKey, selectGradeIndex, selectUnitIndex, module, pkIndex |
| `uploadRecord` | filePath, userId, type, preId, times |
| `userSet` | id, examGrade, specialGrade, pk, newWord |
| `wordDict` | Word, AudioUrl_EN, AudioUrl_US, Trans, Spell_EN, Spell_US |
| `wordPractice` | userUnitId, currentIndex, currentStep, type, count, words |

键布局（Chromium IDB LevelDB，实测前缀）：

- `00 01 <dbid> <osid> …` = 对象存储数据记录；`00 00 …` = 元数据/空值墓碑（1,235 条）。
- 键类型：`0x01` + 长度 + `0x00` + UTF-16LE 字符串（如 `that`/`voluntary`/账号）；`0x03` + 8 字节小端 double（如 1.0）。
- `dbid` 实测分布与内容映射（按值内容识别，非元数据精确解码）：`0x0c`=**wordDict 词库**（198,255 条，其中 28,322 条含 `AudioUrl_EN/Spell_EN`，其余 135k 为 `other`（多义/变形/图片等变体）、34.8k 空值墓碑）；`0x09`=**mockExam/评测上传记录**（36 条含 `xml`+`audio`+`upload_file_url`）；`0x04`=**uploadRecord**（432 条含本地 `public_*.xml` 路径）；`0x02`=**login**；`0x0a`/`0x0d`=作业/题目明细（set_id 7477xx + homework_id）；`0x0b`=syncLession；`0x0e`=配置（currentSchema）；`0x0`=全局元数据。

**登录态记录（已脱敏）**：

```
key (hex) 000102 01 01 0b 00 ... = 前缀 00 01 | dbid=02 | osid=01 | type=01(string) | len=0x0b | enc=00 | UTF-16 "SHM*******"
value  : account / pwd("<8字节混淆串>") / rememberMe / autoLogin / token(JWT HS256)
JWT payload（脱敏后）: {"create":1793792115,"id":"********","login":"1**********"}
索引记录 : 0001021f… = pwd+account 索引；00010220… = token(hex)+account 索引
```

### 3.6 其它存储文件

| 文件 | 事实 |
|---|---|
| `databases\Databases.db` | SQLite，仅 `meta(mmap_status=-1, version=2, last_compatible_version=1)`，无 WebSQL 库登记（`work/data/storage/databases_db.json`） |
| `Network Persistent State` | JSON：`http_server_properties.servers` 记录 `cdnfei.ets100.com / static.geetest.com / static.ets100.com / cdnfeis.ets100.com / www.aliyun.com / cloud.tencent.com` 支持 SPDY(HTTP/2)；`network_qualities` 记录 4G/Offline |
| `Visited Links` | magic `VLnk`(0x6B6E4C56) v3，**URL 哈希**，不存明文，无法还原 |
| `DevToolsActivePort` | `10086` + `/devtools/browser/e6be91f9-1267-4192-a618-7f125397b86f`（CEF 远程调试已开启过；端口取 `app.json` 的 `suspensionBallPort=40001` 之外的值） |
| `QuotaManager` / `Reporting and NEL` | SQLite，配额/NEL 策略，无业务数据 |

### 3.7 HTTP Cache / Code Cache

- `Cache\index` 262 KB（Chromium Simple Cache 的 hash 索引），`data_0..3` 5.7 MB（索引桶/元数据），`f_000001..f_000030` **48 个**内容块 11.57 MB：主文档、Vite JS bundle（`f_000002` 3.48 MB，含加密包口令算法）、图片等；`f_000014/f_000012` 为业务页面 chunk（E卡登录、手机号绑定等）。
- `Code Cache\js\` **99 个脚本**编译缓存 + `index/index-dir/the-real-index`；`Code Cache\wasm\` 2 个（业务未使用 wasm）。
- `Cache\data_3` 内可直接读到前端 SDK 明文（`cef.message.*` 桥、`HttpHelper.download/downloadresource/isrpkexist`、`FileHelper.readrpk_kqlx` 等），是本项目理解 CEF 桥最直接的证据之一。

---

## 4. 资源包（`temp\resources`）

### 4.1 清单

| 包 | 大小 | 内容 | 加密 |
|---|---|---|---|
| `common.zip` | 2,903,820 B | **276 文件**：根 23 文件（22 个 html + 无扩展名 `config`）、`css\`27、`images\`157（png148/gif9）、`js\`55、`material\`13（10 mp3、2 wav、`word\worddict_data.json` 2,096,868 B） | 否 |
| `clear_cache.zip` | 915 B | `clean_cache.bat`（2,014 B） | 否 |
| `pc_xst_dict.zip` | 1,948,882 B | `pc_xst_dict.json` 11,937,396 B（**28,323 条**单词对象） | 否 |
| `747716\content_811841..811848.zip` | 27,765–912,161 B | 8 个题目资源包 | **是（ZipCrypto）** |
| `747716\template_686.zip` | 890,071 B | 套卷模板：`ctrl.json` 30,664 B、`res.json` 3,791 B、`info.json` 2,175 B、`material\1_desc..5_desc/Di/start/stop.mp3` | 否 |
| `747725\content_811857..811864.zip` + `template_686.zip` | 同上规模 | 第 2 套套卷 | content 加密 / template 否 |
| `747726\content_811865..811872.zip` + `template_686.zip` | 同上规模 | 第 3 套套卷 | 同上 |

三个 `template_686.zip` 内容完全一致（SHA-256 `A252C1C9…AFC18`），说明模板按 **template_id** 缓存、多套套卷共用。

`pc_xst_dict.json` 单条结构（`work/data/resources_dict_pc_xst_full.json`）：

```json
{"Word":"analyse","Trans":"v.分析，剖析\n…","Spell_EN":"英 [/ˈænəl-aɪz/]","Spell_US":"美 [/ˈænəlaɪz/]",
 "AudioUrl_EN":"http://bjbdn.openstorage.cn/v1/aiedata/aiedata_public/ldoce5_BrE_analyse0205.mp3",
 "AudioUrl_US":"http://bjbdn.openstorage.cn/v1/aiedata/aiedata_public/ldoce5_NAmE_laadanalyse.mp3"}
```
与 IndexedDB `wordDict`（按含 `AudioUrl_EN` 计 28,322 条）规模一致，推断为同一词表的包内源文件/前端缓存两份。

### 4.2 content 包的 ZipCrypto 加密与口令还原（关键发现）

现象：`7z l` 显示 `Encrypted = +`、`Method = ZipCrypto Deflate`；`7z x` 会要求口令，并在归档尾部报告 `Tail Size = 336`。

口令算法（证据：HTTP 缓存 `f_000002` 偏移 ≈0xD93EA 的 Vite 打包 JS；可复现脚本见 `work/data/_scripts/extract_content.py`）：

```js
function getPasswordFromPackage(buf) {                    // 336 字节口令块
  const t = parsePasswordInfo(buf.slice(buf.byteLength - 336));
  if (t.company !== "MSTCHINA" || t.productid !== "EPLAT") return "";
  const n = md5(t.pwd).toUpperCase();
  return n + md5(n).toUpperCase();                        // 64 位 hex 口令
}
parsePasswordInfo = (b) => ({ company: b[0:8], version: b[8:16], pwd: b[16:144],
  productid: b[144:176], keySerialNum: b[176:304], thisAnswer: b[304:336] }); // 均 UTF-8、去 \0、trim
// 另有 getPasswordFromResourcePackage(): 取包尾 40 字节，decode 后 substring(8) 再做两级 MD5（用于 40 字节尾的旧/别种包）
```

实测 `content_811841.zip` 尾部：`MSTCHINA` / `1.0` / pwd 字段(128 B) / `EPLAT` / keySerialNum(128 B) / thisAnswer(32 B)；按上式得到 64 位大写 hex 口令，`7z t -p<口令>` 全 4 文件 CRC 通过，24 个 content 包全部解包成功（`work/data/extracted/content/*`）。

> 注意：`common.zip`、`clear_cache.zip`、`pc_xst_dict.zip`、`template_686.zip` **不是** ZipCrypto 加密，也无 MSTCHINA 尾块——权限差异来自服务端打包方式，不是本地状态。

### 4.3 content 包结构（`content_<stid>.zip`）

| 文件 | 必选 | 说明 |
|---|---|---|
| `content.json` | 是 | 题目主数据：`structure_type` + `info{…}` |
| `content2.json` | 是 | 与 content.json 同构；**仅对话题 `ask` 字段不同**：content 用 `ets_th1 <p>…</p>`（引擎/音频 id 对齐），content2 用 `1. <p>…</p>`（学生端展示序号） |
| `info.json` | 是 | 智能展示字段表：`[{code_id, code_value, code_class, code_type}]`，供 `ctrl.json` 的 `jsparam` 引用 |
| `material\*` | 视题型 | `content.mp3`（朗读/图片题示范音）、`content.jpg`（图片题图片）、`ques1..5askaudio.mp3`（交际应答 5 题问句音频） |

`content.json` 的三类 `structure_type` 与字段（实测 24 个包覆盖）：

| structure_type | `info` 字段 | 说明 | info.json 的 code_id |
|---|---|---|---|
| `collector.read`（15/24） | `value`(原文)、`analyze`(解析)、`ai`、`audio`(示范音频名)、`image`、`video`、`translate`、`symbol`、`stid` | 朗读题（词组/句子） | `value`、`jiexi` |
| `collector.dialogue`（3/24） | `question[]{std[]{value,ai,audio}, ref, ask, answer, askaudio, aswaudio, xh, analyze, sucai, keywords, role}`、`image`、`video`、`value`、`stid`、`audio` | 交际应答（1 包 5 题，标准答案集合在 `std`） | `askall`、`ask1..ask5` |
| `collector.picture`（6/24） | `std[]{value,ai,audio}`（参考范文）、`ref`、`keypoint`、`image`、`value`(题干)、`analyze`、`topic`、`audio`、`stid` | 复述/表达（图片题） | `value`、`pic1`（图片） |

示例（content_811841，朗读题，脱敏后）：

```json
{"structure_type":"collector.read",
 "info":{"translate":"","image":"","video":"","value":"excuse me",
         "ai":"","analyze":"1. excuse me</br>2. a good reason</br>3. improve your handwriting",
         "stid":"811841","symbol":"","audio":"content.mp3"}}
```

### 4.4 template 包结构（`template_<templateId>.zip`）

| 文件 | 大小 | 结构 |
|---|---|---|
| `info.json` | 2,175 B | 模板级文案表 `[{code_id:"des503_1"…, code_value:"I. Read aloud朗读（5小题，共2.5分）<br>Section 1", code_class, code_type:"txt"}]`，10 条（des503_1/2、des504_1/2、des505_1/2、des507_1/2、des653_1/2） |
| `res.json` | 3,791 B | 套卷能力结构（见下） |
| `ctrl.json` | 30,664 B | 播放/交互脚本 **76 步**（见下） |
| `material\*.mp3` | 1.27 MB | 模板音频：`1_desc..5_desc.mp3`（指令）、`Di.mp3`（提示音）、`start.mp3`/`stop.mp3`（录音起止提示） |

**res.json 字段表**（`work/data/resources_template_analysis.json`）：

| 路径 | 字段 | 示例/枚举 |
|---|---|---|
| 顶层 | `set_score`、`set_intro`、`exam_type_list[]` | `"10"`、`""` |
| exam_type_list[] | `exam_type_order`、`exam_type_name`、`exam_type_intro`、`exam_type_collect`、`exam_type_score`、`exam_type_count`、`exam_list[]` | 1 朗读词组 / 2 朗读句子 / 3 交际应答 / 4 复述 / 5 表达；`collector.read/dialogue/picture`；分值 1.5/1/2.5/2.5/2.5 |
| exam_list[] | `exam_order`、`exam_id`、`exam_info[]`、`exam_score`、`exam_count`、`question_list[]` | `{{st1}}`…`{{st8}}` 槽位占位；`exam_info[{id:"ets_th1",value:"1."}]` |
| question_list[] | `question_order`、`question_count`、`question_score`、`evaluation_type`、`engine_area`、`engine_type` | `read_sentence` / `simple_expression_ufi` / `topic`；`shanghai`；`Simulation` |

**ctrl.json 字段表**（76 个对象，字段固定 16 个）：

| 字段 | 含义 | 观测值 |
|---|---|---|
| `order` | 播放/执行顺序 | `1..76` |
| `subid` | 槽位+题内序号 | `{{st1}}_1`、`{{st6}}_0`…`{{st8}}_1` |
| `dirtype` | 文件来源目录 | `templet`(29)、`content`(7)、``(40) |
| `filetype` | 步骤类型 | `file.audio`(36)、`view.html`(19)、`action.record`(12)、`wait`(9) |
| `filename` | 文件名/录音名 | `begin.html`/`word.html`/`word1.html`、`1_desc.mp3`、`start.mp3`、`ques1askaudio.mp3`、`{{stN}}_k`(录音槽) |
| `fileparams` | 文件参数 | 全空 |
| `playtime` | 时长（秒） | `wait`(10/15/60…)、`action.record`(5/8/60…) |
| `playparams` | 播放参数 | 全空 |
| `playhint` | 提示文案 | `听指令/听语音/请准备/开始录音/开始录音.../正在录音/停止录音/提示音/阅读题目/准备回答` |
| `synchro` | 同步标记 | 全空 |
| `model_pc` / `model_mobile` | 视图模型 | `{"htmlmodel":"templet_common","jsparam":[{"classname","source","code_id"}]}`；classname ∈ `title/subtitle/content/content_symbol/content_img`；source ∈ `templet`(引用模板 info.json) / `content`(引用题目 info.json，如 `value/jiexi/analyze/ask1..5/pic1`)；html 模型仅 `templet_common` |
| `Extendedfield1..4` | 扩展字段 | 全空 |

### 4.5 id 命名规则与包间关系

- 目录名 `<set_id>`（本快照 3 个：**747716 / 747725 / 747726**）= 套卷/作业的 `set_id`（CEF 日志 URL `#/mockExamDetail?set_id=747726&resource_id=239&homework_id=110271129&first_column_id=1`）；与作业 id 的对应由 IndexedDB 记录给出：

| set_id | homework_id | 题目资源 stid | 模板 |
|---|---|---|---|
| 747716 | 111035707 | 811841–811848 | 686 |
| 747725 | 111035665 | 811857–811864 | 686 |
| 747726 | 110271129 | 811865–811872 | 686 |

- `content_<stid>.zip`：`stid` 为**题目/子题资源 id**（6 位，全局递增），与 `content.json.info.stid` **完全一致**（24/24 校验通过）。
- `template_<templateId>.zip`：`templateId=686` 为**套卷模板 id**，同一模板跨套卷复用（三份文件 hash 相同）。
- 关系：`res.json` 用 `{{st1}}..{{st8}}` 定义 8 个槽位（5 朗读 + 1 交际应答 + 2 图片题）→ 按 `stid` 升序把 8 个 content 包依次绑定 `st1..st8`（推断）；`ctrl.json` 的 `subid={{stN}}_k` 驱动每个槽位的播放/录音步骤；`ctrl.json` 的 `jsparam(code_id)` 或在模板 `info.json`（`des*`）或在该槽位 content 包 `info.json`（`value/jiexi/ask1../pic1/analyze`）中取值。
  证据：每套 8 包结构类型顺序 = `read,read,read,read,read,dialogue,picture,picture`，与 `res.json` 的 `exam_type_collect` 顺序及 `ctrl.json` 的 subid 计数（st1 8 步、st2 4、st3 4、st4 8、st5 4、st6_0..5 每 6、st7 9、st8 7）一致。

### 4.6 下载来源与结果（`work/data/logs/resources_download_table.json`、`resources_downloads.json`）

两类 URL：

| 类型 | URL 规则 | 例 |
|---|---|---|
| 题目/模板包（内容中台） | `https://cdnsubject.ets100.com/made/<md5>.zip` | `content_811857.zip` ← `…/made/05a5d4b0ecc03c857b7911b59015be92.zip`（27,820 B） |
| 公共资源包（版本化 CDN） | `https://cdnfeis.ets100.com/<YYYYMMDDHHMM>/<hash>/file/<md5>.zip` | `common.zip` ← `…/202611041935/fa6ff66b…/file/ebcef9b0…zip`；`pc_xst_dict.zip` ← `…/202610281905/…/file/c3f11348…zip` |

24 个 content 包 + 3 个 template 的 `(本地文件, size, 源 URL)` 全部记录在 `resources_download_table.json`；下载结果均为 `下载成功 → 解压成功`（ETSShell 侧先 `OnGetMd5` 探测缺失，再 `httphelper download`，最后 `sevenzip unzip`；日志中含 `下载前的解压本地旧包解压成功` 的覆盖安装逻辑）。

---

## 5. soundfiles：录音与评测结果

### 5.1 命名与三件套

```
public_<32位hex>_<13位Unix毫秒>.mp3        # 学生录音（上传/回放用）
public_<同上>.mp3.spx                      # 同录音的压缩副本（.spx 后缀挂在 .mp3 后）
public_<同上>.xml                          # 讯飞评测引擎返回的评分结果
```
共 **36 组**（每组 3 文件）。`public_` 前缀 + 32 hex 推测为录音资源 UUID/命名空间，13 位毫秒为生成时间（如 `1793186570347` ≈ 2026-10-28 18:56 +08）；同一组的三个文件前缀与时间戳完全相同，可直接配对。

### 5.2 mp3 / spx 二进制事实（`work/data/soundfiles/audio_pair_analysis.json`）

| 项 | mp3 | spx |
|---|---|---|
| 头部 | `FF F3 38 C4…`（MPEG 音频帧头） | 高熵随机字节，**无 OggS/Speex/RIFF 等容器魔数** |
| ffmpeg 识别 | `mp3, 16000 Hz, mono, 24 kb/s`（如 15,228 B ≈ 5.08 s） | `Invalid data found`（不支持） |
| 熵 | — | ≈7.97 bit/byte（1KB 首块 7.48） |
| 大小分布 | 6,912(1) / 15,228(9) / 24,300(20) / 56,916(1) / 86,940(1) / 180,252(4) | 对应 10,070 / 26,500 / 42,400 / 98,580 / 151,580 / 318,000 |
| spx/mp3 比 | — | 1.73–1.76（除 6,912 组 1.46） |
| 推断 | 16 kHz 单声道 24 kbps 的 MP3 上传件 | 约 42 kbps 的 **Speex 宽带高码率裸流**（Speex WB q10≈42 kbps 与尺寸/时长吻合），按帧裸拼接无容器；也可能是加密副本——**未确认（缺口）** |

### 5.3 xml 评测结果结构（36 个文件，`work/data/soundfiles/xml_parse.json`）

统一外壳 + 三类评测元素：

```
<?xml version="1.0" encoding="UTF-8"?>
<xml_result>
  <read_sentence lan="en" region="shanghai" region_version="1" type="study"
                 version="V4.1.0R6.81.20.38M5.81.38.0">
    <rec_paper>
      <read_chapter …> <sentence …> <word …> <syll …> <phone …/> </syll></word></sentence></read_chapter>
    </rec_paper>
  </read_sentence>
</xml_result>
```

- 36 个样本：`read_sentence` 15、`simple_expression_ufi` 15、`topic` 6；`type="study"`、`lan="en"`、`region="shanghai"`、`region_version="1"`、引擎版本 `V4.1.0R6.81.20.38M5.81.38.0`（全部一致）。
- 结构路径：
  - `read_sentence`：`read_sentence/rec_paper/read_chapter/sentence/word/syll/phone`
  - `simple_expression_ufi`：`simple_expression_ufi/rec_paper/rec_paper/sentence/word`（顶层 rec_paper 下再嵌一层 rec_paper 表示“整段录音”结果）
  - `topic`：`topic/rec_paper/…`（含 `keypoints`/`speeking_speed`/`word_hit_of_each_kw`）

**字段语义（按标签）**：

| 标签 | 关键属性 | 含义 |
|---|---|---|
| `read_sentence`/`simple_expression_ufi`/`topic` | `lan/region/region_version/type/version` | 语种、评测区域（上海考区）、区域版本、业务类型（study=练习）、引擎版本 |
| `read_chapter` | `accuracy_score, fluency_score, integrity_score, standard_score, total_score, word_count, words_per_min, beg_pos, end_pos, is_rejected, reject_type, except_info, score_pattern` | 整段朗读总分项（0–5 分制，`score_pattern=strict`） |
| `rec_paper` | 同上 + `phone_score, keywords, keypoints, speeking_speed, word_hit_of_each_kw` | 交际应答/话题题整段结果：`keywords` 为“|”分隔的可接受答案，`is_rejected/reject_type/except_info` 为拒识信息（如 `except_info=28676`、`reject_type=32`） |
| `sentence` | `index, content, beg_pos, end_pos, accuracy_score, fluency_score, standard_score, total_score, word_count` | 句级结果（`content` 为 ASR 识别文本） |
| `word` | `index, global_index, content, beg_pos, end_pos, dp_message, property, total_score, pitch, pitch_beg, pitch_end` | 词级：`dp_message` 发音缺陷码（0=正常），`property` 词性/标记，`pitch` 为基频轨迹（空格分隔帧值） |
| `syll` | `content, beg_pos, end_pos, syll_accent, serr_msg, syll_score` | 音节级：重音、错误码 |
| `phone` | `content, beg_pos, end_pos, dp_message, gwpp, phone_total_score` | 音素级：`gwpp` 为音素后验/置信差，`phone_total_score` 音素得分 |

**统计**（36 文件聚合）：`total_score` n=113（0–5，均值 3.44）、`accuracy_score` n=36（0–4.88）、`fluency_score` n=30（3.11–4.94）、`integrity_score` n=15（3.33–5.0）、`standard_score` n=30（2.94–4.53）、`syll_score` n=94（0–5）、`phone_total_score` n=241（0–5）；`is_rejected=true` 9/36（拒识/无效录音）。

**脱敏示例**（read_sentence，内容为 UGC 识别文本，截断）：

```xml
<read_sentence lan="en" region="shanghai" region_version="1" type="study" version="V4.1.0R6.81.20.38M5.81.38.0">
  <rec_paper>
    <read_chapter accuracy_score="2.387886" fluency_score="4.189174" integrity_score="5.000000"
      is_rejected="false" reject_type="0" score_pattern="strict" standard_score="3.593364"
      total_score="1.457507" word_count="3" words_per_min="141.732285" content="a native speaker">
      <sentence index="0" content="a native speaker" total_score="3.048820">
        <word content="native" total_score="3.309103" dp_message="0" pitch=" 118.74 …（略）">
          <syll content="n ey" syll_score="3.750100" syll_accent="1" serr_msg="1">
            <phone content="ey" phone_total_score="0.096221" gwpp="-3.950543"/>
```

### 5.4 三件套与其它数据的关系

- `xml` 中 `content` 是引擎对学生录音的识别文本/评分输入；音频本体即同名 `.mp3`。
- IndexedDB `mockExam` 记录（36 条）保存：`xml`（`C:\...\ETS\soundfiles\public_*.xml`）、`audio`（同名 `.mp3`）、`upload_file_url`（如 `https://ets60.ets100.com/ugc/evaluate/mp3/middleApp/pc/2026/10/28/33888…`）——即 **mp3 上传到评测服务、xml 为返回结果、spx 为本地压缩副本**。
- `uploadRecord`（432 条）另存本地 `filePath`（拍读/跟读等录音路径）与 `userId/type/preId/times`。
- 命名中的 36 组与 `soundfiles` 目录一一对应，`public_` 前缀表示公共（非校本私有）资源域的录音。

---

## 6. 日志：更新与资源下载

### 6.1 客户端自动更新（`temp\update\log\INFO_uLOG_*`，3 份）

- 文件格式：glog 风格 `I1104 19:22:59.143107 21152 main.cpp:36] …`；进程 `Ets.exe`；命令行 `--AppName=Ets.exe --AppTitle=讯飞E听说 --AppDirectory=C:\Program Files (x86)\ETS\ --DetectionTimeout=2000 --ForceShow=0`。
- 更新请求（`update_info.h:28`，body 为 base64）：

```json
[{"r":"client/mobile-update","params":{"client_version":5079,"os_type":"10","tag":"pc_refactor","sn":"***"}}]
```

- 更新响应（`update_info.h:29`）：

```json
[{"code":0,"msg":"","body":{"client_version":5079,"update":[{"client_version":5079,
  "client_verions_name":"5.7.9","text":"修复已知问题","force":1,
  "link":"http://cdnfeis.ets100.com/202611041922/bc1db1467a4c40622757e721b14725a9/file/878ae3da384d962f4b191902bf9c555a.exe"}]}}]
```

- 结论：更新接口 `http://api.ets100.com`（`EtsUpdate.exe` 内 `r=client/mobile-update`）；更新包装为带日期/hash 的 CDN 路径；`force=1` 时强制更新（日志 `[关闭]：不需要更新！` / `[关闭]：用户取消更新！`）；三次检查（10-28 18:56、11-04 19:22、19:34）返回同一 exe（`878ae3da…`），仅 CDN 路径 hash 随检查时间变化。

### 6.2 资源下载/解压事件（`logs\ets_2026-*.log`，PLG_STIC）

- 共解析 **594 条**事件、**30 个本地文件**（`work/data/logs/resources_downloads.json`、`resources_download_table.json`）。
- 事件序列（每个文件）：`start download file {size,url,local_file,exists}` → `下载成功（进度 n%）` → `解压成功` / `解压失败`；`exists.existZipFile=true` 时跳过重复下载；`下载前的解压本地旧包解压成功` 表示覆盖前先解旧包。
- 30 个文件覆盖：`clear_cache.zip`、`common.zip`、`pc_xst_dict.zip`、3×`template_686.zip`、24×`content_*.zip`，全部 `下载成功 + 解压成功`。
- 下载 URL 规则见 §4.6；`HttpProvider::downloadRequest::curl_easy_perform res:0` 表示成功。

### 6.3 CEF 日志（`logs\cef_2026-*.log`）

- 743 个唯一 URL；host 分布（TOP）：`statics.ets100.com` 261、`ets60.ets100.com` 109、`cdnsubject.ets100.com` 83、`dcp.changyan.com` 63、`api.ets100.com` 59、`cdnfeis.ets100.com` 32、`cdnfei.ets100.com` 26、`teacher.ets100.com` 22、`static.geetest.com` 19、`static.ets100.com` 11。
- 应用入口：`https://statics.ets100.com/ets-student-pc-web/index.html`（SPA，hash 路由），首屏 JS `…/assets/index-dc0257dd.js`；典型路由含 `#/main/home`、`#/main/homework`、`#/mockExamDetail?set_id=…&resource_id=…&homework_id=…&first_column_id=…`、`#/mockExamResult?…`、`#/auth/eCardLogin?…`。
- 埋点/日志：`https://ets-vpc-log.cn-hangzhou.log.aliyuncs.com/logstores/app-general-log`、`https://collect.ets100.com`、`https://ai-thor.eduaiplat.com/ai-thor-data-collector/feedback/batchUpload`。
- 网络探测：`http://file.fei.ets100.com/network_test`（282 次）。
- 说明：`cef_2026-11-4.log` 含二进制片段（编码判定为 latin1），提取的 URL 可能有少量噪声；`cef_2026-10-28.log` 15.7 MB / 115,950 行。

### 6.4 `7z.log`

- 记录 7z.dll 的解包动作与**原始安装路径** `C:\Program Files (x86)\ETS\temp\resources\…`；`common.zip`（276 文件）、`clear_cache.zip`、`pc_xst_dict.zip`、`template_686.zip` 与 24 个 content 包依次 `Extracting` 且 `Everything is Ok`；`content_811841.zip` 条目为 `content.json / content2.json / info.json / material\content.mp3`（4 files），与本次解包一致。
- 与 `logs\shell_*.log` 中 `sevenzip.cpp` 的 `OnUnzip begin/end` 对应，说明解包由 ETSShell 内置 sevenzip 模块（`7z.dll` 950,272 B）完成。

---

## 7. 前端持久化了什么 / 鉴权 token 在哪

| 问题 | 结论 | 证据 |
|---|---|---|
| 登录账号/密码 | `Local Storage[appLogin]`（账号+8 字节混淆 pwd+rememberPwd/autoLogin）；IndexedDB `login` 记录（account+pwd+token） | §3.3、§3.5 |
| **鉴权 token** | **IndexedDB `login` 对象存储**的 `token`（HS256 JWT，payload `create/id/login`）；IndexedDB 还有 `token+account` 索引记录 | §3.5 |
| 资源平台 token | `Local Storage[resourcePlatformStore].resourceTokenConfig.token`（RS256 JWT，504 B，`iss/sub=rop`） | §3.3 |
| OSS 上传临时凭证 | `Local Storage[appOssStore].ossEvaluateUploadConfig.upload`（STS `securityToken` 1,180 B） | §3.3 |
| Cookie 身份态 | **无**；11 条 Cookie 均为第三方（阿里云 WAF、极验、腾讯云、百度）DPAPI 密文 | §3.2 |
| 会话级数据 | sessionStorage 命名空间 map（`token`、`__aiplat_token_config`、`allEcardList`、路由等），退出即清空 | §3.4 |
| 业务缓存 | 作业/教材/系统配置（LS）、词库 28,322 词（IDB）、评测记录 36+432 条（IDB）、下载文件登记（IDB `downloadFiles`） | §3.3、§3.5 |
| 设备指纹 | `Local Storage[appConfig]`：机器名/IP/MAC/HD 序列号；埋点设备 ID | §3.3 |
| 调试通道 | `DevToolsActivePort` 暴露 CDP 端口 10086（引擎远程调试） | §3.1 |

---

## 8. 缺口与限制

1. **`SQL\ETS.db.sql` 为 0 字节**：本次快照无法直接读到 GBK 建库脚本；已用 `EtsUpdate.exe` 内嵌 SQL/流程还原（§2.3），但脚本原文（含注释、完整 DDL）缺失。
2. **Cookie 无法解密**：`LocalPrefs.json` 只有 DPAPI 包裹的 `os_crypt.encrypted_key`，其解开依赖原 Windows 用户的 DPAPI 主密钥；无 `Local State` 文件，离线不可还原明文（本机也非原始用户环境）。
3. **`.spx` 容器未确认**：无标准容器魔数、ffmpeg 不识别、熵≈7.97；按码率/尺寸推断为 Speex 宽带裸流（或加密副本），**未解码验证**。
4. **IndexedDB 精确结构部分未知**：对象存储名来自库内 `currentSchema` 记录；`dbid→存储名` 映射按值内容推断（非元数据库表），`00 00` 类键的语义未完全解码。
5. **`content2.json` 的用途**只有差异证据（对话题 `ask` 前缀 `ets_thN` → 序号），具体消费页面未在本快照中定位。
6. **大值只做摘要**：`userInfo` 378 KB、`systemConfig` 348 KB 仅输出键级摘要（已脱敏），未逐字段展开。
7. **`Visited Links` 为 URL 哈希**（VLnk v3），不可还原访问历史。
8. **更新包内容缺失**：`temp\update` 下仅日志，无 `update.dat`/`Temp/Update` 更新物；更新器下载/安装细节只能靠日志与二进制字符串。
9. **`Session Storage` 值全空**：只能确认键命名空间，无法还原会话值。
10. **`public_` 前缀/32 hex 语义**未确认（录音 UUID 或存储命名空间，推断）。

---

## 9. 产物索引（`work/data`，约 39 MB）

| 目录/文件 | 内容 |
|---|---|
| `db/ETS_db_dump.json`、`db/ETS_db_Config_rows.json` | ETS.db 全表结构+数据（含 GBK/UTF-8 校验）、Config 行语义 |
| `db/BuryPoint_db_dump.json`、`db/EtsUpdate_SQL_region.txt` | 埋点库；EtsUpdate.exe GBK 区段（SQL/更新流程证据） |
| `storage/local_storage.json`、`session_storage.json`、`indexeddb.json` | 三大 Web 存储键值/摘要（已脱敏） |
| `storage/cookies.json`、`databases_db.json`、`chromium_misc.json` | Cookie（DPAPI 密文元数据）、Databases.db、LocalPrefs/NetState/VisitedLinks/DevToolsActivePort/LOG |
| `extracted/common/` | common.zip 全解 276 文件 |
| `extracted/template_686/` | 模板包全解（含 ctrl/res/info/material） |
| `extracted/content/content_<stid>/` | 24 个 content 包解密后全解 |
| `extracted/pc_xst_dict/`、`extracted/clear_cache/`、`extracted/packages/` | 词典包、清理脚本、`packages.7z` 全解 |
| `resources_content_index.json`、`resources_template_analysis.json`、`resources_common_index.json` | content 包索引（文件/hash/structure_type/stid）、模板 res/ctrl 字段统计、common 文件清单 |
| `resources_dict_pc_xst_full.json` | `pc_xst_dict.json` 全文（28,323 词条，10.9 MB） |
| `soundfiles/xml_parse.json`、`soundfiles/audio_pair_analysis.json` | 36 个 xml 解析（结构/属性/评分统计）、mp3/spx 配对与二进制特征 |
| `logs/update_logs.json`、`logs/resources_downloads.json`、`logs/resources_download_table.json`、`logs/resource_events.json`、`logs/log_urls.json` | 更新请求/响应、594 条下载解压事件、30 文件下载表、资源相关日志行、743 URL 统计（均脱敏） |
| `_scripts/` | 全部解析脚本（含纯 Python LevelDB 读取器、ZipCrypto 口令复现、日志/XML/DB 解析），可复跑 |

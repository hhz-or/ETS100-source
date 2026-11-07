# 插件实现与构建说明（plugins_build.md）

> 范围：`native-replica/plugins/` 下 7 个插件 DLL 的实现说明、action 覆盖、编译与验证结果。
> ABI 依据 `shared/stic_plugin.h`，接口契约依据 `CONTRACT.md` §3/§6。
> 最后验证时间：2026-11-07（MSVC 14.51.36231 / CMake 4.4.4 / Ninja 1.13.2）。

## 1. 文件清单

| 插件 | 源文件 | 产物（CMake 当前命名） |
|---|---|---|
| EtsHelper | `plugins/etshelper/etshelper.cpp` | `bin/plugins/EtsHelper/etshelper.dll` |
| FileHelper | `plugins/filehelper/filehelper.cpp` | `bin/plugins/FileHelper/filehelper.dll` |
| HttpHelper | `plugins/httphelper/httphelper.cpp` | `bin/plugins/HttpHelper/httphelper.dll` |
| SQLitePln | `plugins/sqlitepln/sqlitepln.cpp`（链接 `third_party/sqlite3.c`） | `bin/plugins/SQLitePln/sqlitepln.dll` |
| ShellHelper | `plugins/shellhelper/shellhelper.cpp` | `bin/plugins/ShellHelper/shellhelper.dll` |
| SevenZip | `plugins/sevenzip/sevenzip.cpp`（链接 `third_party/miniz.c`） | `bin/plugins/SevenZip/sevenzip.dll` |
| SysConfig | `plugins/sysconfig/sysconfig.cpp` | `bin/plugins/SysConfig/sysconfig.dll` |

> 注意：任务开始后 Lead 调整过 `CMakeLists.txt`：插件 `OUTPUT_NAME`/输出目录已改为小写
> （`etshelper`、`filehelper`…），因此 DLL 文件名是小写；目标目录名沿用首次生成的
> `EtsHelper` 等（Windows 大小写不敏感，两种写法等价）。壳加载时请按当前 CMake 命名
> （`<小写>.dll`）并按 pluginKey 大小写不敏感匹配。旧命名残留 `etshelder.dll` 已删除。

## 2. 通用 ABI 实现约定

每个 DLL 都实现 4 个导出（`extern "C" __declspec(dllexport)`，cdecl，未修饰名）：

| 导出 | 行为 |
|---|---|
| `PlnInitiliaze(PlnHost*)` | 保存 `ets::g_host`；把 `AppDir/DataDir/CacheDir/HomeUrl` 复制为 `std::string`（不持有宿主指针）；打印初始化日志 |
| `PlnSetParam(const char* key, void* fn)` | 保存 `"LOG"`/`"WLOG"` 为 `PLN_LOG`；其它 key 忽略 |
| `PlnOnProcessMessage(action,args,cb,uid)` | `nlohmann::json` 解析 args（空串/`"{}"` 均可，非对象按 `{}` 处理）→ 分发 → `cb(uid, result.dump())` **恰好一次**；异常/解析失败统一 `{"code":-1,"msg":"..."}` |
| `PlnUnInitialize()` | 释放连接/清空回调与 `g_host`（sqlite 会关闭数据库） |

- 全部字符串 UTF-8；中文日志/字段依赖 `CMakeLists.txt` 的 `/utf-8` 编译选项。
- 未知 action 一律返回 `{"code":-2,"msg":"not implemented"}`（符合 CONTRACT §10，不伪造）。
- args 取值容错：`"time"`、`"volume"` 等既接受字符串也接受 JSON 数字。
- 潜在阻塞操作（HTTP、解压、遍历目录、SQLite）按契约由壳在 worker 线程调用；
  sqlite 内部有 `std::mutex`，sevenzip CRC 表用 `std::call_once` 初始化。

## 3. 逐插件 action 覆盖

### 3.1 EtsHelper（`etshelper.cpp`）

| action | 状态 | 返回 |
|---|---|---|
| `encode_api_body_v2` | ✅ | `{"pid":"pcWin","key_id":"202608","sign":MD5("pcWin"+time+body+KEY_V2),"sign_version":"2"}` |
| `encode_api_body`（别名 `encode_api_body_v1`） | ✅ | JSON 字符串 `MD5("grlx"+time+body+KEY_V1)`（32 位小写 hex） |
| `encode_api_resp_v2` | ✅ | `{"pid","key_id","sign":MD5("pcWin"+response+KEY_V2+"test"),"sign_version":"2"}` |
| `aes_ecb_encrypt` | ✅ | `{"b64":"<AES-128-ECB/PKCS7，key=f05323cb91d422b2>"}` |
| `aes_ecb_decrypt` | ✅ | `{"plain":"..."}`（失败返回 `code:-1`） |
| `get_appdata_path` | ✅ | JSON 字符串，如 `"C:\\Users\\<u>\\AppData\\Roaming"`（`GetEnvironmentVariableW("APPDATA")`） |
| `log_data` | ✅ | `{"ok":true}`，并写宿主日志 |
| `check_update` | ✅（桩） | `{"rncode":0,"rnmsg":"no newer version"}` |
| 其它 | ⛔ | not implemented |

密钥与契约一致：`KEY_V2=94cfbda3fbfef02b93693f8bc153be82`、`KEY_V1=355ffbe95ccf4e9535a110170b445ab8`、`k_serves=f05323cb91d422b2`。
签名/加密全部走 `shared/common.cpp` 的 BCrypt 实现（MD5/AES-128-ECB+PKCS7/Base64）。

### 3.2 FileHelper（`filehelper.cpp`）

| action | 状态 | 说明/返回 |
|---|---|---|
| `readfile` | ✅ | `{"content":"<UTF-8 text>"}` |
| `readbinaryfile` / `getbase64` | ✅ | `{"base64":"..."}` |
| `writefile` | ✅ | `{"code":0}`，自动建父目录 |
| `writefilewithbinary` | ✅ | `{"code":0}`，base64 解码后写入 |
| `existfileorfolder` | ✅ | `{"result":true,"size":N}`（目录 size=0；不存在 result=false） |
| `deletefileordirectory` | ✅ | `{"code":0}`（`remove_all`，不存在视为成功） |
| `createfolder` | ✅ | `{"code":0}` |
| `copyfileordirectory` | ✅ | `{"code":0}`，目录递归复制并覆盖 |
| `removefiletootherpath` | ✅ | `{"code":0}`，先 rename，失败降级 copy+delete |
| `getmd5` | ✅ | `{"md5":"<32 hex>"}`（文件字节 MD5） |
| `getfoledersize` | ✅ | `{"errorCode":0,"errorMsg":"get dir size ok","size":N}`（递归求和，跳过无权限项） |
| 对话框类等其它 | ⛔ | not implemented |

实现：`std::filesystem` + `shared/common.cpp` 的 UTF-8↔宽字符路径转换。

### 3.3 HttpHelper（`httphelper.cpp`，WinHTTP）

| action | 状态 | 说明/返回 |
|---|---|---|
| `request` | ✅ | 入参 `{url,method(GET/POST/PUT…),body,headers,timeoutMs}`；返回 `{"status":N,"body":"<UTF-8 text>","headers":{...}}` |
| `download` | ✅ | `{url,filePath}` → `{"code":0,"filePath","size"}`；流式写盘，非 2xx 返回 `code:-1` |
| `upload`/`downloadresource`/`downloadsdk`/`monitornetspeed`/`isrpkexist`/`stopdownload` | ⛔ | `{"code":-2,"msg":"not implemented"}` |

细节：
- `WinHttpCrackUrl` 解析 http/https（`WINHTTP_FLAG_SECURE`，正常校验证书）；自动跟随 302（`REDIRECT_POLICY_ALWAYS`）；
- `timeoutMs` 同时设 resolve/connect/send/receive（默认 30000；download 固定 60000）；
- 未显式提供 `Content-Type` 且有 body 时自动加 `application/json; charset=utf-8`；不手动写 `Content-Length`；
- 响应头：原始 `WINHTTP_QUERY_RAW_HEADERS_CRLF` 解析为对象，重复头用 `", "` 合并，同时给出原始大小写与全小写别名；
- 文本解码：`Content-Type` 声明 gbk/gb2312/gb18030 时按 CP936 转 UTF-8，否则校验 UTF-8，非法则按 CP_ACP 兜底（避免 JSON 序列化失败）。

### 3.4 SQLitePln（`sqlitepln.cpp` + `third_party/sqlite3.c`）

| action | 状态 | 返回 |
|---|---|---|
| `connect` | ✅ | `{"code":0}`（READWRITE\|CREATE\|FULLMUTEX，自动创建 dbPath 父目录，busy_timeout=5s，best-effort WAL） |
| `execQuery` | ✅ | `{"code":0,"rows":[{...}]}`；按列名建对象；INTEGER/FLOAT/TEXT/NULL 直出，BLOB → base64 |
| `execDML` | ✅ | `{"code":0,"changes":N,"lastInsertRowid":N}` |
| `disconnect` | ✅ | `{"code":0}` |
| 其它 | ⛔ | not implemented |

- `params` 支持 JSON 数组（按位置 bind，含 null/bool/int/uint/float/string）与 JSON 对象（`:name`/`$name`/`@name` 命名 bind）。
- 简单实现：进程内保留“最近一个 dbPath”的连接；dbPath 变化时先关旧连接再打开（多个库交替使用时每次重开，功能正确、无缓存）。
- 单语句 prepare/step；`execQuery` 只支持首条语句（多语句请拆分调用）。
- 用 `json::error_handler_t::replace` 序列化，避免非法 UTF-8 的 TEXT 让整次回调抛异常。

### 3.5 ShellHelper（`shellhelper.cpp`）

| action | 状态 | 返回/说明 |
|---|---|---|
| `getpcinfo` | ✅ | 字段子集：`AppTitle/ClientType/CopyRight/Name/computername/OsBit/SystemVersion/ProcessName/DwNum/HDD/IP2/Version/Memory`（`RtlGetVersion` 取真实版本；HDD/Memory 单位为 GB；`IP2` 优先 Ethernet/Wi-Fi 适配器，避免 VPN/TUN 地址） |
| `getconfig` | ✅ | `{"appDir","dataDir","cacheDir","homeUrl","version"}`（来自 PlnHost） |
| `getvolume` | ✅ | `{"volume":0-100,"code":0}`（`waveOutGetVolume`，取左声道） |
| `setvolume` | ✅ | `{"volume":N,"code":0}`（`waveOutSetVolume` 双声道；入参 clamp 0-100） |
| `checkadapter` | ✅ | `{"rncode":1,"rnmsg":"网卡正常.","count":N}` / 无网卡 `rncode:0,"网卡异常."`（`GetAdaptersAddresses` 过滤 loopback/未启用） |
| `getuniqueid` | ✅ | `{"id":"<sha1 hex>","code":0}`；`HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid` 的 SHA1；缺失时用 计算机名+系统盘卷序列号+用户名 兜底 |
| `startprocess` | ✅ | `{"code":0,"pids":[...]}`；支持 `{"process_list":[路径|{path/exePath/processPath/exe/name}]}` 或单个 `path/name`；`CreateProcessW` + `CREATE_NO_WINDOW` |
| `stopprocess` | ✅ | `{"code":0,"failed":N}`；数字按 `/PID`，否则取 basename 走 `taskkill /F /IM`（退出码 128=进程不存在视为成功） |
| `processexist` | ✅ | `{"result":true/false}`；`CreateToolhelp32Snapshot` 匹配 basename（自动补 `.exe`，大小写不敏感） |
| `cmd`/`gettoken`/`initActAuth` 等 | ⛔ | not implemented |

链接：`#pragma comment(lib, "winmm.lib"/"iphlpapi.lib"/"advapi32.lib")`；`winsock2.h` 必须在
`windows.h` 之前包含（否则 `IP_ADAPTER_ADDRESSES` 因 `_WINSOCK2API_` 未定义而不可见）。

### 3.6 SevenZip（`sevenzip.cpp` + `third_party/miniz.c`）

| action | 状态 | 返回 |
|---|---|---|
| `unzip` | ✅ | `{"code":0,"files":N}`（`{zipPath,outDir}`；自动建目录；zip-slip 防护：拒绝绝对路径/盘符/`..`；UTF-8 文件名用宽字符路径写盘） |
| `zip` / `test` | ⛔ | not implemented |

**口令恢复（docs/06_data.md §4.2）**：取文件尾部 336 B 块
`company[0:8] / version[8:16] / pwd[16:144] / productid[144:176] / keySerialNum[176:304] / thisAnswer[304:336]`，
校验 `MSTCHINA`+`EPLAT` 后：`pwd = upper(md5(pwdField)) + upper(md5(previous))`（64 位大写 hex）。
另附 40 B 旧式尾块启发式候选（跳过前 8 字符后做同样两级 MD5），仅在 336 B 口令不匹配时尝试。
候选口令逐个用 ZipCrypto 12 B 头校验字节 + 解压后 CRC32 双重验证，全部失败才报错。

**实现偏差（重要）**：本仓库 vendored 的 **miniz 3.0.0 没有任何口令 API**
（无 `mz_zip_reader_set_password`；`mz_zip_reader_extract_*` 遇到加密条目直接返回
`MZ_ZIP_UNSUPPORTED_ENCRYPTION`）。因此加密条目改为自行实现传统 PKWARE ZipCrypto：
CRC32 表驱动的 key0/key1/key2 流 + 12 B 加密头校验，随后对明文流用 miniz 的
`tinfl_decompress_mem_to_heap`（method=8，raw deflate）或原样拷贝（method=0），
再用 `mz_crc32` 校验；未加密归档仍走 miniz 的
`mz_zip_reader_extract_to_callback`（回调写入 `std::ofstream`，支持宽字符路径）。
归档解析（EOCD/中央目录/ZIP64 条目信息）仍由 miniz 完成。

### 3.7 SysConfig（`sysconfig.cpp`）

| action | 状态 | 返回 |
|---|---|---|
| `init` | ✅（桩） | `{"ok":true}` |
| 其它 | ⛔ | not implemented |

## 4. 编译

环境：`VsDevCmd.bat -arch=x64`，CMake 4.4.4，Ninja 1.13.2。

> 已知环境问题：任务给出的 `C:\rea_tools\pylibs\bin\cmake.exe` 是 Python 启动器 shim，
> 直接调用会 `ModuleNotFoundError: No module named 'cmake'`；
> 真正的二进制在 `C:\rea_tools\pylibs\cmake\data\bin\cmake.exe`（`build.ps1` 也是优先用它）。
> Ninja 用 `C:\rea_tools\pylibs\bin\ninja.exe` 可正常工作。

实际使用的命令：

```bat
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
"C:\rea_tools\pylibs\cmake\data\bin\cmake.exe" -S D:\ets-rea\native-replica -B C:\ets-rea-build -G Ninja ^
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM="C:\rea_tools\pylibs\bin\ninja.exe"
"C:\rea_tools\pylibs\cmake\data\bin\cmake.exe" --build C:\ets-rea-build --target ^
  plugin_etshelper plugin_filehelper plugin_httphelper plugin_sqlitepln ^
  plugin_shellhelper plugin_sevenzip plugin_sysconfig --parallel
```

结果（最终一次全量重编，先 touch 全部插件源码）：

- `configure`：成功（shell 目前是占位源码，也能 configure；仅插件 target 参与构建）。
- `build`：**EXIT=0，0 warning / 0 error**（我们自己的源文件；仅 `third_party/miniz.c` 有 1 条
  C4005 `WIN32_LEAN_AND_MEAN` 宏重定义，属第三方，可忽略）。
- 产物大小：etshelper 141,312 B；filehelper 183,808 B；httphelper 173,568 B；
  sqlitepln 1,248,256 B；shellhelper 165,888 B；sevenzip 195,072 B；sysconfig 118,784 B。
- 4 导出自检：测试 harness 用 `GetProcAddress` 逐个取 `PlnInitiliaze/PlnSetParam/PlnOnProcessMessage/PlnUnInitialize` 全部成功。

## 5. 功能验证（实测）

测试 harness（仅构建目录，`C:\ets-rea-build\plugintest\test.cpp`，不在工程内）：`LoadLibrary`
+ 构造 `PlnHost` + 依次调用多个 action，校验“每个 action 只回调一次”。

| 插件 | 验证内容 | 结果 |
|---|---|---|
| EtsHelper | `encode_api_body_v2/encode_api_body/encode_api_resp_v2` 与 Python `hashlib.md5` 对拍；AES encrypt→decrypt 回环；`get_appdata_path/check_update/log_data/未知 action/坏 JSON` | 3 个签名与 Python 完全一致（如 `bba249ce…`/`25255aeb…`/`cf2e9107…`）；AES 回环 `hello` 一致；坏 JSON 返回 `code:-1` 且只回调 1 次 |
| FileHelper | createfolder→writefile→readfile→exist(size)→getmd5→getbase64→copy→move→getfoledersize→writefilewithbinary→readbinaryfile→delete | MD5 `5eb63bbb…`、base64 `aGVsbG8gd29ybGQ=`、目录大小 22 B 均与 Python 一致 |
| HttpHelper | 本地 Python HTTP 服务：GET、GBK 页面、302、POST+自定义头、二进制 download、404、HTTPS(example.com) | GET 200/body 正确；GBK 正确转 “网卡正常”；302 跟随到 200；POST 服务端收到 `{"a":1}`+`X-Custom`；download 256 B，MD5 `e2c865db…` 与源一致；404 → `code:-1`；HTTPS 200 |
| SQLitePln | connect→CREATE→位置 bind INSERT→命名 bind INSERT→SELECT→BLOB→坏表→disconnect | `rows` 正确（null/real/text）、named params 生效、BLOB→`AAEC/w==`、错误 `no such table`；Python 复核库内容一致 |
| ShellHelper | getpcinfo/getconfig/getvolume/setvolume(50↔100)/checkadapter/getuniqueid/startprocess/processexist | MachineGuid SHA1 `39e7dedd…` 与 Python 完全一致；音量往返正确；`whoami.exe` 启动返回 pid；`processexist` 路径/裸名均正确 |
| SevenZip | 真实 `ETS/temp/resources/**/content_*.zip` 24 个（ZipCrypto）+ `template_686.zip`（未加密） | 24/24 解密解包成功；**111 个文件与 Python `zipfile`（同口令）逐字节 MD5 全部一致**；`template_686.zip` 11 个文件一致 |
| SysConfig | init/未知 action | `{"ok":true}` / `code:-2` |

## 6. 未实现项汇总（显式返回 `{"code":-2,"msg":"not implemented"}`）

- HttpHelper：`upload`、`downloadresource`、`downloadsdk`、`monitornetspeed`、`isrpkexist`、`stopdownload`（无下载任务句柄/断点续传）。
- FileHelper：系统文件对话框、文件关联等契约外 action。
- SQLitePln：事务/批量脚本 API、跨多库并发连接池、加密库。
- ShellHelper：`cmd`、`gettoken`、`initActAuth`、`setproxy` 等。
- SevenZip：`zip`（压缩）、`test`（完整性测试 action）。
- SysConfig：仅 `init` 桩。
- EtsHelper：`check_update` 为固定桩（无真实升级服务）。

## 7. 给 Lead 的注意事项（不改 shell/shared 的前提下）

1. **DLL 命名**：当前 `CMakeLists.txt` 输出 `etshelper.dll` 等小写名（目录 `EtsHelper` 是旧目录名，大小写不敏感）。
   壳的 pluginKey→路径映射请使用小写文件名或做大小写不敏感探测；仓库里旧的 `etshelder.dll` 已从构建目录删除。
2. **回调线程**：插件可能被多个 worker 并发调用（sqlite 已加锁）；HTTP/解压在 1–3 s 级，
   建议壳在 worker 线程调用，不要阻塞 UI 线程。
3. **PlnHost 生命周期**：插件把 `AppDir/DataDir/CacheDir/HomeUrl` 复制为 `std::string`，
   但 `g_host` 指针仍指向壳结构；请保证 `PlnHost` 及 `Log/WLog` 回调在 DLL 卸载前有效。
4. **调用约定**：4 个导出为 cdecl、未修饰名；`PLN_CALLBACK` 为 `__stdcall`，与 `stic_plugin.h` 一致。
5. **shared 无需改动**；若后续希望减少各插件重复的 `ArgStr`/UTF-8 辅助，可考虑把
   `ArgStr(json&,key,def)`、`IsValidUtf8` 等下沉到 `shared/common.h`（本次未改，避免越界）。
6. `/utf-8` 编译选项是中文常量（如 “网卡正常.”、AppTitle “E听说”）正确编码的前提，请勿移除。
7. 建议构建脚本修正 cmake 路径（用 `pylibs\cmake\data\bin\cmake.exe`），否则一键构建会在 configure 阶段失败。

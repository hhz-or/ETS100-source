# 09 原生反编译摘录与解读（Ghidra 12.1.4）

> 目的：把"原生层到底做了什么"从汇编级证据落到可读结论。
> 工具：Ghidra 12.1.4（headless `analyzeHeadless`）+ JDK 21+；脚本 `work/ghidra_scripts/DumpDecomp.java`（导出 `decompiled.c` / `functions.tsv` / `strings.tsv`）。
> 产物：`work/ghidra_out/<binary>/`。
> 说明：反编译输出不是原始源码；函数名多为 `FUN_xxxx`，变量名为反编译器生成。结论均标注【观察】/【推断】。

---

## 1. 覆盖情况

| 二进制 | 规模 | 函数数（反编译数） | 产物 |
|---|---|---|---|
| `plugins\etshelper\etshelper.pln` | 497 KB | 2,669（1,801） | `work/ghidra_out/etshelper.pln/` |
| `plugins\appcontroller\appcontroller.pln` | 552 KB | 2,862（2,030） | `work/ghidra_out/appcontroller.pln/` |
| `plugins\filehelper\filehelper.pln` | 674 KB | 4,071（2,738） | `work/ghidra_out/filehelper.pln/` |
| `plugins\window_control\window_control.pln` | 437 KB | 2,489（1,630） | `work/ghidra_out/window_control.pln/` |
| `plugins\sqlitepln\sqlitepln.pln` | 345 KB | 2,078（1,196） | `work/ghidra_out/sqlitepln.pln/` |
| `plugins\sevenzip\sevenzip.pln` | 467 KB | 3,243（1,890） | `work/ghidra_out/sevenzip.pln/` |
| `plugins\shellhelper\shellhelper.pln` | 2.12 MB | 12,320（8,279） | `work/ghidra_out/shellhelper.pln/` |
| `ETSShell.exe` | 2.19 MB | **9,109（5,966）** | `work/ghidra_out/ETSShell.exe/`（`decompiled.c` 7.3 MB） |
| `EtsUpdate.exe` | 1.98 MB | **9,646（7,611）** | `work/ghidra_out/EtsUpdate.exe/`（`decompiled.c` 8.7 MB） |

> 合计 **9 个二进制、48,487 个函数、31,141 个函数已反编译**（约 41 MB C 伪代码）。
> 未反编译：`httphelper.pln`（1.73 MB，OpenSSL 静态库占大头，结论已由导入表/字符串/日志覆盖）、`soundhelper.pln`（3.18 MB）、`Ets.exe`、`bugreport.exe`——Ghidra 工具链为临时安装，交付时已清理，如需补全可按 §7 复跑。

统一编译特征：32 位 MSVC（VS2012/2015 运行库混用）、`/GS` 栈保护（`__security_check_cookie`）、异常处理 `__CxxThrowException`、STL/MFC、无壳；字符串里保留完整源码路径（`D:\code\STIC\stic-misc\stic-pro_ets\...`）。

---

## 2. `etshelper.pln` —— API 签名与消息分发

### 2.1 导出与 ABI【观察】

```
PlnInitiliaze        (厂商拼写，原样)
PlnOnProcessMessage
PlnSetParam
PlnUnInitialize
```

`PlnOnProcessMessage`（`0x1000aa70`）是唯一入口：读入 `actionKey` + JSON 参数，做**线性字符串比较**后分派，例如：

```
"dub_merge" / "get_appdata_path" / "log_data" / "check_ets_server"
"check_update" / "check_update_force" / "test_crash"
"encode_api_body" / "encode_api_resp" / "encode_api_body_v2" / "encode_api_resp_v2"
```

每个分支构造结果 JSON（v2 的 `pid="pcWin"`、v1 的 `pid="grlx"`），再通过回调把字符串回传前端。

### 2.2 签名链路【观察 → 已验证】

见 [08_signature.md](08_signature.md)：

- `OnEncodeAPIBody` @ `0x1000a410`：解析 `{body,time}` → 校验 → `sign_body` → 组装 `{pid,key_id,sign,sign_version}`
- `sign_body` @ `0x10014110`：`MD5(PID ‖ time ‖ body_b64 ‖ keystream)`
- `feed_key` @ `0x10013e00` + `key_byte` @ `0x10013d30`：从 `.rdata` 两张表派生 32 字节 ASCII 密钥流，并用 FNV-1a 校验完整性
- 两张表的 FNV 期望值：v1 `0x32A7B273`、v2 `0xB9EF3CD1`；**本报告用 PE 直接提取重算，校验一致**
- v2 的 `key_id="202608"`（硬编码字符串，`build_v2_result` @ `0x100051c0`）

### 2.3 JSON/字符串实现【观察】

- 使用 Chromium 风格 `base::DictionaryValue` / `StringValue` + 自研 `SimpleString`（小型字符串优化，`0xF` 内联阈值）
- 参数字符串经 `MultiByteToWideChar(CP_UTF8)` 转 Unicode 再解析；日志里 `[etshelper::OnEncodeAPIBody] invalid params: time/body` 可定位错误分支

---

## 3. `appcontroller.pln` —— 窗口控制

【观察】日志字符串与分派分支对应 14 个 action：

| action | 日志/证据 | 说明 |
|---|---|---|
| `init` | `[appcontroller::OnInitAction]` | 传入 topDomId/窗口句柄，初始化容器 |
| `move` | `[appcontroller::MoveWindows] arguments:` | 拖动窗口 |
| `close` / `maximize` / `minimize` / `restore` | ` close.` / ` maximize.` / ` minimize.` / ` restore.` | 窗口状态 |
| `restore_max` | ` restore_max ---restore` / `---max` | 最大化/还原切换 |
| `fullscreen` / `reduction` | — | 全屏/退出全屏 |
| `hide` / `show` | `isHide` 参数 | 隐藏/显示 |
| `get_win_pos` | `[appcontroller::get_win_pos] return string:` | 返回 `{win_x,win_y,...}` |
| `set_win_pos` | `[appcontroller::SetWinPos] device scale:` / `reset pos` / `left:` | 设置位置，含 DPI 缩放与越界重置(-1=居中) |
| `startapp` | `[appcontroller::ResizeForm]` | 启动子应用/调整表单 |
| `idg_exist` | — | 判断实例/控件存在 |

另从字符串可见壳配置项：`FullScreen`、`WindowMaximize`、`ShowDevTools`、`CloseApp`、`ShowTray`、`WindowHide`、`MsgSize` 等（`shell.ini` 同名字段）→ appcontroller 读取壳配置决定窗口行为。【推断】

前端侧对应 `packages\default\appcontroller.js`（`AppController` 类，14 action + `@error/@init/@close/...` 回调），协议见 `07_shell_update.md` §5。

---

## 4. `filehelper.pln` —— 文件系统能力

【观察】`PlnOnProcessMessage` 分派（action 字符串 + 对应处理函数）：

| action | 处理函数 | 能力 |
|---|---|---|
| `copyfileordirectory` | `DoCopyFile` | 复制文件/目录（递归） |
| `readfile` | `OnGetFileContent` | 读文本 |
| `readbinaryfile` | `OnGetFileContentBinary` | 读二进制（Base64 回传） |
| `writefile` | `OnSetFileContent` | 写文本（自动建目录） |
| `writefilewithbinary` | `OnSaveContentWithBinary` | 写二进制 |
| `existfileorfolder` | `OnExistFileOrFolder` | 存在性 + stat 大小（日志 `stat-size`） |
| `deletefileordirectory` | `OnDeleteFileOrFolder` | 删除 |
| `getfoldersize` | `OnGetFolederSize`（原文拼写） | 目录大小 |
| `createfolder` / `renamefolder` | `OnCreateFolder` / `OnRenameFolder` | 目录操作 |
| `removefiletootherpath` | `OnRemoveFileToOtherPath` | 移动 |
| `savefiledir` / `cleardir` | `OnSaveFileDir` / `ClearDir` | 目录枚举/清空 |
| `ergodic`（遍历） | `OnErgoDic` | 递归遍历（上限保护 `dirs is too big`） |
| `getopenfile` | `OnGetOpenFile` | 文件选择对话框 |
| `getmd5` | `OnGetFileMd5` | 文件 MD5 |
| `aliyun_oss_md5` | — | 与 OSS 上传相关的分块 MD5 |
| `getnpkcontent` / `getrpkcontent_kqlx` | `OnGetNpkContent` / `OnGetRpkContent_KQLX` | 读取本地加密包（npk/rpk）内容 |

【推断】`filehelper` 是前端"文件能力"的唯一出口：前端通过它读写 `%APPDATA%\ETS`、`soundfiles`、`temp\resources`，并为 OSS 上传计算 MD5。

---

## 5. `ETSShell.exe` —— 壳与 CEF 框架

> 反编译产物：`work/ghidra_out/ETSShell.exe/`（约 1.1 万函数级，见 `functions.tsv`）。

【观察】关键字符串/符号：

| 符号/字符串 | 含义 |
|---|---|
| `StiAdapter::CreateMainBrowser` / `RunMessageLoop` | STIC 适配 CEF 的主入口 |
| `StiCore` / `StiCorePlnManager`（RTTI） | 插件管理与消息路由核心 |
| `StiCorePlugin.h`（日志） | 每个插件实例的生命周期日志 |
| `ClientSchemeHandlerFactory` / `UTClientSchemeHandler` | 自定义 scheme 处理器 |
| `rpk.iflytek.com` / `cpk.iflytek.com` / `upk.client.iflytek.com` / `test.wpk` | scheme host 与本地加密包 |
| `SetRpkPwd` / `SetCpkPwd` / `rpkSalt` / `rpkUid` | 包口令/盐 |
| `CefRegisterSchemeHandlerFactory` | CEF 注册 |
| `shell_upgrade.cpp` / `UpdateProduct` | 壳自升级 |
| `shell.ini` 的 `FullScreen/WindowMaximize/LogLevel/DisableGPU/...` | 壳配置 |

调试路径 `D:\code\STIC\stic-pro_ets\_bin\ETSShell.pdb` 说明该二进制是内部构建产物。

### 5.1 插件装载器【观察】（native-analyst 独立反汇编交叉验证）

`StiCorePlnManager` 对每个 `.pln`：

```
LoadLibrary("plugins\\<name>\\<name>.pln")
GetProcAddress(h, "PlnInitiliaze")     // 注意拼写
GetProcAddress(h, "PlnSetParam")
GetProcAddress(h, "PlnOnProcessMessage")
→ PlnInitiliaze(host_callbacks)
```

宿主注入 3 个回调（`appcontroller::PlnSetParam` 内三个 `strcmp` 实证）：`LOG`、`WLOG`、`EXEC_CALLBACK`。消息进入 `PlnOnProcessMessage` 后先做 **action 小写归一化**再分派（因此日志里 action 全小写）。

### 5.2 注入 renderer 的 JS 桥【观察】

壳向每个页面注入 V8 扩展（`work/native/ETSShell/js_bridge_full.js`，17 个 `native function`）：

```
sendMessage / setMessageCallback / openFile / openFileCallback / removeMessageCallback
createGuid / getExePath / getAppConfig / getHomeUrl
setRpkPwd / setCpkPwd / setRpkInfo / setRpkInfoList / releaseAllDb3
setZoomLevel / getZoomLevel / setProxy
```

与 `work/lead/shell_bridge_prelude.js`（从 ETSShell 字符串直接提取的 2130 字节）一致。

### 5.3 安全观察【观察】

- `ETSShell.exe` 签名者：广州讯飞易听说（Sectigo R36，SHA384），**证书 2026-05-09 已过期**；`Ets.exe` 签名者 iFLYTEK（GlobalSign R45）。
- 9 个 `.pln` **全部未签名**（无 Authenticode）。
- 壳启用 `ignore-certificate-errors` / `disable-web-security` / `allow-running-insecure-content`（`ETSShell.exe` 反编译 `decompiled.c` 行 113620–113904）。
- 未发现主动反调试（仅 CRT `IsDebuggerPresent`；`NtQueryInformationProcess` 仅字符串出现在 `shell_utils`，推断用于进程查重）。

### 5.4 壳的关键函数（反编译定位）

由 `ETSShell.exe` 的 `decompiled.c`（9,109 函数 / 5966 已反编译）直接定位：

| 地址 | 函数/证据 | 结论 |
|---|---|---|
| `0x004b06d0` | 插件装载 `StiCorePlnManager` | `LoadLibraryExA(path,0,8)` → `GetProcAddress("PlnInitiliaze")` → 调用 → `GetProcAddress("PlnSetParam")` → 注册 `LOG` / `WLOG` / `EXEC_CALLBACK` 三个宿主回调（`DAT_00581334`、`DAT_00581368`、字符串 `EXEC_CALLBACK`）；失败抛 `"Could not load dynamic library ... System Error:"` / `"SYMBOL_INIT Fail:"` / `"SYMBOL_SETPARAM Fail:"`（源码行号 `StiCorePlnManager.cpp:0x6a/0x74`） |
| `0x004b0c80` | 消息入口 | 引用 `PlnOnProcessMessage`，按 action 分发到插件 |
| `0x00499df0` | CEF 初始化 | 设置 `--allow-running-insecure-content`、`disable-web-security`、`ignore-certificate-errors` 等开关 |
| `0x0049e5d0` | 自定义 scheme | `rpk.iflytek.com` / `cpk.iflytek.com` 等 host 映射 |
| `0x0045a480` | 命令行 | `--shell-app-` 前缀解析（壳自启动参数） |
| `0x004b11a0` | 单实例 | `CreateMutexW` + 互斥检测 |

> 摘要：**插件机制 = 动态库 + 3 个固定导出 + 宿主回调注入**；schema 与 CEF 开关都可在反编译中直接定位，进一步佐证 `02_architecture.md`/`07_shell_update.md` 的结论。

（ETSShell 函数级解读以 `work/ghidra_out/ETSShell.exe/decompiled.c` 为准；本报告只摘关键结论。）

---

## 6. `EtsUpdate.exe` —— 更新器

【观察 + 已验证】`EtsUpdate.exe` 反编译产物 `work/ghidra_out/EtsUpdate.exe/`（9,646 函数 / 7,611 已反编译，`decompiled.c` 9.15 MB）。

关键函数 `FUN_0042f070`（签名上下文初始化）：

```
pid      = "grlx"
version  = "1.0"
key      = "555ffbe95ccf4e9535a110170b445ab8"     // 更新器专用密钥（与 API v1 的 355ff… 首字符不同）
```

MD5 实现：`FUN_00438b23`（init，常量 `0x67452301/0xefcdab89/0x98badcfe/0x10325476`）、`FUN_0043985e`（另一处 init）。

**更新签名（已 3/3 验证）**：

```
sign = MD5( "grlx" + time_seconds + base64(JSON body) + "555ffbe95ccf4e9535a110170b445ab8" )
```

配合日志还原的完整流程：

- 入口 `main.cpp`（duilib UI）→ `WndUpdateFrame::发送更新请求` → `update_info.h` 构造 `head{version,sign,pid:"grlx",time}` + `body=Base64([{r:"client/mobile-update",params}])`
- 响应 `[{code,msg,body{client_version,update[]}}]`，本地版本取自 `ETS.db.Update_Version`，相等即"不需要更新"（退出码 1）
- 安装面：下载 `%.2f%%` → 备份/复制 → `update.dat` + `/Dir /CVer /UVer /Exe /File /Slient` → `RunOnce\ETS_UPDATE` → `taskkill` → `ExitWindowsEx`
- 证明：`work/api/update_sign_proof.json`（3 组真实请求全部命中）；脚本 `work/scripts/update_sign_verify.py`

---

## 7. 如何自行继续

```powershell
# 反编译任意 PE（Ghidra 12.1.4 + JDK 21+）
$env:JAVA_HOME="C:\Program Files\Zulu\zulu-25"
& "<ghidra>\support\analyzeHeadless.bat" <projDir> <projName> `
   -import "D:\ets-rea\ETS\plugins\xxx\xxx.pln" `
   -scriptPath "D:\ets-rea\work\ghidra_scripts" `
   -postScript DumpDecomp.java "D:\ets-rea\work\ghidra_out" -deleteProject
```

输出：
- `decompiled.c`：全部函数 C 伪代码（按 `// ==== 地址 名称 ====` 分节）
- `functions.tsv`：地址、名称、大小、thunk/external、参数数、反编译状态
- `strings.tsv`：已定义字符串 + 地址 + 引用点

检索技巧：

```powershell
Select-String -Path work\ghidra_out\etshelper.pln\decompiled.c -Pattern 'encode_api|sign_version|key_id'
Select-String -Path work\ghidra_out\*\strings.tsv -Pattern '\[.*::On[A-Z]'
```

# 05 原生层（ETSShell / 插件 / 更新器 / 辅助进程）

> 目标目录：`D:\ets-rea\ETS`（只读，全程未修改）
> 分析日期：2026-11-06
> 分析方式：**纯静态** PE 解析 + 递归下降反汇编 + 插件字符串/导出表/导入表/RTTI，对照目标自身写下的历史日志（`ETS\logs\*.log`，属"目标留下的运行时痕迹"，不是本次执行所得）
> 证据等级：**【观察】**=来自文件字节或工具输出；**【推断】**=由观察推理；**【未知】**=证据不足
> 配套可机读产物：`work/native/<binary>/exports.json`、`imports.json`、`strings.txt`、`meta.json`、`dispatch.json`；汇总 `work/native/_summary.json`、`work/native/_overview.md`、`work/native/plugin_abi.json`
> 反编译摘录见 [09_decompiled.md](09_decompiled.md)；签名算法完整还原见 [08_signature.md](08_signature.md)，本文只补原生侧证据，不重复推导。

---

## 一、结论速览

1. **原生层 = 1 个 STIC CEF 壳（`ETSShell.exe`）+ 9 个 `.pln` C++ 插件 + 3 个独立 exe**（预启动器 `Ets.exe`、更新器 `EtsUpdate.exe`、崩溃上报 `bugreport\bugreport.exe`）+ 1 个 Node.js 日志总线（`mq_server\ets_mq_server.exe`）。【观察】
2. 插件 ABI 极其固定：每个 `.pln` 都导出 **同名同序号的 4 个函数** `PlnInitiliaze`（注意多一个 `i`）、`PlnOnProcessMessage`、`PlnSetParam`、`PlnUnInitialize`，序号 1–4；`soundhelper.pln` 额外导出 29 个 `snd*` C 接口（序号 5–33）。【观察】
3. 壳通过 `LoadLibrary` + `GetProcAddress("PlnInitiliaze"/"PlnSetParam"/"PlnOnProcessMessage")` 装载插件，并用 `PlnSetParam("LOG"|"WLOG"|"EXEC_CALLBACK", fn)` 向插件注入宿主回调；插件通过 `EXEC_CALLBACK` 把异步结果回传给 JS。【观察 + 推断】
4. 前端与原生之间的桥是注入到 renderer 的 JS：`cef.message.sendMessage(uid, pluginKey, actionKey, args)`，另有 16 个 `cef.message.*` 原生函数（见 §四）。【观察】
5. 构建血缘清晰：PDB 路径全部为 `D:\code\STIC\...`，存在**两代工具链**——`stic-pro_ets`（VS2019，linker 14.29，新壳/新插件）与 `stic-pro_2010`（VS2010，linker 10.0，多数老插件）。【观察】
6. 安全面：**未发现主动反调试逻辑**；壳/预启动器/更新器/崩溃器/mq_server 有 Authenticode 签名，**9 个插件全部未签名**；壳内部存在多个危险 CEF 开关（`ignore-certificate-errors`、`disable-web-security`）；`mq_server` 在 `0.0.0.0:40001` 无鉴权广播日志（含阿里云 STS 临时凭证）。【观察 + 推断】

---

## 二、14 个二进制身份表

> 机器均为 `i386 (x86)`/PE32；PE 时间戳为 COFF `TimeDateStamp`（UTC）；"链接器"为 PE 可选头 Major.MinorLinkerVersion；熵为整文件 Shannon 熵（0–8，越高越接近压缩/加密）。

| 名称 | 类型 | 大小(B) | PE 时间戳(UTC) | 链接器 | PDB 路径（残留） | 整文件熵 | 签名 |
|---|---|---|---|---|---|---|---|
| `ETSShell.exe` | EXE/GUI | 2,297,440 | 2025-07-28 03:43:45 | 14.29 (VS2019) | `D:\code\STIC\stic-pro_ets\_bin\ETSShell.pdb` | 6.390 | 有，见 §八 |
| `Ets.exe` | EXE/GUI | 485,824 | 2025-12-16 10:23:23 | 14.29 | `D:\code\STIC\preshell_2\Release\preshell.pdb` | 5.897 | 有（iFLYTEK/GlobalSign R45） |
| `EtsUpdate.exe` | EXE/GUI | 2,079,784 | 2024-07-11 03:35:17 | 12.0 (VS2013) | `D:\code\ets_git_code\stic_tools\ets_tool_stic\bin\EtsUpdate\Release\EtsUpdate.pdb` | 6.645 | 有（结构见 §八，签名者未解析） |
| `bugreport\bugreport.exe` | EXE/GUI | 3,614,240 | 2024-11-05 08:06:30 | 10.0 (VS2010) | `D:\code\STIC\stic-pro_ets\src\third_party\bugreport\build\Release\bugreport.pdb` | 6.411 | 有（未解析） |
| `mq_server\ets_mq_server.exe` | EXE/CUI | 12,080,168 | 2016-06-23 13:35:12 | 12.0 | `c:\ws\Release\node.pdb` | 6.778 | 有（未解析） |
| `plugins\appcontroller\appcontroller.pln` | DLL | 552,448 | 2024-10-28 09:29:09 | 14.29 | `...\stic-pro_ets\build\Release\plugins\appcontroller\appcontroller.pdb` | 6.613 | **无** |
| `plugins\etshelper\etshelper.pln` | DLL | 497,664 | 2026-08-15 06:39:14 | 14.29 | `D:\code\STIC\stic-misc\stic-pro_ets\build\Release\plugins\etshelper\etshelper.pdb` | 6.605 | **无** |
| `plugins\filehelper\filehelper.pln` | DLL | 674,304 | 2024-10-29 03:33:46 | 10.0 | `...\stic-pro_2010\build\Release\plugins\filehelper\filehelper.pdb` | 6.462 | **无** |
| `plugins\httphelper\httphelper.pln` | DLL | 1,730,560 | 2024-10-28 10:06:58 | 10.0 | `...\stic-pro_2010\build\Release\lib\httphelper.pdb` | 6.734 | **无** |
| `plugins\sevenzip\sevenzip.pln` | DLL | 467,456 | 2024-10-28 12:24:58 | 10.0 | `...\stic-pro_2010\build\Release\plugins\sevenzip\sevenzip.pdb` | 6.453 | **无** |
| `plugins\shellhelper\shellhelper.pln` | DLL | 2,117,632 | 2024-10-31 08:17:26 | 10.0 | `...\stic-pro_2010\build\Release\plugins\shellhelper\shellhelper.pdb` | 6.521 | **无** |
| `plugins\soundhelper\soundhelper.pln` | DLL | 3,175,936 | 2025-08-26 03:59:04 | 10.0 | `...\stic-pro_2010\build\Release\plugins\soundhelper\soundhelper.pdb` | 7.250 | **无** |
| `plugins\sqlitepln\sqlitepln.pln` | DLL | 345,088 | 2024-10-28 12:39:12 | 10.0 | `...\stic-pro_2010\build\Release\lib\sqlitepln.pdb` | 6.431 | **无** |
| `plugins\window_control\window_control.pln` | DLL | 436,736 | 2024-10-28 12:39:58 | 10.0 | `...\stic-pro_2010\build\Release\plugins\window_control\window_control.pdb` | 6.490 | **无** |

补充身份信息（观察）：

- `ETSShell.exe` 版本资源：`FileVersion/ProductVersion=5.0.91.329`，`ProductName=CCS`，`CompanyName=iflytek`，`FileDescription=shell.exe`，`OriginalFilename=shell.exe`，`LegalCopyright=Copyright (C) IFLYTEK 2023`，子系统 GUI，ImageBase `0x400000`，入口 `0x10D22D`。
- `Ets.exe`：**无版本资源、无导出**，PDB 名为 `preshell.pdb`，字符串含 `shell.exe` 且仅导入 KERNEL32/USER32/GDI32/SHELL32/SHLWAPI →【推断】"预启动器/引导器"（pre-shell，负责拉起 `ETSShell.exe`，与 `07_shell_update.md` 的启动链一致）。
- `EtsUpdate.exe`：`ProductName=E听说更新工具`，`CompanyName=广州讯飞易听说网络科技有限公司`。
- `mq_server\ets_mq_server.exe`：**就是官方 `node.exe` 改名**——版本资源 `Node.js 5.12.0`、`OriginalFilename=node.exe`、PDB `c:\ws\Release\node.pdb`，导出表 1,429 项全是 V8/Node 的 C++ 符号；同目录 `main.js` 为明文源码，`node_modules` 实际安装的是 `ws@1.1.2`（`package.json` 声明 `^8.17.0`，与 `node@5.12` 不兼容，说明实际运行时以 `node_modules` 内已安装版本为准）。【观察 + 推断】
- `bugreport\bugreport.exe`：导出 2,853 项几乎全是 Google Test/glog、DuiLib 的 C++ mangled 名，依赖 `dbghelp.dll`、`sqlite3.dll`，RTTI 含 `DuiLib::*`、`Sti::SevenZip::ZipHelper` →【推断】基于 gtest/glog + DuiLib 的内部崩溃上报工具，由壳的 `dumpfile::RunBugReport` 拉起（见 §六）。
- 全部 14 个文件均**非加壳、未混淆**（节区可读、导入表完整、无 UPX/VMProtect 类节名）。【观察】

### 2.1 节区与熵（观察）

| 二进制 | 节区（VA / 原始大小 / 熵） |
|---|---|
| ETSShell | `.text`(0x1000/1,360,384/6.58) `.rdata`(0x14E000/331,264/5.38) `.data`(0x19F000/15,872/4.51) **`.fptable`**(0x1A8000/512/0) **`Shared`**(0x1A9000/512/0) `.rsrc`(0x1AA000/507,904/4.32) `.reloc`(0x226000/67,584/6.59) |
| Ets | `.text`(0x1000/168,448/6.63) `.rdata`(0x2B000/59,904/5.50) `.data`(0x3A000/4,608/3.18) `.fptable`(0x3C000/512/0) `.rsrc`(0x3D000/229,888/4.23) `.reloc`(0x76000/8,192/6.55) |
| EtsUpdate | `.text`(0x1000/1,439,744/6.57) `.rdata`(0x161000/270,848/5.62) `.data`(0x1A4000/29,696/5.08) `.rsrc`(0x1C2000/259,584/5.79) `.reloc`(0x202000/66,560/6.60) |
| bugreport | `.text`(0x1000/2,170,880/6.47) `.rdata`(0x213000/587,264/5.60) `.data`(0x2A3000/34,304/4.79) `.tls`(0x2C6000/30,720/0.0005) `.rsrc`(0x2CE000/555,008/5.19) `.reloc`(0x356000/222,720/5.23) |
| mq_server | `.text`(0x1000/6,211,584/6.57) `.rdata`(0x5EE000/5,415,936/6.36) `.data`(0xB19000/66,560/5.29) `.rsrc`(0xB35000/110,592/5.02) `.reloc`(0xB50000/262,144/6.64) |
| appcontroller | `.text`(0x1000/427,008/6.63) `.rdata`(0x6A000/97,792/5.33) `.data`(0x82000/7,680/4.19) `.rsrc`(0x86000/512/4.72) `.reloc`(0x87000/18,432/6.59) |
| etshelper | `.text`(0x1000/366,592/6.63) `.rdata`(0x5B000/101,888/5.50) `.data`(0x74000/9,216/4.36) `.fptable`(0x79000/512/0) `.rsrc`(0x7A000/512/2.53) `.reloc`(0x7B000/17,920/6.58) |
| filehelper | `.text`(0x1000/535,552/6.52) `.rdata`(0x84000/91,136/4.96) `.data`(0x9B000/11,776/4.64) `.tls`(0xA2000/512/0) `.rsrc` `.reloc` |
| httphelper | `.text`(0x1000/1,278,464/6.71) `.rdata`(0x13A000/330,240/5.83) `.data`(0x18B000/43,008/5.36) `.tls`(0x19B000/512/0) `.rsrc` `.reloc` |
| sevenzip | `.text`(0x1000/342,016/6.65) `.rdata`(0x55000/78,848/4.78) `.data`(0x69000/12,800/4.57) `.tls`(0x72000/512/0) `.rsrc` `.reloc` |
| shellhelper | `.text`(0x1000/1,555,456/6.59) `.rdata`(0x17D000/339,968/5.35) `.data`(0x1D0000/28,160/5.02) `.tls`(0x1E0000/512/0) `.rsrc` `.reloc` |
| soundhelper | `.text`(0x1000/1,575,424/6.71) **`.rdata`(0x182000/1,423,872/7.46)** `.data`(0x2DE000/87,040/6.33) `.tls`(0x351000/512/0) `.rsrc` `.reloc` |
| sqlitepln | `.text`(0x1000/255,488/6.64) `.rdata`(0x40000/55,296/4.93) `.data`(0x4E000/8,192/4.22) `.tls`(0x53000/512/0) `.rsrc` `.reloc` |
| window_control | `.text`(0x1000/332,288/6.66) `.rdata`(0x53000/65,536/4.90) `.data`(0x63000/10,752/4.55) `.tls`(0x69000/512/0) `.rsrc` `.reloc` |

- **`.fptable`（512B，全 0）与 `Shared`（512B，全 0）是 STIC 自定义节**，只出现在 `ETSShell`、`Ets`、`etshelper`（"stic-pro_ets" 新工具链产物）。两者在本安装发布件中均为全零，推测为 STIC 框架预留的函数指针表 / 共享数据槽（运行时填充）。【观察 + 推断】
- 多数 `stic-pro_2010` 插件带 `.tls` 节（静态 CRT 的线程局部存储）；`soundhelper` 的 `.rdata` 熵 7.46 明显高于同类，与其内嵌 AQC/VAD/AGC 参数与 SVM 模型数据（字符串 `nu_svr`/`epsilon_svr`/`double_threshold_model`/`ftr_*`）相符。【推断】
- `soundhelper` 的 `.rdata` 原始大小 1.42MB 占整个文件 45%，是 9 个插件中最大的数据段。【观察】

### 2.2 编译指纹（观察 + 推断）

- **链接器版本**（来自 PE 可选头，可靠）：`ETSShell`/`Ets`/`appcontroller`/`etshelper` = **14.29（VS2019 16.11）**；`EtsUpdate`/`mq_server` = 12.0（VS2013）；其余 7 个插件 + `bugreport` = **10.0（VS2010）**。
- **Rich header**（全部 14 个均存在，key 各不相同）：解码后含多组 `(prodid, build)`，例如 `ETSShell` 出现 build `33140/30034/30319/31101`、`appcontroller` 出现 `27412/30034/30154`、`shellhelper`/`filehelper` 出现 `40219` 与 `30729` 混排 →【推断】主代码与第三方静态库（OpenSSL、7-Zip、glog/gtest 等）由不同年代 MSVC 编译后链接在一起；具体每个 prodid 对应的 VS 版本未逐一核对，标为【未知】。
- **调试信息残留**：14 个文件均有 Debug Directory（type 2 CodeView），保留**原始 PDB 路径**（见上表）——泄露内网构建机目录结构 `D:\code\STIC\...`、`D:\code\ets_git_code\...`、`c:\ws\...`（Node 官方构建机）。【观察】
- 所有文件 `.reloc` 完好、`DYNAMIC_BASE`+`NX_COMPAT` 均开启；均未设置 `NO_SEH`；**CFG（Control Flow Guard）只有 `etshelper.pln` 一个开启**（`DllCharacteristics & 0x4000`）。【观察】

---

## 三、插件 ABI（导出表、调用约定、参数）

### 3.1 9 个插件的精确导出表（观察，`work/native/<pln>/exports.json`）

所有导出均为 **stdcall 序号连续、无 name ordinal 冲突**；`PlnSetParam`/`PlnUnInitialize` 在部分插件中指向同一 RVA（空桩）。

| 插件 | PlnInitiliaze | PlnOnProcessMessage | PlnSetParam | PlnUnInitialize |
|---|---|---|---|---|
| appcontroller | ord1 RVA `0x2100` | ord2 RVA `0x5260` | ord3 RVA `0x2150` | ord4 RVA `0x2140` |
| etshelper | ord1 RVA `0x2A70` | ord2 RVA `0xAA70` | ord3 RVA `0x2AB0` | ord4 RVA `0x2AB0`（与 setparam 同址=空桩） |
| filehelper | ord1 RVA `0x3A60` | ord2 RVA `0x5B10` | ord3 RVA `0x3B00` | ord4 RVA `0x3AD0` |
| httphelper | ord1 RVA `0x9820` | ord2 RVA `0x14100` | ord3 RVA `0x98C0` | ord4 RVA `0x98A0` |
| sevenzip | ord1 RVA `0x1F20` | ord2 RVA `0x2660` | ord3 RVA `0x1FD0` | ord4 RVA `0x1FA0` |
| shellhelper | ord1 RVA `0xF4B0` | ord2 RVA `0x10B40` | ord3 RVA `0xF550` | ord4 RVA `0xF520` |
| soundhelper | ord1 RVA `0x17860` | ord2 RVA `0x24300` | ord3 RVA `0x17900` | ord4 RVA `0x178D0` |
| sqlitepln | ord1 RVA `0x29E0` | ord2 RVA `0x52A0` | ord3 RVA `0x2A80` | ord4 RVA `0x2A60` |
| window_control | ord1 RVA `0x1D60` | ord2 RVA `0x2D20` | ord3 RVA `0x1DF0` | ord4 RVA `0x1DD0` |

> `PlnInitiliaze` 的拼写是 **`PlnInitiliaze`**（`Init` + `iliaze`，共 13 个字符），9 个插件与 `ETSShell.exe` 全部一致；旧评估中的拼写结论正确。【观察】

### 3.2 `soundhelper.pln` 额外导出（序号 5–33，观察）

`5 sndAppendFile@0x54490`、`6 sndAudiocheck@0x54050`、`7 sndChannelfile@0x54260`、`8 sndContinue@0x53E70`、`9 sndConvertfile@0x54120`、`10 sndConvertfileA@0x54170`、`11 sndCopyFile@0x54430`、`12 sndCreateInstance@0x53D60`、`13 sndCutFile@0x543C0`、`14 sndDeleteFile@0x54340`、`15 sndDestoryInstance@0x53D90`、`16 sndGetFileDetail@0x54590`、`17 sndGetParam@0x53DC0`、`18 sndGetVAD@0x54090`、`19 sndMergeFile@0x544F0`、`20 sndNormalizefile@0x541C0`、`21 sndNormalizefileA@0x54210`、`22 sndPause@0x53E80`、`23 sndPlay@0x53EB0`、`24 sndPlayA@0x53EE0`、`25 sndPlayBinary@0x53F20`、`26 sndPlayData@0x53E90`、`27 sndRecord@0x54020`、`28 sndScanfile@0x53F60`、`29 sndScanfileA@0x53FA0`、`30 sndScanfileBinary@0x53FF0`、`31 sndSetParam@0x53D20`、`32 sndSliceFile@0x542C0`、`33 sndStop@0x53E60`。
→【推断】这 29 个是给其它原生模块（如壳内 C++ 直接 `GetProcAddress`）使用的进程内 C API，与 `PlnOnProcessMessage` 的 JSON action 路径并存；命名风格（Create/Destory 拼写错误、A/W 双版本）为 2010 年代自研 SDK。

### 3.3 调用约定与参数（观察 + 推断）

以 `appcontroller.pln` 为样本（`work/native/appcontroller/abi_stubs.txt`）：

- `PlnInitiliaze()`：**无参数**（函数体在 `ret` 前只用 `esp` 上的临时字符串），初始化插件日志：构造 `std::string "logs\shell.log"` 并调用日志器。【观察】
- `PlnSetParam(const char* name, void* value)`：`push ebp; mov ebp,esp`，第一个参数 `[ebp+8]` 为名字，第二个 `[ebp+0xc]` 为值；内部对 `"LOG"`、`"WLOG"`、`"EXEC_CALLBACK"` 做逐字符比较，命中 `EXEC_CALLBACK` 时把 `[ebp+0xc]` 存入全局 `0x10085534`，最后 `ret`（cdecl）。【观察】→ 签名推断为 `void PlnSetParam(const char* key, void* value)`。
- `PlnUnInitialize()`：`ret`（空桩，appcontroller 2 条指令）。【观察】
- `PlnOnProcessMessage`：在入口读取 `[ebp+8]/[ebp+0xc]/[ebp+0x10]/[ebp+0x14]` 共 4 个参数，进入 SEH 后：
  1. 对第一个参数（字符串）计算长度并拷贝到 `std::string`，随后逐字符做 `sub al,0x41` 的**大小写归一化**（解释了所有 action 在二进制里都是小写）；
  2. 与 `init/close/maximize/...` 等 action 字符串比较后分派；
  3. 结束时把 `[ebp+0x14]` 指向的内存写 0（输出参数）。
  →【推断】`int PlnOnProcessMessage(const char* actionKey, const char* argsJson, const char* callbackId, void* out)`；参数顺序中"哪一个承载 args"尚需 `09_decompiled.md` 的 C 伪代码逐字确认，标为【未知】。【观察依据】appcontroller 入口处 `mov esi,[ebp+8]; mov edi,[ebp+0xc]; mov eax,[ebp+0x10]; mov [ebp-0x188],eax([ebp+0x14])`。
- **异步回调**：插件内对 `call dword ptr [0x10085534]` 有直接引用（appcontroller 文件偏移 `0x3F5F`，即 `EXEC_CALLBACK` 全局），结合日志里 `uid@action` 回调命名 →【推断】插件完成异步工作后调用宿主注入的 `EXEC_CALLBACK(uid, jsonResult)`，宿主再执行 JS 侧 `setMessageCallback(uid, cb)` 注册的函数。

### 3.4 宿主侧装载器（观察）

`ETSShell.exe` 内 `StiCorePlnManager.cpp`（PDB 路径字符串 `D:\code\STIC\stic-pro_ets\src\core\StiCorePlnManager.cpp`）相关函数（`work/native/ETSShell/plugin_loader_disasm.txt`）：

- `sub_004B084A`（251 指令）：`GetProcAddress(?, "PlnSetParam")`、`GetProcAddress(?, "PlnInitiliaze")`，随后 `GetProcAddress` 解析 `"WLOG"`、`"EXEC_CALLBACK"`；失败日志 `SYMBOL_INIT Fail:`、`SYMBOL_SETPARAM Fail:`。
- `sub_004B0CC2`（104 指令）：`GetProcAddress(?, "PlnOnProcessMessage")`；失败日志 `SYMBOL_PROCMESSAGE Fail:`。
- 字符串同区还有 `".pln"`、`"LOG"`、`"WLOG"`、`"EXEC_CALLBACK"`、`"========StiCorePlugin.log starting==========="`、`"StiCorePlugin.h"`。
- `ETSShell.exe` **自身也导出** `PlnInitiliaze`（ord 365 RVA `0xAF840`）、`PlnSetParam`（ord 366 RVA `0x733B0`）、`PlnUnInitialize`（ord 367 同 RVA `0x733B0`，空桩），另有 **364 个 jsoncpp 符号导出**（`Json::*`）。【观察】→【推断】壳与插件共用同一套"可作为插件被加载"的基类/接口（或为宿主自注册预留）；所有插件的导入表中**均无 `ETSShell.exe`**，插件并不按导入表依赖壳，jsoncpp 由各插件静态链接（`Json::` RTTI 遍布各插件）。【观察】
- 插件目录与文件名：`plugins\<name>\<name>.pln`；日志显示启动时依次收到各插件 `action->init`，顺序中可见 `shellhelper → httphelper → filehelper → etshelper → …`（`logs\shell_2026-11-4.log` 第 28–99 行）。【观察】
- `shell.ini` 的 `AppName=ETSShell.exe`、`MsgSize=50`、`LogLevel=1`、`FullScreen=1`、`DisableGPU=1`；插件日志统一落到 `logs\shell_*.log`（`PlnInitiliaze` 里的 `logs\shell.log`）。【观察】

---

## 四、JS ↔ 原生桥（CEF 注入脚本，观察）

`ETSShell.exe` 的 `.rdata` 中内嵌一段注入 renderer 的 JS（文件偏移 `0x17DD08`，2,130 字节，已提取为 `work/native/ETSShell/js_bridge_full.js`），声明 **17 个 native function**：

```
cef.message.sendMessage(uid, pluginKey, actionKey, args)   // 主入口
cef.message.setMessageCallback(uid, callback)              // 注册异步结果回调
cef.message.openFile(uid, pluginKey, actionKey, args)      // 注意：实现只透传 uid
cef.message.openFileCallback(uid, callback)
cef.message.removeMessageCallback(uid)
cef.message.createGuid()
cef.message.getExePath()
cef.message.getAppConfig()
cef.message.getHomeUrl()
cef.message.setRpkPwd(pwd) / setRpkInfo(path, code, salt) / setRpkInfoList(list)
cef.message.releaseAllDb3()
cef.message.setZoomLevel(val) / getZoomLevel()
cef.message.setCpkPwd(pwd)
cef.message.setProxy(server)
```

- 该脚本以 `native function xxx();` 形式声明，由 `ClientHandler`/`ClientAppExtensionHandler`（RTTI：`Sti::Adapter::ClientHandler`、`Sti::Adapter::ClientAppExtensionHandler`、`Sti::Adapter::ClientApp`）注册到 V8。【观察 + 推断】
- 前端实际用法（`ETS\packages\default\appcontroller.js` 与 `logs\ets_*.log`）：`uid = createGuid()`，然后 `sendMessage(uid, 'appcontroller', 'init', JSON.stringify(args))`；异步结果通过 `setMessageCallback(uid, cb)` 回来；`uid` 后缀 `@error/@init/@close/...` 是约定（`appcontroller.js` 第 5–19 行）。【观察】
- **actionKey 全小写**（`init`、`close`、`encode_api_body_v2`……）；`pluginKey` 形如 `appcontroller`/`etshelper`/`filehelper`/`httphelper`/`sevenzip`/`shellhelper`/`soundhelper`/`sqlitepln`/`window_control`（日志与 JS 双侧一致）。【观察】
- 日志里 `mq_server` 收到的 `[H5_SOUND] ... audioUrl=stic://file.iflytek.com/C:\...mp3` 表明壳注册了自定义协议 `stic://` 把本地文件映射给 H5（`ClientSchemeHandler`/`UTClientSchemeHandler` RTTI）。【观察 + 推断】

---

## 五、逐插件能力面（action 清单来自 `PlnOnProcessMessage` 反汇编中的字符串比较，交叉日志）

> 说明：下表 action 由"分发函数中引用到的字符串"提取；个别字符串是**参数名/前缀**而非 action（已标注）。`callback_id` 类参数说明该 action 是异步的，结果走 `EXEC_CALLBACK`。

### 5.1 appcontroller.pln —— 壳窗口控制 + 拉起主程序
- 定位：控制 STIC 壳窗口（无边框窗口拖拽/缩放/最大化/全屏），并 `startapp` 启动主程序。【观察】
- action（15 个）：`init, close, maximize, minimize, restore, restore_max, move, fullscreen, reduction, hide, show, get_win_pos, set_win_pos, resize_window, startapp`；参数键 `win_name, win_class, win_x, win_y, win_width, win_height, error_callback_id`。【观察】
- 日志方法（6）：`OnInitAction, MoveWindows, OnGetCurWinHandle, ResizeForm, SetWinPos, get_win_pos`。【观察】
- 依赖：KERNEL32/USER32/GDI32/SHELL32/SHLWAPI/WINMM（无第三方 DLL）；导入 `ShellExecuteExW`（`startapp`）、`CreateToolhelp32Snapshot`（进程存在性）。【观察】
- 备注：JS 侧还会发 `idg_exist`（`appcontroller.js:268`），但**本版本插件字符串中不存在该 action** →【推断】前端与插件版本轻微错位，或该 action 由壳内核处理。【观察 + 未知】

### 5.2 etshelper.pln —— 签名工具 + 更新检查 + 调试
- 定位：**API 请求/响应签名**（v1/v2）、更新检查、崩溃测试、`get_appdata_path`、视频合并（`dub_merge`）、日志转发；直接静态链接 sqlite3 客户端（导入 `sqlite3.dll` 6 API）。【观察】
- action（12 个）：`init, encode_api_body, encode_api_body_v2, encode_api_resp, encode_api_resp_v2, check_update, check_update_force, check_ets_server, get_appdata_path, log_data, dub_merge, test_crash`；前缀参数 `grlx`（v1 pid）/`pcWin`（v2 pid）、键 `key_id, sign_version, update_pid, update_wnd, new_update_id, cur_update_id, ets_update_info, begin_time, audio_path, audio_list, erasure_video_path, force_show, force_update, skip_normal_update, error_callback_id`。【观察】
- 日志方法（6）：`OnInitAction, OnEncodeAPIBody, OnEncodeAPIResp, OnLogData, OnVideoMerge, PlnOnProcessMessage`。【观察】
- 详见 §七（签名原生证据）。

### 5.3 filehelper.pln —— 文件系统全能工具
- 定位：读写/复制/移动/删除/重命名、目录遍历、文件对话框、MD5/Base64、`.rpk/.npk` 包读取、阿里云 OSS MD5 校验；含 **CppSQLite3**（导入 `sqlite3.dll` 17 API，含 `sqlite3_key` 加密库）。【观察】
- action（30 个，逐字以 `work/native/filehelper/dispatch.json` 为准）：`aliyun_oss_md5, cleardir, closeshell, copyfileordirectory, createfolder, createnewfile, deletefileordirectory, ergodic, ergodicfiles, existfileorfolder, getbase64, getcode, getfoledersize, getmd5, getsystemdirs, isfileexisted, isfileuse, ncttools, openbrowsedialog, openfiledialog, readbinaryfile, readfile, readnpk, readrpk_kqlx, removefiletootherpath, renamefile, renamefolder, savefiledialog, writefile, writefilewithbinary`。【观察】
- 日志方法（23）：`OnGetMd5, OnGetBase64, OnGetAliyunMd5, OnReadFileContent(…), OnGetRpkContent_KQLX, OnGetNpkContent, OnErgodicFiles, OnErgoDic, OnExistFileOrFolder, OnGetFolederSize, OnCreateFolder, OnDeleteFileOrFolder, OnRenameFile, OnRenameFolder, OnRemoveFileToOtherPath, OnIsFileUse, OnGetOpenFile, OnSaveFileDir, OnSetFileContent, OnSaveContentWithBinary, OnGetFileContent, OnGetFileContentBinary` 等。【观察】
- 备注：包含 `closeshell`（在文件动作里关闭壳）——权限最大，"前端可让进程退出"。【推断】

### 5.4 httphelper.pln —— HTTP(S) 客户端（静态 OpenSSL）
- 定位：GET/POST、上传/下载、资源包下载（`downloadresource`）、SDK 下载（`downloadsdk`）、下载进度与停止、rpk 判断；**静态链接 OpenSSL**（字符串 `SHA1/SHA256 block transform for x86, CRYPTOGAMS by <appro@openssl.org>`、`AES for Intel AES-NI`、`Camellia` 等）。【观察】
- action（10 个）：`init, destroy, httpget, httppost, upload, download, downloadresource, downloadsdk, stopdownload, isrpkexist`；参数键 `download_callback_id, httpload_progress_callback_id, upload_callback_id, error_callback_id, content_type, http_proxy, all_proxy, no_proxy, ad_timestamping` 等。【观察】
- 依赖：WS2_32(28)/WLDAP32(16)/ADVAPI32(3)/IPHLPAPI(2)/dbghelp(1)，无 `libcurl.dll`/`libssl.dll` → TLS 由内嵌 OpenSSL 完成。【观察 + 推断】
- RTTI：`Json::*`、`base::internal::JSONStringValue`（无公开类名）→ 实现以 C 风格为主。【观察】

### 5.5 sevenzip.pln —— 压缩/解压
- 定位：zip/7z 解压与测试，配合更新器/资源包；RTTI `Sti::SevenZip::ZipHelper`（与 `bugreport.exe` 中同名类一致，说明共用 STIC 公共库代码）。【观察】
- action（2 个）：`unzip, test`；日志方法（3）：`OnZip, OnUnzip, OnTestZip`（`OnZip` 说明此版本仍有压缩路径，但 dispatch 未暴露 action）。【观察】
- 依赖：KERNEL32(131)/USER32(3)/ADVAPI32(6)/SHELL32(2)/OLEAUT32(5)（无第三方 DLL → 7-Zip SDK 静态链接）。【观察 + 推断】

### 5.6 shellhelper.pln —— 系统外壳/进程/设备/音量
- 定位：执行 cmd/exe/bat、启停进程、进程存在性、音量/静音、设备与 USB 检查、声卡/网卡检查、机器信息、Off2007-2019 检测、网络测试、配置读取、`upgrade_qiniu`（七牛升级）、`start_http`；是导入 API 面最宽的插件（19 个 DLL，含 `SETUPAPI`、`OLEACC`、`gdiplus`、`WINSPOOL`、`IMM32`）。【观察】
- action（20 个）：`init, destroy, getconfig, getroomid, executecmd, executeexe, executebat, startprocess, processexist, stopprocess, checkaudio, getvolume, setvolume, getmute, setmute, checkadapter, getpcinfo, getusbinfo, getofficeversion, netcheck`；参数键 `cmd_hide, process_list, dev_list, vol_list, upgrade_qiniu` 等。【观察】
- 日志方法（22）：`ExecuteCmd, OnGetConfig, OnGetRoomId, OnExecuteCmd/Exe/Bat, OnStartProcess, OnStopProcess, OnProcessExist, OnGetVolume, OnSetVolume, OnGetMute, OnSetMute, OnCheckAudioAction, OnGetOfficeVersion, OnGetPcInfo, OnGetUsbInfo, NetCheck, USBDevCheck, OnDestroyAction, GetExitCodeProcess, executecmd` 等；日志类名出现 `shellhelper::OnStartProcess`。【观察】
- 敏感导入：`CreateProcessW, CreateToolhelp32Snapshot, OpenProcess, TerminateProcess, WinExec, ShellExecuteExW, GetAsyncKeyState, SetWindowsHookExW, VirtualAlloc, VirtualProtect, RegOpenKeyExW/RegSetValueExW`。`GetAsyncKeyState/SetWindowsHookExW` 可能来自 DuiLib/输入法/第三方 UI 库的静态链接（同 `bugreport.exe` 也导入），**不构成键盘记录证据**（未定位调用点）。【观察 + 未知】

### 5.7 soundhelper.pln —— 录音/播放/音频质检（最大插件）
- 定位：录音机/播放器/VAD 断句/AQC 音频质检/AGC 自动增益/波形与能量回调/MP3(SPX) 编解码/切分合并/`combineandconvertwavtomp3`（调外部 `lame.exe`/ffmpeg 链，见 `07_shell_update.md`）；RTTI 揭示完整音频框架 `Asiafly::SoundUtility::{RecorderImpl,PlayerImpl,VadImpl,AudiocheckerImpl,AutogainImpl,AgcStrategy,AgcStrategyGear7,ScanfileImpl,Mp3FileIO,SpeexFileIO,WaveFileIO,WovFileIO,VolumeCtrl,SoundWorker,SoundFileIO}` + `SticPlugins::SoundHelper::SndUtilImpl` + `CheckAudioLoader`。【观察】
- action（17 个）：`init, destroy, loadfile, play, pause, continue, stop, record, trace, convertfile, checkvoice, checkwovfile, aqcwavfile, combineandconvertwavtomp3, setvolume, getvolume, setvolzoom`；参数键极多（`recordbegin/end_callback_id, playbegin/end_callback_id, curplaypos_callback_id, energy_callback_id, waveform_callback_id, aqcresult_callback_id, scanfilebegin/end_callback_id, sample_rate_16k/8k, vad_*, ftr_*, aqc_*, spx_quality, psps_quality, nch/…`）。【观察】
- 日志方法（15）：`OnInitAction, OnUnInitAction, OnLoadFileAction, OnPlayAction, OnPauseAction, OnContinueAction, OnRecordAction, OnConvertfile, OnCheckAudio, OnCheckWovFile, OnAQCWavfile, OnCombineAndConvertWavToMp3, OnSetVolume, OnGetVolume, OnWovToWav`。【观察】
- 依赖：WINMM(26)/SETUPAPI(4)/**HID.DLL(3)**/ole32(4)/SHLWAPI(2)/dbghelp(1) →【推断】HID/SETUPAPI 用于 `check_hardware`/USB 耳麦检测。【观察 + 推断】
- 备注：`.rdata` 高熵的内嵌模型/参数表 + 32/33 个 snd* C 导出 = "音频 SDK 内置成插件"的形态。【推断】

### 5.8 sqlitepln.pln —— 插件化 SQLite 网关
- 定位：连接/断开数据库、执行查询(DQL)/DML，向 JS 暴露结果；导入 `sqlite3.dll` 15 API（含 `sqlite3_key`→支持 SQLCipher 加密库）。【观察】
- action（6 个）：`init, connect, disconnect, execquery, execdml, destroy`；参数键 `query_result_callback, error_callback_id`；日志方法 `OnInitAction, OnConnectAction, OnQueryAction, OnDMLAction, OnPublishAction`。【观察】
- RTTI：`CppSQLite3DB/Query/Exception`、`Json::*`。【观察】

### 5.9 window_control.pln —— 主窗口控制（appcontroller 的简化版）
- 定位：对指定 HWND/窗口名做 close/maximize/minimize/restore/move/fullscreen/reduction/hide；无 `startapp`、无 `get_win_pos`。【观察】
- action（9 个）：`init, close, maximize, minimize, restore, move, fullscreen, reduction, hide`；参数键 `error_callback_id`；日志方法 `OnInitAction, MoveWindows`。【观察】
- 依赖：KERNEL32/USER32/SHELL32/SHLWAPI/WINMM（最小依赖集之一）。【观察】

### 5.10 action 提取方法与置信度

- 方法：对每个 `.pln` 的 `PlnOnProcessMessage` 做 capstone 递归下降，收集所有"立即数指向 `.rdata` 字符串"的引用，按出现顺序得到 action 比较序列；再用日志中 `action->xxx` 实证校准。【观察】
- 置信度：`appcontroller/filehelper/httphelper/shellhelper/soundhelper/sqlitepln/window_control/sevenzip` 的 action 与日志/JS 交叉一致（高）；`etshelper` 全部 action 均在日志出现（高）；个别 action（如 `restore_max`、`resize_window`、`trace`、`ncttools`、`getcode`）在日志中未出现，为**代码中存在但本安装未触发**（中）。【观察】

---

## 六、导入依赖矩阵与 RTTI

### 6.1 导入 DLL 矩阵（观察，`work/native/<name>/imports.json`）

| DLL | 使用者（括号为该文件导入函数数） |
|---|---|
| `libcef.dll` | ETSShell(45) |
| `dbghelp.dll` | ETSShell(2: MiniDumpWriteDump/MakeSureDirectoryPathExists)、filehelper(1)、httphelper(1)、soundhelper(1)、bugreport(7) |
| `sqlite3.dll` | ETSShell(17)、filehelper(17)、sqlitepln(15)、etshelper(6)、bugreport(9) |
| `ADVAPI32.dll` | EtsUpdate(18，含 `CryptAcquireContextW/CryptHashData/CryptEncrypt`)、shellhelper(12)、mq_server(15)、sevenzip(6)、httphelper(3)、bugreport(11)、ETSShell(3，Event Log) |
| `WS2_32.dll` / `WLDAP32.dll` | EtsUpdate、httphelper、mq_server、shellhelper |
| `SETUPAPI.dll` | shellhelper(4)、soundhelper(4) |
| `HID.DLL` | soundhelper(3) |
| `gdiplus.dll` / `COMCTL32` / `OLEACC` / `IMM32` / `WINSPOOL` | shellhelper、bugreport、EtsUpdate、soundhelper（UI 相关） |
| `WINMM.dll` | 全部插件(1–26)，多为 `timeGetTime`；soundhelper 26 个多媒体 API |
| `ole32.dll` | ETSShell(CoCreateGuid/StringFromGUID2)、EtsUpdate、shellhelper、soundhelper、sevenzip、bugreport |

- **无 `libssl/libcrypto.dll`、无 `crypt32.dll` 动态依赖**：OpenSSL 为**静态链接**（`ETSShell.exe` 与 `httphelper.pln` 内均出现 OpenSSL 1.0.1h/CRYPTOGAMS 汇编函数说明与 `EVP/AES/RC4/SHA/HMAC/ASN.1/BN` 模块说明字符串）。【观察】→ OpenSSL 版本锁定 **1.0.1h (2014-06-05)**（字符串 `EVP part of OpenSSL 1.0.1h 5 Jun 2014` 等）。【观察】
- `EtsUpdate.exe` 走 **Windows CryptoAPI**（`ADVAPI32!CryptAcquireContextW/CryptHashData/CryptEncrypt` + RTTI `MD5_CTX`），与主客户端 OpenSSL 体系不同源。【观察 + 推断】
- `sqlite3.dll` 导出被使用的 `sqlite3_key` 表明本地 DB 具备加密能力（`ETS.db` 是否加密见 `06_data.md`）。【观察】

### 6.2 RTTI 类名（节选，观察，完整见 `work/native/<name>/rtti_classes.json`）

- `ETSShell`（166 类）：`Sti::Core::StiCore`、`Sti::Core::StiCorePlnManager`、`Sti::Adapter::{ClientApp,ClientHandler,ClientSchemeHandler,ClientSchemeHandlerFactory,ClientAppExtensionHandler,RunFileDialogCallback,WindowBase,BrowserWindow}`、`Cef{V8Handler,Client,LifeSpanHandler,LoadHandler,RequestHandler,ResourceHandler,RenderHandler,RenderProcessHandler,DownloadHandler,ContextMenuHandler,DisplayHandler,DragHandler,KeyboardHandler}`、`CppSQLite3{DB,Query,Exception}`、`Json::{CharReader,StreamWriter,Writer,…}`、`_cef_*` 结构体；并含 `CefRunFileDialogCallback`。→ STIC 壳 = 标准 CEF client 实现 + 自研插件管理 + SQLite 文件管理器。【观察】
- `EtsUpdate`（325 类）：`DuiLib::CWindowWnd/IListItemUI`、`HttpHandler`、`CppSQLite3*`、`MD5_CTX`、大量 `std::XH::*`（自研工具库命名空间）。【观察】
- `bugreport`（623 类）：`DuiLib::CWindowWnd/WindowImplBase`、`Sti::SevenZip::ZipHelper`、`CWindowDC`、`IOleInPlace*`；导出表为 gtest/glog C++ 符号。【观察】
- `soundhelper`（173 类）：`Asiafly::SoundUtility::*`（见 §5.7）、`CheckAudioLoader`、`SticPlugins::SoundHelper::SndUtilImpl`、`std::tr1` 绑定器。→ 厂商"亚声/Asiafly"音频库。【观察】
- 其余插件：`CppSQLite3*`、`Json::*`、`base::internal::?A0x????::JSONStringValue`（Chromium base 的 JSON 值类，被静态编译进插件）。【观察】
- `mq_server`：`icu_56::*` 等 Node/V8 依赖符号。【观察】
- 未见 STL 之外的可疑/商业保护类名（无 VMProtect/Themida/授权校验类）。【观察】

### 6.3 关键字符串补充（观察）

- 壳：`NtQueryInformationProcess`、`ShellUtils::ExistProcess`、`CreateToolhelp32Snapshot`、`dumpfile::{GetDumpfilePath,RecordDumpLog,ExceptionFilter,RunBugReport}`、`SetUnhandledExceptionFilter`、`shellupgrade::WinExecAndWait32_Process`、`StiAdapter::{CreateMainBrowser,RunMessageLoop}`、`GetFileContent_WPK`、`\packages\default.upk`、`\Modules\Default.upk`、`upk.client.iflytek.com`、`upk.monitor.iflytek.com`、`upk.default.iflytek.com`、硬编码 `http://10.5.15.29:8080/tss`、`http://10.5.115.29:8080/img`、`4d7f61cc485bea346a988d9cfdf1047f`。
- 壳内嵌 About 页 HTML：`STIC:V3.0.76`、`CEF:76.1.13`、`Chromium:76.0.3809.132`、`Flash:32_28_0_0_161` —— 与随包的 `libcef.dll`（`91.1.22+gc67b5dd+chromium-91.0.4472.124`）**不一致** →【推断】该 About 文案是旧版本遗留、未随内核升级更新；以 `README.txt`/`libcef.dll` 版本资源（CEF 91）为准。【观察 + 推断】
- 壳内 SQL（FileManager/Archive 文件内存库）：`Select SUM(Size) From Archive Where Path='%s'`、`Select * From Archive Where SerialNumber >= %d ...`、`select count(*) from sqlite_master where type='table'...`、`key error, fileName:` → 资源包（`.rpk/.upk`）的文件级随机访问实现。【观察】
- 插件：`[filehelper::OnGetMd5] file is being used`、`[soundhelper::OnCombineAndConvertWavToMp3] arguments:`、`[etshelper::OnEncodeAPIBody] signature generation failed.` 等日志模板，可与 `logs\shell_*.log` 逐行对上（例：`shell_2026-11-4.log:499` 处 `[etshelper::OnEncodeAPIBody] success` 对应二进制字符串）【观察】。

---

## 七、`etshelper.pln` 签名相关原生证据（补充 08_signature.md）

> 08_signature.md 已用日志 333/334 验证算法；此处给出**原生侧独立证据**与产物 `work/native/etshelper/sign_disasm.txt`（含 `OnEncodeAPIBody/OnEncodeAPIResp` 及其被调函数的 capstone 反汇编，字符串与 IAT 已注释）。

1. **导入面**：仅 KERNEL32(135)/USER32(9)/SHELL32(4)/`sqlite3.dll`(6)/WINMM(1)。**无 `crypt32/advapi32/libssl` 导入**，无 `CryptAcquireContext`、无 OpenSSL 说明字符串。【观察】→ 签名所用 MD5 为**插件内静态实现**。
2. **MD5 实现存在（算术证据）**：文件中出现 MD5 初始常量 `0x67452301/0xEFCDAB89/0x98BADCFE/0x10325476`（IV 表位于 RVA `0x6A540`，被 `movaps xmm0,[0x1006a540]` 引用），以及 CRC32 表常量 `0xEDB88320`；**未发现** SHA1/SHA256/HMAC/AES/SM4/TEA/Blowfish 常量，未发现 base64 字母表字符串（`ABCDEFGHIJKLMNOPQRSTUVWXYZ...` 在 etshelper 中 0 次命中，base64 由调用方 JS 完成）。【观察】
3. **签名函数定位**（与 08 表格一致，本文从分发函数正向确认）：
   - `0x1000AA70 PlnOnProcessMessage`（634 指令）：分发 `encode_api_body(_v2)`/`encode_api_resp(_v2)` 等；
   - `0x1000A410 OnEncodeAPIBody`（400 指令）：解析 `time`/`body` 参数 → 限流/参数闸门 → MD5 → 组装返回 JSON → UTF-8 转换 → success 日志；
   - `0x10009E60 OnEncodeAPIResp`（375 指令）：同上（参数 `response`）；
   - `0x10014110` 与 `0x10014230`：两个 MD5 包装（IV 表引用在 `0x10014144`/`0x10014264`，`0x10014154`/`0x10014274` 再次写入 `0x67452301`），分别服务 body 与 resp；
   - `0x100051C0`（437 指令）：组装 v2 返回 JSON，引用字符串簇 `pid`、`202608`（=硬编码 `key_id`）、`key_id`、`sign_version`、`sign`；
   - `0x100050A0`（83 指令）：`MultiByteToWideChar`/`WideCharToMultiByte`（`0xFDE9`=CP_UTF8）UTF-8 转换。
4. **"signature request rejected" 的语义（推断）**：`OnEncodeAPIBody` 在解析参数后先调一个"闸门"函数（`0x10013FC0`，47 指令），其中含 `lock cmpxchg` 全局状态、`GetTickCount`、阈值 `cmp ecx,0x400`（1024）、`cmp edx,0x1000000`（16MB）、冷却 `cmp ..,0x3E8`（1000ms），失败即走 `signature request rejected.` 日志；随后 MD5 环节失败才走 `signature generation failed.`。→【推断】该"request"是**本地请求合法性/频率限制**（防抖/大小上限/1 秒节流），不是网络请求；但 `10_unknowns.md` 可保留"是否存在其它签名服务路径"的验证项。
5. **密钥形态（观察 + 引用）**：明文 `secret/appkey/hmac/key` 字符串在 `etshelper.pln` 中 **0 命中**；密钥为 `.rdata` 查表混淆 + FNV-1a 自校验（`work/scripts/keystream.py` 已验证），08_signature.md §2.2 已给出 v1/v2 派生值。本文独立确认：`.rdata` RVA `0x691C8–0x69310` 一带有 32×uint16 索引表与 0x32/0x3D×4 字节数据表，与 08 描述位置一致。【观察】
6. **运行时佐证**：`logs\shell_2026-11-4.log` 共 192 条 `[etshelper::OnEncodeAPIBody] success`（etshelper.cpp:499）；`logs\ets_2026-11-4.log` 首行 `[I] [API_ETS] ets_sign_protocol_selected protocol=v2, pid=pcWin`，请求参数含 `sign_response:1`。→ 与本插件 v2 分支吻合。【观察】

---

## 八、CEF / STIC 痕迹与安全观察

### 8.1 CEF 与 STIC（观察 + 推断）

- 随包 `README.txt`：CEF `91.1.22+gc67b5dd+chromium-91.0.4472.124`（2021-07-15）；`libcef.dll`/`chrome_elf.dll` 版本资源一致 → **实际内核 = CEF 91 / Chromium 91**。【观察】
- 壳内字符串泄露 CEF 集成点：`CefMessageLoop`、`on_console_message`、`cef_*` 导出名、`client_app.cpp`/`client_handler.cpp`/`client_schema.cpp`/`StiAdapter.cpp` 路径；`Sti::Adapter::*` RTTI 与 `_cef_*_t` 结构体 RTTI 表明使用 **C++ libcef_dll_wrapper（静态）** 集成。【观察】
- 危险命令行开关（字符串原文，是否实际传入需运行时验证）：`--enable-speech-input`、`--enable-media-source`、`--enable-media-stream`、`--allow-running-insecure-content`、`disable-web-security`、`allow-running-insecure-content`、`ignore-certificate-errors`、`enable-gpu-rasterization`、`--force-device-scale-factor`、`register-pepper-plugins`（`plugins\pepflash\pepflashplayer32_28_0_0_161.dll`、`plugins/pepflash/mpvjs.node;application/x-mpvjs`）、`--ppapi-flash-version`、`NetworkService,OutOfBlinkCors,SameSiteByDefaultCookies`。→【推断】壳为兼容老业务放宽了浏览器安全策略；`smoke` 结论是"客户端侧 TLS/同源策略保护不可依赖"。【观察 + 推断】
- `shell.ini` 显示 `DisableGPU=1`、`FullScreen=1`、`ShowTray=0`、`MultiApp=1`（多实例）、`AutoUpgrade=1`、`MsgSize=50`、`AppName=ETSShell.exe`；`HomeUrl=https://statics.ets100.com/ets-student-pc-web/index.html`（远程加载 SPA，见 `04_frontend.md`）。【观察】
- STIC 框架构成：`StiCore`（任务/消息中枢）、`StiCorePlnManager`（插件装载）、`StiAdapter`（CEF 外壳适配）、`StiCorePlugin.h`（插件日志/基类）、`dumpfile`（崩溃转储/拉起 bugreport）、`shellupgrade`（进程升级）、`FileManager`（rpk/upk 内存文件库）、`Sti::SevenZip::ZipHelper`（解包）、自定义节 `.fptable`/`Shared`。→【推断】STIC 是讯飞跨产品复用的"CEF 壳 + 原生插件总线"框架（版本 V3.0.76，产品外壳版本 5.0.91.329）。【观察 + 推断】
- 自定义协议 `stic://<host>/<本地路径>` 把本地文件暴露给 H5（日志 `[H5_SOUND] audioUrl=stic://file.iflytek.com/C:\...mp3`），并由 `ClientSchemeHandler`/`UTClientSchemeHandler` 处理；`GetFileContent_WPK` 说明还支持 WPK 加密包内容读取。【观察 + 推断】

### 8.2 签名与完整性（观察）

| 文件 | Authenticode 目录 | 签名者（解析结果） | 证书/算法 |
|---|---|---|---|
| ETSShell.exe | `rva 0x22DE00, 12384B` | `CN=广州讯飞易听说网络科技有限公司, O=广东省`（Sectigo Public Code Signing CA R36） | sha384/RSA，证书有效期 2023-05-10 → **2026-05-09**（相对分析日期已过期；时间戳反签未验证） |
| Ets.exe | `rva 0x73600, 13248B` | `CN=iFLYTEK Co.,Ltd., OU=云计算研究院, O=iFLYTEK Co.,Ltd., L=Hefei, ST=Anhui, C=CN`（GlobalSign GCC R45 CodeSigning CA 2020） | sha256/RSA，2023-10-30 → 2026-12-18 |
| EtsUpdate.exe | 有（12,328B） | 未解析（文件内可见 Certum/DigiCert 时间戳 CA 字符串） | 未解析 |
| bugreport.exe | 有（12,320B） | 未解析 | 未解析 |
| ets_mq_server.exe | 有（12,328B） | 未解析（推测为 Node.js 官方签名，未验证） | 未解析 |
| **9 个 .pln** | `size=0` | **无签名** | — |

- 全部 `.pln` 未签名，壳加载时**未发现**"校验插件签名/哈希"的代码路径（加载器只有 GetProcAddress + 日志；是否在其它位置校验为【未知】）。→【推断】插件可被本地替换（需管理员权限写入 `Program Files (x86)\ETS`）。
- 所有文件 `.reloc` 未剥离、ASLR/DEP 开启；仅 `etshelper.pln` 开了 CFG。【观察】

### 8.3 反调试/校验（重点澄清）

- **未发现主动反调试**：全部 14 个 PE 都导入 `IsDebuggerPresent`，但这是 MSVC 静态 CRT（`abort/_CrtDbgReport` 路径）的标准导入；未发现 `CheckRemoteDebuggerPresent` 导入，未发现 `NtQueryInformationProcess` 的调用点（该字符串仅出现在壳的 `shell_utils.cpp` 区域，与 `ShellUtils::ExistProcess`/`CreateToolhelp32Snapshot` 相邻，推测用于**进程存在性检测**而非反调试）。【观察 + 推断；"无主动反调试"结论以未定位到调用点为准，标为高置信】
- 未见 `VirtualProtect(..., PAGE_EXECUTE_READWRITE)` + 自解码壳、未见 `TlsCallback` 反调试（bugreport 有 `.tls` 节但为静态 CRT 数据）、未见 `NtSetInformationThread(HideFromDebugger)`、未见时间差检测代码特征。【观察】
- 存在 `VirtualProtectEx`/`WriteProcessMemory`/`OpenProcess` 导入（壳、bugreport）：与 `ExistProcess`、崩溃转储（`MiniDumpWriteDump`）、升级器"等待旧进程退出"等正常用途一致；**未定位到跨进程写入的调用点** → 不排除但无证据。【观察 + 未知】

---

## 九、辅助进程与配套件补充

- **`Ets.exe`（preshell）**：485KB，无导出/无版本资源，PDB `preshell.pdb`，字符串含 `shell.exe`；仅 KERNEL32/USER32/GDI32/SHELL32/SHLWAPI，导入 `ShellExecuteExW`、`CreateProcess*`、`TerminateProcess`、`VirtualProtect`、`LoadLibraryW`。→【推断】预启动器：做环境/更新检查后拉起 `ETSShell.exe`（与 `07_shell_update.md` 启动链一致）。【观察 + 推断】
- **`EtsUpdate.exe`**：DuiLib GUI 更新器（RTTI `DuiLib::CWindowWnd`、`HttpHandler`、`MD5_CTX`），依赖 CryptoAPI + WS2_32/WLDAP32 + gdiplus；导入 `CreateToolhelp32Snapshot/OpenProcess/Reg*`；产品名"E听说更新工具"。签名同族见 `08_signature.md §5`（v1 同族、独立内嵌密钥表）。【观察 + 引用】
- **`bugreport.exe`**：gtest/glog + DuiLib + `dbghelp` + `sqlite3`；`bugreport.ini`（`[CLIENT] error_infos= / show_window=0`、`[TYPE] mode=0`）；由壳 `dumpfile::RunBugReport` 拉起，`show_window=0` 静默上报。【观察 + 推断】
- **`mq_server\ets_mq_server.exe` + `main.js`**：Node.js 5.12.0（官方 node.exe 改名）+ `ws@1.1.2`；`main.js` 是明文实现：从 40001 起找空闲端口、把端口写入 `..\packages\app.json` 的 `suspensionBallPort`、`log4js` 落盘 `..\logs\ets_<date>.log`、`wss.on("connection")` 后 `wss.broadcast(message)` 把**任意客户端消息广播给所有客户端**；`shellhelper` 负责 `startprocess/stopprocess/processexist` 管理它（日志 `OnProcessExist:ets_mq_server.exe`、`OnStopProcess ... {"process_list":["ets_mq_server.exe"]}`）。【观察】
- **崩溃/兜底链**：壳 `SetUnhandledExceptionFilter` → `dumpfile::ExceptionFilter/RecordDumpLog/RunBugReport`；导入 `MiniDumpWriteDump`（dbghelp）+ ADVAPI32 `RegisterEventSourceA/ReportEventA`（写 Windows 事件日志）。【观察】

---

## 十、安全观察汇总（按影响排序）

1. **`mq_server` 无鉴权、监听 `0.0.0.0:40001`，且把收到的所有消息广播给所有 WS 客户端**（`main.js` 明文）；而收到的消息就是前端 `log4js` 的运行日志——历史日志中**包含完整 API 请求/响应、阿里云 STS 临时凭证（`access_key_id=STS.*`、`security_token`）、账号信息（已脱敏）**。→【推断】同一局域网/同一主机的其它进程可连接该端口旁路获取业务数据与临时凭证（STS 有过期时间）；属真实暴露面。【观察 + 推断】
2. 壳启用 `ignore-certificate-errors`、`disable-web-security`、`allow-running-insecure-content` 等开关（字符串级证据）→ 客户端侧 TLS/同源保护不可依赖。【观察 + 推断】
3. 签名密钥（v1/v2）内嵌于 `etshelper.pln`，可静态提取（`08_signature.md` 已 333/334 验证）→ 签名只防"随手改包"。【观察/引用】
4. 插件全部未签名且加载前无校验证据 → 本地提权后可替换插件（`Program Files (x86)` 需管理员写入）。【观察 + 推断】
5. 前端 bundle 内置 **RSA 私钥 PEM**（`08_signature.md §6`）——比原生层更严重的问题，已在 08 记录。【引用】
6. 壳/`Ets.exe` 的代码签名证书时间：ETSShell 证书 2026-05-09 过期（当前 2026-11），iFLYTEK 证书 2026-12-18 有效；时间戳有效性未验证。【观察 + 未知】
7. PDB 路径、内网 IP（`10.5.15.29/10.5.115.29`）、内部域名（`upk.*.iflytek.com`）泄露构建/内网信息。【观察】
8. 未发现主动反调试、未发现插件完整性校验、未发现本地授权/计费校验逻辑（原生层只提供能力，业务鉴权全部在服务端 + 前端）。【观察 + 高置信推断】

---

## 十一、未知项与建议验证

| # | 未知项 | 现状 | 建议验证 |
|---|---|---|---|
| N1 | `PlnOnProcessMessage` 四个参数的精确语义/顺序 | 由栈帧使用推断为 `(actionKey, argsJson, callbackId, out)` | 读 `09_decompiled.md` 的 C 伪代码逐参数确认；或对 `appcontroller` 做一次受控调用 |
| N2 | `PlnSetParam` 是否还有 `LOG` 之外的注入键 | 观察到 `LOG/WLOG/EXEC_CALLBACK` 三个字符串 | Ghidra 交叉引用 `StiCorePlnManager` 全量 GetProcAddress 列表 |
| N3 | 插件以 `.pln` 扩展名被 `LoadLibrary` 时是否有额外内存映射/校验 | 加载器仅见 GetProcAddress | 断点/日志方式观察 LoadLibrary 调用参数（不修改目标） |
| N4 | Rich header 每个 prodid 对应的 VS 版本 | 只有 build 号 | 与 richprint 公共映射表逐一比对 |
| N5 | `EtsUpdate/bugreport/mq_server` 的签名者主体 | 仅知有 PKCS#7 | 用 REA `inspect_pe_certificates` 解析（本次未做，输出较大） |
| N6 | `GetAsyncKeyState/SetWindowsHookExW` 的实际调用点 | 仅见导入 | Ghidra 交叉引用确认是否来自 DuiLib/输入法库 |
| N7 | 壳是否在别处校验插件哈希/版本 | 加载器未见 | 搜索 `CryptHashData`/文件校验相关导入（ETSShell 无 crypt32，需看自研实现） |
| N8 | `stic://` 协议对任意本地路径的访问边界 | 见日志可读 `C:\Users\***\*.mp3` | 分析 `ClientSchemeHandler` 的路径校验逻辑（在 Ghidra） |

---

## 十二、产物索引（全部在 `work/native/`）

| 路径 | 内容 |
|---|---|
| `work/native/_summary.json` | 14 个二进制一行摘要（大小/时间戳/链接器/熵/导出/导入/PDB） |
| `work/native/_overview.md` | 自动生成的逐二进制详情（节区、Rich、RTTI、导入、action） |
| `work/native/plugin_abi.json` | 9 插件 ABI 汇总（导出+action+导入+日志方法+PDB） |
| `work/native/<name>/exports.json` `imports.json` `strings.txt` `meta.json` | 每个二进制的导出/导入/关键字符串/完整元数据（strings 已去重、限 3000 行） |
| `work/native/<plugin>/dispatch.json` | `PlnOnProcessMessage` 反汇编统计 + 字符串引用 + action 候选 + 各函数日志方法 |
| `work/native/<plugin>/disasm_plnonprocessmessage.txt` | 分发函数全量注释反汇编（capstone） |
| `work/native/etshelper/sign_disasm.txt` `sign_funcs.json` | 签名路径函数注释反汇编与函数摘要（含 `OnEncodeAPIBody`/`OnEncodeAPIResp` 调用树） |
| `work/native/ETSShell/plugin_loader_disasm.txt` | `StiCorePlnManager` 装载/设参/分发函数注释反汇编 |
| `work/native/ETSShell/js_bridge_full.js` | 从壳 `.rdata` 提取的注入 JS（17 个 native 函数全文） |
| `work/native/ETSShell/js_bridge.txt` | 壳 `.rdata` 字符串窗口（CEF 开关/日志/dumpfile/upk 等） |
| `work/native/appcontroller/abi_stubs.txt` | ABI 空桩与 `PlnSetParam` 证据反汇编 |
| `work/native/_logs_excerpt.txt` | 从 `ETS\logs` 抽取的插件/action/签名/mq 证据行 |
| `work/native/_tools/` | 本次使用的脚本：`pe_scan.py`（PE 全量扫描）、`disasm_tool.py`（插件分发反汇编）、`sig_dump.py`（函数边界+调用树）、`func_dump.py`、`peek.py`、`summarize.py`、`plugin_abi.py`（配套 `pylib/`：pefile 2024.8.26 + capstone 5.0.9） |

> 工具说明：REA MCP 的 `inspect_native_exports` 已用于交叉验证 `etshelper.pln` 导出表（4 项、RVA 与本文一致）；`inspect_pe_certificates` 用于 `ETSShell.exe`/`Ets.exe` 签名解析。**REA 内置 `inspect_with_objdump` 在本机不可用**（未安装 GNU objdump，工具返回 `capability_unavailable`），因此本文反汇编均由 capstone 5.0.9 递归下降生成，非 GNU objdump 文本（输出格式不同，但指令与地址来自同一 PE）。

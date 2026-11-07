# 01 目标识别与文件清单

> **前置条件**：Windows 10/11 x64；Python 3.10+；可选 Node.js 18+（阅读/运行 `mq_server` 与前端 JS）；可选 7-Zip（解包 zip/7z）。
> **如何复现**：在仓库根目录执行 `python scripts/<脚本名>.py`；机读数据在 `data/`，运行时证据在 `runtime/`；分析对象为只读安装副本 `<ETS_INSTALL_DIR>`（全程不修改其中文件）。
> **占位符**：`<ETS_INSTALL_DIR>`=目标程序安装目录；`<APPDATA_ETS>`=`%APPDATA%\ETS`；`<WORK_DIR>`=原分析工作区；`<BUILD_ROOT>`=厂商构建机路径前缀（二进制/日志内嵌字符串原文，仅作证据）。
> **本文复核**：`python scripts/hashes.py`（关键文件 SHA-256 复核）。

## 一、目标识别

### 1.1 产品与版本

| 事实 | 值 | 证据 |
|---|---|---|
| 产品 | 讯飞易听说「E听说」学生端 PC 版 | `shell.ini` → `AppTitle=E听说`；`ETSShell.exe` 版本资源 `ProductName=CCS, CompanyName=iflytek` |
| 客户端版本 | **5.7.9** | `localdata\ETS.db` → Table `Config`，`Section=System, Entry=C_Version, Value=5.7.9` |
| 更新版本号 | 5079 | 同上 `Update_Version` |
| 环境 | 正式（EnvType=1） | 同上 `EnvType`，注释"1-正式, 2-灰度, 3-测试" |
| 外壳版本 | 5.0.91.329 | `ETSShell.exe` VS_VERSION_INFO |
| 壳框架 | **STIC V3.0.76** | `ETSShell.exe` 字符串：`<html>...STIC:</td><td >V3.0.76</td>`；`About Version` 对话框 |
| CEF/Chromium | CEF 91.1.22+gc67b5dd / Chromium 91.0.4472.124 | `README.txt`；`libcef.dll` 版本资源 |
| 前端地址 | `https://statics.ets100.com/ets-student-pc-web/index.html` | `shell.ini` `[HomeUrl] URL=` |
| 日志总线 | `mq_server`，端口 **40001** | `logs\ets_*.log` 第 1 行 `mq_server running! port is 40001`；`packages\app.json` `{"suspensionBallPort":40001}` |

### 1.2 识别依据（二进制内残留）

`ETSShell.exe` 中保留了完整的开发路径与调试信息（未加壳、未混淆）：

```
<BUILD_ROOT>\STIC\stic-pro_ets\src\shell\shell.cpp
<BUILD_ROOT>\STIC\stic-pro_ets\src\adapter\StiAdapter.cpp
<BUILD_ROOT>\STIC\stic-pro_ets\src\adapter\ClientAppHandler.h
<BUILD_ROOT>\STIC\stic-pro_ets\src\adapter\cefclient\client_app.cpp
<BUILD_ROOT>\STIC\stic-pro_ets\src\adapter\cefclient\client_handler.cpp
<BUILD_ROOT>\STIC\stic-pro_ets\src\base\logging.cc
<BUILD_ROOT>\STIC\stic-pro_ets\src\base\json\string_escape.cc
<BUILD_ROOT>\STIC\stic-pro_ets\src\cef-custom-schema\client_schema.cpp
<BUILD_ROOT>\STIC\stic-pro_ets\src\common\StiCorePlugin.h
<BUILD_ROOT>\STIC\stic-pro_ets\src\commonlib\{dumpfile,shell_utils,shell_upgrade,shell_string,str_coding,shell_file}.cpp
<BUILD_ROOT>\STIC\stic-pro_ets\src\core\{StiCore,StiCorePlnManager}.cpp
<BUILD_ROOT>\STIC\stic-pro_ets\src\third_party\filememory\FileManager.cpp
<BUILD_ROOT>\STIC\stic-pro_ets\_bin\ETSShell.pdb
```

RTTI 类名（`.?AV...`）保留了 C++ 类型：`Sti::Core::StiCore`、`Sti::Core::StiCorePlnManager`、`Adapter::ClientSchemeHandlerFactory`、`Adapter::UTClientSchemeHandler`、`Adapter::ClientSchemeHandler`、`CefSchemeHandlerFactory` 等。【观察】

### 1.3 安装形态

- `logs\ets_*.log` 中的路径均指向 `<ETS_INSTALL_DIR>\...`（例如 `soundfiles\public_*.xml` 写入路径），说明该分析副本是 **默认安装目录树的完整拷贝**。
- 补充：历史评估已核对 `ETSShell.exe / libcef.dll / Ets.exe` 与 `<ETS_INSTALL_DIR>` 下同名文件字节一致。

---

## 二、目录结构

```
<ETS_INSTALL_DIR>\
├─ ETSShell.exe            2.19MB  STIC 壳主程序（CEF browser 进程）
├─ Ets.exe                 0.46MB  启动器（拉起 ETSShell + mq_server 等）
├─ EtsUpdate.exe           1.98MB  更新器
├─ Uninstall.exe           1.66MB  卸载器
├─ libcef.dll            126.55MB  CEF 91 二进制
├─ *.pak / *.bin / *.dat            CEF 资源、V8 快照、ICU 数据
├─ shell.ini               376B    壳配置（HomeUrl/窗口/日志/升级）
├─ README.txt / LICENSE.txt         CEF 发行说明与许可证
├─ 7z.dll / lame.exe / sqlite3.dll  第三方运行库
├─ bugreport\              8.04MB  崩溃/埋点上报工具（含 BuryPoint.db、MainUI.xml）
├─ ffmpeg\                50.64MB  ffmpeg.exe + process_ori.bat（音频转码）
├─ localdata\ETS.db        12KB    客户端配置 SQLite
├─ locales\               20.94MB  53 个 CEF 语言包（含 zh-CN）
├─ logs\                  29.79MB  cef_/ets_/shell_ 各两份历史日志
├─ mq_server\             12.22MB  Node.js WS 日志总线（main.js + node_modules + SEA exe）
├─ packages\               2.45MB  app.json、appcontroller.js、error.html、测试音频
├─ plugins\                9.53MB  9 个原生插件（.pln，32 位 DLL）
├─ soundfiles\             4.03MB  36 组评测音频（mp3 + spx + xml）
├─ SQL\ETS.db.sql                   ETS.db 的建库脚本（GBK）
├─ swiftshader\            2.64MB  软件渲染 DLL
└─ temp\                  41.64MB  CEF 用户数据（Cache/Code Cache/IndexedDB/LocalStorage/Cookies）、
                                    资源包（common.zip、content_*.zip、template_686.zip、pc_xst_dict.zip）、
                                    EtsUpdate.exe、update\log\INFO_uLOG_*
```

按扩展名的体量分布（前 10）：

| 扩展名 | 数量 | 总大小 |
|---|---|---|
| .dll | 16 | 146.82 MB |
| .exe | 9 | 74.21 MB |
| .log | 12 | 30.88 MB |
| .pak | 56 | 29.64 MB |
| (无扩展名) | 206 | 13.64 MB |
| .zip | 30 | 13.30 MB |
| .ldb | 13 | 11.63 MB |
| .dat | 1 | 9.93 MB |
| .pln | 9 | 9.53 MB |
| .spx | 36 | 2.50 MB |

---

## 三、关键文件指纹（SHA-256）

完整清单见 `data/inventory.json（未随仓库发布）`（667 条）与 `data/inventory_hashes.json`（关键文件）。

| 文件 | 大小 | SHA-256（前 32 位） |
|---|---|---|
| ETSShell.exe | 2,297,440 | `2dbdc3248538f2b0a7879b1806ad02fe…` |
| Ets.exe | 485,824 | `38b0865cf805dfe211a10e63c719ea5c…` |
| EtsUpdate.exe | 2,079,784 | `6ecd0568d8bbe7f176e3f8e0ce71b18c…` |
| Uninstall.exe | 1,741,527 | `34394745af16d990f7d71eebc9d2044d…` |
| libcef.dll | 132,696,576 | `306de5b27f38f3582a47067429bc3719…` |
| plugins\etshelper\etshelper.pln | 497,664 | `accb7e462a292b4cc143b0c4cf85eece…` |
| plugins\httphelper\httphelper.pln | 1,730,560 | `49f00a8dd15944d929548159e2eca51d…` |
| plugins\soundhelper\soundhelper.pln | 3,175,936 | `52c4e5d923cb0e873e9d15952d163a19…` |
| plugins\shellhelper\shellhelper.pln | 2,117,632 | `73b0e0f708607fd29814eef707e26972…` |
| plugins\filehelper\filehelper.pln | 674,304 | `d83f497de20a946062f92af274cb77a2…` |
| plugins\appcontroller\appcontroller.pln | 552,448 | `c90f70338cbc39446ae5bfb2d47263f7…` |
| plugins\sevenzip\sevenzip.pln | 467,456 | `00a7d17d6c4ea737710ec65efd59396a…` |
| plugins\window_control\window_control.pln | 436,736 | `be0ca19b45fa6ba178754506b2bcdfc4…` |
| plugins\sqlitepln\sqlitepln.pln | 345,088 | `77cefe026ce01e06e90b249f0aecd193…` |
| mq_server\ets_mq_server.exe | 12,080,168 | `0d38ecdbc42c54c42ba36f0a60c3260c…` |
| bugreport\bugreport.exe | 3,614,240 | `090a5ef72d75783af4b96deffb56160c…` |
| localdata\ETS.db | 12,288 | `0301422dfef7ebe811bb2a8c2b8e9f7a…` |

---

## 四、`temp\Cache_ETSShell` 内的前端资产（原始载荷）

`temp\Cache_ETSShell\Cache\f_*` 是 Chromium Simple Cache 的正文文件，其中包含可直接还原的前端资源：

| 文件 | 大小 | 内容 |
|---|---|---|
| f_000001 | 375 KB | gzip → 1.15 MB **CSS**（Element Plus + 业务样式） |
| f_000002 | 3.48 MB | **主 JS bundle（原始未压缩）**：Vue3 + Element Plus + 业务代码 |
| f_000003 | 49 KB | JS chunk |
| f_00000b/0e/0f/12/14/16/17/18/19/1b/1d | 18–75 KB | 懒加载 JS chunk（`import{...}` / `var choo...` / `var D1=...`） |
| f_00001a/1c | 75/94 KB | 未压缩库文件（注释头 `/*! ... */`） |
| f_000029 | 24 KB | JSON |
| f_000006/08/09/0a/0c/0d/10/11/13/1f/20/21/2a/2b | 18–87 KB | PNG 图片 |
| f_00002c–f_000030 | 17–24 KB | JPEG 图片 |
| f_000015 | 20 KB | GIF |
| 其余 gzip | 15–702 KB | 图片/字体/JSON/CSS |

前端代码特征：`vue`（474 处）、`element-plus`（6 处）、`pinia`（10 处）、`vue-router`（1 处）、`axios`（32 处）、`cef.message`（2 处）。→ 技术栈为 **Vue 3 + Element Plus + Pinia + Vue Router + axios**。【观察】

---

## 五、证据索引

| 主题 | 证据位置 |
|---|---|
| 版本/环境 | `localdata\ETS.db` → Config |
| 壳配置 | `shell.ini` |
| 壳框架/CEF 版本 | `README.txt`、`ETSShell.exe` 字符串、`libcef.dll` 版本资源 |
| 前端 URL | `shell.ini` `[HomeUrl]` |
| 前端 bundle | `temp\Cache_ETSShell\Cache\f_*`、`Code Cache\js\*` |
| 完整网络流量 | `logs\ets_2026-10-28.log`、`logs\ets_2026-11-4.log` |
| 壳/插件运行日志 | `logs\shell_2026-10-28.log`、`logs\shell_2026-11-4.log`（GBK） |
| CEF 日志 | `logs\cef_2026-10-28.log`、`logs\cef_2026-11-4.log` |
| 更新日志 | `temp\update\log\INFO_uLOG_*` |
| 题库/模板资源 | `temp\resources\*.zip`、`temp\resources\{747716,747725,747726}\*` |
| 评测音频 | `soundfiles\public_*_{mp3,spx,xml}` |
| 插件 | `plugins\*\*.pln` |

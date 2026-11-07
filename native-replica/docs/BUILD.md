# 构建与运行（native-replica）

已验证环境（本机）：

| 组件 | 位置/版本 |
|---|---|
| MSVC | `C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools`（MSVC 14.51.36231，x64） |
| Windows SDK | 10.0.26100（VS BuildTools 自带） |
| CMake | `C:\rea_tools\pylibs\cmake\data\bin\cmake.exe`（4.4.x，pip 安装） |
| Ninja | `C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ninja.exe`（winget） |
| WebView2 SDK | `C:\rea_tools\webview2\build\native`（NuGet 1.0.4314.35） |
| WebView2 Runtime | Windows 内建（Edge WebView2 156/157） |
| Node / pnpm | Node 24 / pnpm 12 |
| 第三方（已 vendored） | `third_party/include/json.hpp`、`third_party/sqlite3.c/h`、`third_party/miniz.c/h` |

> 若在其他机器构建：安装 VS2022/2026 BuildTools（C++ 桌面负载）+ Windows SDK；把 CMake/Ninja 路径改成你的；
> WebView2 SDK 从 NuGet 下载 `Microsoft.Web.WebView2` 并解压，`-DWEBVIEW2_SDK=<解压目录>/build/native`。

## 一键构建

```powershell
cd <repo>/native-replica
pwsh -File build.ps1
```

脚本做的事：
1. `VsDevCmd.bat -arch=x64` 设置 MSVC 环境
2. `cmake -S . -B C:\ets-rea-build -G Ninja -DCMAKE_BUILD_TYPE=Release`
3. `cmake --build C:\ets-rea-build`（shell + 7 个插件 DLL）
4. `pnpm -C frontend install --store-dir C:\rea_tools\pnpm-store` + `pnpm -C frontend build`
5. 复制 `frontend/dist` → `bin/assets/web`；复制 `mq_server` → `bin/mq_server` 并 `npm install`
6. 产物：`C:\ets-rea-build\bin\EtsReplica.exe`

跳过前端（只编译原生）：

```powershell
pwsh -File build.ps1 -SkipFrontend
```

## 手动分步

```powershell
$vs = "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat"
$cmake = "C:\rea_tools\pylibs\cmake\data\bin\cmake.exe"
$ninja = (Get-Command ninja).Source

cmd /c "call ""$vs"" -arch=x64 >nul && ""$cmake"" -S . -B C:\ets-rea-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM=""$ninja"""
cmd /c "call ""$vs"" -arch=x64 >nul && ""$cmake"" --build C:\ets-rea-build --parallel"
```

只编译某个目标：

```powershell
cmd /c "call ""$vs"" -arch=x64 >nul && ""$cmake"" --build C:\ets-rea-build --target plugin_etshelper --parallel"
```

## 运行

```
C:\ets-rea-build\bin\EtsReplica.exe
```

- 前端从 `bin\assets\web` 经虚拟主机 `https://app.ets.local` 加载
- 数据目录 `%APPDATA%\ETS-Replica`（缓存/日志/WebView2 profile）
- 日志 `%APPDATA%\ETS-Replica\logs\ets_YYYY-M-D.log`（同时尝试发 mq_server:40001）
- 可选 `bin\shell.ini`：

```ini
AppName=E听说 · 复刻版
HomeUrl=
WindowWidth=1280
WindowHeight=800
DataDir=
LogLevel=1
```

## 常见问题

| 现象 | 处理 |
|---|---|
| `cmake.exe ... ModuleNotFoundError` | 用了 `C:\rea_tools\pylibs\bin\cmake.exe`（pip shim）；改用 `C:\rea_tools\pylibs\cmake\data\bin\cmake.exe` |
| 找不到 `WebView2.h` | `-DWEBVIEW2_SDK=<...>/build/native` 指向不对；目录下应有 `include/WebView2.h` 与 `x64/WebView2LoaderStatic.lib` |
| 运行时白屏 | `bin\assets\web\index.html` 是否存在；`shell.ini` 的 HomeUrl 是否为空 |
| 插件加载失败 | 插件必须在 `bin\plugins\<name>\<name>.dll`；用 `dumpbin /exports` 确认 4 个导出 |
| 音频无法播放 | 确认 `media_server` 已启动且 `__core/media_url` 返回 `http://127.0.0.1:<port>/media?...` |
| mq_server 未启动 | 需要 `bin\mq_server\node_modules\ws`；可先 `npm install`，或忽略（日志会降级为本地文件） |

# 构建与运行（native-replica）

## 1. 已验证环境

| 组件 | 要求 / 已验证值 |
|---|---|
| MSVC | VS BuildTools（C++ 桌面负载），MSVC 14.4x+ x64；本机为 14.51.36231 |
| Windows SDK | 10.0.26100+（BuildTools 自带） |
| CMake | ≥3.25（本机 4.4.x） |
| Ninja | 任意较新版本（`winget install Ninja-build.Ninja` 或 VS 自带） |
| WebView2 SDK | NuGet `Microsoft.Web.WebView2`（本机 1.0.4314.35），cmake 参数 `-DWEBVIEW2_SDK=<解压目录>/build/native` |
| WebView2 Runtime | Win10/11 一般已内建；否则装 Evergreen Runtime |
| Node / pnpm | Node 18+（本机 24）/ pnpm 10+ |
| 第三方（已 vendored） | `third_party/include/json.hpp`、`third_party/sqlite3.c/h`、`third_party/miniz.c/h`、`third_party/speex` |
| ffmpeg（可选） | 录音上传回传用；放到 `<BUILD_DIR>\bin\tools\ffmpeg.exe`，或设置 `ETS_FFMPEG` |

本仓库不包含 MSVC/CMake/Ninja/WebView2 SDK 的二进制；`build.ps1` 会从环境变量或 PATH 查找工具，
也可直接调用 `cmake`。示例占位符：`<VS_BUILDTOOLS>`、`<BUILD_DIR>`、`<WEBVIEW2_SDK>`、`<NINJA>`。

## 2. 一键构建

```powershell
cd <REPO_ROOT>\native-replica
pwsh -File build.ps1
```

脚本做的事：

1. `VsDevCmd.bat -arch=x64` 设置 MSVC 环境
2. `cmake -S . -B <BUILD_DIR> -G Ninja -DCMAKE_BUILD_TYPE=Release -DWEBVIEW2_SDK=<WEBVIEW2_SDK>`
3. `cmake --build <BUILD_DIR> --parallel`（壳 + 8 个插件 DLL，含 speex 静态库）
4. `pnpm -C frontend install` + `pnpm -C frontend build`
5. 复制 `frontend/dist` → `<BUILD_DIR>\bin\assets\web`；复制 `mq_server` → `bin\mq_server` 并安装 `ws`
6. 产物：`<BUILD_DIR>\bin\EtsReplica.exe`

跳过前端（只编译原生）：

```powershell
pwsh -File build.ps1 -SkipFrontend
```

## 3. 手动分步（排查用）

```powershell
# 1) 设置 MSVC 环境（路径按本机 VS 安装调整）
$vs = "<VS_BUILDTOOLS>\Common7\Tools\VsDevCmd.bat"
$cmake = "cmake"          # 或 CMake 安装目录下的 cmake.exe
$ninja = (Get-Command ninja).Source
$sdk = "<WEBVIEW2_SDK>"

cmd /c "call ""$vs"" -arch=x64 >nul && ""$cmake"" -S . -B <BUILD_DIR> -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM=""$ninja"" -DWEBVIEW2_SDK=""$sdk"""
cmd /c "call ""$vs"" -arch=x64 >nul && ""$cmake"" --build <BUILD_DIR> --parallel"
```

只编译某个目标：

```powershell
cmd /c "call ""$vs"" -arch=x64 >nul && ""$cmake"" --build <BUILD_DIR> --target plugin_etshelper --parallel"
# 插件目标：plugin_etshelper / plugin_filehelper / plugin_httphelper / plugin_sqlitepln /
#          plugin_shellhelper / plugin_sevenzip / plugin_sysconfig / plugin_soundhelper
```

## 4. 运行

```
<BUILD_DIR>\bin\EtsReplica.exe
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

- 调试端口：设置环境变量 `ETS_REPLICA_DEBUG_PORT=9333` 后，`http://127.0.0.1:9333/json/list` 可接 CDP。
- 录音上传所需 ffmpeg：`<BUILD_DIR>\bin\tools\ffmpeg.exe`，或环境变量 `ETS_FFMPEG=<ffmpeg.exe 路径>`。

## 5. 常见问题

| 现象 | 处理 |
|---|---|
| `cmake.exe ... ModuleNotFoundError` | 用了 pip 的 cmake shim；直接安装官方 CMake 或用 VS 自带 cmake |
| 找不到 `WebView2.h` | `-DWEBVIEW2_SDK=<...>/build/native` 指向不对；目录下应有 `include/WebView2.h` 与 `x64/WebView2LoaderStatic.lib` |
| 运行时白屏 | `bin\assets\web\index.html` 是否存在；`shell.ini` 的 HomeUrl 是否为空 |
| 插件加载失败 | 插件必须在 `bin\plugins\<name>\<name>.dll`；用 `dumpbin /exports` 确认 4 个导出 |
| 日志显示 `loaded 7/8` | `soundhelper` 未生成/未复制；重新构建 `plugin_soundhelper` |
| 音频无法播放 | 确认 `media_server` 已启动且 `__core/media_url` 返回 `http://127.0.0.1:<port>/media?...` |
| 录音面板提示“无法打开麦克风” | WebView2 运行时需允许麦克风；壳已自动授权，若被系统隐私设置拦截请在 Windows 设置中允许 |
| “上传并回传成绩”提示缺少 ffmpeg | 按上文放置 `bin\tools\ffmpeg.exe` 或设置 `ETS_FFMPEG` |
| 回传失败 `登录状态已失效` | 副本 token 过期/被官方客户端顶掉，重新登录（单会话策略） |
| mq_server 未启动 | 需要 `bin\mq_server\node_modules\ws`；可先 `npm install`，或忽略（日志会降级为本地文件） |

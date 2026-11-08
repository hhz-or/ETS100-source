# Build script for native-replica (MSVC + Ninja + Vite)
# Usage: pwsh -File build.ps1 [-SkipFrontend] [-BuildDir <dir>]
# 环境变量（可选）：WEBVIEW2_SDK、VSDEVCMD、ETS_CMAKE、ETS_NINJA、PNPM_STORE
param(
  [switch]$SkipFrontend,
  [string]$BuildDir = ""
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $BuildDir) { $BuildDir = Join-Path $root "build" }

# --- Visual Studio 环境 ---
$vs = $env:VSDEVCMD
if (-not $vs -or -not (Test-Path $vs)) {
  $candidates = @()
  foreach ($base in @("$env:ProgramFiles\Microsoft Visual Studio", "${env:ProgramFiles(x86)}\Microsoft Visual Studio")) {
    if (Test-Path $base) {
      $candidates += Get-ChildItem $base -Recurse -Filter VsDevCmd.bat -ErrorAction SilentlyContinue
    }
  }
  if ($candidates.Count -gt 0) { $vs = $candidates[0].FullName }
}
if (-not $vs -or -not (Test-Path $vs)) { throw "VsDevCmd.bat 未找到：请安装 VS BuildTools（C++ 桌面负载），或用 VSDEVCMD 指定" }

# --- CMake / Ninja ---
$cmake = $env:ETS_CMAKE
if (-not $cmake) {
  $cmd = Get-Command cmake -ErrorAction SilentlyContinue
  if ($cmd) { $cmake = $cmd.Source }
}
if (-not $cmake -or -not (Test-Path $cmake)) { throw "cmake 未找到：安装 CMake>=3.25，或用 ETS_CMAKE 指定" }

$ninja = $env:ETS_NINJA
if (-not $ninja) {
  $cmd = Get-Command ninja -ErrorAction SilentlyContinue
  if ($cmd) { $ninja = $cmd.Source }
}
if (-not $ninja -or -not (Test-Path $ninja)) { throw "ninja 未找到：winget install Ninja-build.Ninja，或用 ETS_NINJA 指定" }

# --- WebView2 SDK ---
$sdk = $env:WEBVIEW2_SDK
if (-not $sdk) {
  throw "WEBVIEW2_SDK 未设置：下载 NuGet Microsoft.Web.WebView2 并解压，然后 set WEBVIEW2_SDK=<解压目录>\build\native"
}

Write-Host "== configure =="
$cfg = "call `"$vs`" -arch=x64 >nul && `"$cmake`" -S `"$root`" -B `"$BuildDir`" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM=`"$ninja`" -DWEBVIEW2_SDK=`"$sdk`""
cmd /c $cfg
if ($LASTEXITCODE -ne 0) { throw "cmake configure failed" }

Write-Host "== build native =="
cmd /c "call `"$vs`" -arch=x64 >nul && `"$cmake`" --build `"$BuildDir`" --parallel"
if ($LASTEXITCODE -ne 0) { throw "native build failed" }

$bin = Join-Path $BuildDir "bin"
New-Item -ItemType Directory -Force -Path (Join-Path $bin "assets\web") | Out-Null

if (-not $SkipFrontend) {
  Write-Host "== frontend =="
  Push-Location (Join-Path $root "frontend")
  try {
    if (-not (Test-Path "node_modules")) {
      $pnpmArgs = @("install")
      if ($env:PNPM_STORE) { $pnpmArgs += @("--store-dir", $env:PNPM_STORE) }
      & pnpm @pnpmArgs
      if ($LASTEXITCODE -ne 0) { throw "pnpm install failed" }
    }
    pnpm run build
    if ($LASTEXITCODE -ne 0) { throw "vite build failed" }
  } finally { Pop-Location }
}

$dist = Join-Path $root "frontend\dist"
if (Test-Path $dist) {
  Write-Host "== copy frontend dist =="
  Copy-Item (Join-Path $dist "*") (Join-Path $bin "assets\web") -Recurse -Force
}

Write-Host "== mq_server =="
$mqSrc = Join-Path $root "mq_server"
$mqDst = Join-Path $bin "mq_server"
if (Test-Path $mqSrc) {
  New-Item -ItemType Directory -Force -Path $mqDst | Out-Null
  Copy-Item (Join-Path $mqSrc "*.js"),(Join-Path $mqSrc "package.json") $mqDst -Force -ErrorAction SilentlyContinue
  Push-Location $mqDst
  try {
    if (-not (Test-Path "node_modules\ws")) {
      npm install --omit=dev --no-audit --no-fund | Out-Null
    }
  } finally { Pop-Location }
}

Write-Host "== done =="
Write-Host "exe: $bin\EtsReplica.exe"
Write-Host "run: $bin\EtsReplica.exe"

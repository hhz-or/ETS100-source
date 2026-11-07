# Build script for native-replica (MSVC + Ninja + Vite)
# Usage: pwsh -File build.ps1 [-SkipFrontend]
param(
  [switch]$SkipFrontend,
  [string]$BuildDir = "C:\ets-rea-build"
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$vs = "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path $vs)) {
  $cand = Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio" -Recurse -Filter VsDevCmd.bat -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($cand) { $vs = $cand.FullName }
}
if (-not (Test-Path $vs)) { throw "VsDevCmd.bat not found" }
$cmake = "C:\rea_tools\pylibs\cmake\data\bin\cmake.exe"
if (-not (Test-Path $cmake)) { $cmake = "C:\rea_tools\pylibs\bin\cmake.exe" }
$ninja = (Get-Command ninja -ErrorAction SilentlyContinue).Source
if (-not $ninja) { $ninja = "C:\rea_tools\pylibs\bin\ninja.exe" }
if (-not (Test-Path $cmake)) { throw "cmake not found at $cmake" }

Write-Host "== configure =="
$cfg = "call `"$vs`" -arch=x64 >nul && `"$cmake`" -S `"$root`" -B `"$BuildDir`" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM=`"$ninja`""
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
      pnpm install --store-dir C:\rea_tools\pnpm-store
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

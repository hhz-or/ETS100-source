# ETS 练习抓包 · 一键启动
# 用法：pwsh -File capture\run_capture.ps1 [-OutDir <dir>] [-Cdp http://127.0.0.1:10086]
param(
  [string]$OutDir = "",
  [string]$Cdp = "http://127.0.0.1:10086"
)
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $OutDir) {
  $OutDir = Join-Path $here ("runs\" + (Get-Date -Format "yyyyMMdd_HHmmss"))
}
$OutDir = [IO.Path]::GetFullPath($OutDir)
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Write-Host "输出目录: $OutDir"
Write-Host "CDP 端点: $Cdp"

$ets = Get-Process ETSShell -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle }
if (-not $ets) {
  Write-Warning "未检测到「E听说」主窗口进程。请先启动官方客户端并确认窗口可见。"
}

$procs = @()
function Start-Child($name, $exe, $argList, $log) {
  $p = Start-Process -FilePath $exe -ArgumentList $argList -RedirectStandardOutput (Join-Path $OutDir $log) -RedirectStandardError (Join-Path $OutDir ($log -replace '\.log$', '.err.log')) -PassThru -WindowStyle Hidden
  $script:procs += @{ name = $name; p = $p }
  return $p
}

Write-Host "启动 cdp / native / logs / files 四个采集器..."
Start-Child "cdp" "node" @("`"$here\cdp_capture.js`"", "`"$OutDir`"", "`"$Cdp`"") "cdp.log" | Out-Null
Start-Child "native" "python" @("`"$here\native_capture.py`"", "`"$OutDir`"") "native.log" | Out-Null
Start-Child "logs" "python" @("`"$here\log_tail.py`"", "`"$OutDir`"") "logs.log" | Out-Null
Start-Child "files" "python" @("`"$here\files_watch.py`"", "`"$OutDir`"") "files.log" | Out-Null

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "================ 现在请做一次【真实练习】 ================" -ForegroundColor Yellow
Write-Host "建议流程（约 3-5 分钟）："
Write-Host "  1) 进入「我的作业」→ 点「开始练习」"
Write-Host "  2) 按页面提示录音（对着麦克风朗读/作答），等待即时评分出来"
Write-Host "  3) 如需，再进一次「套卷练习」或模拟考试"
Write-Host "  4) 完成/提交作业（如果页面有提交按钮）后回到这里"
Write-Host "=========================================================" -ForegroundColor Yellow
Write-Host ""
Read-Host "练习结束后按 Enter 停止抓包"

foreach ($c in $procs) {
  try { Stop-Process -Id $c.p.Id -Force -ErrorAction SilentlyContinue } catch {}
}
Start-Sleep -Seconds 1
$done = @{ done = (Get-Date).ToString("o"); outDir = $OutDir } | ConvertTo-Json
$done | Out-File -Encoding utf8 (Join-Path $OutDir "run_done.json")
Write-Host ""
Write-Host "抓包已停止：$OutDir"
Write-Host "下一步：python `"$here\summarize.py`" `"$OutDir`""
Write-Host "然后把 $OutDir 目录（或 REPORT.md）交回给 Lead 分析。"

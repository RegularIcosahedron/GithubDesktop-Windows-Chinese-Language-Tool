# GitHub Desktop 汉化工具（Windows）一键入口
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\ghd-zh.ps1 -Action Apply
#   .\ghd-zh.ps1 -Action Restore
#   .\ghd-zh.ps1 -Action Status
#   .\ghd-zh.ps1 -Action Apply -DryRun
#   .\ghd-zh.ps1 -Action Apply -AppPath "C:\...\app-3.6.10\resources\app"

[CmdletBinding()]
param(
    [ValidateSet('Apply', 'Restore', 'Status')]
    [string]$Action = 'Apply',
    [string]$AppPath,
    [string]$DictPath,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $DictPath) { $DictPath = Join-Path $root 'dict.json' }
if (-not (Test-Path $DictPath)) { throw "找不到词典: $DictPath" }

$python = $null
$cand = Get-Command python -ErrorAction SilentlyContinue
if ($cand) { $python = $cand.Source }
if (-not $python) {
    $cand = Get-Command py -ErrorAction SilentlyContinue
    if ($cand) { $python = $cand.Source }
}
if (-not $python) { throw '未找到 Python 3。请先安装 Python 3.8+ 并把它加入 PATH。' }

$running = Get-Process GitHubDesktop -ErrorAction SilentlyContinue
if ($running -and $Action -ne 'Status') {
    Write-Host '[提示] GitHub Desktop 正在运行。' -ForegroundColor Yellow
    Write-Host '       改文件不会影响已打开的窗口，但需要完全退出后重新启动才能看到中文。' -ForegroundColor Yellow
    Write-Host '       脚本会先备份原版，可随时用 -Action Restore 还原。' -ForegroundColor Yellow
}

$pyArgs = @('-I', (Join-Path $root 'apply_windows.py'),
            '--action', $Action.ToLower(),
            '--dict', $DictPath)
if ($AppPath) { $pyArgs += @('--app', $AppPath) }
if ($DryRun) { $pyArgs += '--dry-run' }

& $python @pyArgs
exit $LASTEXITCODE

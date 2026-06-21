# 世界杯战报 - 定时更新脚本（Windows 任务计划程序每 1 小时调用一次）
# 流程：fetch_espn.py 拉 ESPN 真实数据 -> build.py 生成 report.html -> deploy.ps1 部署 -> 记日志
# 注：已从「调 Claude headless 做 web 检索」改为「ESPN 结构化端点」，去掉幻觉来源，也不再依赖 claude CLI。
$ErrorActionPreference = 'Continue'
$root = 'E:\CWORK\worldcup'
Set-Location $root

# 让 python 输出 UTF-8，且 PowerShell 按 UTF-8 接收原生命令输出，避免日志中文乱码
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- 日志 ---
$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $logDir "update_$stamp.log"
# 统一用 UTF-8 追加写日志（Tee-Object 在 PS5.1 写 UTF-16，故自定义 Log）
function Log([string]$msg) { Write-Host $msg; Add-Content -Path $log -Value $msg -Encoding UTF8 }

Log "=== 更新开始 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# --- 拉真实数据并生成页面 ---
python (Join-Path $root 'fetch_espn.py') 2>&1 | ForEach-Object { Log $_ }
python (Join-Path $root 'build.py')      2>&1 | ForEach-Object { Log $_ }

# --- 部署到 Cloudflare Pages ---
try {
    & (Join-Path $root 'deploy.ps1') 2>&1 | ForEach-Object { Log $_ }
} catch {
    Log "部署失败: $($_.Exception.Message)"
}

Log "=== 更新结束 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# 只保留最近 30 个日志
Get-ChildItem $logDir -Filter 'update_*.log' | Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 30 | Remove-Item -Force -ErrorAction SilentlyContinue

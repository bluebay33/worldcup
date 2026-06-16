# 世界杯战报 - 定时更新脚本（Windows 任务计划程序每 6 小时调用一次）
# 流程：fetch_espn.py 拉 ESPN 真实数据 -> build.py 生成 report.html -> 记日志
# 注：已从「调 Claude headless 做 web 检索」改为「ESPN 结构化端点」，去掉幻觉来源，也不再依赖 claude CLI。
$ErrorActionPreference = 'Continue'
$root = 'E:\CWORK\worldcup'
Set-Location $root

# --- 日志 ---
$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $logDir "update_$stamp.log"
"=== 更新开始 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Tee-Object -FilePath $log

# --- 拉真实数据并生成页面 ---
python (Join-Path $root 'fetch_espn.py') 2>&1 | Tee-Object -FilePath $log -Append
python (Join-Path $root 'build.py')      2>&1 | Tee-Object -FilePath $log -Append

# --- 部署到 Cloudflare Pages ---
try {
    & (Join-Path $root 'deploy.ps1') 2>&1 | Tee-Object -FilePath $log -Append
} catch {
    "部署失败: $($_.Exception.Message)" | Tee-Object -FilePath $log -Append
}

"=== 更新结束 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Tee-Object -FilePath $log -Append

# 只保留最近 30 个日志
Get-ChildItem $logDir -Filter 'update_*.log' | Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 30 | Remove-Item -Force -ErrorAction SilentlyContinue

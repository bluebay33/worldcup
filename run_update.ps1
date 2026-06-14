# 世界杯战报 - 定时更新脚本（由 Windows 任务计划程序每 6 小时调用一次）
# 流程：调 Claude Code headless 检索+交叉验证更新 data.json -> 兜底重生成 report.html -> 记日志
$ErrorActionPreference = 'Continue'
$root = 'E:\CWORK\worldcup'
Set-Location $root

# --- 定位 claude CLI（npm 全局）---
$claude = Join-Path $env:APPDATA 'npm\claude.cmd'
if (-not (Test-Path $claude)) {
    $g = Get-Command claude -ErrorAction SilentlyContinue
    if ($g) { $claude = $g.Source }
}

# --- 日志 ---
$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $logDir "update_$stamp.log"
"=== 更新开始 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Tee-Object -FilePath $log

if (-not (Test-Path $claude)) {
    "[错误] 找不到 claude CLI：$claude。请确认已 npm i -g @anthropic-ai/claude-code" | Tee-Object -FilePath $log -Append
    exit 1
}

# --- 调 Claude headless 做检索更新 ---
$prompt = Get-Content (Join-Path $root 'update_prompt.txt') -Raw -Encoding UTF8
try {
    & $claude -p $prompt `
        --add-dir $root `
        --allowedTools "Read,Edit,Write,Bash,WebSearch,WebFetch" `
        --dangerously-skip-permissions 2>&1 | Tee-Object -FilePath $log -Append
    "[claude 退出码] $LASTEXITCODE" | Tee-Object -FilePath $log -Append
} catch {
    "[异常] $($_.Exception.Message)" | Tee-Object -FilePath $log -Append
}

# --- 兜底：无论 claude 有没有自己跑 build，都重生成一次，确保 HTML 与 data.json 同步 ---
python (Join-Path $root 'build.py') 2>&1 | Tee-Object -FilePath $log -Append

"=== 更新结束 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Tee-Object -FilePath $log -Append

# 只保留最近 30 个日志
Get-ChildItem $logDir -Filter 'update_*.log' | Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 30 | Remove-Item -Force -ErrorAction SilentlyContinue

# 世界杯战报 - 部署到 Cloudflare Pages
# 流程：整理静态产物到 _site -> wrangler 直传到 Pages 项目
# 由 run_update.ps1 在生成页面后调用，也可单独手动跑。
$ErrorActionPreference = 'Stop'
$root = 'E:\CWORK\worldcup'
Set-Location $root

# wrangler 装在 npm 全局目录，定时任务环境下 PATH 可能不含它，这里兜底刷新
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path","Machine")

# --- 整理发布目录（只放静态文件，不含 .py / .git）---
$site = Join-Path $root '_site'
if (Test-Path $site) { Remove-Item $site -Recurse -Force }
New-Item -ItemType Directory -Path $site | Out-Null
Copy-Item (Join-Path $root 'index.html')  (Join-Path $site 'index.html')
Copy-Item (Join-Path $root 'report.html') (Join-Path $site 'report.html')
Copy-Item (Join-Path $root 'data.json')   (Join-Path $site 'data.json')

# --- 直传到 Cloudflare Pages ---
wrangler pages deploy $site --project-name=worldcup --branch=main --commit-dirty=true

# 世界杯战报 - 部署到统一体育门户站（Cloudflare Pages 项目 sports）
# 把自己的产物拷进聚合目录 sports\_site\worldcup\，刷新门户首页，再整站部署。
# 各运动共享同一聚合目录、各更新各的子目录，互不影响。
$ErrorActionPreference = 'Stop'
$root   = 'E:\CWORK\worldcup'
$portal = 'E:\CWORK\sports'
$site   = Join-Path $portal '_site'
Set-Location $root

# wrangler 装在 npm 全局目录，定时任务环境下 PATH 可能不含它，这里兜底刷新
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path","Machine")

# --- 确保聚合目录与门户首页就位（不清空整站，只更新自己那格）---
New-Item -ItemType Directory -Force -Path $site | Out-Null
Copy-Item (Join-Path $portal 'index.html') (Join-Path $site 'index.html') -Force

# --- 更新 worldcup 子目录 ---
$mine = Join-Path $site 'worldcup'
if (Test-Path $mine) { Remove-Item $mine -Recurse -Force }
New-Item -ItemType Directory -Path $mine | Out-Null
Copy-Item (Join-Path $root 'index.html')  (Join-Path $mine 'index.html')
Copy-Item (Join-Path $root 'report.html') (Join-Path $mine 'report.html')
Copy-Item (Join-Path $root 'data.json')   (Join-Path $mine 'data.json')

# --- 整站直传到 Cloudflare Pages ---
wrangler pages deploy $site --project-name=sports --branch=main --commit-dirty=true

# 世界杯战报 - 部署到自己的独立站（CF Pages 项目 worldcup，worldcup-ata.pages.dev）
# 与门户、羽毛球互不干涉:各自部署各自的 CF 项目。门户 /worldcup/ 会实时代理过来。
$ErrorActionPreference = 'Stop'
$root = 'E:\CWORK\worldcup'
$site = Join-Path $root '_site'
Set-Location $root

# wrangler 装在 npm 全局目录，定时任务环境下 PATH 可能不含它，这里兜底刷新
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path","Machine")

# 整理发布目录（只放静态产物，不含 .py / .git）
if (Test-Path $site) { Remove-Item $site -Recurse -Force }
New-Item -ItemType Directory -Path $site | Out-Null
Copy-Item (Join-Path $root 'index.html')  (Join-Path $site 'index.html')
Copy-Item (Join-Path $root 'report.html') (Join-Path $site 'report.html')
Copy-Item (Join-Path $root 'data.json')   (Join-Path $site 'data.json')

wrangler pages deploy $site --project-name=worldcup --branch=main --commit-dirty=true

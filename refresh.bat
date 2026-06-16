@echo off
chcp 65001 >nul
echo 正在刷新世界杯战报并部署上线...
powershell -ExecutionPolicy Bypass -File "%~dp0run_update.ps1"
echo.
echo 完成。线上地址: https://worldcup-ata.pages.dev/
pause

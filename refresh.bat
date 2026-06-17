@echo off
echo 正在刷新世界杯战报并部署上线...
powershell -ExecutionPolicy Bypass -File "%~dp0run_update.ps1"
echo.
echo 完成。线上地址: https://sports-aeg.pages.dev/worldcup/
pause

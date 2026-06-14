# 注册 Windows 任务计划程序：每 6 小时跑一次世界杯战报更新
# 用法（普通权限即可，无需管理员）：powershell -ExecutionPolicy Bypass -File register_task.ps1
$taskName = 'WorldCup2026-ReportUpdate'
$script   = 'E:\CWORK\worldcup\run_update.ps1'

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""

# 从今天某个整点起，每 6 小时重复一次（00/06/12/18 这种节奏可改 -At）
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(6) `
    -RepetitionInterval (New-TimeSpan -Hours 6)

# 当前用户、登录时运行（个人机足够；若要锁屏/未登录也跑需改 -LogonType S4U 并存密码）
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force -Description '每6小时检索并更新2026世界杯战报'

Write-Host "已注册任务计划：$taskName（每6小时）。可在『任务计划程序』里看到，或运行 Start-ScheduledTask -TaskName $taskName 立即测试。"

# 注册 Windows 任务计划程序：每 1 小时跑一次世界杯战报更新
# 用法（普通权限即可，无需管理员）：powershell -ExecutionPolicy Bypass -File register_task.ps1
$taskName = 'WorldCup2026-ReportUpdate'
$script   = 'E:\CWORK\worldcup\run_update.ps1'

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""

# 从今天 0 点为锚点、每 1 小时重复一次（即每个整点触发；不指定时长 = 无限期重复）
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Hours 1)

# 当前用户、whether-logged-on-or-not 运行：S4U 无需存密码，锁屏/未登录也跑（PC 仍需开机）
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force -Description '每1小时检索并更新2026世界杯战报'

Write-Host "已注册任务计划：$taskName（每1小时）。可在『任务计划程序』里看到，或运行 Start-ScheduledTask -TaskName $taskName 立即测试。"

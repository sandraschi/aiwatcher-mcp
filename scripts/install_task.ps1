param()
# install_task.ps1 -- Register AIWatcher morning alert as a Windows Scheduled Task.
# Run once as Administrator. Safe to re-run (updates existing task).
#
# Task fires at 05:55 local Vienna time.
# Windows handles DST automatically when using local time triggers.

$ErrorActionPreference = "Stop"

$TaskName    = "AIWatcher-MorningAlert"
$ScriptPath  = "D:\Dev\repos\aiwatcher-mcp\scripts\morning_alert.py"
$UvPath      = "C:\Users\sandr\.local\bin\uv.exe"
$RepoDir     = "D:\Dev\repos\aiwatcher-mcp"
$TriggerTime = "05:55"

$Action = New-ScheduledTaskAction `
    -Execute $UvPath `
    -Argument "run python `"$ScriptPath`"" `
    -WorkingDirectory $RepoDir

$Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -WakeToRun

$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -RunLevel Highest `
    -LogonType S4U

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Set-ScheduledTask -TaskName $TaskName `
        -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal
    Write-Host "Updated task: $TaskName" -ForegroundColor Yellow
} else {
    Register-ScheduledTask -TaskName $TaskName `
        -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal
    Write-Host "Registered task: $TaskName" -ForegroundColor Green
}

Write-Host ""
Write-Host "Task '$TaskName' fires daily at $TriggerTime local time." -ForegroundColor Cyan
Write-Host ""
Write-Host "Test immediately (do not wait for 05:55):" -ForegroundColor DarkGray
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor DarkGray
Write-Host "  Get-ScheduledTaskInfo -TaskName '$TaskName'" -ForegroundColor DarkGray

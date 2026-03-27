$taskName = "Antigravity_X_Growth_Engine"
$projectRoot = (Resolve-Path $PSScriptRoot).Path
$batPath = Join-Path $projectRoot "run_x_growth.bat"

if (-not (Test-Path $batPath)) {
    throw "Task runner not found: $batPath"
}

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batPath`"" -WorkingDirectory $projectRoot
$times = @("05:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00")
$triggers = @()

foreach ($t in $times) {
    $triggers += New-ScheduledTaskTrigger -Daily -At $t
}

Register-ScheduledTask `
    -TaskName $taskName `
    -Trigger $triggers `
    -Action $action `
    -Description "Antigravity X Growth Engine - Daily Automation" `
    -Force

Write-Host "Task '$taskName' has been registered with 9 daily triggers."

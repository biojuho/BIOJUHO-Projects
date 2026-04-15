$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DailyNews scheduler setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator." -ForegroundColor Red
    exit 1
}

$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$DailyNewsRoot = Join-Path $WorkspaceRoot "automation\DailyNews"
$MorningScript = Join-Path $WorkspaceRoot "ops\scripts\run_morning_insights.bat"
$EveningScript = Join-Path $WorkspaceRoot "ops\scripts\run_evening_insights.bat"
$LogDir = Join-Path $DailyNewsRoot "logs\insights"

foreach ($scriptPath in @($MorningScript, $EveningScript)) {
    if (-not (Test-Path $scriptPath)) {
        Write-Host "ERROR: Script not found: $scriptPath" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Workspace root: $WorkspaceRoot" -ForegroundColor Green
Write-Host "DailyNews root: $DailyNewsRoot" -ForegroundColor Green

$MorningAction = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$MorningScript`"" -WorkingDirectory $DailyNewsRoot
$MorningTrigger = New-ScheduledTaskTrigger -Daily -At "07:00"
$MorningSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName "DailyNews_Morning_Insights" `
    -Action $MorningAction `
    -Trigger $MorningTrigger `
    -Settings $MorningSettings `
    -Description "DailyNews morning insights (07:00)" `
    -Force | Out-Null

$EveningAction = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$EveningScript`"" -WorkingDirectory $DailyNewsRoot
$EveningTrigger = New-ScheduledTaskTrigger -Daily -At "18:00"
$EveningSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName "DailyNews_Evening_Insights" `
    -Action $EveningAction `
    -Trigger $EveningTrigger `
    -Settings $EveningSettings `
    -Description "DailyNews evening insights (18:00)" `
    -Force | Out-Null

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Morning task: DailyNews_Morning_Insights" -ForegroundColor Yellow
Write-Host "Evening task: DailyNews_Evening_Insights" -ForegroundColor Yellow
Write-Host "Logs: $LogDir" -ForegroundColor Yellow

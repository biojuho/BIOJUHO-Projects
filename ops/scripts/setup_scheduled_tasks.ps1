# DailyNews Insight Generator - Task Scheduler Setup
# Run as Administrator: PowerShell -ExecutionPolicy Bypass -File setup_scheduled_tasks.ps1

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DailyNews Insight Generator - Scheduler Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if running as Administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Project paths
$ProjectRoot = "d:\AI 프로젝트"
$MorningScript = Join-Path $ProjectRoot "scripts\run_morning_insights.bat"
$EveningScript = Join-Path $ProjectRoot "scripts\run_evening_insights.bat"

# Verify scripts exist
if (-not (Test-Path $MorningScript)) {
    Write-Host "ERROR: Morning script not found: $MorningScript" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $EveningScript)) {
    Write-Host "ERROR: Evening script not found: $EveningScript" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Found morning script: $MorningScript" -ForegroundColor Green
Write-Host "✓ Found evening script: $EveningScript" -ForegroundColor Green

# Create morning task (7 AM)
Write-Host ""
Write-Host "Creating morning task (7:00 AM)..." -ForegroundColor Cyan

$MorningAction = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$MorningScript`"" -WorkingDirectory $ProjectRoot
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
    -Description "DailyNews 오전 인사이트 자동 생성 (7:00 AM)" `
    -Force | Out-Null

Write-Host "✓ Morning task created: DailyNews_Morning_Insights" -ForegroundColor Green

# Create evening task (6 PM)
Write-Host ""
Write-Host "Creating evening task (6:00 PM)..." -ForegroundColor Cyan

$EveningAction = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$EveningScript`"" -WorkingDirectory $ProjectRoot
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
    -Description "DailyNews 오후 인사이트 자동 생성 (6:00 PM)" `
    -Force | Out-Null

Write-Host "✓ Evening task created: DailyNews_Evening_Insights" -ForegroundColor Green

# Verify tasks
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verifying scheduled tasks..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$MorningTask = Get-ScheduledTask -TaskName "DailyNews_Morning_Insights" -ErrorAction SilentlyContinue
$EveningTask = Get-ScheduledTask -TaskName "DailyNews_Evening_Insights" -ErrorAction SilentlyContinue

if ($MorningTask -and $EveningTask) {
    Write-Host "✓ Both tasks successfully registered" -ForegroundColor Green
    Write-Host ""
    Write-Host "Morning task:" -ForegroundColor Yellow
    Write-Host "  Name: $($MorningTask.TaskName)"
    Write-Host "  State: $($MorningTask.State)"
    Write-Host "  Next run: 7:00 AM daily"
    Write-Host ""
    Write-Host "Evening task:" -ForegroundColor Yellow
    Write-Host "  Name: $($EveningTask.TaskName)"
    Write-Host "  State: $($EveningTask.State)"
    Write-Host "  Next run: 6:00 PM daily"
} else {
    Write-Host "ERROR: Task registration failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Open Task Scheduler (taskschd.msc) to verify tasks"
Write-Host "2. Right-click task → 'Run' to test manually"
Write-Host "3. Check logs at: d:\AI 프로젝트\DailyNews\logs\insights\"
Write-Host ""

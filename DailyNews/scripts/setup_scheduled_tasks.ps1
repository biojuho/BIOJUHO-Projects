# =========================================================================
# DailyNews - Windows Task Scheduler 자동 설정 스크립트
# =========================================================================
#
# 이 스크립트는 Windows Task Scheduler에 하루 2회 인사이트 생성 작업을 등록합니다.
#
# 실행 방법:
#   1. PowerShell을 관리자 권한으로 실행
#   2. cd "d:\AI 프로젝트\DailyNews\scripts"
#   3. .\setup_scheduled_tasks.ps1
#
# 작성일: 2026-03-21
# =========================================================================

param(
    [switch]$NonInteractive
)

# 관리자 권한 확인
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "DailyNews Task Scheduler Setup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

if ($isAdmin) {
    Write-Host "✅ Administrator privileges detected" -ForegroundColor Green
    Write-Host "   Tasks will be created with S4U logon (can run without user login)." -ForegroundColor Gray
} else {
    Write-Host "⚠️  Administrator privileges not detected" -ForegroundColor Yellow
    Write-Host "   Falling back to Interactive logon for the current user." -ForegroundColor Gray
    Write-Host "   Tasks will run when this user is logged in." -ForegroundColor Gray
}

Write-Host ""

# 스크립트 경로 설정
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunnerScript = "$ProjectRoot\scripts\run_scheduled_insights.ps1"
$TaskUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name

# 스크립트 파일 존재 확인
if (-not (Test-Path $RunnerScript)) {
    Write-Host "❌ ERROR: Runner script not found: $RunnerScript" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Script files found" -ForegroundColor Green
Write-Host "   Runner: $RunnerScript" -ForegroundColor Gray
Write-Host ""

# 기존 작업 삭제 (있는 경우)
Write-Host "Removing existing tasks (if any)..." -ForegroundColor Yellow

try {
    Unregister-ScheduledTask -TaskName "DailyNews_Morning_Insights" -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "DailyNews_Evening_Insights" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "✅ Existing tasks removed" -ForegroundColor Green
} catch {
    Write-Host "⚠️  No existing tasks to remove" -ForegroundColor Yellow
}

Write-Host ""

# =========================================================================
# 1. 오전 7시 작업 등록
# =========================================================================

Write-Host "Creating Morning Task (7:00 AM)..." -ForegroundColor Cyan

$MorningAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunnerScript`" -Window morning" `
    -WorkingDirectory $ProjectRoot

$MorningTrigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "07:00"

$MorningSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$MorningPrincipal = if ($isAdmin) {
    New-ScheduledTaskPrincipal `
        -UserId $TaskUser `
        -LogonType S4U `
        -RunLevel Limited
} else {
    New-ScheduledTaskPrincipal `
        -UserId $TaskUser `
        -LogonType Interactive `
        -RunLevel Limited
}

try {
    Register-ScheduledTask `
        -TaskName "DailyNews_Morning_Insights" `
        -Description "DailyNews 오전 인사이트 생성 (7:00 AM)" `
        -Action $MorningAction `
        -Trigger $MorningTrigger `
        -Settings $MorningSettings `
        -Principal $MorningPrincipal `
        -Force | Out-Null

    Write-Host "✅ Morning task created successfully" -ForegroundColor Green
    Write-Host "   Task Name: DailyNews_Morning_Insights" -ForegroundColor Gray
    Write-Host "   Schedule: Daily at 7:00 AM" -ForegroundColor Gray
} catch {
    Write-Host "❌ ERROR: Failed to create morning task" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Write-Host ""

# =========================================================================
# 2. 오후 6시 작업 등록
# =========================================================================

Write-Host "Creating Evening Task (6:00 PM)..." -ForegroundColor Cyan

$EveningAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunnerScript`" -Window evening" `
    -WorkingDirectory $ProjectRoot

$EveningTrigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "18:00"

$EveningSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$EveningPrincipal = if ($isAdmin) {
    New-ScheduledTaskPrincipal `
        -UserId $TaskUser `
        -LogonType S4U `
        -RunLevel Limited
} else {
    New-ScheduledTaskPrincipal `
        -UserId $TaskUser `
        -LogonType Interactive `
        -RunLevel Limited
}

try {
    Register-ScheduledTask `
        -TaskName "DailyNews_Evening_Insights" `
        -Description "DailyNews 오후 인사이트 생성 (6:00 PM)" `
        -Action $EveningAction `
        -Trigger $EveningTrigger `
        -Settings $EveningSettings `
        -Principal $EveningPrincipal `
        -Force | Out-Null

    Write-Host "✅ Evening task created successfully" -ForegroundColor Green
    Write-Host "   Task Name: DailyNews_Evening_Insights" -ForegroundColor Gray
    Write-Host "   Schedule: Daily at 6:00 PM" -ForegroundColor Gray
} catch {
    Write-Host "❌ ERROR: Failed to create evening task" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "✅ Setup Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Scheduled tasks created:" -ForegroundColor White
Write-Host "  1. DailyNews_Morning_Insights - Daily at 7:00 AM" -ForegroundColor White
Write-Host "  2. DailyNews_Evening_Insights - Daily at 6:00 PM" -ForegroundColor White
Write-Host "  3. User: $TaskUser" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open Task Scheduler (taskschd.msc) to verify" -ForegroundColor Gray
Write-Host "  2. Test run: Right-click task > Run" -ForegroundColor Gray
Write-Host "  3. Check logs: d:\AI 프로젝트\DailyNews\logs\insights\" -ForegroundColor Gray
Write-Host ""
Write-Host "To remove tasks later, run:" -ForegroundColor Yellow
Write-Host '  Unregister-ScheduledTask -TaskName "DailyNews_Morning_Insights" -Confirm:$false' -ForegroundColor Gray
Write-Host '  Unregister-ScheduledTask -TaskName "DailyNews_Evening_Insights" -Confirm:$false' -ForegroundColor Gray
Write-Host ""

# Task Scheduler 열기 (선택 사항)
if (-not $NonInteractive) {
    $openTaskScheduler = Read-Host "Open Task Scheduler now? (Y/N)"
    if ($openTaskScheduler -eq "Y" -or $openTaskScheduler -eq "y") {
        Start-Process "taskschd.msc"
    }

    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

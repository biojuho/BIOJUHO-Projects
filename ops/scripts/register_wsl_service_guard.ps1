#Requires -RunAsAdministrator

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$guardScript = Join-Path $scriptRoot "ensure_wsl_services.ps1"

if (-not (Test-Path -LiteralPath $guardScript)) {
    throw "Guard script not found: $guardScript"
}

$startupTaskName = "AIProject_WSL_Service_Guard_OnStart"
$logonTaskName = "AIProject_WSL_Service_Guard_OnLogon"
$repairTaskName = "AIProject_WSL_Service_Guard_Repair"

function New-GuardAction {
    param([switch]$StartServices)

    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $guardScript
    if ($StartServices) {
        $arguments += " -StartServices"
    }

    return New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument $arguments
}

Write-Host ""
Write-Host "Registering WSL service guard tasks..." -ForegroundColor Cyan

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

$startupTrigger = New-ScheduledTaskTrigger -AtStartup
$startupTrigger.Delay = "PT30S"

$logonTrigger = New-ScheduledTaskTrigger -AtLogOn
$logonTrigger.Delay = "PT30S"

$repairTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)

Register-ScheduledTask -TaskName $startupTaskName -Action (New-GuardAction -StartServices) -Trigger $startupTrigger -Principal $principal -Settings $settings -Description "Ensures WSL services are enabled and started at system startup." -Force | Out-Null
Write-Host "Registered task: $startupTaskName" -ForegroundColor Green

Register-ScheduledTask -TaskName $logonTaskName -Action (New-GuardAction -StartServices) -Trigger $logonTrigger -Principal $principal -Settings $settings -Description "Ensures WSL services are enabled and started when a user signs in." -Force | Out-Null
Write-Host "Registered task: $logonTaskName" -ForegroundColor Green

Register-ScheduledTask -TaskName $repairTaskName -Action (New-GuardAction) -Trigger $repairTrigger -Principal $principal -Settings $settings -Description "Repairs WSL service startup settings every 30 minutes." -Force | Out-Null
Write-Host "Registered task: $repairTaskName" -ForegroundColor Green

Write-Host ""
Write-Host "Running the startup guard once now..." -ForegroundColor Cyan
& PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File $guardScript -StartServices

Write-Host ""
Write-Host "WSL service guard tasks are ready:" -ForegroundColor Green
Write-Host "  - $startupTaskName"
Write-Host "  - $logonTaskName"
Write-Host "  - $repairTaskName"
Write-Host ""
Write-Host "Log file: $env:ProgramData\AIProject\Logs\wsl-service-guard.log" -ForegroundColor Yellow

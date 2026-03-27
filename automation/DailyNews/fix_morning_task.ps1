#Requires -RunAsAdministrator

$taskName = "DailyNews_Morning"
$projectRoot = (Resolve-Path $PSScriptRoot).Path
$commandPath = Join-Path $projectRoot "run_daily_news.bat"

Write-Host "=== DailyNews morning task refresh ===" -ForegroundColor Cyan

Write-Host "[1/3] Removing existing task..." -ForegroundColor Yellow
schtasks /delete /tn $taskName /f 2>$null

Write-Host "[2/3] Creating replacement task..." -ForegroundColor Yellow

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>DailyNews morning run at 07:00</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-03-06T07:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$env:USERNAME</UserId>
      <LogonType>S4U</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT72H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>/c "$commandPath"</Arguments>
      <WorkingDirectory>$projectRoot</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$xmlPath = "$env:TEMP\DailyNews_Morning.xml"
$xml | Out-File -Encoding unicode $xmlPath -Force
schtasks /create /tn $taskName /xml $xmlPath /f

Write-Host ""
Write-Host "[3/3] Verifying task..." -ForegroundColor Yellow
schtasks /query /tn $taskName /fo LIST /v | Select-String -Pattern "TaskName|Status|Next Run|Last Run|Last Result|Logon Mode|Power|Start Time"

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Command: $commandPath" -ForegroundColor White

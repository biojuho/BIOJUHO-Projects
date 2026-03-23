param(
    [int]$IntervalHours = 3,
    [string]$StartAt = "09:00",
    [string]$TaskName = "GetDayTrends",
    [switch]$NonInteractive
)

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$ProjectRoot = $PSScriptRoot
$RunnerScript = Join-Path $ProjectRoot "run_scheduled_getdaytrends.ps1"
$TaskUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "GetDayTrends Task Scheduler Setup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

if ($isAdmin) {
    Write-Host "Administrator privileges detected" -ForegroundColor Green
    Write-Host "Tasks will be created with S4U logon." -ForegroundColor Gray
} else {
    Write-Host "Administrator privileges not detected" -ForegroundColor Yellow
    Write-Host "Falling back to InteractiveToken for the current user." -ForegroundColor Gray
    Write-Host "If the legacy task is protected, a current-user fallback task will be created." -ForegroundColor Gray
}

if (-not (Test-Path $RunnerScript)) {
    Write-Host "ERROR: Runner script not found: $RunnerScript" -ForegroundColor Red
    exit 1
}

try {
    $ParsedStart = [datetime]::ParseExact($StartAt, "HH:mm", [System.Globalization.CultureInfo]::InvariantCulture)
} catch {
    Write-Host "ERROR: StartAt must use HH:mm format (example: 09:00)." -ForegroundColor Red
    exit 1
}

$StartBoundaryTime = Get-Date -Hour $ParsedStart.Hour -Minute $ParsedStart.Minute -Second 0
while ($StartBoundaryTime -le (Get-Date)) {
    $StartBoundaryTime = $StartBoundaryTime.AddHours($IntervalHours)
}

$StartBoundary = $StartBoundaryTime.ToString("s")
$LogonType = if ($isAdmin) { "S4U" } else { "InteractiveToken" }
$RunLevel = if ($isAdmin) { "HighestAvailable" } else { "LeastPrivilege" }
$EscapedUser = [System.Security.SecurityElement]::Escape($TaskUser)
$EscapedProjectRoot = [System.Security.SecurityElement]::Escape($ProjectRoot)
$EscapedArguments = [System.Security.SecurityElement]::Escape("-NoProfile -ExecutionPolicy Bypass -File `"$RunnerScript`"")
$IntervalToken = "PT{0}H" -f $IntervalHours

$TaskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>GetDayTrends automated trend pipeline (every $IntervalHours hours)</Description>
    <Author>$EscapedUser</Author>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <Repetition>
        <Interval>$IntervalToken</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>$StartBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$EscapedUser</UserId>
      <LogonType>$LogonType</LogonType>
      <RunLevel>$RunLevel</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT3H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>$EscapedArguments</Arguments>
      <WorkingDirectory>$EscapedProjectRoot</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$CandidateTaskNames = @($TaskName)
if (-not $isAdmin) {
    $CandidateTaskNames += "{0}_CurrentUser" -f $TaskName
}

$EffectiveTaskName = $null
$UsedFallbackTaskName = $false

foreach ($CandidateTaskName in $CandidateTaskNames) {
    try {
        Unregister-ScheduledTask -TaskName $CandidateTaskName -Confirm:$false -ErrorAction Stop | Out-Null
    } catch {
    }

    try {
        Register-ScheduledTask -TaskName $CandidateTaskName -Xml $TaskXml -Force -ErrorAction Stop | Out-Null
        $EffectiveTaskName = $CandidateTaskName
        $UsedFallbackTaskName = $CandidateTaskName -ne $TaskName
        break
    } catch {
        Write-Host ("Notice: failed to register task '{0}': {1}" -f $CandidateTaskName, $_.Exception.Message) -ForegroundColor Yellow
    }
}

if (-not $EffectiveTaskName) {
    Write-Host "ERROR: Failed to register scheduled task." -ForegroundColor Red
    exit 1
}

$Task = Get-ScheduledTask -TaskName $EffectiveTaskName
$Action = $Task.Actions | Select-Object -First 1
$TaskInfo = Get-ScheduledTaskInfo -TaskName $EffectiveTaskName

if ($Action.Execute -ne "powershell.exe" -or $Action.Arguments -notmatch "run_scheduled_getdaytrends\.ps1") {
    Write-Host "ERROR: Task action validation failed." -ForegroundColor Red
    Write-Host ("Execute    : {0}" -f $Action.Execute) -ForegroundColor Red
    Write-Host ("Arguments  : {0}" -f $Action.Arguments) -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ("Task Name       : {0}" -f $EffectiveTaskName) -ForegroundColor Gray
Write-Host ("User            : {0}" -f $TaskUser) -ForegroundColor Gray
Write-Host ("LogonType       : {0}" -f $LogonType) -ForegroundColor Gray
Write-Host ("RunLevel        : {0}" -f $RunLevel) -ForegroundColor Gray
Write-Host ("Schedule        : every {0} hours from {1}" -f $IntervalHours, $StartAt) -ForegroundColor Gray
Write-Host ("Execute         : {0}" -f $Action.Execute) -ForegroundColor Gray
Write-Host ("Arguments       : {0}" -f $Action.Arguments) -ForegroundColor Gray
Write-Host ("WorkingDirectory: {0}" -f $Action.WorkingDirectory) -ForegroundColor Gray
Write-Host ("NextRunTime     : {0}" -f $TaskInfo.NextRunTime) -ForegroundColor Gray
if ($UsedFallbackTaskName) {
    Write-Host ("Legacy task '{0}' could not be replaced without elevation." -f $TaskName) -ForegroundColor Yellow
    Write-Host ("Using current-user fallback task '{0}' instead." -f $EffectiveTaskName) -ForegroundColor Yellow
}
Write-Host ""

if (-not $NonInteractive) {
    $OpenTaskScheduler = Read-Host "Open Task Scheduler now? (Y/N)"
    if ($OpenTaskScheduler -match "^[Yy]$") {
        Start-Process "taskschd.msc"
    }
}

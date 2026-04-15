[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet("Disable", "Delete")]
    [string]$LegacyTaskAction = "Disable",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-TaskSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TaskName
    )

    try {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
        $action = $task.Actions | Select-Object -First 1
        return [pscustomobject]@{
            TaskName         = $TaskName
            State            = $task.State
            LastRunTime      = $info.LastRunTime
            LastTaskResult   = $info.LastTaskResult
            NextRunTime      = $info.NextRunTime
            UserId           = $task.Principal.UserId
            LogonType        = $task.Principal.LogonType
            RunLevel         = $task.Principal.RunLevel
            Execute          = $action.Execute
            Arguments        = $action.Arguments
            WorkingDirectory = $action.WorkingDirectory
        }
    } catch {
        return $null
    }
}

function Show-TaskSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Snapshot
    )

    Write-Host ("  - {0}" -f $Snapshot.TaskName) -ForegroundColor Cyan
    Write-Host ("    State          : {0}" -f $Snapshot.State) -ForegroundColor Gray
    Write-Host ("    LastRunTime    : {0}" -f $Snapshot.LastRunTime) -ForegroundColor Gray
    Write-Host ("    LastTaskResult : {0}" -f $Snapshot.LastTaskResult) -ForegroundColor Gray
    Write-Host ("    NextRunTime    : {0}" -f $Snapshot.NextRunTime) -ForegroundColor Gray
    Write-Host ("    UserId         : {0}" -f $Snapshot.UserId) -ForegroundColor Gray
    Write-Host ("    LogonType      : {0}" -f $Snapshot.LogonType) -ForegroundColor Gray
    Write-Host ("    Execute        : {0}" -f $Snapshot.Execute) -ForegroundColor Gray
    Write-Host ("    Arguments      : {0}" -f $Snapshot.Arguments) -ForegroundColor Gray
    Write-Host ("    WorkingDir     : {0}" -f $Snapshot.WorkingDirectory) -ForegroundColor Gray
}

if (-not (Test-IsAdministrator)) {
    Write-Host "ERROR: Run this script as Administrator." -ForegroundColor Red
    exit 1
}

$canonicalTasks = @(
    "DailyNews_Morning_Insights",
    "DailyNews_Evening_Insights",
    "GetDayTrends_CurrentUser"
)

$legacyTasks = @(
    @{
        Name   = "DailyNews_Evening"
        Reason = "Superseded by DailyNews_Evening_Insights."
    },
    @{
        Name   = "GetDayTrends"
        Reason = "Legacy SYSTEM task with a broken split path action."
    },
    @{
        Name   = "GetDayTrends_AutoStart"
        Reason = "Deprecated launcher wrapper."
    }
)

$missingCanonical = @()
foreach ($taskName in $canonicalTasks) {
    if (-not (Get-TaskSnapshot -TaskName $taskName)) {
        $missingCanonical += $taskName
    }
}

if ($missingCanonical.Count -gt 0 -and -not $Force) {
    Write-Host "ERROR: Refusing to touch legacy tasks because canonical tasks are missing:" -ForegroundColor Red
    foreach ($taskName in $missingCanonical) {
        Write-Host ("  - {0}" -f $taskName) -ForegroundColor Red
    }
    Write-Host "Re-run with -Force only after you verify replacements." -ForegroundColor Yellow
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Canonical scheduled tasks" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
foreach ($taskName in $canonicalTasks) {
    $snapshot = Get-TaskSnapshot -TaskName $taskName
    if ($snapshot) {
        Show-TaskSnapshot -Snapshot $snapshot
    } else {
        Write-Host ("  - {0}: missing" -f $taskName) -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ("Legacy task cleanup ({0})" -f $LegacyTaskAction) -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$results = foreach ($entry in $legacyTasks) {
    $before = Get-TaskSnapshot -TaskName $entry.Name
    if (-not $before) {
        [pscustomobject]@{
            TaskName = $entry.Name
            Action   = $LegacyTaskAction
            Outcome  = "missing"
            State    = "missing"
            Reason   = $entry.Reason
        }
        continue
    }

    if ($LegacyTaskAction -eq "Disable") {
        if ($before.State -eq "Disabled") {
            [pscustomobject]@{
                TaskName = $entry.Name
                Action   = $LegacyTaskAction
                Outcome  = "already-disabled"
                State    = "Disabled"
                Reason   = $entry.Reason
            }
            continue
        }

        if ($PSCmdlet.ShouldProcess($entry.Name, "Disable scheduled task")) {
            Disable-ScheduledTask -TaskName $entry.Name -ErrorAction Stop | Out-Null
        }

        $after = Get-TaskSnapshot -TaskName $entry.Name
        [pscustomobject]@{
            TaskName = $entry.Name
            Action   = $LegacyTaskAction
            Outcome  = "updated"
            State    = if ($after) { $after.State } else { "missing" }
            Reason   = $entry.Reason
        }
        continue
    }

    if ($PSCmdlet.ShouldProcess($entry.Name, "Delete scheduled task")) {
        Unregister-ScheduledTask -TaskName $entry.Name -Confirm:$false -ErrorAction Stop | Out-Null
    }

    $after = Get-TaskSnapshot -TaskName $entry.Name
    [pscustomobject]@{
        TaskName = $entry.Name
        Action   = $LegacyTaskAction
        Outcome  = "updated"
        State    = if ($after) { $after.State } else { "Deleted" }
        Reason   = $entry.Reason
    }
}

$results | Format-Table -AutoSize

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Post-cleanup canonical status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
foreach ($taskName in $canonicalTasks) {
    $snapshot = Get-TaskSnapshot -TaskName $taskName
    if ($snapshot) {
        Write-Host ("  - {0}: {1}, next run {2}, last result {3}" -f $snapshot.TaskName, $snapshot.State, $snapshot.NextRunTime, $snapshot.LastTaskResult) -ForegroundColor Green
    } else {
        Write-Host ("  - {0}: missing" -f $taskName) -ForegroundColor Yellow
    }
}

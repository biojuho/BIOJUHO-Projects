param(
    [ValidateSet("Disable", "Delete")]
    [string]$LegacyTaskAction = "Disable",
    [switch]$Force,
    [switch]$Elevated
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$cleanupScript = Join-Path $PSScriptRoot "cleanup_legacy_scheduled_tasks.ps1"
$logDir = Join-Path $workspaceRoot "var\logs"
$logPath = Join-Path $logDir "cleanup_legacy_scheduled_tasks.out.txt"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-IsAdministrator)) {
    $argList = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-LegacyTaskAction", $LegacyTaskAction,
        "-Elevated"
    )
    if ($Force) {
        $argList += "-Force"
    }

    try {
        $process = Start-Process powershell.exe -Verb RunAs -ArgumentList $argList -PassThru -Wait
    } catch {
        Write-Host "Elevation was cancelled or failed." -ForegroundColor Yellow
        exit 1
    }

    if (Test-Path $logPath) {
        Get-Content $logPath -Tail 200
    }

    exit $process.ExitCode
}

try {
    & $cleanupScript -LegacyTaskAction $LegacyTaskAction -Force:$Force *>&1 | Tee-Object -FilePath $logPath
    exit $LASTEXITCODE
} catch {
    $_ | Out-String | Tee-Object -FilePath $logPath -Append | Out-Host
    exit 1
}

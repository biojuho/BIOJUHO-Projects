param(
    [string]$Country = "",
    [int]$Limit = 0,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$projectRoot = Split-Path -Parent $PSCommandPath
$workspaceRoot = Split-Path -Parent (Split-Path -Parent $projectRoot)
$pythonExe = Join-Path $workspaceRoot ".venv\Scripts\python.exe"
$mainPy = Join-Path $projectRoot "main.py"
$schedulerLogDir = Join-Path $projectRoot "logs\scheduler"
$summaryLog = Join-Path $projectRoot "run_scheduled.log"

if (-not (Test-Path $pythonExe)) {
    throw "Python runtime not found: $pythonExe"
}

if (-not (Test-Path $mainPy)) {
    throw "Entrypoint not found: $mainPy"
}

New-Item -ItemType Directory -Path $schedulerLogDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$detailLog = Join-Path $schedulerLogDir "run_${timestamp}.log"
$pythonPathParts = @(
    $workspaceRoot,
    (Join-Path $workspaceRoot "packages"),
    $projectRoot
) | Where-Object { Test-Path $_ }
$env:PYTHONPATH = ($pythonPathParts -join [IO.Path]::PathSeparator)

$argsList = @($mainPy, "--one-shot")
if ($Country) {
    $argsList += @("--country", $Country)
}
if ($Limit -gt 0) {
    $argsList += @("--limit", "$Limit")
}
if ($DryRun) {
    $argsList += "--dry-run"
}

$start = Get-Date
$header = @(
    "========================================="
    "[$($start.ToString('yyyy-MM-dd HH:mm:ss'))] GetDayTrends scheduled run started"
    "ProjectRoot: $projectRoot"
    "Python: $(& $pythonExe -c 'import sys; print(sys.version.replace(chr(10), \" \"))')"
    "PYTHONPATH: $env:PYTHONPATH"
    "Command: $pythonExe $($argsList -join ' ')"
    ""
)

$header | Tee-Object -FilePath $summaryLog -Append | Tee-Object -FilePath $detailLog -Append | Out-Null

Push-Location $projectRoot
try {
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $pythonExe @argsList 2>&1 |
            ForEach-Object { $_.ToString() } |
            Tee-Object -FilePath $summaryLog -Append |
            Tee-Object -FilePath $detailLog -Append | Out-Null
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
}
finally {
    Pop-Location
}

$finish = Get-Date
if ($exitCode -eq 0) {
    @(
        "[SUCCESS] GetDayTrends scheduled run completed"
        "DetailLog: $detailLog"
        "Finished: $($finish.ToString('yyyy-MM-dd HH:mm:ss'))"
        "========================================="
    ) | Tee-Object -FilePath $summaryLog -Append | Tee-Object -FilePath $detailLog -Append | Out-Null
    exit 0
}

@(
    "[ERROR] GetDayTrends scheduled run failed with exit code $exitCode"
    "DetailLog: $detailLog"
    "Finished: $($finish.ToString('yyyy-MM-dd HH:mm:ss'))"
    "========================================="
) | Tee-Object -FilePath $summaryLog -Append | Tee-Object -FilePath $detailLog -Append | Out-Null
exit $exitCode

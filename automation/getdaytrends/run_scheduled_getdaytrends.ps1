param(
    [switch]$DryRun,
    [int]$Limit = 0,
    [string]$Country
)

$ProjectRoot = $PSScriptRoot
$WorkspaceRoot = (Resolve-Path (Join-Path $ProjectRoot "..")).Path
$PythonExe = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"
$SummaryLog = Join-Path $ProjectRoot "run_scheduled.log"
$LogDir = Join-Path $ProjectRoot "logs\scheduler"
$Timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$DetailLog = Join-Path $LogDir ("run_{0}.log" -f $Timestamp)

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)

    $Line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $SummaryLog -Value $Line -Encoding utf8
    Add-Content -Path $DetailLog -Value $Line -Encoding utf8
}

Write-Log "========================================="
Write-Log "GetDayTrends scheduled run started"
Write-Log ("ProjectRoot: {0}" -f $ProjectRoot)

if (-not (Test-Path $PythonExe)) {
    Write-Log ("[ERROR] Python executable not found: {0}" -f $PythonExe)
    exit 1
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = "{0};{1};{2}" -f $WorkspaceRoot, $ProjectRoot, $env:PYTHONPATH
$env:ENABLE_FACT_CHECKING = "false"
$env:HALLUCINATION_ZERO_TOLERANCE = "false"

$CommandArgs = @("main.py", "--one-shot")
if ($DryRun) {
    $CommandArgs += "--dry-run"
}
if ($Limit -gt 0) {
    $CommandArgs += @("--limit", $Limit.ToString())
}
if ($Country) {
    $CommandArgs += @("--country", $Country)
}

Push-Location $ProjectRoot
try {
    Write-Log ("Python: {0}" -f (& $PythonExe --version))
    Write-Log ("PYTHONPATH: {0}" -f $env:PYTHONPATH)
    Write-Log ("Command: {0} {1}" -f $PythonExe, ($CommandArgs -join " "))

    & $PythonExe @CommandArgs 2>&1 | ForEach-Object {
        Add-Content -Path $DetailLog -Value $_.ToString() -Encoding utf8
    }
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -eq 0) {
        Write-Log "[SUCCESS] GetDayTrends scheduled run completed"
    } else {
        Write-Log ("[ERROR] GetDayTrends scheduled run failed with exit code {0}" -f $ExitCode)
    }

    Write-Log ("DetailLog: {0}" -f $DetailLog)
    Write-Log ("Finished: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    Write-Log "========================================="
    exit $ExitCode
}
finally {
    Pop-Location
}

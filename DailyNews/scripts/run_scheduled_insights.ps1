param(
    [ValidateSet("morning", "evening")]
    [string]$Window = "morning"
)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $ProjectRoot "logs\insights"
$PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$Timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$LogFile = Join-Path $LogDir ("{0}_{1}.log" -f $Window, $Timestamp)

$WindowConfig = @{
    morning = @{
        PromptMode = "v2-deep"
        Categories = @("Tech", "AI_Deep", "Economy_KR", "Economy_Global")
    }
    evening = @{
        PromptMode = "v2-multi"
        Categories = @("Tech", "AI_Deep", "Economy_KR", "Economy_Global", "Crypto", "Global_Affairs")
    }
}

$Config = $WindowConfig[$Window]

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)
    Add-Content -Path $LogFile -Value $Message -Encoding utf8
}

Write-Log "========================================="
Write-Log ("DailyNews {0} insight generation started" -f $Window)
Write-Log ("Mode: {0}" -f $Config.PromptMode)
Write-Log ("Started: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Write-Log ("ProjectRoot: {0}" -f $ProjectRoot)
Write-Log "========================================="

if (-not (Test-Path $PythonExe)) {
    Write-Log ("[ERROR] Python executable not found: {0}" -f $PythonExe)
    exit 1
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = "{0}\src;{1}" -f $ProjectRoot, $env:PYTHONPATH

$GenerateArgs = @(
    "-m", "antigravity_mcp",
    "jobs", "generate-brief",
    "--window", $Window,
    "--max-items", "10",
    "--categories"
) + $Config.Categories

Push-Location $ProjectRoot
try {
    Write-Log ("Python: {0}" -f (& $PythonExe --version))
    Write-Log ("PYTHONPATH: {0}" -f $env:PYTHONPATH)
    Write-Log ("Command: {0} {1}" -f $PythonExe, ($GenerateArgs -join " "))

    & $PythonExe @GenerateArgs *>> $LogFile
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -eq 0) {
        Add-Content -Path $LogFile -Value "[SUCCESS] Brief generation completed" -Encoding utf8

        $RefreshArgs = @("-m", "antigravity_mcp", "ops", "refresh-dashboard")
        & $PythonExe @RefreshArgs *>> $LogFile
        if ($LASTEXITCODE -eq 0) {
            Add-Content -Path $LogFile -Value "[SUCCESS] Dashboard refresh completed" -Encoding utf8
        } else {
            Add-Content -Path $LogFile -Value "[WARNING] Dashboard refresh failed" -Encoding utf8
        }
    } else {
        Add-Content -Path $LogFile -Value ("[ERROR] Brief generation failed with exit code {0}" -f $ExitCode) -Encoding utf8
    }

    Add-Content -Path $LogFile -Value ("Finished: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -Encoding utf8
    exit $ExitCode
}
finally {
    Pop-Location
}

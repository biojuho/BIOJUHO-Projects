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
$env:NO_COLOR = "1"
$env:LOGURU_COLORIZE = "false"

$projectRoot = Split-Path -Parent $PSCommandPath
$workspaceRoot = Split-Path -Parent (Split-Path -Parent $projectRoot)
$workspacePython = Join-Path $workspaceRoot ".venv\Scripts\python.exe"
$workspacePyvenvCfg = Join-Path $workspaceRoot ".venv\pyvenv.cfg"
$pythonExe = $workspacePython
if (-not ((Test-Path $workspacePython) -and (Test-Path $workspacePyvenvCfg))) {
    $pythonExe = ""
    $pathPythonCandidates = Get-Command python -All -ErrorAction SilentlyContinue
    foreach ($pathPython in $pathPythonCandidates) {
        $candidatePath = $pathPython.Source
        if (-not $candidatePath) {
            continue
        }
        if ((Test-Path $candidatePath) -and ($candidatePath -ne $workspacePython)) {
            $pythonExe = $candidatePath
            break
        }
    }
}
$mainPy = Join-Path $projectRoot "main.py"
$schedulerLogDir = Join-Path $projectRoot "logs\scheduler"
$summaryLog = Join-Path $projectRoot "run_scheduled.log"
$script:SummaryFallbackUsed = $false

if (-not (Test-Path $pythonExe)) {
    throw "Python runtime not found: $pythonExe"
}

if (-not (Test-Path $mainPy)) {
    throw "Entrypoint not found: $mainPy"
}

New-Item -ItemType Directory -Path $schedulerLogDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$detailLog = Join-Path $schedulerLogDir "run_${timestamp}.log"
$artifactPath = Join-Path $schedulerLogDir "run_${timestamp}.json"
$summaryFallbackLog = Join-Path $schedulerLogDir "summary_${timestamp}.log"
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

function Repair-SummaryLogEncoding {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
        for ($i = 0; $i -lt $bytes.Length; $i++) {
            if ($bytes[$i] -eq 0) {
                $legacyPath = "$Path.legacy-${timestamp}.log"
                Move-Item -LiteralPath $Path -Destination $legacyPath -Force
                return
            }
        }
    }
    catch {
        # Keep scheduler startup resilient; Add-LogLines will surface hard write failures.
        return
    }
}

Repair-SummaryLogEncoding -Path $summaryLog

function Write-LogLine {
    param(
        [string]$Path,
        [string]$Text
    )

    $stream = $null
    $writer = $null
    try {
        $stream = [System.IO.FileStream]::new(
            $Path,
            [System.IO.FileMode]::Append,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::ReadWrite
        )
        $writer = [System.IO.StreamWriter]::new($stream, [System.Text.UTF8Encoding]::new($false))
        $writer.WriteLine($Text)
        $writer.Flush()
    }
    finally {
        if ($null -ne $writer) {
            $writer.Dispose()
        }
        elseif ($null -ne $stream) {
            $stream.Dispose()
        }
    }
}

function Remove-AnsiEscapeSequences {
    param(
        [AllowNull()]
        [string]$Text
    )

    if ($null -eq $Text) {
        return ""
    }

    $escape = [char]27
    return ($Text -replace "$escape\[[0-?]*[ -/]*[@-~]", "")
}

function Add-LogLines {
    param(
        [Parameter(ValueFromPipeline = $true)]
        [AllowNull()]
        [object]$Line
    )

    process {
        $text = if ($null -eq $Line) { "" } else { $Line.ToString() }
        $text = Remove-AnsiEscapeSequences -Text $text
        foreach ($path in @($summaryLog, $detailLog)) {
            $written = $false
            for ($attempt = 1; $attempt -le 5; $attempt++) {
                try {
                    Write-LogLine -Path $path -Text $text
                    $written = $true
                    break
                }
                catch {
                    Start-Sleep -Milliseconds (100 * $attempt)
                }
            }
            if (-not $written) {
                if ($path -eq $detailLog) {
                    throw "Failed to write log after retries: $path"
                }
                for ($attempt = 1; $attempt -le 5; $attempt++) {
                    try {
                        Write-LogLine -Path $summaryFallbackLog -Text $text
                        $written = $true
                        $script:SummaryFallbackUsed = $true
                        break
                    }
                    catch {
                        Start-Sleep -Milliseconds (100 * $attempt)
                    }
                }
            }
        }
    }
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

$header | Add-LogLines

Push-Location $projectRoot
try {
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $pythonExe @argsList 2>&1 |
            ForEach-Object { $_.ToString() } |
            Add-LogLines
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
$durationSeconds = [Math]::Round(($finish - $start).TotalSeconds, 3)
$generatedCount = $null
$savedCount = $null
$errorCount = $null

try {
    $detailText = Get-Content -Raw -Path $detailLog -ErrorAction Stop
    $metricMatches = [regex]::Matches(
        $detailText,
        "pipeline_metrics \| .*?\bgenerated=(\d+)\s+saved=(\d+)\s+errors=(\d+)"
    )
    if ($metricMatches.Count -gt 0) {
        $lastMetric = $metricMatches[$metricMatches.Count - 1]
        $generatedCount = [int]$lastMetric.Groups[1].Value
        $savedCount = [int]$lastMetric.Groups[2].Value
        $errorCount = [int]$lastMetric.Groups[3].Value
    }
}
catch {
    "ArtifactMetricParseWarning: $($_.Exception.Message)" | Add-LogLines
}

$artifact = [ordered]@{
    status = $(if ($exitCode -eq 0) { "success" } else { "failed" })
    exit_code = $exitCode
    started_at = $start.ToString("o")
    finished_at = $finish.ToString("o")
    duration_seconds = $durationSeconds
    project_root = $projectRoot
    python = $pythonExe
    command = "$pythonExe $($argsList -join ' ')"
    artifact_path = $artifactPath
    summary_log = $summaryLog
    summary_fallback_log = $summaryFallbackLog
    summary_fallback_used = [bool]$script:SummaryFallbackUsed
    detail_log = $detailLog
    country = $Country
    limit = $Limit
    dry_run = [bool]$DryRun
    generated = $generatedCount
    saved = $savedCount
    errors = $errorCount
}

try {
    $artifactJson = ($artifact | ConvertTo-Json -Depth 4) + [Environment]::NewLine
    [System.IO.File]::WriteAllText($artifactPath, $artifactJson, [System.Text.UTF8Encoding]::new($false))
}
catch {
    "ArtifactWriteWarning: $($_.Exception.Message)" | Add-LogLines
}

if ($exitCode -eq 0) {
    @(
        "[SUCCESS] GetDayTrends scheduled run completed"
        "DetailLog: $detailLog"
        "Artifact: $artifactPath"
        "Finished: $($finish.ToString('yyyy-MM-dd HH:mm:ss'))"
        "DurationSeconds: $durationSeconds"
        "========================================="
    ) | Add-LogLines
    exit 0
}

@(
    "[ERROR] GetDayTrends scheduled run failed with exit code $exitCode"
    "DetailLog: $detailLog"
    "Artifact: $artifactPath"
    "Finished: $($finish.ToString('yyyy-MM-dd HH:mm:ss'))"
    "DurationSeconds: $durationSeconds"
    "========================================="
) | Add-LogLines
exit $exitCode

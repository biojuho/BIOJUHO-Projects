param(
    [string]$Country = "korea",
    [int]$Limit = 1,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$projectRoot = Split-Path -Parent $PSCommandPath
$workspaceRoot = Split-Path -Parent $projectRoot
$pythonExe = Join-Path $workspaceRoot ".venv\Scripts\python.exe"
$utf8Runner = Join-Path $workspaceRoot ".agents\skills\windows-encoding-safe-test\scripts\run_utf8_safe.py"
$schedulerRunner = Join-Path $projectRoot "run_scheduled_getdaytrends.ps1"

if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "== $Name =="
    & $Action
}

function Invoke-Utf8Command {
    param(
        [string]$Command,
        [string]$Cwd
    )

    if (Test-Path $utf8Runner) {
        & $pythonExe $utf8Runner --cwd $Cwd --command $Command --strict
    }
    else {
        Push-Location $Cwd
        try {
            cmd /c "chcp 65001 >nul && $Command"
        }
        finally {
            Pop-Location
        }
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command"
    }
}

function Get-ActiveTaskName {
    foreach ($taskName in @("GetDayTrends_CurrentUser", "GetDayTrends")) {
        try {
            $null = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
            return $taskName
        }
        catch {
        }
    }

    throw "No GetDayTrends scheduled task found."
}

Invoke-Step "Environment" {
    if (-not (Test-Path (Join-Path $projectRoot ".env"))) {
        throw ".env file not found at $projectRoot"
    }

    $envCheck = @'
from __future__ import annotations
import json
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.getcwd(), ".env"))

summary = {
    "storage_type": os.getenv("STORAGE_TYPE", ""),
    "notion_token_set": bool(os.getenv("NOTION_TOKEN")),
    "notion_database_id_set": bool(os.getenv("NOTION_DATABASE_ID")),
    "content_hub_database_id_set": bool(os.getenv("CONTENT_HUB_DATABASE_ID")),
    "google_api_key_set": bool(os.getenv("GOOGLE_API_KEY")),
    "anthropic_api_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
    "openai_api_key_set": bool(os.getenv("OPENAI_API_KEY")),
    "telegram_bot_token_set": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
    "discord_webhook_url_set": bool(os.getenv("DISCORD_WEBHOOK_URL")),
    "database_url_set": bool(os.getenv("DATABASE_URL")),
}

print(json.dumps(summary, indent=2))
'@
    $tempScript = Join-Path $env:TEMP "getdaytrends_env_check.py"
    Set-Content -Path $tempScript -Value $envCheck -Encoding utf8
    Push-Location $projectRoot
    try {
        & $pythonExe $tempScript
    }
    finally {
        Pop-Location
        Remove-Item $tempScript -ErrorAction SilentlyContinue
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Environment check failed."
    }
}

Invoke-Step "Entrypoint" {
    Invoke-Utf8Command -Cwd $projectRoot -Command "python main.py --help"
}

if (-not $SkipTests) {
    Invoke-Step "Syntax Check" {
        Invoke-Utf8Command -Cwd $projectRoot -Command "python -m py_compile main.py core/pipeline.py core/pipeline_steps.py generator.py content_qa.py prompt_builder.py utils.py"
    }

    Invoke-Step "Core Tests" {
        Invoke-Utf8Command -Cwd $projectRoot -Command "python -m pytest tests/test_config.py tests/test_models.py tests/test_prompt_builder.py tests/test_utils.py tests/test_pipeline_steps.py -q"
    }

    Invoke-Step "QA Regression Tests" {
        Invoke-Utf8Command -Cwd $projectRoot -Command "python -m pytest tests/test_generator.py -q -k AuditGeneratedContent"
    }
}

Invoke-Step "Scheduler Dry Run" {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $schedulerRunner -DryRun -Limit $Limit -Country $Country
    if ($LASTEXITCODE -ne 0) {
        throw "Scheduler dry run failed with exit code $LASTEXITCODE"
    }
}

Invoke-Step "Scheduler Status" {
    $taskName = Get-ActiveTaskName
    $task = Get-ScheduledTask -TaskName $taskName
    $info = Get-ScheduledTaskInfo -TaskName $taskName
    $latestLog = Get-ChildItem -Path (Join-Path $projectRoot "logs\scheduler") |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    $pipelineMetrics = ""
    $successMarker = $false

    if ($latestLog) {
        $pipelineMetrics = Select-String -Path $latestLog.FullName -Pattern "pipeline_metrics \|" |
            Select-Object -Last 1 |
            ForEach-Object { $_.Line }
        $successMarker = [bool](Select-String -Path $latestLog.FullName -Pattern "\[SUCCESS\] GetDayTrends scheduled run completed")
    }

    [pscustomobject]@{
        TaskName = $taskName
        State = $task.State
        LastRunTime = $info.LastRunTime
        LastTaskResult = $info.LastTaskResult
        NextRunTime = $info.NextRunTime
        LatestLog = if ($latestLog) { $latestLog.FullName } else { "" }
        SuccessMarker = $successMarker
        PipelineMetrics = $pipelineMetrics
    } | Format-List

    if ($info.LastTaskResult -ne 0) {
        throw "Scheduled task last result is not zero: $($info.LastTaskResult)"
    }

    if (-not $successMarker) {
        throw "Latest scheduler log does not contain a success marker."
    }
}

Write-Host ""
Write-Host "[OK] Local deployment validation completed."

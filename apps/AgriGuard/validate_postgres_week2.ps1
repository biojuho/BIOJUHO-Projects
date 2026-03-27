param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"

$projectRoot = Split-Path -Parent $PSCommandPath
$workspaceRoot = Split-Path -Parent $projectRoot
$backendDir = Join-Path $projectRoot "backend"
$composeFile = Join-Path $projectRoot "docker-compose.yml"
$pythonExe = Join-Path $workspaceRoot ".venv\Scripts\python.exe"
$utf8Runner = Join-Path $workspaceRoot ".agents\skills\windows-encoding-safe-test\scripts\run_utf8_safe.py"

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

function Load-DotEnv {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $pair = $trimmed -split "=", 2
        if ($pair.Count -ne 2) {
            continue
        }

        $name = $pair[0].Trim()
        $value = $pair[1].Trim()

        if ($value.Length -ge 2) {
            if (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            ) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Normalize-LocalDatabaseUrl {
    if (-not $env:DATABASE_URL) {
        return
    }

    $env:DATABASE_URL = $env:DATABASE_URL -replace "@postgres:5432/", "@localhost:5432/"
    $env:DATABASE_URL = $env:DATABASE_URL -replace "@agriguard-postgres:5432/", "@localhost:5432/"
}

function Get-SanitizedDatabaseUrl {
    if (-not $env:DATABASE_URL) {
        return ""
    }

    if ($env:DATABASE_URL -notmatch "://" -or $env:DATABASE_URL -notmatch "@") {
        return $env:DATABASE_URL
    }

    $parts = $env:DATABASE_URL -split "://", 2
    $scheme = $parts[0]
    $hostPart = ($parts[1] -split "@")[-1]
    return "${scheme}://***@${hostPart}"
}

function Get-ServiceSummary {
    param([string[]]$Names)

    $services = foreach ($name in $Names) {
        Get-Service -Name $name -ErrorAction SilentlyContinue
    }

    if (-not $services) {
        return "not found"
    }

    return ($services | ForEach-Object {
            "$($_.Name)=$($_.Status)/$($_.StartType)"
        }) -join ", "
}

function Get-RecentDockerBackendHint {
    $backendLog = Join-Path $env:LOCALAPPDATA "Docker\log\host\com.docker.backend.exe.log"
    if (-not (Test-Path $backendLog)) {
        return ""
    }

    $lines = Get-Content $backendLog -Tail 120 | Where-Object {
        $_ -match "Wsl/0x80070422|engine linux/wsl failed to start|dockerDesktopLinuxEngine"
    }

    if (-not $lines) {
        return ""
    }

    $sanitizedLines = foreach ($line in $lines) {
        if ($line -match "Wsl/0x80070422") {
            "Docker backend log: WSL engine startup failed with Wsl/0x80070422 because a required Windows service is disabled."
            continue
        }

        $line
    }

    return (($sanitizedLines | Select-Object -Unique) -join [Environment]::NewLine)
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

function Assert-DockerDaemon {
    $dockerVersionOutput = (cmd /c "docker version 2>&1" | Out-String).Trim()
    if ($LASTEXITCODE -eq 0) {
        return
    }

    $dockerServiceSummary = Get-ServiceSummary -Names @("com.docker.service")
    $wslServiceSummary = Get-ServiceSummary -Names @("WslService", "LxssManager", "vmcompute")
    $recentDockerBackendHint = Get-RecentDockerBackendHint

    if ($recentDockerBackendHint -match "Wsl/0x80070422") {
        throw @"
Docker daemon is unavailable.
Docker Desktop is failing to start its WSL engine with Wsl/0x80070422.

Detected services:
- Docker: $dockerServiceSummary
- WSL/Hyper-V: $wslServiceSummary

Recovery:
1. Open an elevated PowerShell or Windows Terminal.
2. Re-enable and start the disabled WSL/Hyper-V services. On this machine, WslService is currently the likely blocker.
3. Start Docker Desktop again and wait until `docker version` shows both Client and Server sections.
4. Re-run:
   powershell -NoProfile -ExecutionPolicy Bypass -File AgriGuard/validate_postgres_week2.ps1

docker version output:
$dockerVersionOutput

Recent Docker backend log lines:
$recentDockerBackendHint
"@
    }

    throw @"
Docker daemon is unavailable. Start Docker Desktop and retry.

Detected services:
- Docker: $dockerServiceSummary
- WSL/Hyper-V: $wslServiceSummary

docker version output:
$dockerVersionOutput
"@
}

Invoke-Step "Environment" {
    Load-DotEnv (Join-Path $projectRoot ".env")
    Load-DotEnv (Join-Path $backendDir ".env")

    if (-not $env:DATABASE_URL) {
        $dbUser = if ($env:AGRIGUARD_DB_USER) { $env:AGRIGUARD_DB_USER } else { "agriguard" }
        $dbPassword = if ($env:AGRIGUARD_DB_PASSWORD) { $env:AGRIGUARD_DB_PASSWORD } else { "agriguard_secret" }
        $dbName = if ($env:AGRIGUARD_DB_NAME) { $env:AGRIGUARD_DB_NAME } else { "agriguard" }
        $env:DATABASE_URL = "postgresql://$dbUser`:$dbPassword@localhost:5432/$dbName"
    }

    Normalize-LocalDatabaseUrl

    if ($env:DATABASE_URL -like "sqlite*") {
        throw "DATABASE_URL still points to SQLite. Update AgriGuard/backend/.env to a PostgreSQL URL before running Week 2 validation."
    }

    if (-not $env:AUTO_CREATE_SCHEMA) {
        $env:AUTO_CREATE_SCHEMA = "false"
    }

    [pscustomobject]@{
        RootEnvPresent = Test-Path (Join-Path $projectRoot ".env")
        BackendEnvPresent = Test-Path (Join-Path $backendDir ".env")
        DatabaseUrl = Get-SanitizedDatabaseUrl
        AutoCreateSchema = $env:AUTO_CREATE_SCHEMA
    } | Format-List
}

Invoke-Step "Docker" {
    Assert-DockerDaemon
    docker compose -f $composeFile up -d postgres --wait
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start PostgreSQL with docker compose."
    }

    docker compose -f $composeFile ps postgres
}

Invoke-Step "Migrations" {
    Invoke-Utf8Command -Cwd $backendDir -Command "python scripts/run_migrations.py"
}

Invoke-Step "Connection Smoke" {
    Invoke-Utf8Command -Cwd $backendDir -Command "python scripts/check_database_connection.py"
}

if (-not $SkipTests) {
    Invoke-Step "Backend Smoke Tests" {
        Invoke-Utf8Command -Cwd $backendDir -Command "python -m pytest tests/test_database_config.py tests/test_smoke.py -q --override-ini addopts="
    }
}

Write-Host ""
Write-Host "[OK] AgriGuard PostgreSQL Week 2 validation completed."

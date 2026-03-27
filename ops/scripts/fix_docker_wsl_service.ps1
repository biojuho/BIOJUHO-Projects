<#
.SYNOPSIS
    Fix Docker Desktop WSL service issues (Wsl/0x80070422)

.DESCRIPTION
    Enables and starts WslService, vmcompute, and Docker Desktop service.
    Requires Administrator privileges.

.EXAMPLE
    # Run as Administrator
    powershell -ExecutionPolicy Bypass -File scripts/fix_docker_wsl_service.ps1

.NOTES
    Created: 2026-03-24
    Related: docs/DOCKER_WSL_SERVICE_FIX.md
#>

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

Write-Host "`n=== Docker WSL Service Fix ===" -ForegroundColor Cyan
Write-Host "This script will enable and start required services for Docker Desktop`n"

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] This script requires Administrator privileges" -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again.`n" -ForegroundColor Yellow
    exit 1
}

Write-Host "[INFO] Running with Administrator privileges`n" -ForegroundColor Green

# Function to check service status
function Get-ServiceStatus {
    param([string]$ServiceName)

    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -eq $service) {
        return "NotFound"
    }
    return "$($service.Status) ($($service.StartType))"
}

# Display current status
Write-Host "=== Current Service Status ===" -ForegroundColor Cyan
$services = @("WslService", "vmcompute", "com.docker.service")
foreach ($svc in $services) {
    $status = Get-ServiceStatus -ServiceName $svc
    Write-Host "  $svc : $status" -ForegroundColor Yellow
}
Write-Host ""

# Fix WslService
Write-Host "[1/4] Enabling WslService..." -ForegroundColor Cyan
try {
    $wslService = Get-Service -Name WslService -ErrorAction SilentlyContinue

    if ($null -eq $wslService) {
        Write-Host "[WARN] WslService not found. WSL may not be installed." -ForegroundColor Yellow
        Write-Host "[INFO] Installing WSL (this may take a few minutes)..." -ForegroundColor Cyan

        # Enable WSL feature
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart -WarningAction SilentlyContinue

        Write-Host "[OK] WSL feature enabled. A reboot may be required." -ForegroundColor Green
    }
    elseif ($wslService.StartType -eq "Disabled") {
        Set-Service -Name WslService -StartupType Manual
        Write-Host "[OK] WslService startup type changed to Manual" -ForegroundColor Green
    }
    else {
        Write-Host "[OK] WslService already enabled" -ForegroundColor Green
    }
}
catch {
    Write-Host "[ERROR] Failed to enable WslService: $($_.Exception.Message)" -ForegroundColor Red
}

# Start WslService
Write-Host "`n[2/4] Starting WslService..." -ForegroundColor Cyan
try {
    $wslService = Get-Service -Name WslService -ErrorAction SilentlyContinue
    if ($null -ne $wslService -and $wslService.Status -ne "Running") {
        Start-Service WslService -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2

        $wslService = Get-Service -Name WslService
        if ($wslService.Status -eq "Running") {
            Write-Host "[OK] WslService is now running" -ForegroundColor Green
        }
        else {
            Write-Host "[WARN] WslService status: $($wslService.Status)" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "[OK] WslService already running" -ForegroundColor Green
    }
}
catch {
    Write-Host "[WARN] Could not start WslService: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Start vmcompute
Write-Host "`n[3/4] Starting vmcompute (Hyper-V Host Compute Service)..." -ForegroundColor Cyan
try {
    $vmService = Get-Service -Name vmcompute -ErrorAction SilentlyContinue
    if ($null -ne $vmService -and $vmService.Status -ne "Running") {
        Start-Service vmcompute -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2

        $vmService = Get-Service -Name vmcompute
        if ($vmService.Status -eq "Running") {
            Write-Host "[OK] vmcompute is now running" -ForegroundColor Green
        }
        else {
            Write-Host "[WARN] vmcompute status: $($vmService.Status)" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "[OK] vmcompute already running" -ForegroundColor Green
    }
}
catch {
    Write-Host "[WARN] Could not start vmcompute: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Start Docker Desktop service
Write-Host "`n[4/4] Starting Docker Desktop Service..." -ForegroundColor Cyan
try {
    $dockerService = Get-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
    if ($null -ne $dockerService -and $dockerService.Status -ne "Running") {
        Start-Service "com.docker.service" -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3

        $dockerService = Get-Service -Name "com.docker.service"
        if ($dockerService.Status -eq "Running") {
            Write-Host "[OK] Docker Desktop Service is now running" -ForegroundColor Green
        }
        else {
            Write-Host "[WARN] Docker Desktop Service status: $($dockerService.Status)" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "[OK] Docker Desktop Service already running" -ForegroundColor Green
    }
}
catch {
    Write-Host "[WARN] Could not start Docker Desktop Service: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Final status check
Write-Host "`n=== Final Service Status ===" -ForegroundColor Cyan
$allRunning = $true
foreach ($svc in $services) {
    $service = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if ($null -ne $service) {
        $color = if ($service.Status -eq "Running") { "Green" } else { "Yellow" }
        Write-Host "  $svc : $($service.Status) ($($service.StartType))" -ForegroundColor $color
        if ($service.Status -ne "Running") {
            $allRunning = $false
        }
    }
    else {
        Write-Host "  $svc : NotFound" -ForegroundColor Red
        $allRunning = $false
    }
}

# Wait for Docker Engine to be ready
if ($allRunning) {
    Write-Host "`n[INFO] Waiting for Docker Engine to be ready..." -ForegroundColor Cyan
    Write-Host "(This may take 10-30 seconds)`n" -ForegroundColor Gray

    $maxAttempts = 15
    $dockerReady = $false

    for ($i = 1; $i -le $maxAttempts; $i++) {
        Start-Sleep -Seconds 2

        $dockerVersion = docker version 2>&1 | Out-String
        if ($dockerVersion -match "Server:.*Version") {
            Write-Host "[OK] Docker Engine is ready!" -ForegroundColor Green
            $dockerReady = $true
            break
        }

        Write-Host "  Attempt $i/$maxAttempts : Waiting for Docker daemon..." -ForegroundColor Gray
    }

    if ($dockerReady) {
        Write-Host "`n=== Docker Verification ===" -ForegroundColor Cyan
        docker version

        Write-Host "`n[SUCCESS] Docker Desktop is fully operational!" -ForegroundColor Green
        Write-Host "`nNext steps:" -ForegroundColor Cyan
        Write-Host "  1. Run: docker compose up -d" -ForegroundColor White
        Write-Host "  2. Run: powershell -ExecutionPolicy Bypass -File AgriGuard\validate_postgres_week2.ps1`n" -ForegroundColor White
        exit 0
    }
    else {
        Write-Host "`n[WARN] Services started but Docker Engine did not respond within $($maxAttempts*2) seconds" -ForegroundColor Yellow
        Write-Host "Try starting Docker Desktop manually: 'C:\Program Files\Docker\Docker\Docker Desktop.exe'`n" -ForegroundColor Yellow
        exit 2
    }
}
else {
    Write-Host "`n[ERROR] Some services failed to start" -ForegroundColor Red
    Write-Host "Please check Event Viewer or try manual steps in: docs/DOCKER_WSL_SERVICE_FIX.md`n" -ForegroundColor Yellow
    exit 1
}

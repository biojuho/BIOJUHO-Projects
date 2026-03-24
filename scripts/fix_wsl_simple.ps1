#Requires -RunAsAdministrator

Write-Host "`n=== Docker WSL Quick Fix ===" -ForegroundColor Cyan

# Enable WslService
Write-Host "[1/4] Enabling WslService..." -ForegroundColor Yellow
try {
    Set-Service -Name WslService -StartupType Manual -ErrorAction Stop
    Write-Host "  OK - WslService enabled" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    exit 1
}

# Start WslService
Write-Host "[2/4] Starting WslService..." -ForegroundColor Yellow
try {
    Start-Service WslService -ErrorAction Stop
    Start-Sleep -Seconds 2
    Write-Host "  OK - WslService started" -ForegroundColor Green
} catch {
    Write-Host "  WARN: $_" -ForegroundColor Yellow
}

# Start vmcompute
Write-Host "[3/4] Starting vmcompute..." -ForegroundColor Yellow
try {
    Start-Service vmcompute -ErrorAction Stop
    Start-Sleep -Seconds 2
    Write-Host "  OK - vmcompute started" -ForegroundColor Green
} catch {
    Write-Host "  WARN: $_" -ForegroundColor Yellow
}

# Start Docker service
Write-Host "[4/4] Starting Docker Desktop Service..." -ForegroundColor Yellow
try {
    Start-Service com.docker.service -ErrorAction Stop
    Start-Sleep -Seconds 3
    Write-Host "  OK - Docker service started" -ForegroundColor Green
} catch {
    Write-Host "  WARN: $_" -ForegroundColor Yellow
}

# Check status
Write-Host "`n=== Service Status ===" -ForegroundColor Cyan
Get-Service -Name 'WslService','vmcompute','com.docker.service' | Format-Table Name,Status -AutoSize

Write-Host "`nWaiting for Docker Engine (20 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

Write-Host "`nTesting Docker..." -ForegroundColor Cyan
docker version

Write-Host "`n=== SUCCESS ===" -ForegroundColor Green
Write-Host "Docker is ready! You can close this window.`n"
Read-Host "Press Enter to exit"

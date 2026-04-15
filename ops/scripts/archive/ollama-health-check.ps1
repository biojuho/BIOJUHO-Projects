<#
.SYNOPSIS
    Ollama Health Check & Auto-Restart Script
.DESCRIPTION
    5분마다 실행하여 Ollama 서버 상태를 확인하고,
    응답 없으면 자동 재시작합니다.
#>

$ErrorActionPreference = "SilentlyContinue"
$OllamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
$LogFile = "$PSScriptRoot\..\logs\ollama-health.log"

# 로그 디렉토리 생성
$logDir = Split-Path $LogFile -Parent
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts | $msg" | Out-File -Append -FilePath $LogFile -Encoding utf8
}

# 1. 프로세스 확인
$proc = Get-Process "ollama" -ErrorAction SilentlyContinue
if (-not $proc) {
    Write-Log "WARN: Ollama process not found. Starting..."
    if (Test-Path $OllamaExe) {
        Start-Process $OllamaExe -WindowStyle Hidden
        Start-Sleep -Seconds 5
        Write-Log "INFO: Ollama started via '$OllamaExe'"
    } else {
        Write-Log "ERROR: Ollama executable not found at '$OllamaExe'"
        exit 1
    }
}

# 2. API 헬스 체크 (http://localhost:11434)
try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434" -TimeoutSec 10
    if ($response -match "Ollama is running") {
        Write-Log "OK: Ollama API responding (PID=$($proc.Id))"
    } else {
        Write-Log "WARN: Unexpected response: $response"
    }
} catch {
    Write-Log "ERROR: API health check failed: $($_.Exception.Message)"

    # 응답 없으면 재시작 시도
    Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue
    Stop-Process -Name "ollama app" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3

    if (Test-Path $OllamaExe) {
        Start-Process $OllamaExe -WindowStyle Hidden
        Start-Sleep -Seconds 5
        Write-Log "INFO: Ollama restarted after API failure"
    }
}

# 3. 로그 rotation (1MB 초과 시 truncate)
if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt 1MB)) {
    $lines = Get-Content $LogFile -Tail 100
    $lines | Set-Content $LogFile -Encoding utf8
    Write-Log "INFO: Log rotated (kept last 100 lines)"
}

# ===================================================
# AI Projects Workspace - 원클릭 개발 환경 설정 스크립트
# Docker Compose 통합 개발 환경을 자동으로 설정합니다
# ===================================================
#
# 사용법:
#   PowerShell -ExecutionPolicy Bypass -File scripts/setup_dev_environment.ps1
#
# 옵션:
#   -Profile <profile>    실행할 프로필 (desci, agriguard, tools, monitoring, full)
#   -Down                 서비스 중지
#   -Clean                볼륨까지 완전히 제거
#   -Status               서비스 상태만 확인
#
# 예시:
#   setup_dev_environment.ps1                          # 기본 서비스 실행
#   setup_dev_environment.ps1 -Profile desci           # DeSci만 실행
#   setup_dev_environment.ps1 -Profile full            # 모든 서비스 실행
#   setup_dev_environment.ps1 -Down                    # 서비스 중지
#   setup_dev_environment.ps1 -Clean                   # 완전 제거
#   setup_dev_environment.ps1 -Status                  # 상태 확인
#
# ===================================================

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("desci", "agriguard", "tools", "monitoring", "full")]
    [string]$Profile = "",

    [Parameter(Mandatory=$false)]
    [switch]$Down = $false,

    [Parameter(Mandatory=$false)]
    [switch]$Clean = $false,

    [Parameter(Mandatory=$false)]
    [switch]$Status = $false
)

# 색상 함수
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Header {
    param([string]$Title)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Message)
    Write-ColorOutput "[*] $Message" "Green"
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "[+] $Message" "Green"
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "[!] $Message" "Yellow"
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-ColorOutput "[x] $Message" "Red"
}

function Invoke-CheckedExpression {
    param([string]$Command)
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command"
    }
}

# 워크스페이스 루트로 이동
$WorkspaceRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $WorkspaceRoot

Write-Header "AI Projects Workspace - Dev Environment Setup"
Write-ColorOutput "Workspace: $WorkspaceRoot" "Gray"
Write-ColorOutput "Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" "Gray"
Write-Host ""

# ===================================================
# 1. 사전 요구사항 확인
# ===================================================

Write-Header "1. Checking Prerequisites"

# Docker 설치 확인
Write-Step "Checking Docker installation..."
try {
    $dockerVersion = docker --version
    if ($LASTEXITCODE -ne 0) {
        throw "docker --version failed with exit code $LASTEXITCODE"
    }
    Write-Success "Docker found: $dockerVersion"
} catch {
    Write-ErrorMsg "Docker is not installed or not in PATH"
    Write-Warning "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
    exit 1
}

# Docker Compose 확인
Write-Step "Checking Docker Compose..."
try {
    $composeVersion = docker compose version
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose version failed with exit code $LASTEXITCODE"
    }
    Write-Success "Docker Compose found: $composeVersion"
} catch {
    Write-ErrorMsg "Docker Compose is not available"
    Write-Warning "Please upgrade Docker Desktop to the latest version"
    exit 1
}

# Docker Daemon 실행 확인
Write-Step "Checking Docker daemon..."
try {
    docker ps | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "docker ps failed with exit code $LASTEXITCODE"
    }
    Write-Success "Docker daemon is running"
} catch {
    Write-ErrorMsg "Docker daemon is not running"
    Write-Warning "Please start Docker Desktop"
    exit 1
}

# Docker Compose engine access 확인
Write-Step "Checking Docker Compose engine access..."
try {
    docker compose ls | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose ls failed with exit code $LASTEXITCODE"
    }
    Write-Success "Docker Compose can reach the container engine"
} catch {
    Write-ErrorMsg "Docker Compose cannot reach the container engine"
    Write-Warning "If Docker Desktop just started, wait a moment and retry."
    Write-Warning "If you are on Windows, ensure the Linux container engine is running."
    exit 1
}

# .env 파일 확인
Write-Step "Checking .env file..."
if (Test-Path ".env") {
    Write-Success ".env file found"
} else {
    Write-Warning ".env file not found. Creating from .env.example..."
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-ColorOutput "Please edit .env file with your API keys before proceeding!" "Yellow"
        Write-ColorOutput "Press any key to continue after editing .env..." "Yellow"
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    } else {
        Write-ErrorMsg ".env.example not found. Cannot create .env file."
        exit 1
    }
}

# docker-compose.dev.yml 확인
Write-Step "Checking docker-compose.dev.yml..."
if (Test-Path "docker-compose.dev.yml") {
    Write-Success "docker-compose.dev.yml found"
} else {
    Write-ErrorMsg "docker-compose.dev.yml not found in $WorkspaceRoot"
    exit 1
}

# ===================================================
# 2. 상태 확인 모드
# ===================================================

if ($Status) {
    Write-Header "2. Service Status"
    try {
        Invoke-CheckedExpression "docker compose -f docker-compose.dev.yml ps"
        Write-Host ""
        Write-ColorOutput "Disk usage:" "Cyan"
        Invoke-CheckedExpression "docker system df"
    } catch {
        Write-ErrorMsg "Failed to read service status: $_"
        exit 1
    }
    exit 0
}

# ===================================================
# 3. 서비스 중지 모드
# ===================================================

if ($Down -or $Clean) {
    Write-Header "2. Stopping Services"

    Write-Step "Stopping all containers..."
    try {
        Invoke-CheckedExpression "docker compose -f docker-compose.dev.yml down"
    } catch {
        Write-ErrorMsg "Failed to stop services: $_"
        exit 1
    }

    if ($Clean) {
        Write-Warning "Cleaning mode: This will DELETE ALL DATA (volumes)!"
        Write-ColorOutput "Press 'Y' to confirm or any other key to cancel..." "Yellow"
        $confirmation = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

        if ($confirmation.Character -eq 'Y' -or $confirmation.Character -eq 'y') {
            Write-Step "Removing volumes..."
            Invoke-CheckedExpression "docker compose -f docker-compose.dev.yml down -v"

            Write-Step "Pruning Docker system..."
            Invoke-CheckedExpression "docker system prune -f"

            Write-Success "Clean completed. All data removed."
        } else {
            Write-ColorOutput "Clean cancelled." "Yellow"
        }
    } else {
        Write-Success "Services stopped (volumes preserved)"
    }
    exit 0
}

# ===================================================
# 4. 서비스 시작
# ===================================================

Write-Header "2. Starting Services"

# 프로필에 따라 명령어 구성
$composeCmd = "docker compose -f docker-compose.dev.yml"
if ($Profile -ne "") {
    $composeCmd += " --profile $Profile"
    Write-ColorOutput "Profile: $Profile" "Cyan"
} else {
    Write-ColorOutput "Profile: default (all base services)" "Cyan"
}

# Pull latest images (optional, can skip for faster startup)
# Write-Step "Pulling latest images..."
# Invoke-Expression "$composeCmd pull"

# 서비스 시작
Write-Step "Starting services in detached mode..."
try {
    Invoke-CheckedExpression "$composeCmd up -d"
    Write-Success "Services started successfully"
} catch {
    Write-ErrorMsg "Failed to start services: $_"
    Write-Warning "Check logs with: docker compose -f docker-compose.dev.yml logs"
    exit 1
}

# ===================================================
# 5. 서비스 상태 확인
# ===================================================

Write-Header "3. Service Status"

Start-Sleep -Seconds 3

# 컨테이너 상태 출력
Write-Step "Checking container status..."
try {
    Invoke-CheckedExpression "docker compose -f docker-compose.dev.yml ps"
} catch {
    Write-ErrorMsg "Failed to read container status: $_"
    exit 1
}

Write-Host ""

# Health check 확인
Write-Step "Waiting for services to become healthy..."
$maxWait = 60  # 최대 60초 대기
$waited = 0

while ($waited -lt $maxWait) {
    $unhealthy = docker compose -f docker-compose.dev.yml ps --filter "health=unhealthy" --format "{{.Service}}"
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Failed to query unhealthy services."
        exit 1
    }
    $starting = docker compose -f docker-compose.dev.yml ps --filter "health=starting" --format "{{.Service}}"
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Failed to query starting services."
        exit 1
    }

    if (-not $unhealthy -and -not $starting) {
        Write-Success "All services are healthy!"
        break
    }

    Write-ColorOutput "  Waiting... ($waited/$maxWait seconds)" "Gray"
    Start-Sleep -Seconds 5
    $waited += 5
}

if ($waited -ge $maxWait) {
    Write-Warning "Some services may not be healthy yet. Check logs for details."
}

# ===================================================
# 6. 접속 정보 출력
# ===================================================

Write-Header "4. Access Information"

$services = @{
    "DeSci Frontend" = "http://localhost:5173"
    "DeSci API (Swagger)" = "http://localhost:8000/docs"
    "AgriGuard Frontend" = "http://localhost:5174"
    "AgriGuard API (Swagger)" = "http://localhost:8002/docs"
    "ChromaDB" = "http://localhost:8001"
}

if ($Profile -eq "tools" -or $Profile -eq "full") {
    $services["pgAdmin"] = "http://localhost:5050"
}

if ($Profile -eq "monitoring" -or $Profile -eq "full") {
    $services["Prometheus"] = "http://localhost:9090"
    $services["Grafana"] = "http://localhost:3000"
}

foreach ($service in $services.GetEnumerator()) {
    Write-ColorOutput "  $($service.Key): $($service.Value)" "Cyan"
}

Write-Host ""

# ===================================================
# 7. 유용한 명령어 안내
# ===================================================

Write-Header "5. Useful Commands"

Write-ColorOutput "Logs (real-time):" "Yellow"
Write-ColorOutput "  docker compose -f docker-compose.dev.yml logs -f" "Gray"
Write-ColorOutput "  docker compose -f docker-compose.dev.yml logs -f biolinker" "Gray"

Write-ColorOutput "`nRestart service:" "Yellow"
Write-ColorOutput "  docker compose -f docker-compose.dev.yml restart biolinker" "Gray"

Write-ColorOutput "`nStop services:" "Yellow"
Write-ColorOutput "  docker compose -f docker-compose.dev.yml down" "Gray"

Write-ColorOutput "`nAccess container:" "Yellow"
Write-ColorOutput "  docker exec -it dev-biolinker bash" "Gray"

Write-ColorOutput "`nPostgreSQL:" "Yellow"
Write-ColorOutput "  docker exec -it dev-postgres psql -U postgres -d biolinker" "Gray"

Write-Host ""

# ===================================================
# 8. 완료
# ===================================================

Write-Header "Setup Complete!"

Write-ColorOutput "Environment is ready for development." "Green"
Write-ColorOutput "Check service status: " "Cyan" -NoNewline
Write-ColorOutput "docker compose -f docker-compose.dev.yml ps" "White"

Write-Host "`nHappy Coding! 🚀`n" -ForegroundColor Green

# 로그 출력 옵션 (선택)
Write-ColorOutput "Show logs? (Y/n): " "Yellow" -NoNewline
$showLogs = Read-Host
if ($showLogs -eq "" -or $showLogs -eq "Y" -or $showLogs -eq "y") {
    Write-Host ""
    Write-ColorOutput "Showing logs (Ctrl+C to exit)..." "Cyan"
    Start-Sleep -Seconds 2
    docker compose -f docker-compose.dev.yml logs -f
}

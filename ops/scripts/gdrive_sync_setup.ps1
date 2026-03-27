<#
  Google Drive Desktop 동기화 설정 스크립트
  - Google Drive Desktop 설치 확인
  - 프로젝트 폴더를 Google Drive에 스트리밍 동기화
  - 불필요 파일 자동 제외
#>

param(
    [string]$ProjectPath = "D:\AI 프로젝트",
    [string]$DriveLetter = "G"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Google Drive Desktop 동기화 설정" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Google Drive Desktop 설치 확인
$driveFS = Get-ItemProperty "HKLM:\SOFTWARE\Google\DriveFS" -ErrorAction SilentlyContinue
$driveFSUser = Get-ItemProperty "HKCU:\SOFTWARE\Google\DriveFS" -ErrorAction SilentlyContinue
$driveProcess = Get-Process -Name "GoogleDriveFS" -ErrorAction SilentlyContinue

if (-not $driveFS -and -not $driveFSUser -and -not $driveProcess) {
    Write-Host "[!] Google Drive Desktop이 설치되지 않았습니다." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "설치 방법:" -ForegroundColor White
    Write-Host "  1. https://www.google.com/drive/download/ 에서 다운로드" -ForegroundColor Gray
    Write-Host "  2. GoogleDriveSetup.exe 실행" -ForegroundColor Gray
    Write-Host "  3. Google 계정으로 로그인" -ForegroundColor Gray
    Write-Host "  4. 이 스크립트를 다시 실행" -ForegroundColor Gray
    Write-Host ""

    $install = Read-Host "지금 다운로드 페이지를 열까요? (y/n)"
    if ($install -eq 'y') {
        Start-Process "https://www.google.com/drive/download/"
    }
    Write-Host ""
    Write-Host "설치 후 이 스크립트를 다시 실행해주세요." -ForegroundColor Yellow
    exit 0
}

Write-Host "[OK] Google Drive Desktop 감지됨" -ForegroundColor Green

# 2. 프로젝트 폴더 확인
if (-not (Test-Path $ProjectPath)) {
    Write-Host "[ERROR] 프로젝트 폴더를 찾을 수 없습니다: $ProjectPath" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] 프로젝트 폴더: $ProjectPath" -ForegroundColor Green

# 3. Google Drive 마운트 포인트 확인
$gDrivePath = "${DriveLetter}:\내 드라이브"
if (-not (Test-Path $gDrivePath)) {
    $gDrivePath = "${DriveLetter}:\My Drive"
}
if (-not (Test-Path $gDrivePath)) {
    # 다른 경로 시도
    $possiblePaths = @(
        "$env:USERPROFILE\Google Drive",
        "$env:USERPROFILE\Google Drive\내 드라이브",
        "$env:USERPROFILE\Google Drive\My Drive"
    )
    foreach ($p in $possiblePaths) {
        if (Test-Path $p) {
            $gDrivePath = $p
            break
        }
    }
}

if (-not (Test-Path $gDrivePath)) {
    Write-Host "[!] Google Drive 마운트 포인트를 찾을 수 없습니다." -ForegroundColor Yellow
    Write-Host "  Google Drive Desktop 로그인 후 다시 시도해주세요." -ForegroundColor Gray
    Write-Host "  또는 드라이브 문자를 지정: .\gdrive_sync_setup.ps1 -DriveLetter H" -ForegroundColor Gray
    exit 1
}

Write-Host "[OK] Google Drive 경로: $gDrivePath" -ForegroundColor Green

# 4. 동기화 대상 폴더 생성
$syncTarget = Join-Path $gDrivePath "AI-Projects-Backup"
if (-not (Test-Path $syncTarget)) {
    New-Item -ItemType Directory -Path $syncTarget -Force | Out-Null
    Write-Host "[OK] 동기화 폴더 생성: $syncTarget" -ForegroundColor Green
} else {
    Write-Host "[OK] 동기화 폴더 존재: $syncTarget" -ForegroundColor Green
}

# 5. 제외 패턴 정의 (gitignore 기반)
$excludePatterns = @(
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".git",
    ".agent",
    ".agents",
    "artifacts",
    "cache",
    "chroma_db",
    "*.pyc",
    "*.log",
    "*.db",
    "*.sqlite",
    ".env",
    "credentials.json",
    "token.json",
    "serviceAccountKey.json"
)

Write-Host ""
Write-Host "제외 패턴: $($excludePatterns.Count)개" -ForegroundColor Gray
Write-Host "  $($excludePatterns -join ', ')" -ForegroundColor DarkGray

# 6. Robocopy로 미러 동기화 (제외 적용)
Write-Host ""
Write-Host "동기화 시작..." -ForegroundColor Cyan

$excludeDirs = @("node_modules", "__pycache__", ".venv", "venv", "dist", "build",
                  ".git", ".agent", ".agents", "artifacts", "cache", "chroma_db",
                  "test-results", "output", "data", "ignition")
$excludeFiles = @("*.pyc", "*.log", "*.db", "*.sqlite", ".env", "credentials.json",
                   "token.json", "serviceAccountKey.json", "*.tmp", "canva_url.txt",
                   "package-lock.json")

$robocopyArgs = @(
    "`"$ProjectPath`"",
    "`"$syncTarget`"",
    "/MIR",        # 미러 (추가+삭제)
    "/MT:8",       # 8 스레드
    "/R:1",        # 재시도 1회
    "/W:1",        # 대기 1초
    "/NFL",        # 파일 리스트 안 보임
    "/NDL",        # 디렉터리 리스트 안 보임
    "/NJH",        # 헤더 없음
    "/NJS",        # 요약 없음
    "/XD $($excludeDirs -join ' ')",
    "/XF $($excludeFiles -join ' ')"
)

# Robocopy 실행
$cmd = "robocopy `"$ProjectPath`" `"$syncTarget`" /MIR /MT:8 /R:1 /W:1 /XD $($excludeDirs -join ' ') /XF $($excludeFiles -join ' ')"
Write-Host "실행: $cmd" -ForegroundColor DarkGray
Invoke-Expression $cmd

$exitCode = $LASTEXITCODE
if ($exitCode -le 3) {
    Write-Host ""
    Write-Host "[OK] 동기화 완료!" -ForegroundColor Green

    # 동기화 결과 요약
    $fileCount = (Get-ChildItem -Path $syncTarget -Recurse -File -ErrorAction SilentlyContinue).Count
    $sizeMB = [math]::Round((Get-ChildItem -Path $syncTarget -Recurse -File -ErrorAction SilentlyContinue |
               Measure-Object -Property Length -Sum).Sum / 1MB, 1)

    Write-Host "  파일 수: $fileCount" -ForegroundColor Gray
    Write-Host "  총 크기: ${sizeMB} MB" -ForegroundColor Gray
    Write-Host "  위치: $syncTarget" -ForegroundColor Gray
} else {
    Write-Host "[ERROR] Robocopy 오류 (exit code: $exitCode)" -ForegroundColor Red
}

# 7. 자동 동기화 스케줄 등록 안내
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  자동 동기화 설정 (선택)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "매시간 자동 동기화를 설정하려면:" -ForegroundColor White
Write-Host '  schtasks /create /tn "AI-Projects-GDrive-Sync" /tr "powershell -ExecutionPolicy Bypass -File \"D:\AI 프로젝트\scripts\gdrive_sync_setup.ps1\"" /sc hourly /st 00:00' -ForegroundColor Gray
Write-Host ""
Write-Host "수동 동기화: 이 스크립트를 다시 실행" -ForegroundColor Gray
Write-Host ""

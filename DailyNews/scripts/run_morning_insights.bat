@echo off
REM =========================================================================
REM DailyNews - Morning Insight Generation (오전 7시 실행)
REM =========================================================================
REM
REM v2-deep 모드: 1개 Signal 딥다이브 분석
REM 카테고리: Tech + AI_Deep, Economy_KR, Economy_Global
REM 수집 범위: 전날 18시 ~ 당일 7시 (13시간)
REM
REM 업데이트: 2026-03-22 (v2 프롬프트 + 2회 통합 스케줄)
REM =========================================================================

setlocal enabledelayedexpansion

REM 프롬프트 모드 설정
set PROMPT_VERSION=v2-deep

REM 로그 디렉토리 생성
set LOG_DIR=d:\AI 프로젝트\DailyNews\logs\insights
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 날짜 및 시간 설정 (로그 파일명용)
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set DATE=%%c-%%a-%%b
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIME=%%a%%b
set LOGFILE=%LOG_DIR%\morning_%DATE%_%TIME%.log

echo ========================================= >> "%LOGFILE%" 2>&1
echo Morning Insight Generation Started >> "%LOGFILE%" 2>&1
echo Mode: %PROMPT_VERSION% (1-Signal Deep Dive) >> "%LOGFILE%" 2>&1
echo Date: %DATE% >> "%LOGFILE%" 2>&1
echo Time: %TIME% >> "%LOGFILE%" 2>&1
echo ========================================= >> "%LOGFILE%" 2>&1

REM 프로젝트 디렉토리로 이동
cd /d "d:\AI 프로젝트\DailyNews"
echo Current directory: %CD% >> "%LOGFILE%" 2>&1

REM 가상환경 활성화
echo Activating virtual environment... >> "%LOGFILE%" 2>&1
call venv\Scripts\activate.bat >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment >> "%LOGFILE%" 2>&1
    exit /b 1
)

REM 파이썬 버전 확인
echo Python version: >> "%LOGFILE%" 2>&1
python --version >> "%LOGFILE%" 2>&1

REM Morning 인사이트 생성 실행
echo. >> "%LOGFILE%" 2>&1
echo ========================================= >> "%LOGFILE%" 2>&1
echo Running Morning Brief (v2-deep, 3 categories)... >> "%LOGFILE%" 2>&1
echo ========================================= >> "%LOGFILE%" 2>&1

python -m antigravity_mcp jobs generate-brief ^
    --window morning ^
    --max-items 10 ^
    --categories Tech,AI_Deep,Economy_KR,Economy_Global >> "%LOGFILE%" 2>&1

set EXITCODE=%errorlevel%

if %EXITCODE% equ 0 (
    echo. >> "%LOGFILE%" 2>&1
    echo [SUCCESS] Morning insights generated successfully >> "%LOGFILE%" 2>&1
    echo ========================================= >> "%LOGFILE%" 2>&1
) else (
    echo. >> "%LOGFILE%" 2>&1
    echo [ERROR] Morning insight generation failed with exit code %EXITCODE% >> "%LOGFILE%" 2>&1
    echo ========================================= >> "%LOGFILE%" 2>&1
)

REM 로그 파일 위치 출력 (콘솔용)
echo Morning insight generation completed.
echo Log file: %LOGFILE%

REM Notion 대시보드 업데이트 (선택 사항)
if %EXITCODE% equ 0 (
    echo. >> "%LOGFILE%" 2>&1
    echo Updating Notion dashboard... >> "%LOGFILE%" 2>&1
    python -m antigravity_mcp ops refresh-dashboard >> "%LOGFILE%" 2>&1

    if errorlevel 1 (
        echo [WARNING] Dashboard update failed but insights were generated >> "%LOGFILE%" 2>&1
    ) else (
        echo [SUCCESS] Dashboard updated >> "%LOGFILE%" 2>&1
    )
)

REM 가상환경 비활성화
deactivate

REM 로그 정리 (30일 이상 된 로그 삭제)
echo. >> "%LOGFILE%" 2>&1
echo Cleaning old logs (older than 30 days)... >> "%LOGFILE%" 2>&1
forfiles /p "%LOG_DIR%" /s /m *.log /d -30 /c "cmd /c del @path" 2>nul

echo. >> "%LOGFILE%" 2>&1
echo Script completed at %DATE% %TIME% >> "%LOGFILE%" 2>&1
echo ========================================= >> "%LOGFILE%" 2>&1

exit /b %EXITCODE%

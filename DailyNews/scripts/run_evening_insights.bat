@echo off
REM =========================================================================
REM DailyNews - Evening Insight Generation (오후 6시 실행)
REM =========================================================================
REM
REM 이 스크립트는 오후 6시에 실행되어 당일 7시 ~ 18시 뉴스를 수집하고
REM 3대 품질 원칙을 충족하는 인사이트를 생성합니다.
REM
REM 작성일: 2026-03-21
REM =========================================================================

setlocal enabledelayedexpansion

REM 로그 디렉토리 생성
set LOG_DIR=d:\AI 프로젝트\DailyNews\logs\insights
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 날짜 및 시간 설정 (로그 파일명용)
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set DATE=%%c-%%a-%%b
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIME=%%a%%b
set LOGFILE=%LOG_DIR%\evening_%DATE%_%TIME%.log

echo ========================================= >> "%LOGFILE%" 2>&1
echo Evening Insight Generation Started >> "%LOGFILE%" 2>&1
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

REM Evening 인사이트 생성 실행
echo. >> "%LOGFILE%" 2>&1
echo ========================================= >> "%LOGFILE%" 2>&1
echo Running Evening Brief Generation... >> "%LOGFILE%" 2>&1
echo ========================================= >> "%LOGFILE%" 2>&1

python -m antigravity_mcp jobs generate-brief ^
    --window evening ^
    --max-items 10 ^
    --categories Tech,Economy_KR,AI_Deep >> "%LOGFILE%" 2>&1

set EXITCODE=%errorlevel%

if %EXITCODE% equ 0 (
    echo. >> "%LOGFILE%" 2>&1
    echo [SUCCESS] Evening insights generated successfully >> "%LOGFILE%" 2>&1
    echo ========================================= >> "%LOGFILE%" 2>&1
) else (
    echo. >> "%LOGFILE%" 2>&1
    echo [ERROR] Evening insight generation failed with exit code %EXITCODE% >> "%LOGFILE%" 2>&1
    echo ========================================= >> "%LOGFILE%" 2>&1
)

REM 로그 파일 위치 출력 (콘솔용)
echo Evening insight generation completed.
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

@echo off
REM =========================================================================
REM DailyNews - Test Insight Generation (테스트 실행용)
REM =========================================================================
REM
REM 이 스크립트는 스케줄링 설정 전에 인사이트 생성을 테스트합니다.
REM
REM 사용법:
REM   test_insight_generation.bat morning     (오전 테스트)
REM   test_insight_generation.bat evening     (오후 테스트)
REM
REM =========================================================================

setlocal enabledelayedexpansion

REM 파라미터 확인
if "%1"=="" (
    echo Usage: test_insight_generation.bat [morning^|evening]
    echo.
    echo Examples:
    echo   test_insight_generation.bat morning
    echo   test_insight_generation.bat evening
    exit /b 1
)

set WINDOW=%1

REM 로그 디렉토리 생성
set LOG_DIR=d:\AI 프로젝트\DailyNews\logs\insights
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 날짜 및 시간 설정
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set DATE=%%c-%%a-%%b
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIME=%%a%%b
set LOGFILE=%LOG_DIR%\test_%WINDOW%_%DATE%_%TIME%.log

echo =========================================
echo DailyNews Insight Generation Test
echo Window: %WINDOW%
echo Date: %DATE%
echo Time: %TIME%
echo =========================================
echo.
echo Log file: %LOGFILE%
echo.

REM 프로젝트 디렉토리로 이동
cd /d "d:\AI 프로젝트\DailyNews"

REM 가상환경 활성화
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

REM 파이썬 버전 확인
echo.
echo Python version:
python --version
echo.

REM 인사이트 생성 실행
echo =========================================
echo Running %WINDOW% Brief Generation...
echo =========================================
echo.

python -m antigravity_mcp jobs generate-brief ^
    --window %WINDOW% ^
    --max-items 5 ^
    --categories Tech 2>&1 | tee "%LOGFILE%"

set EXITCODE=%errorlevel%

echo.
echo =========================================
if %EXITCODE% equ 0 (
    echo [SUCCESS] Test completed successfully
) else (
    echo [ERROR] Test failed with exit code %EXITCODE%
)
echo =========================================
echo.
echo Log saved to: %LOGFILE%
echo.

REM 가상환경 비활성화
deactivate

pause
exit /b %EXITCODE%

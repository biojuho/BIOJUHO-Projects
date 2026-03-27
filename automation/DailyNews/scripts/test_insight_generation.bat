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

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"

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
set NO_PAUSE=%2

REM 로그 디렉토리 생성
set "LOG_DIR=%PROJECT_ROOT%\logs\insights"
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

echo ========================================= > "%LOGFILE%" 2>&1
echo DailyNews Insight Generation Test >> "%LOGFILE%" 2>&1
echo Window: %WINDOW% >> "%LOGFILE%" 2>&1
echo Date: %DATE% >> "%LOGFILE%" 2>&1
echo Time: %TIME% >> "%LOGFILE%" 2>&1
echo ========================================= >> "%LOGFILE%" 2>&1

REM 프로젝트 디렉토리로 이동
cd /d "%PROJECT_ROOT%"

REM 가상환경 활성화
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    echo [ERROR] Failed to activate virtual environment >> "%LOGFILE%" 2>&1
    pause
    exit /b 1
)

set "PYTHONPATH=%PROJECT_ROOT%\src;%PYTHONPATH%"
echo PYTHONPATH: %PYTHONPATH%
echo Current directory: %CD% >> "%LOGFILE%" 2>&1
echo PYTHONPATH: %PYTHONPATH% >> "%LOGFILE%" 2>&1

REM 파이썬 버전 확인
echo.
echo Python version:
python --version
echo.
python --version >> "%LOGFILE%" 2>&1

REM 인사이트 생성 실행
echo =========================================
echo Running %WINDOW% Brief Generation...
echo =========================================
echo.

call "%PROJECT_ROOT%\run_cli.bat" jobs generate-brief ^
    --window %WINDOW% ^
    --max-items 5 ^
    --categories Tech >> "%LOGFILE%" 2>&1

set EXITCODE=%errorlevel%

echo.
echo =========================================
if %EXITCODE% equ 0 (
    echo [SUCCESS] Test completed successfully
    echo [SUCCESS] Test completed successfully >> "%LOGFILE%" 2>&1
) else (
    echo [ERROR] Test failed with exit code %EXITCODE%
    echo [ERROR] Test failed with exit code %EXITCODE% >> "%LOGFILE%" 2>&1
)
echo =========================================
echo.
echo Log saved to: %LOGFILE%
echo.
echo Log saved to: %LOGFILE% >> "%LOGFILE%" 2>&1

REM 가상환경 비활성화
deactivate

if /I "%NO_PAUSE%"=="--no-pause" goto :end
if /I "%DAILYNEWS_NO_PAUSE%"=="1" goto :end

pause
:end
exit /b %EXITCODE%

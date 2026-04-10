@echo off
REM =========================================================================
REM DailyNews - Evening Deep Dive Generation (오후 6시 실행)
REM =========================================================================
REM
REM 딥다이브 뉴스레터 모드: 6개 카테고리 멀티섹션 분석
REM 카테고리: Tech, AI_Deep, Economy_KR, Economy_Global, Crypto, Global_Affairs
REM 수집 범위: 당일 7시 ~ 18시 (11시간)
REM
REM 업데이트: 2026-04-10 (오전=브리핑, 오후=딥다이브 구조 복원)
REM =========================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"

REM 프롬프트 모드 설정 (run_v2_pipeline.py 내부에서 처리)
set PROMPT_VERSION=v2-deep

REM 로그 디렉토리 생성
set "LOG_DIR=%PROJECT_ROOT%\logs\insights"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 날짜 및 시간 설정 (로그 파일명용)
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set DATE=%%c-%%a-%%b
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIME=%%a%%b
set LOGFILE=%LOG_DIR%\evening_%DATE%_%TIME%.log

echo ========================================= >> "%LOGFILE%" 2>&1
echo Evening Insight Generation Started >> "%LOGFILE%" 2>&1
echo Mode: Deep Dive Newsletter (6 categories) >> "%LOGFILE%" 2>&1
echo Date: %DATE% >> "%LOGFILE%" 2>&1
echo Time: %TIME% >> "%LOGFILE%" 2>&1
echo ========================================= >> "%LOGFILE%" 2>&1

REM 프로젝트 디렉토리로 이동
cd /d "%PROJECT_ROOT%"
echo Current directory: %CD% >> "%LOGFILE%" 2>&1

REM 가상환경 활성화
echo Activating virtual environment... >> "%LOGFILE%" 2>&1
call venv\Scripts\activate.bat >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment >> "%LOGFILE%" 2>&1
    exit /b 1
)

set "PYTHONPATH=%PROJECT_ROOT%\src;%PROJECT_ROOT%\..\..\packages;%PYTHONPATH%"
echo PYTHONPATH: %PYTHONPATH% >> "%LOGFILE%" 2>&1

REM 파이썬 버전 확인
echo Python version: >> "%LOGFILE%" 2>&1
python --version >> "%LOGFILE%" 2>&1

REM Evening 인사이트 생성 실행
echo. >> "%LOGFILE%" 2>&1
echo ========================================= >> "%LOGFILE%" 2>&1
echo Running Evening Deep Dive (newsletter format, 6 categories)... >> "%LOGFILE%" 2>&1
echo ========================================= >> "%LOGFILE%" 2>&1

python "%PROJECT_ROOT%\scripts\run_v2_pipeline.py" >> "%LOGFILE%" 2>&1

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
    call "%PROJECT_ROOT%\run_cli.bat" ops refresh-dashboard >> "%LOGFILE%" 2>&1

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

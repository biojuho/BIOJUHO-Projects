@echo off
REM DailyNews Evening Insights Runner (6 PM)
REM Auto-generated for Windows Task Scheduler

setlocal enabledelayedexpansion

REM Navigate to project root
cd /d "d:\AI 프로젝트\DailyNews"

REM Setup logging
set LOG_DIR=d:\AI 프로젝트\DailyNews\logs\insights
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set DATE_STAMP=%date:~0,4%%date:~5,2%%date:~8,2%
set TIME_STAMP=%time:~0,2%%time:~3,2%%time:~6,2%
set TIME_STAMP=%TIME_STAMP: =0%
set LOGFILE=%LOG_DIR%\evening_%DATE_STAMP%_%TIME_STAMP%.log

echo ========================================== >> "%LOGFILE%" 2>&1
echo DailyNews Evening Insights >> "%LOGFILE%" 2>&1
echo Started: %date% %time% >> "%LOGFILE%" 2>&1
echo ========================================== >> "%LOGFILE%" 2>&1

REM Activate virtual environment
call venv\Scripts\activate.bat >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Failed to activate venv >> "%LOGFILE%" 2>&1
    exit /b 1
)

REM Run evening insight generation
echo Running evening window insight generation... >> "%LOGFILE%" 2>&1
python -m antigravity_mcp jobs generate-brief ^
    --window evening ^
    --max-items 10 ^
    --categories Tech,Economy_KR,AI_Deep >> "%LOGFILE%" 2>&1

set EXITCODE=%errorlevel%

if %EXITCODE% equ 0 (
    echo SUCCESS: Evening insights generated >> "%LOGFILE%" 2>&1
) else (
    echo ERROR: Insight generation failed with exit code %EXITCODE% >> "%LOGFILE%" 2>&1
)

echo ========================================== >> "%LOGFILE%" 2>&1
echo Finished: %date% %time% >> "%LOGFILE%" 2>&1
echo ========================================== >> "%LOGFILE%" 2>&1

REM Cleanup old logs (keep last 30 days)
forfiles /p "%LOG_DIR%" /s /m *.log /d -30 /c "cmd /c del @path" 2>nul

exit /b %EXITCODE%

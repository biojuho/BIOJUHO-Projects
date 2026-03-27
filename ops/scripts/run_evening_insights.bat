@echo off
setlocal enabledelayedexpansion

for %%I in ("%~dp0..\..") do set "WORKSPACE_ROOT=%%~fI"
set "PROJECT_ROOT=%WORKSPACE_ROOT%\automation\DailyNews"
set "ACTIVATE_SCRIPT=%WORKSPACE_ROOT%\.venv\Scripts\activate.bat"
if not exist "%ACTIVATE_SCRIPT%" set "ACTIVATE_SCRIPT=%PROJECT_ROOT%\venv\Scripts\activate.bat"

cd /d "%PROJECT_ROOT%" || exit /b 1

set "LOG_DIR=%PROJECT_ROOT%\logs\insights"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set "DATE_STAMP=%date:~0,4%%date:~5,2%%date:~8,2%"
set "TIME_STAMP=%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIME_STAMP=%TIME_STAMP: =0%"
set "LOGFILE=%LOG_DIR%\evening_%DATE_STAMP%_%TIME_STAMP%.log"

echo ========================================== >> "%LOGFILE%" 2>&1
echo DailyNews Evening Insights >> "%LOGFILE%" 2>&1
echo Started: %date% %time% >> "%LOGFILE%" 2>&1
echo ========================================== >> "%LOGFILE%" 2>&1

if not exist "%ACTIVATE_SCRIPT%" (
    echo ERROR: Failed to find a virtual environment. >> "%LOGFILE%" 2>&1
    exit /b 1
)

call "%ACTIVATE_SCRIPT%" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Failed to activate venv >> "%LOGFILE%" 2>&1
    exit /b 1
)

set "PYTHONPATH=%PROJECT_ROOT%\src;%WORKSPACE_ROOT%;%PYTHONPATH%"

echo Running evening window insight generation... >> "%LOGFILE%" 2>&1
python -m antigravity_mcp jobs generate-brief ^
    --window evening ^
    --max-items 10 ^
    --categories Tech Economy_KR AI_Deep >> "%LOGFILE%" 2>&1

set "EXITCODE=%errorlevel%"

if %EXITCODE% equ 0 (
    echo SUCCESS: Evening insights generated >> "%LOGFILE%" 2>&1
) else (
    echo ERROR: Insight generation failed with exit code %EXITCODE% >> "%LOGFILE%" 2>&1
)

echo ========================================== >> "%LOGFILE%" 2>&1
echo Finished: %date% %time% >> "%LOGFILE%" 2>&1
echo ========================================== >> "%LOGFILE%" 2>&1

forfiles /p "%LOG_DIR%" /s /m *.log /d -30 /c "cmd /c del @path" 2>nul

exit /b %EXITCODE%

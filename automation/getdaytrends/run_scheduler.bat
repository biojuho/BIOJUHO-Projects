@echo off
setlocal
chcp 65001 >nul

for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%~dp0..\..") do set "WORKSPACE_ROOT=%%~fI"
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%WORKSPACE_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

cd /d "%PROJECT_ROOT%" || exit /b 1

set "LOCKFILE=%~dp0scheduler.lock"
if exist "%LOCKFILE%" (
    set /p LOCK_PID=<"%LOCKFILE%"
    tasklist /FI "PID eq %LOCK_PID%" 2>nul | find /i "python.exe" >nul
    if %ERRORLEVEL%==0 (
        echo [%date% %time%] Scheduler already running (PID=%LOCK_PID%) >> run_scheduler.log
        exit /b 0
    ) else (
        echo [%date% %time%] Removing stale lock file >> run_scheduler.log
        del "%LOCKFILE%" 2>nul
    )
)

echo [%date% %time%] Starting GetDayTrends scheduler >> run_scheduler.log
start "GetDayTrends Scheduler" /MIN "%PYTHON_EXE%" main.py

timeout /t 2 /nobreak >nul
for /f "tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq GetDayTrends Scheduler" /FO LIST 2^>nul ^| find "PID:"') do (
    echo %%a > "%LOCKFILE%"
    echo [%date% %time%] Scheduler started (PID=%%a) >> run_scheduler.log
)

if not exist "%LOCKFILE%" (
    echo [%date% %time%] WARNING: Failed to capture PID for lock file >> run_scheduler.log
)

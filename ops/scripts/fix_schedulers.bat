@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "CLEANUP_SCRIPT=%SCRIPT_DIR%invoke_cleanup_legacy_scheduled_tasks.ps1"

echo =========================================
echo Scheduler cleanup
echo =========================================
echo This helper launches the cleanup wrapper,
echo elevates if needed, and disables broken legacy tasks
echo and keeps the canonical replacement tasks.
echo.

if not exist "%CLEANUP_SCRIPT%" (
    echo ERROR: Missing cleanup script:
    echo   %CLEANUP_SCRIPT%
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CLEANUP_SCRIPT%"
if errorlevel 1 (
    echo.
    echo Cleanup failed. Run this batch as Administrator.
    exit /b 1
)

echo.
echo Cleanup completed.
exit /b 0

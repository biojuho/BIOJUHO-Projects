@echo off
setlocal

chcp 65001 > nul
set "SCRIPT_DIR=%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run_scheduled_getdaytrends.ps1"
exit /b %ERRORLEVEL%

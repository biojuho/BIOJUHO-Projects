@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
chcp 65001 > nul

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%setup_scheduled_task.ps1"
exit /b %ERRORLEVEL%

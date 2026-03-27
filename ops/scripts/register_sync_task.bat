@echo off
setlocal
chcp 65001 >nul

for %%I in ("%~dp0..\..") do set "WORKSPACE_ROOT=%%~fI"
set "PYTHON_EXE=%WORKSPACE_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set "SYNC_SCRIPT=%WORKSPACE_ROOT%\ops\scripts\sync_gdrive.py"

echo Registering Google Drive sync task...
schtasks /create /tn "AI-Projects-GDrive-Sync" /tr "\"%PYTHON_EXE%\" \"%SYNC_SCRIPT%\"" /sc daily /st 09:00 /f
if %errorlevel% == 0 (
    echo [OK] Task registered: runs daily at 09:00
    schtasks /query /tn "AI-Projects-GDrive-Sync"
) else (
    echo [ERROR] Failed to register task. Try running as Administrator.
)
pause

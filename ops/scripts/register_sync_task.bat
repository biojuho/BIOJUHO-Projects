@echo off
chcp 65001 > nul
echo Registering Google Drive sync task...
schtasks /create /tn "AI-Projects-GDrive-Sync" /tr "\"D:\AI 프로젝트\.venv\Scripts\python.exe\" \"D:\AI 프로젝트\scripts\sync_gdrive.py\"" /sc daily /st 09:00 /f
if %errorlevel% == 0 (
    echo [OK] Task registered: runs daily at 09:00
    schtasks /query /tn "AI-Projects-GDrive-Sync"
) else (
    echo [ERROR] Failed to register task. Try running as Administrator.
)
pause

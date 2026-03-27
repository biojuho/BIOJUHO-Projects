@echo off
setlocal
chcp 65001 >nul

for %%I in ("%~dp0..\..") do set "WORKSPACE_ROOT=%%~fI"

echo ===== Workspace backup =====
echo Current time: %date% %time%

cd /d "%WORKSPACE_ROOT%" || exit /b 1

echo [1/4] Checking git status...
git status

echo [2/4] Staging changes...
git add .

echo [3/4] Creating commit...
for /f "tokens=1-3 delims=/" %%a in ("%date%") do set "today=%%c-%%a-%%b"
git commit -m "Daily backup %today%"

echo [4/4] Pushing to GitHub...
git push origin main

echo ===== Backup complete =====
pause

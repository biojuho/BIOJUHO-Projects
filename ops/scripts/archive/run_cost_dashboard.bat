@echo off
setlocal

for %%I in ("%~dp0..\..") do set "WORKSPACE_ROOT=%%~fI"
cd /d "%WORKSPACE_ROOT%" || exit /b 1

echo [%date% %time%] Starting Cost Dashboard >> "%WORKSPACE_ROOT%\ops\scripts\cost_dashboard.log"
python ops\scripts\cost_dashboard.py >> "%WORKSPACE_ROOT%\ops\scripts\cost_dashboard.log" 2>&1
set "EXITCODE=%errorlevel%"
echo [%date% %time%] Cost Dashboard complete >> "%WORKSPACE_ROOT%\ops\scripts\cost_dashboard.log"
exit /b %EXITCODE%

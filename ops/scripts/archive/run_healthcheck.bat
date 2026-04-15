@echo off
setlocal

for %%I in ("%~dp0..\..") do set "WORKSPACE_ROOT=%%~fI"
cd /d "%WORKSPACE_ROOT%" || exit /b 1

python ops\scripts\healthcheck.py --json-out ops\scripts\health-report.json
if errorlevel 1 exit /b %errorlevel%

python ops\scripts\dora_metrics.py --days 7 --json-out ops\scripts\dora-weekly.json
if errorlevel 1 exit /b %errorlevel%

echo [%date% %time%] Healthcheck complete >> "%WORKSPACE_ROOT%\ops\scripts\healthcheck.log"

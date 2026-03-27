@echo off
setlocal

for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%~dp0..\..") do set "WORKSPACE_ROOT=%%~fI"
set "ACTIVATE_SCRIPT=%PROJECT_ROOT%\venv\Scripts\activate.bat"
if not exist "%ACTIVATE_SCRIPT%" set "ACTIVATE_SCRIPT=%WORKSPACE_ROOT%\.venv\Scripts\activate.bat"

cd /d "%PROJECT_ROOT%" || exit /b 1

if not exist "%ACTIVATE_SCRIPT%" exit /b 1
call "%ACTIVATE_SCRIPT%"
if errorlevel 1 exit /b 1

python scripts\auto_project_log.py
set "EXITCODE=%errorlevel%"
echo [%date% %time%] Daily project log completed >> logs\auto_log.log
exit /b %EXITCODE%

@echo off
setlocal

for %%I in ("%~dp0..\..") do set "WORKSPACE_ROOT=%%~fI"
set "PROJECT_ROOT=%WORKSPACE_ROOT%\automation\DailyNews"
set "ACTIVATE_SCRIPT=%PROJECT_ROOT%\venv\Scripts\activate.bat"
if not exist "%ACTIVATE_SCRIPT%" set "ACTIVATE_SCRIPT=%WORKSPACE_ROOT%\.venv\Scripts\activate.bat"

echo ==========================================
echo DailyNews Insight Generator - Test Mode
echo ==========================================
echo.

cd /d "%PROJECT_ROOT%" || exit /b 1

if not exist "%ACTIVATE_SCRIPT%" (
    echo ERROR: Failed to find a virtual environment.
    pause
    exit /b 1
)

echo Activating virtual environment...
call "%ACTIVATE_SCRIPT%"
if errorlevel 1 (
    echo ERROR: Failed to activate venv
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Testing Morning Window
echo ==========================================
echo.
python -m antigravity_mcp jobs generate-brief --window morning --max-items 10 --categories Tech,Economy_KR,AI_Deep

echo.
echo ==========================================
echo Test Complete
echo ==========================================
echo.
echo Check output at:
echo - %PROJECT_ROOT%\output\
echo - Your Notion dashboard
echo.
pause

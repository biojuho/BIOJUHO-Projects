@echo off
REM DailyNews Insight Generation - Manual Test Script
REM For testing before scheduling

echo ==========================================
echo DailyNews Insight Generator - Test Mode
echo ==========================================
echo.

cd /d "d:\AI 프로젝트\DailyNews"

echo Activating virtual environment...
call venv\Scripts\activate.bat
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
echo - d:\AI 프로젝트\DailyNews\output\
echo - Your Notion dashboard
echo.
pause

@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

:: 설정 환경
set TOPIC="Agentic AI Trends https://www.youtube.com/watch?v=0hW2xO7nO9k"
set OUTDIR="output"
set VENV_DIR=venv

echo [INFO] Starting Content Publisher Pipeline...

:: 1. Deep Research 실행 (Track 1 - Step 1)
echo [PROCESS] Running deep-research module...
call %VENV_DIR%\Scripts\activate
python scripts\new_deep_research.py --topic %TOPIC% --outd %OUTDIR%

:: 2. 리서치 결과를 노션에 게시 (Track 1 - Step 2)
echo [PROCESS] Publishing content to Notion...
set /p LATEST_REPORT=<%OUTDIR%\latest_report.txt
python scripts\content_publisher.py --title %TOPIC% --file "%LATEST_REPORT%"

echo [SUCCESS] Articles successfully published!

endlocal
pause

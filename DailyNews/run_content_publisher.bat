@echo off
setlocal

cd /d "%~dp0"
call venv\Scripts\activate.bat || goto :fail

if not "%~1"=="" (
    set "TOPIC=%~1"
) else (
    for /f "usebackq delims=" %%i in (`python -c "import os; from dotenv import load_dotenv; load_dotenv('.env'); print(os.getenv('DEFAULT_RESEARCH_TOPIC','Agentic AI Trends'))"`) do set "TOPIC=%%i"
)

if "%TOPIC%"=="" goto :fail

python scripts\new_deep_research.py --topic "%TOPIC%" --outd output
if errorlevel 1 goto :fail

if not exist output\latest_report.txt goto :fail
set /p LATEST_REPORT=<output\latest_report.txt
if "%LATEST_REPORT%"=="" goto :fail
if not exist "%LATEST_REPORT%" goto :fail

python scripts\content_publisher.py --title "%TOPIC%" --file "%LATEST_REPORT%"
if errorlevel 1 goto :fail

echo [%date% %time%] Content publisher completed>>logs\scheduler.log
exit /b 0

:fail
echo [%date% %time%] Content publisher failed with errorlevel %errorlevel%>>logs\scheduler.log
exit /b 1

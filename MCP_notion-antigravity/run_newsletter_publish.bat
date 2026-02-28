@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

:: 설정 환경
set VENV_DIR=venv

:: 사용법: run_newsletter_publish.bat <PAGE_ID> <FORMAT>
set PAGE_ID=%1
set FORMAT=%2

if "%PAGE_ID%"=="" (
    echo [ERROR] Please provide a Notion Page ID.
    echo Usage: run_newsletter_publish.bat PAGE_ID [blog^|newsletter^|snippet]
    exit /b 1
)

if "%FORMAT%"=="" (
    set FORMAT=blog
)

echo [INFO] Starting Content Pull & Format Pipeline...
echo [INFO] Target Page ID: %PAGE_ID%
echo [INFO] Target Format: %FORMAT%

call %VENV_DIR%\Scripts\activate
python scripts\content_publisher.py pull --page-id %PAGE_ID% --format %FORMAT%

echo [SUCCESS] Publishing pipeline finished!
endlocal
pause

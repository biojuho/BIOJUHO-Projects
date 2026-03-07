@echo off
setlocal

cd /d "%~dp0"
call venv\Scripts\activate.bat

echo [%DATE% %TIME%] Daily news bot starting... >> logs\scheduler.log

python scripts\news_bot.py
if errorlevel 1 (
    echo [%DATE% %TIME%] Daily news bot FAILED with errorlevel %errorlevel% >> logs\scheduler.log
    exit /b 1
)

echo [%DATE% %TIME%] Daily news bot completed successfully. >> logs\scheduler.log
exit /b 0

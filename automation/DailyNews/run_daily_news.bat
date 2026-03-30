@echo off
setlocal

cd /d "%~dp0"
call venv\Scripts\activate.bat

echo [%DATE% %TIME%] Daily news bot starting... >> logs\scheduler.log

REM --- Pre-run: clean stale locks ---
if exist "data\news_bot.lock" (
    del /f "data\news_bot.lock" 2>nul
    echo [%DATE% %TIME%] Cleaned stale lock file >> logs\scheduler.log
)
python -c "import sqlite3,datetime;c=sqlite3.connect('data/pipeline_state.db');c.execute(\"UPDATE job_runs SET status='failed',finished_at=?,error_text='Auto-cleaned(bat)' WHERE status='running' AND started_at<datetime('now','-30 minutes')\",(datetime.datetime.now(datetime.timezone.utc).isoformat(),));c.commit();print(f'Cleaned {c.total_changes} stale lock(s)');c.close()" 2>> logs\scheduler.log

python scripts\news_bot.py
if errorlevel 1 (
    echo [%DATE% %TIME%] Daily news bot FAILED with errorlevel %errorlevel% >> logs\scheduler.log
    exit /b 1
)

echo [%DATE% %TIME%] Daily news bot completed successfully. >> logs\scheduler.log
exit /b 0

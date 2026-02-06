@echo off
REM Antigravity Daily News Runner
REM 매일 오전 7시 Windows Task Scheduler로 실행

cd /d "D:\AI 프로젝트\MCP_notion-antigravity"
call venv\Scripts\activate.bat
python scripts\run_daily_news.py

REM 로그 저장
echo [%date% %time%] Daily news completed >> logs\scheduler.log

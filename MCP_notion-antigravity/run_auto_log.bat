@echo off
REM Antigravity Daily Project Log Runner
REM 매일 오후 10시 Windows Task Scheduler로 실행

cd /d "D:\AI 프로젝트\MCP_notion-antigravity"
call venv\Scripts\activate.bat
python scripts\auto_project_log.py

REM 로그 저장
echo [%date% %time%] Daily project log completed >> logs\auto_log.log

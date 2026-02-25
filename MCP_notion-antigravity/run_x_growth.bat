@echo off
REM X Growth Engine v2.0 Daily Trigger Script
REM 윈도우 작업 스케줄러(Windows Task Scheduler)에 등록하여 사용하세요.

echo ============================================
echo   X Growth Engine v2.0 - Daily Pipeline
echo ============================================

cd /d "D:\AI 프로젝트\MCP_notion-antigravity"

REM 가상환경이 있다면 여기서 활성화
REM call venv\Scripts\activate.bat

REM 1. RLHF Engagement Tracker (Check yesterday's hooks)
echo [RLHF] Tracking Engagement...
python .agent\skills\rlhf_tracker\engagement_tracker.py

REM 2. Full pipeline (기본)
echo [Pipeline] Starting Daily Generation...
python .agent\utils\daily_pipeline.py

REM 다른 모드 사용 예시:
REM python .agent\engine\pipeline.py --mode quick --topic "AI Agent"
REM python .agent\engine\pipeline.py --mode stats
REM python .agent\engine\pipeline.py --mode calendar

echo.
echo Pipeline Execution Finished.
pause

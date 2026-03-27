@echo off
REM ========================================================
REM FinOps Cost Dashboard 스케줄러 실행 스크립트
REM 매일 자정에 AI 비용 리포트 생성 및 스레스홀드 체크
REM ========================================================

cd /d "D:\AI 프로젝트"

echo [%date% %time%] Starting Cost Dashboard >> scripts\cost_dashboard.log
python scripts\cost_dashboard.py >> scripts\cost_dashboard.log 2>&1
echo [%date% %time%] Cost Dashboard complete >> scripts\cost_dashboard.log

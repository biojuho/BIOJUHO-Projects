@echo off
REM ========================================================
REM 프로젝트 헬스체크 스케줄러 등록 스크립트
REM 매일 09:00에 헬스체크 실행 (Windows Task Scheduler)
REM 사용법: run_healthcheck.bat 또는 Task Scheduler에 등록
REM ========================================================

cd /d "D:\AI 프로젝트"

REM 파이썬 헬스체크 실행
python scripts\healthcheck.py --json-out scripts\health-report.json

REM Webhook 알림을 사용하려면 아래 주석 해제 + URL 설정
REM python scripts\healthcheck.py --webhook YOUR_DISCORD_WEBHOOK_URL

REM DORA 메트릭도 함께 측정
python scripts\dora_metrics.py --days 7 --json-out scripts\dora-weekly.json

echo [%date% %time%] Healthcheck complete >> scripts\healthcheck.log

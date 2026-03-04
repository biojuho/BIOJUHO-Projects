@echo off
chcp 65001 > nul
cd /d "d:\AI 프로젝트\getdaytrends"
echo [%date% %time%] GetDayTrends 실행 시작 >> run_scheduled.log
"d:\AI 프로젝트\.venv\Scripts\python.exe" main.py --one-shot 2>&1 >> run_scheduled.log
echo [%date% %time%] GetDayTrends 실행 완료 >> run_scheduled.log

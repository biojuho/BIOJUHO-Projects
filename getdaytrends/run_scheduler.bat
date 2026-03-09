@echo off
chcp 65001 > nul
cd /d "d:\AI 프로젝트\getdaytrends"

REM 이미 실행 중인 프로세스가 있으면 스킵
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq GetDayTrends*" 2>nul | find /i "python.exe" >nul
if %ERRORLEVEL%==0 (
    echo [%date% %time%] GetDayTrends 이미 실행 중 - 스킵 >> run_scheduler.log
    exit /b 0
)

echo [%date% %time%] GetDayTrends 스케줄러 시작 >> run_scheduler.log
start "GetDayTrends Scheduler" /MIN "d:\AI 프로젝트\.venv\Scripts\python.exe" main.py 2>&1 >> run_scheduler.log
echo [%date% %time%] GetDayTrends 프로세스 시작됨 >> run_scheduler.log

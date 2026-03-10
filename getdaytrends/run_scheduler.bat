@echo off
chcp 65001 > nul
cd /d "d:\AI 프로젝트\getdaytrends"

REM Lock 파일로 중복 실행 방지 (WINDOWTITLE 기반보다 안정적)
set "LOCKFILE=%~dp0scheduler.lock"
if exist "%LOCKFILE%" (
    REM Lock 파일이 있으면 프로세스가 아직 살아있는지 확인
    set /p LOCK_PID=<"%LOCKFILE%"
    tasklist /FI "PID eq %LOCK_PID%" 2>nul | find /i "python.exe" >nul
    if %ERRORLEVEL%==0 (
        echo [%date% %time%] GetDayTrends 이미 실행 중 (PID=%LOCK_PID%) - 스킵 >> run_scheduler.log
        exit /b 0
    ) else (
        echo [%date% %time%] 이전 Lock 파일 제거 (프로세스 종료됨) >> run_scheduler.log
        del "%LOCKFILE%" 2>nul
    )
)

echo [%date% %time%] GetDayTrends 스케줄러 시작 >> run_scheduler.log
start "GetDayTrends Scheduler" /MIN "d:\AI 프로젝트\.venv\Scripts\python.exe" main.py

REM 시작된 프로세스의 PID를 Lock 파일에 기록
timeout /t 2 /nobreak > nul
for /f "tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq GetDayTrends Scheduler" /FO LIST 2^>nul ^| find "PID:"') do (
    echo %%a > "%LOCKFILE%"
    echo [%date% %time%] GetDayTrends 프로세스 시작됨 (PID=%%a) >> run_scheduler.log
)

if not exist "%LOCKFILE%" (
    echo [%date% %time%] WARNING: PID 캡처 실패, Lock 파일 미생성 >> run_scheduler.log
)

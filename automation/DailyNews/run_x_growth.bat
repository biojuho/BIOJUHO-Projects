@echo off
setlocal

cd /d "%~dp0"
call venv\Scripts\activate.bat || goto :fail

python .agent\skills\rlhf_tracker\engagement_tracker.py
if errorlevel 1 goto :rlhf_fail

python .agent\utils\daily_pipeline.py
if errorlevel 1 goto :pipeline_fail

echo [%date% %time%] X growth pipeline completed>>logs\scheduler.log
exit /b 0

:rlhf_fail
echo [%date% %time%] X growth RLHF step failed with errorlevel %errorlevel%>>logs\scheduler.log
exit /b 1

:pipeline_fail
echo [%date% %time%] X growth pipeline step failed with errorlevel %errorlevel%>>logs\scheduler.log
exit /b 1

:fail
echo [%date% %time%] X growth bootstrap failed with errorlevel %errorlevel%>>logs\scheduler.log
exit /b 1

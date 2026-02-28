@echo off
setlocal

cd /d "%~dp0"
call venv\Scripts\activate.bat || goto :fail

python scripts\collect_news.py --max-items 10
if errorlevel 1 goto :fail

python scripts\visualization.py
if errorlevel 1 goto :fail

python scripts\news_bot.py --max-items 5
if errorlevel 1 goto :fail

python scripts\export_to_notebooklm.py
if errorlevel 1 goto :fail

python scripts\update_dashboard.py
if errorlevel 1 goto :fail

python -c "import os,sys; from dotenv import load_dotenv; load_dotenv('.env'); sys.exit(0 if os.getenv('AUTO_PUSH_ENABLED','0').strip().lower() in ('1','true','yes','on') else 1)"
if errorlevel 1 goto :skip_push

git add output\*.png
git commit -m "Auto-update visualization charts [%date% %time%]"
if errorlevel 1 goto :fail
git push origin main
if errorlevel 1 goto :fail

:skip_push
echo [%date% %time%] Daily news completed>>logs\scheduler.log
exit /b 0

:fail
echo [%date% %time%] Daily news failed with errorlevel %errorlevel%>>logs\scheduler.log
exit /b 1

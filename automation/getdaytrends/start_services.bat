@echo off
setlocal
chcp 65001 >nul

for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%~dp0..\..") do set "WORKSPACE_ROOT=%%~fI"
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%WORKSPACE_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo ========================================
echo   NotebookLM + n8n startup
echo ========================================
echo.

set "PYTHONIOENCODING=utf-8"

echo [1/2] Starting NotebookLM API on port 8788...
start "NotebookLM-API" /B cmd /c "cd /d ""%PROJECT_ROOT%"" && ""%PYTHON_EXE%"" -m uvicorn notebooklm_api:app --host 0.0.0.0 --port 8788 > notebooklm_api.log 2>&1"
timeout /t 5 /nobreak >nul

curl -s http://127.0.0.1:8788/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK] API server is reachable.
) else (
    echo   [!!] API server failed to start. Check notebooklm_api.log.
)

echo [2/2] Starting n8n on port 5678...
start "n8n" /B cmd /c "n8n start > n8n.log 2>&1"
timeout /t 5 /nobreak >nul

curl -s http://127.0.0.1:5678 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK] n8n is reachable.
) else (
    echo   [!!] n8n failed to start. Check n8n.log.
)

echo.
echo ========================================
echo   Startup complete
echo   - API: http://127.0.0.1:8788
echo   - n8n: http://localhost:5678
echo ========================================
echo.
echo Close this window to stop both processes.
pause >nul
taskkill /FI "WINDOWTITLE eq NotebookLM-API" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq n8n" /F >nul 2>&1

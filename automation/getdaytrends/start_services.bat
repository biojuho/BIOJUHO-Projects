@echo off
chcp 65001 >nul
echo ========================================
echo   NotebookLM + n8n 자동 시작
echo ========================================
echo.

:: 환경 설정
set PYTHONIOENCODING=utf-8

:: 1. NotebookLM API 서버 시작 (백그라운드)
echo [1/2] NotebookLM API 서버 시작 (포트 8788)...
start /B "NotebookLM-API" cmd /c "cd /d \"D:\AI 프로젝트\getdaytrends\" && python -m uvicorn notebooklm_api:app --host 0.0.0.0 --port 8788 > notebooklm_api.log 2>&1"
timeout /t 5 /nobreak >nul

:: API 서버 헬스 체크
curl -s http://127.0.0.1:8788/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK] API 서버 정상 가동
) else (
    echo   [!!] API 서버 시작 실패 - notebooklm_api.log 확인
)

:: 2. n8n 시작 (백그라운드)
echo [2/2] n8n 시작 (포트 5678)...
start /B "n8n" cmd /c "n8n start > n8n.log 2>&1"
timeout /t 5 /nobreak >nul

curl -s http://127.0.0.1:5678 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK] n8n 정상 가동
) else (
    echo   [!!] n8n 시작 실패 - n8n.log 확인
)

echo.
echo ========================================
echo   모든 서비스 시작 완료!
echo   - API: http://127.0.0.1:8788
echo   - n8n: http://localhost:5678
echo ========================================
echo.
echo 이 창을 닫으면 서비스가 종료됩니다.
echo 종료하려면 아무 키나 누르세요...
pause >nul
taskkill /FI "WINDOWTITLE eq NotebookLM-API" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq n8n" /F >nul 2>&1

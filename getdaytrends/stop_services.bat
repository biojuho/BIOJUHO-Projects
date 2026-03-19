@echo off
chcp 65001 >nul
echo 서비스 종료 중...

:: NotebookLM API 서버 종료
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8788.*LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    echo [OK] API 서버 종료 (PID: %%a)
)

:: n8n 종료
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5678.*LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    echo [OK] n8n 종료 (PID: %%a)
)

echo 모든 서비스가 종료되었습니다.
timeout /t 3 /nobreak >nul

@echo off
setlocal

cd /d "%~dp0"

:: 가상환경 디렉토리 이름
set VENV_DIR=venv

:: 가상환경이 없으면 생성
if not exist %VENV_DIR% (
    echo [INFO] Creating virtual environment...
    python -m venv %VENV_DIR%
)

:: 가상환경 활성화
call %VENV_DIR%\Scripts\activate

:: 의존성 설치 확인 (간단히 requirements.txt 존재 여부만 체크하여 설치 시도)
if exist requirements.txt (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt > nul 2>&1
)

:: 서버 실행
echo [INFO] Starting Notion MCP Server...
python server.py

endlocal

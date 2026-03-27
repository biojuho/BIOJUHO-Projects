@echo off
cd /d "%~dp0"
set GOOGLE_APPLICATION_CREDENTIALS=%~dp0credentials.json
echo [INFO] NotebookLM 인증을 시작합니다. 브라우저가 열리면 로그인해주세요.
venv\Scripts\python -m notebooklm_mcp.auth_cli
pause

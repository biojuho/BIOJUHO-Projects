@echo off
cd /d "%~dp0"
set GOOGLE_APPLICATION_CREDENTIALS=%~dp0credentials.json
venv\Scripts\notebooklm-mcp.exe
pause

@echo off
cd /d "%~dp0"
set GOOGLE_APPLICATION_CREDENTIALS=%~dp0credentials.json
venv\Scripts\python -m notebooklm_mcp.server
pause

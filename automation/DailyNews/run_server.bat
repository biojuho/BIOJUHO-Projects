@echo off
setlocal

cd /d "%~dp0"

echo [INFO] Starting Antigravity Content Engine MCP server...
call "%CD%\run_cli.bat" serve

endlocal

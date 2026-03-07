@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_BIN=%PYTHON_BIN%"
if "%PYTHON_BIN%"=="" set "PYTHON_BIN=python"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo [INFO] Starting Antigravity Content Engine MCP server...
%PYTHON_BIN% -m antigravity_mcp serve

endlocal

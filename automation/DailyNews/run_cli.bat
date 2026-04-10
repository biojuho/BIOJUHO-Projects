@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_BIN=%PYTHON_BIN%"
if "%PYTHON_BIN%"=="" (
    if exist "%CD%\venv\Scripts\python.exe" (
        set "PYTHON_BIN=%CD%\venv\Scripts\python.exe"
    ) else (
        set "PYTHON_BIN=python"
    )
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%CD%\src;%CD%\..\..\packages;%PYTHONPATH%"

"%PYTHON_BIN%" -m antigravity_mcp %*
set "EXITCODE=%ERRORLEVEL%"

endlocal & exit /b %EXITCODE%

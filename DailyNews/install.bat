@echo off
setlocal

cd /d "%~dp0"

echo [INFO] Preparing Antigravity Content Engine environment...

if not exist venv (
    echo [STEP 1] Creating virtual environment...
    python -m venv venv
) else (
    echo [STEP 1] Reusing existing virtual environment...
)

call venv\Scripts\activate

if exist requirements-dev.txt (
    echo [STEP 2] Installing project and development dependencies...
    pip install -r requirements-dev.txt
) else (
    echo [STEP 2] Installing runtime dependencies...
    pip install -r requirements.txt
)

echo [SUCCESS] Environment is ready.
echo Use "run_server.bat" to start the MCP server.

endlocal

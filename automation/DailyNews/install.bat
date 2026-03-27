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

if exist pyproject.toml (
    echo [STEP 2] Installing project in editable mode...
    pip install -e .[dev]
    if errorlevel 1 (
        echo [WARN] Editable install failed, falling back to requirements files...
        if exist requirements-dev.txt (
            pip install -r requirements-dev.txt
        ) else (
            pip install -r requirements.txt
        )
    )
) else (
    echo [STEP 2] Installing runtime dependencies...
    if exist requirements-dev.txt (
        pip install -r requirements-dev.txt
    ) else (
        pip install -r requirements.txt
    )
)

echo [SUCCESS] Environment is ready.
echo Use "run_cli.bat" or "run_server.bat" to start the CLI/server.

endlocal

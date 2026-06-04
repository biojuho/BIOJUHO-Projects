from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEALTHCHECK_PATH = PROJECT_ROOT / "ops" / "scripts" / "healthcheck.py"


def load_healthcheck_module():
    spec = importlib.util.spec_from_file_location("healthcheck_under_test", HEALTHCHECK_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_npm_build_failure_reports_command_not_found(monkeypatch, tmp_path: Path) -> None:
    healthcheck = load_healthcheck_module()
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    monkeypatch.setattr(healthcheck, "WORKSPACE", tmp_path)

    class Proc:
        returncode = 127
        stdout = "> frontend@0.0.0 build:dry\n> vite build --emptyOutDir=false\n"
        stderr = "sh: vite: command not found\n"

    monkeypatch.setattr(healthcheck.subprocess, "run", lambda *args, **kwargs: Proc())

    result = healthcheck.check_npm_build("frontend")

    assert result == {"ok": False, "message": "FAILED build dry-run: sh: vite: command not found"}

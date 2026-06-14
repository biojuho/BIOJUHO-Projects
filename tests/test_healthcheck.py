from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEALTHCHECK_PATH = PROJECT_ROOT / "ops" / "scripts" / "healthcheck.py"


def load_healthcheck_module():
    spec = importlib.util.spec_from_file_location("healthcheck_under_test", HEALTHCHECK_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("healthcheck module spec could not be loaded")
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
        stdout = "> frontend@0.0.0 build:dry
> vite build --emptyOutDir=false
"
        stderr = "sh: vite: command not found
"

    monkeypatch.setattr(healthcheck.subprocess, "run", lambda *args, **kwargs: Proc())

    result = healthcheck.check_npm_build("frontend")

    expected = {"ok": False, "message": "FAILED build dry-run: sh: vite: command not found"}
    if result != expected:
        raise AssertionError(result)


def test_npm_build_skips_when_node_modules_absent(monkeypatch, tmp_path: Path) -> None:
    """node_modules 없는 환경(Python-only CI)에서는 ok=True로 조기 반환."""
    healthcheck = load_healthcheck_module()
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    # node_modules 디렉터리 없음 — npm install 미완료 상태 시뮬레이션
    monkeypatch.setattr(healthcheck, "WORKSPACE", tmp_path)

    result = healthcheck.check_npm_build("frontend")

    assert result["ok"] is True
    assert "SKIP" in result["message"]
    assert "node_modules" in result["message"]


def test_npm_build_missing_package_dir(monkeypatch, tmp_path: Path) -> None:
    """package 디렉터리 자체가 없으면 ok=False로 반환."""
    healthcheck = load_healthcheck_module()
    monkeypatch.setattr(healthcheck, "WORKSPACE", tmp_path)

    result = healthcheck.check_npm_build("nonexistent-app")

    assert result["ok"] is False
    assert "MISSING" in result["message"]

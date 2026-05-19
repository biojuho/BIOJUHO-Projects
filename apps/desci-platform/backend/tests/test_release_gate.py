from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import release_gate  # noqa: E402


def _args(**overrides):
    defaults = {
        "profile": "local",
        "env_file": [],
        "ignore_process_env": False,
        "python_command": sys.executable,
        "backend_tests": list(release_gate.DEFAULT_BACKEND_TESTS),
        "skip_env": False,
        "skip_compose": False,
        "skip_backend": False,
        "skip_frontend": False,
        "skip_contracts": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_release_gate_builds_expected_default_steps() -> None:
    steps = release_gate.build_steps(_args())

    assert [step.name for step in steps] == [
        "env-doctor",
        "compose-config",
        "backend-tests",
        "frontend-lint",
        "frontend-typecheck",
        "frontend-tests",
        "frontend-build",
        "frontend-bundle",
        "contracts-build",
        "contracts-tests",
        "contracts-deploy-core",
        "contracts-deploy-nft",
    ]


def test_release_gate_can_skip_frontend_and_compose() -> None:
    steps = release_gate.build_steps(_args(skip_frontend=True, skip_compose=True))

    assert [step.name for step in steps] == [
        "env-doctor",
        "backend-tests",
        "contracts-build",
        "contracts-tests",
        "contracts-deploy-core",
        "contracts-deploy-nft",
    ]


def test_release_gate_can_skip_contracts() -> None:
    steps = release_gate.build_steps(_args(skip_contracts=True, skip_compose=True))

    assert [step.name for step in steps] == [
        "env-doctor",
        "backend-tests",
        "frontend-lint",
        "frontend-typecheck",
        "frontend-tests",
        "frontend-build",
        "frontend-bundle",
    ]


def test_release_gate_preserves_uv_python_runner() -> None:
    steps = release_gate.build_steps(_args(python_command="uv run python", skip_frontend=True, skip_compose=True))

    backend = next(step for step in steps if step.name == "backend-tests")
    assert backend.command[:3] == ("uv", "run", "python")
    assert "tests" in backend.command


def test_release_gate_json_report_contains_operator_summary(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate.json"
    results = [
        release_gate.GateResult(
            name="env-doctor",
            command="python scripts/env_doctor.py",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=12.5,
        ),
        release_gate.GateResult(
            name="backend-tests",
            command="python -m pytest tests -q",
            cwd=str(release_gate.BACKEND_DIR),
            returncode=1,
            elapsed_ms=30.0,
        ),
    ]

    release_gate.write_json_report(report_path, results)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["passed"] == 1
    assert payload["summary"]["failed"] == 1
    assert payload["summary"]["failed_step"] == "backend-tests"
    assert payload["duration_ms"] == 42.5

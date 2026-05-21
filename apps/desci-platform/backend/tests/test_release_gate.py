from __future__ import annotations

import argparse
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
    ]


def test_release_gate_can_skip_frontend_and_compose() -> None:
    steps = release_gate.build_steps(_args(skip_frontend=True, skip_compose=True))

    assert [step.name for step in steps] == ["env-doctor", "backend-tests"]


def test_release_gate_preserves_uv_python_runner() -> None:
    steps = release_gate.build_steps(_args(python_command="uv run python", skip_frontend=True, skip_compose=True))

    backend = next(step for step in steps if step.name == "backend-tests")
    assert backend.command[:3] == ("uv", "run", "python")
    assert "tests" in backend.command

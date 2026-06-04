from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATH = PROJECT_ROOT / "apps" / "AgriGuard" / "frontend" / "bootstrap_legacy_paths.py"


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_agriguard_frontend_bootstrap_delegates_to_workspace_root() -> None:
    source = WRAPPER_PATH.read_text(encoding="utf-8")

    _expect("parents[3]" in source, "wrapper should resolve the repository root from the frontend directory")
    _expect("bootstrap_legacy_paths.py" in source, "wrapper should delegate to the root bootstrap script")
    _expect("runpy.run_path" in source, "wrapper should execute the root bootstrap script")

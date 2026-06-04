from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = PROJECT_ROOT / "ops" / "hooks" / "pre-push"


def test_pre_push_hook_runs_completion_and_mcp_smokes() -> None:
    hook = HOOK_PATH.read_text(encoding="utf-8")

    assert "tests/test_workspace_smoke.py" in hook
    assert "tests/test_autoresearch_completion_audit.py" in hook
    assert "tests/test_dev_server_browser_smoke.py" in hook
    assert "tests/test_dev_server_mcp_contract.py" in hook
    assert "tests/test_dev_server_mcp_runtime.py" in hook
    assert "tests/test_dev_server_mcp_runtime_smoke.py" in hook
    assert "python ops/scripts/dev_server_mcp_runtime_smoke.py" in hook
    assert "python ops/scripts/autoresearch_completion_audit.py" in hook

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


def test_hook_installer_normalizes_shell_hook_line_endings(tmp_path: Path) -> None:
    import importlib.util

    installer_path = PROJECT_ROOT / "ops" / "hooks" / "install_hooks.py"
    spec = importlib.util.spec_from_file_location("install_hooks", installer_path)
    installer = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(installer)

    source = tmp_path / "pre-push"
    destination = tmp_path / "installed-pre-push"
    source.write_text("#!/bin/sh\r\necho ok\r\n", encoding="utf-8", newline="")

    installer._install_hook_file(source, destination)

    assert destination.read_bytes() == b"#!/bin/sh\necho ok\n"

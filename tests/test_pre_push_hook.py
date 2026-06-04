from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = PROJECT_ROOT / "ops" / "hooks" / "pre-push"
INSTALLER_PATH = PROJECT_ROOT / "ops" / "hooks" / "install_hooks.py"


def test_pre_push_hook_runs_completion_and_mcp_smokes() -> None:
    hook = HOOK_PATH.read_text(encoding="utf-8")

    assert "tests/test_workspace_smoke.py" in hook
    assert "tests/test_pre_push_hook.py" in hook
    assert "tests/test_autoresearch_completion_audit.py" in hook
    assert "tests/test_dashboard_api.py" in hook
    assert "tests/test_telegram_notification_live_verify.py" in hook
    assert "tests/test_canva_widget_click_smoke.py" in hook
    assert "tests/test_dev_server_browser_smoke.py" in hook
    assert "tests/test_dev_server_mcp_contract.py" in hook
    assert "tests/test_dev_server_mcp_runtime.py" in hook
    assert "tests/test_dev_server_mcp_runtime_smoke.py" in hook
    assert "python ops/hooks/install_hooks.py --check" in hook
    assert "npm.cmd --prefix apps/dashboard test -- --run" in hook
    assert "python ops/scripts/dev_server_mcp_runtime_smoke.py" in hook
    assert "python ops/scripts/autoresearch_completion_audit.py" in hook
    assert "python ops/scripts/telegram_notification_live_verify.py" in hook
    assert "--check-operator-checklist-json" in hook
    assert "--check-operator-checklist-markdown" in hook
    assert "EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.json" in hook
    assert "EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.md" in hook


def test_pre_push_hook_uses_read_only_installer_check() -> None:
    hook_lines = HOOK_PATH.read_text(encoding="utf-8").splitlines()
    executable_lines = [line.strip() for line in hook_lines if line.strip() and not line.lstrip().startswith("#")]
    installer_lines = [line for line in executable_lines if "install_hooks.py" in line and not line.startswith("echo ")]

    assert installer_lines
    assert all("--check" in line for line in installer_lines)


def test_hook_installer_normalizes_shell_hook_line_endings(tmp_path: Path) -> None:
    installer = load_installer()

    source = tmp_path / "pre-push"
    destination = tmp_path / "installed-pre-push"
    source.write_text("#!/bin/sh\r\necho ok\r\n", encoding="utf-8", newline="")

    installer._install_hook_file(source, destination)

    assert destination.read_bytes() == b"#!/bin/sh\necho ok\n"


def test_hook_installer_check_detects_stale_shell_hook(tmp_path: Path) -> None:
    installer = load_installer()

    source = tmp_path / "pre-push"
    destination = tmp_path / "installed-pre-push"
    source.write_text("#!/bin/sh\r\necho ok\r\n", encoding="utf-8", newline="")
    destination.write_text("#!/bin/sh\necho stale\n", encoding="utf-8", newline="\n")

    assert installer._installed_hook_matches(source, destination) is False

    installer._install_hook_file(source, destination)

    assert installer._installed_hook_matches(source, destination) is True


def test_hook_installer_check_normalizes_destination_line_endings(tmp_path: Path) -> None:
    installer = load_installer()

    source = tmp_path / "pre-push"
    destination = tmp_path / "installed-pre-push"
    source.write_text("#!/bin/sh\r\necho ok\r\n", encoding="utf-8", newline="")
    destination.write_text("#!/bin/sh\r\necho ok\r\n", encoding="utf-8", newline="")

    assert installer._installed_hook_matches(source, destination) is True


def test_hook_installer_check_mode_does_not_overwrite_stale_hook(tmp_path: Path) -> None:
    installer = load_installer()

    source_dir = tmp_path / "source"
    hooks_dir = tmp_path / "hooks"
    source_dir.mkdir()
    hooks_dir.mkdir()
    source = source_dir / "pre-push"
    destination = hooks_dir / "pre-push"
    source.write_text("#!/bin/sh\necho current\n", encoding="utf-8")
    destination.write_text("#!/bin/sh\necho stale\n", encoding="utf-8")

    original_source_dir = installer.HOOKS_SRC
    installer.HOOKS_SRC = source_dir
    try:
        assert installer.check_hooks(hooks_dir) is False
    finally:
        installer.HOOKS_SRC = original_source_dir

    assert destination.read_text(encoding="utf-8") == "#!/bin/sh\necho stale\n"


def load_installer():
    import importlib.util

    spec = importlib.util.spec_from_file_location("install_hooks", INSTALLER_PATH)
    installer = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(installer)
    return installer

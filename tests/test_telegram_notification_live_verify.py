from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "telegram_notification_live_verify.py"
DRY_RUN_JSON_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "TELEGRAM_NOTIFICATION_LIVE_VERIFY_DRY_RUN_2026-06-05.json"
DRY_RUN_MARKDOWN_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "TELEGRAM_NOTIFICATION_LIVE_VERIFY_DRY_RUN_2026-06-05.md"


def load_module():
    spec = importlib.util.spec_from_file_location("telegram_notification_live_verify", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dry_run_reports_missing_env_without_secret_values() -> None:
    verifier = load_module()

    report = verifier.run(env={})

    assert report["status"] == "pass"
    assert report["mode"] == "dry_run"
    assert report["live_status"] == "blocked_missing_required_env"
    assert report["missing_required_env"] == ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    assert "Secret values: not emitted" in verifier.render_markdown(report)


def test_execute_requires_telegram_env() -> None:
    verifier = load_module()

    report = verifier.run(execute=True, env={})

    assert report["status"] == "fail"
    assert report["summary"]["message_attempted"] is False
    assert "missing required env" in report["errors"][0]


def test_execute_sends_message_with_injected_sender_and_redacts_secret() -> None:
    verifier = load_module()

    def fake_sender(token: str, chat_id: str, message: str, timeout_seconds: float) -> dict:
        return {
            "ok": True,
            "message_id": 123,
            "error": f"sent {token} to {chat_id}: {message}",
        }

    report = verifier.run(
        execute=True,
        env={
            "TELEGRAM_BOT_TOKEN": "telegram-secret-token",
            "TELEGRAM_CHAT_ID": "telegram-secret-chat",
        },
        sender=fake_sender,
    )
    serialized = json.dumps(report)

    assert report["status"] == "pass"
    assert report["summary"]["message_attempted"] is True
    assert report["summary"]["message_sent"] is True
    assert report["delivery"]["message_id"] == 123
    assert "telegram-secret-token" not in serialized
    assert "telegram-secret-chat" not in serialized
    assert "<redacted:TELEGRAM_BOT_TOKEN>" in serialized
    assert "<redacted:TELEGRAM_CHAT_ID>" in serialized


def test_cli_writes_dry_run_outputs(tmp_path: Path) -> None:
    verifier = load_module()
    json_out = tmp_path / "telegram-live.json"
    markdown_out = tmp_path / "telegram-live.md"

    exit_code = verifier.main(
        [
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["mode"] == "dry_run"
    assert "Telegram Notification Live Verify" in markdown
    assert "Secret values: not emitted" in markdown


def test_checked_in_dry_run_artifacts_match_current_plan() -> None:
    verifier = load_module()

    expected = verifier.run(env={})
    checked_json = json.loads(DRY_RUN_JSON_PATH.read_text(encoding="utf-8"))
    checked_markdown = DRY_RUN_MARKDOWN_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert _stable_report(checked_json) == _stable_report(expected)
    assert checked_markdown == verifier.render_markdown(expected)


def _stable_report(report: dict) -> dict:
    stable = dict(report)
    stable["generated_at"] = "<ignored>"
    stable["summary"] = dict(report["summary"])
    stable["summary"]["elapsed_seconds"] = 0.0
    return stable

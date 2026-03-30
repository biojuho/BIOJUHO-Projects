from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("notebooklm_automation", reason="notebooklm_automation package unavailable")

from notebooklm_automation import health as nlm_health
from notebooklm_automation.config import reset_config


@pytest.fixture
def notebooklm_home(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTEBOOKLM_HOME", str(tmp_path))
    reset_config()
    yield tmp_path
    reset_config()


def _write_storage(home_dir, cookies, age_hours: float | None = None):
    storage_file = home_dir / "storage_state.json"
    storage_file.write_text(json.dumps({"cookies": cookies}), encoding="utf-8")
    if age_hours is not None:
        old_time = (datetime.now() - timedelta(hours=age_hours)).timestamp()
        os.utime(storage_file, (old_time, old_time))
    return storage_file


class TestCheckAuthStatus:
    def test_no_storage_file(self, notebooklm_home):
        result = nlm_health.check_auth_status()

        assert result["authenticated"] is False
        assert result["storage_file_exists"] is False
        assert result["needs_refresh"] is True

    def test_fresh_session(self, notebooklm_home):
        _write_storage(notebooklm_home, [{"name": "c1"}, {"name": "c2"}])

        with patch(
            "notebooklm_automation.health.subprocess.run",
            return_value=MagicMock(returncode=0),
        ):
            result = nlm_health.check_auth_status()

        assert result["storage_file_exists"] is True
        assert result["authenticated"] is True
        assert result["age_hours"] is not None
        assert result["age_hours"] < 1
        assert result["needs_refresh"] is False

    def test_expired_session(self, notebooklm_home):
        _write_storage(notebooklm_home, [], age_hours=22)

        with patch(
            "notebooklm_automation.health.subprocess.run",
            return_value=MagicMock(returncode=0),
        ):
            result = nlm_health.check_auth_status()

        assert result["authenticated"] is True
        assert result["needs_refresh"] is True
        assert result["age_hours"] >= 20

    def test_cli_not_found(self, notebooklm_home):
        _write_storage(notebooklm_home, [])

        with patch(
            "notebooklm_automation.health.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = nlm_health.check_auth_status()

        assert result["authenticated"] is False


class TestGetSessionCookiesCount:
    def test_no_file(self, notebooklm_home):
        assert nlm_health.get_session_cookies_count() == 0

    def test_with_cookies(self, notebooklm_home):
        _write_storage(notebooklm_home, [{"name": "a"}, {"name": "b"}, {"name": "c"}])

        assert nlm_health.get_session_cookies_count() == 3


class TestRefreshAuth:
    def test_reuse_session_success(self, notebooklm_home):
        with patch(
            "notebooklm_automation.health.subprocess.run",
            return_value=MagicMock(returncode=0, stderr=""),
        ):
            result = nlm_health.refresh_auth()

        assert result["success"] is True
        assert result["method"] == "reuse_session"

    def test_fallback_to_new_session(self, notebooklm_home):
        with patch(
            "notebooklm_automation.health.subprocess.run",
            side_effect=[
                MagicMock(returncode=1, stderr="reuse failed"),
                MagicMock(returncode=0, stderr=""),
            ],
        ) as mock_run:
            result = nlm_health.refresh_auth()

        assert result["success"] is True
        assert result["method"] == "new_session"
        assert mock_run.call_count == 2

    def test_both_fail(self, notebooklm_home):
        with patch(
            "notebooklm_automation.health.subprocess.run",
            return_value=MagicMock(returncode=1, stderr="auth failed"),
        ):
            result = nlm_health.refresh_auth()

        assert result["success"] is False
        assert result["method"] == "none"

    def test_cli_not_installed(self, notebooklm_home):
        with patch(
            "notebooklm_automation.health.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = nlm_health.refresh_auth()

        assert result["success"] is False
        assert "not installed" in result["message"]

    def test_records_history(self, notebooklm_home):
        with patch(
            "notebooklm_automation.health.subprocess.run",
            return_value=MagicMock(returncode=0, stderr=""),
        ):
            nlm_health.refresh_auth()

        history_file = notebooklm_home / "refresh_history.json"
        history = json.loads(history_file.read_text(encoding="utf-8"))

        assert history_file.exists()
        assert len(history) == 1
        assert history[0]["success"] is True


class TestProactiveRefresh:
    def test_skip_when_healthy(self):
        auth_status = {
            "authenticated": True,
            "needs_refresh": False,
            "age_hours": 5.0,
            "storage_file_exists": True,
            "last_modified": datetime.now().isoformat(),
        }

        with (
            patch("notebooklm_automation.health.check_auth_status", return_value=auth_status),
            patch("notebooklm_automation.health.refresh_auth") as mock_refresh,
        ):
            result = nlm_health.proactive_refresh()

        assert result["action"] == "skipped"
        assert result["refresh_result"] is None
        mock_refresh.assert_not_called()

    def test_refresh_when_needed(self):
        auth_status = {
            "authenticated": True,
            "needs_refresh": True,
            "age_hours": 21.0,
            "storage_file_exists": True,
            "last_modified": (datetime.now() - timedelta(hours=21)).isoformat(),
        }
        refresh_result = {
            "success": True,
            "method": "reuse_session",
            "message": "ok",
            "timestamp": datetime.now().isoformat(),
        }

        with (
            patch("notebooklm_automation.health.check_auth_status", return_value=auth_status),
            patch("notebooklm_automation.health.refresh_auth", return_value=refresh_result),
        ):
            result = nlm_health.proactive_refresh()

        assert result["action"] == "refreshed"

    def test_alert_on_failure(self):
        auth_status = {
            "authenticated": False,
            "needs_refresh": True,
            "age_hours": 25.0,
            "storage_file_exists": True,
            "last_modified": (datetime.now() - timedelta(hours=25)).isoformat(),
        }
        refresh_result = {
            "success": False,
            "method": "none",
            "message": "timeout",
            "timestamp": datetime.now().isoformat(),
        }

        with (
            patch("notebooklm_automation.health.check_auth_status", return_value=auth_status),
            patch("notebooklm_automation.health.refresh_auth", return_value=refresh_result),
            patch("notebooklm_automation.health.send_auth_alert", return_value=True) as mock_alert,
        ):
            result = nlm_health.proactive_refresh()

        assert result["action"] == "failed"
        assert result["alert_sent"] is True
        mock_alert.assert_called_once_with("timeout")


class TestSendAuthAlert:
    def test_sends_telegram_alert(self, notebooklm_home, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        reset_config()

        with (
            patch(
                "notebooklm_automation.health.check_auth_status",
                return_value={"age_hours": 22.0},
            ),
            patch("httpx.post", return_value=MagicMock(status_code=200)) as mock_post,
        ):
            result = nlm_health.send_auth_alert("test error")

        assert result is True
        mock_post.assert_called_once()

    def test_returns_false_without_configured_channels(self, notebooklm_home, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        reset_config()
        assert nlm_health.send_auth_alert("test error") is False


class TestRefreshHistory:
    def test_empty_when_no_file(self, notebooklm_home):
        assert nlm_health.get_refresh_history() == []

    def test_returns_recent(self, notebooklm_home):
        history_file = notebooklm_home / "refresh_history.json"
        records = [{"success": True, "timestamp": f"2026-03-{day:02d}T00:00:00"} for day in range(1, 21)]
        history_file.write_text(json.dumps(records), encoding="utf-8")

        recent = nlm_health.get_refresh_history(limit=5)

        assert len(recent) == 5
        assert recent[-1]["timestamp"] == "2026-03-20T00:00:00"


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_down_when_not_authenticated(self, notebooklm_home):
        auth_status = {
            "authenticated": False,
            "needs_refresh": True,
            "age_hours": None,
            "storage_file_exists": False,
            "last_modified": None,
        }

        with patch("notebooklm_automation.health.check_auth_status", return_value=auth_status):
            result = await nlm_health.health_check()

        assert result["status"] == "down"
        assert result["api_reachable"] is False

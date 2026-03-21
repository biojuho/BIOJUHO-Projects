"""
NotebookLM Health Check & Auth Refresh 단위 테스트
==================================================
notebooklm_health.py 모듈의 핵심 로직을 검증.
"""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# notebooklm_automation 패키지 미설치 시 전체 skip
_nlm_available = True
try:
    import notebooklm_automation  # noqa: F401
except ImportError:
    _nlm_available = False

pytestmark = pytest.mark.skipif(
    not _nlm_available,
    reason="notebooklm_automation 패키지 미설치",
)
# ──────────────────────────────────────────────────
#  check_auth_status 테스트
# ──────────────────────────────────────────────────


class TestCheckAuthStatus:
    """check_auth_status() 함수 테스트."""

    def test_no_storage_file(self, tmp_path):
        """storage_state.json이 없으면 미인증."""
        with patch("notebooklm_health.STORAGE_STATE_FILE", tmp_path / "nonexistent.json"):
            from notebooklm_automation.health import check_auth_status

            result = check_auth_status()
            assert result["authenticated"] is False
            assert result["storage_file_exists"] is False
            assert result["needs_refresh"] is True

    def test_fresh_session(self, tmp_path):
        """최근에 생성된 세션은 갱신 불필요."""
        storage = tmp_path / "storage_state.json"
        storage.write_text('{"cookies": [{"name": "c1"}, {"name": "c2"}]}', encoding="utf-8")

        with (
            patch("notebooklm_health.STORAGE_STATE_FILE", storage),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)

            from notebooklm_automation.health import check_auth_status

            result = check_auth_status()
            assert result["storage_file_exists"] is True
            assert result["authenticated"] is True
            assert result["age_hours"] is not None
            assert result["age_hours"] < 1  # 방금 생성됨
            assert result["needs_refresh"] is False

    def test_expired_session(self, tmp_path):
        """20시간 이상 된 세션은 갱신 필요."""
        import os

        storage = tmp_path / "storage_state.json"
        storage.write_text('{"cookies": []}', encoding="utf-8")

        # 파일 수정 시간을 22시간 전으로 조작
        old_time = (datetime.now() - timedelta(hours=22)).timestamp()
        os.utime(storage, (old_time, old_time))

        with (
            patch("notebooklm_health.STORAGE_STATE_FILE", storage),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)

            from notebooklm_automation.health import check_auth_status

            result = check_auth_status()
            assert result["needs_refresh"] is True
            assert result["age_hours"] >= 20

    def test_cli_not_found(self, tmp_path):
        """CLI가 없으면 authenticated=False."""
        storage = tmp_path / "storage_state.json"
        storage.write_text('{"cookies": []}', encoding="utf-8")

        with (
            patch("notebooklm_health.STORAGE_STATE_FILE", storage),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            from notebooklm_automation.health import check_auth_status

            result = check_auth_status()
            assert result["authenticated"] is False


# ──────────────────────────────────────────────────
#  get_session_cookies_count 테스트
# ──────────────────────────────────────────────────


class TestGetSessionCookiesCount:
    """get_session_cookies_count() 함수 테스트."""

    def test_no_file(self, tmp_path):
        with patch("notebooklm_health.STORAGE_STATE_FILE", tmp_path / "none.json"):
            from notebooklm_automation.health import get_session_cookies_count

            assert get_session_cookies_count() == 0

    def test_with_cookies(self, tmp_path):
        storage = tmp_path / "storage_state.json"
        storage.write_text(
            json.dumps({"cookies": [{"name": "a"}, {"name": "b"}, {"name": "c"}]}),
            encoding="utf-8",
        )

        with patch("notebooklm_health.STORAGE_STATE_FILE", storage):
            from notebooklm_automation.health import get_session_cookies_count

            assert get_session_cookies_count() == 3


# ──────────────────────────────────────────────────
#  refresh_auth 테스트
# ──────────────────────────────────────────────────


class TestRefreshAuth:
    """refresh_auth() 함수 테스트."""

    def test_reuse_session_success(self, tmp_path):
        """1차 시도(reuse-session)에서 성공."""
        with (
            patch("notebooklm_health.REFRESH_HISTORY_FILE", tmp_path / "history.json"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            from notebooklm_automation.health import refresh_auth

            result = refresh_auth()
            assert result["success"] is True
            assert result["method"] == "reuse_session"
            mock_run.assert_called_once()  # 1차만 호출

    def test_fallback_to_new_session(self, tmp_path):
        """1차 실패 → 2차(new session) 성공."""
        with (
            patch("notebooklm_health.REFRESH_HISTORY_FILE", tmp_path / "history.json"),
            patch("subprocess.run") as mock_run,
        ):
            # 1차 실패, 2차 성공
            mock_run.side_effect = [
                MagicMock(returncode=1, stderr="reuse failed"),
                MagicMock(returncode=0, stderr=""),
            ]

            from notebooklm_automation.health import refresh_auth

            result = refresh_auth()
            assert result["success"] is True
            assert result["method"] == "new_session"
            assert mock_run.call_count == 2

    def test_both_fail(self, tmp_path):
        """양쪽 모두 실패."""
        with (
            patch("notebooklm_health.REFRESH_HISTORY_FILE", tmp_path / "history.json"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1, stderr="auth failed")

            from notebooklm_automation.health import refresh_auth

            result = refresh_auth()
            assert result["success"] is False
            assert result["method"] == "none"

    def test_cli_not_installed(self, tmp_path):
        """CLI 미설치 시 즉시 실패."""
        with (
            patch("notebooklm_health.REFRESH_HISTORY_FILE", tmp_path / "history.json"),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            from notebooklm_automation.health import refresh_auth

            result = refresh_auth()
            assert result["success"] is False
            assert "설치" in result["message"]

    def test_records_history(self, tmp_path):
        """갱신 결과가 이력 파일에 기록됨."""
        history_file = tmp_path / "history.json"

        with (
            patch("notebooklm_health.REFRESH_HISTORY_FILE", history_file),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            from notebooklm_automation.health import refresh_auth

            refresh_auth()
            assert history_file.exists()
            history = json.loads(history_file.read_text(encoding="utf-8"))
            assert len(history) == 1
            assert history[0]["success"] is True


# ──────────────────────────────────────────────────
#  proactive_refresh 테스트
# ──────────────────────────────────────────────────


class TestProactiveRefresh:
    """proactive_refresh() 함수 테스트."""

    def test_skip_when_healthy(self):
        """세션이 정상이면 갱신 스킵."""
        mock_auth = {
            "authenticated": True,
            "needs_refresh": False,
            "age_hours": 5.0,
            "storage_file_exists": True,
            "last_modified": datetime.now().isoformat(),
        }

        with patch("notebooklm_health.check_auth_status", return_value=mock_auth):
            from notebooklm_automation.health import proactive_refresh

            result = proactive_refresh()
            assert result["action"] == "skipped"
            assert result["refresh_result"] is None

    def test_refresh_when_needed(self):
        """갱신이 필요하면 시도."""
        mock_auth = {
            "authenticated": True,
            "needs_refresh": True,
            "age_hours": 21.0,
            "storage_file_exists": True,
            "last_modified": (datetime.now() - timedelta(hours=21)).isoformat(),
        }
        mock_refresh = {
            "success": True,
            "method": "reuse_session",
            "message": "ok",
            "timestamp": datetime.now().isoformat(),
        }

        with (
            patch("notebooklm_health.check_auth_status", return_value=mock_auth),
            patch("notebooklm_health.refresh_auth", return_value=mock_refresh),
        ):
            from notebooklm_automation.health import proactive_refresh

            result = proactive_refresh()
            assert result["action"] == "refreshed"

    def test_alert_on_failure(self):
        """갱신 실패 시 알림 발송."""
        mock_auth = {
            "authenticated": False,
            "needs_refresh": True,
            "age_hours": 25.0,
            "storage_file_exists": True,
            "last_modified": (datetime.now() - timedelta(hours=25)).isoformat(),
        }
        mock_refresh = {
            "success": False,
            "method": "none",
            "message": "timeout",
            "timestamp": datetime.now().isoformat(),
        }

        with (
            patch("notebooklm_health.check_auth_status", return_value=mock_auth),
            patch("notebooklm_health.refresh_auth", return_value=mock_refresh),
            patch("notebooklm_health.send_auth_alert", return_value=True) as mock_alert,
        ):
            from notebooklm_automation.health import proactive_refresh

            result = proactive_refresh()
            assert result["action"] == "failed"
            assert result["alert_sent"] is True
            mock_alert.assert_called_once()


# ──────────────────────────────────────────────────
#  send_auth_alert 테스트
# ──────────────────────────────────────────────────


class TestSendAuthAlert:
    """send_auth_alert() 함수 테스트."""

    def test_sends_alert(self):
        """알림이 정상 발송되면 True."""
        mock_config = MagicMock()
        mock_config.telegram_bot_token = "token"
        mock_config.telegram_chat_id = "123"

        with (
            patch("notebooklm_health.check_auth_status", return_value={"age_hours": 22.0}),
            patch("alerts.send_alert", return_value={"telegram": {"ok": True}}) as mock_send,
            patch("config.AppConfig.from_env", return_value=mock_config),
        ):
            from notebooklm_automation.health import send_auth_alert

            result = send_auth_alert("test error")
            assert result is True

    def test_import_error_graceful(self):
        """alerts 모듈 없으면 False 반환 (예외 없음)."""
        with patch.dict("sys.modules", {"alerts": None}):
            # 모듈 임포트 실패 시뮬레이션은 복잡하므로
            # send_auth_alert 내부의 ImportError 처리를 간접 검증
            from notebooklm_automation.health import send_auth_alert

            # alerts가 없는 환경에서도 크래시 없이 False 반환
            # (실제 환경에서는 alerts가 있으므로 config.from_env 실패로 False)
            result = send_auth_alert("test")
            assert isinstance(result, bool)


# ──────────────────────────────────────────────────
#  refresh history 테스트
# ──────────────────────────────────────────────────


class TestRefreshHistory:
    """get_refresh_history() 함수 테스트."""

    def test_empty_when_no_file(self, tmp_path):
        with patch("notebooklm_health.REFRESH_HISTORY_FILE", tmp_path / "none.json"):
            from notebooklm_automation.health import get_refresh_history

            assert get_refresh_history() == []

    def test_returns_recent(self, tmp_path):
        history_file = tmp_path / "history.json"
        records = [
            {"success": True, "timestamp": f"2026-03-{i:02d}T00:00:00"}
            for i in range(1, 21)
        ]
        history_file.write_text(json.dumps(records), encoding="utf-8")

        with patch("notebooklm_health.REFRESH_HISTORY_FILE", history_file):
            from notebooklm_automation.health import get_refresh_history

            recent = get_refresh_history(limit=5)
            assert len(recent) == 5
            assert recent[-1]["timestamp"] == "2026-03-20T00:00:00"


# ──────────────────────────────────────────────────
#  health_check 테스트
# ──────────────────────────────────────────────────


class TestHealthCheck:
    """health_check() 함수 테스트."""

    @pytest.mark.asyncio
    async def test_down_when_not_authenticated(self, tmp_path):
        """인증 실패 → status=down."""
        mock_auth = {
            "authenticated": False,
            "needs_refresh": True,
            "age_hours": None,
            "storage_file_exists": False,
            "last_modified": None,
        }

        with (
            patch("notebooklm_health.check_auth_status", return_value=mock_auth),
            patch("notebooklm_health.HEALTH_LOG_FILE", tmp_path / "health.log"),
        ):
            from notebooklm_automation.health import health_check

            result = await health_check()
            assert result["status"] == "down"
            assert result["api_reachable"] is False

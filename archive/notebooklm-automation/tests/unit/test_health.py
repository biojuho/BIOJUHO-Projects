"""Unit tests for health module."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from notebooklm_automation.config import NotebookLMConfig, reset_config
from notebooklm_automation.health import (
    _record_refresh_history,
    check_auth_status,
    get_refresh_history,
    get_session_cookies_count,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_config()
    yield
    reset_config()


class TestCheckAuthStatus:
    def test_no_storage_file(self, tmp_path):
        cfg = NotebookLMConfig(home_dir=tmp_path)
        with patch("notebooklm_automation.health.get_config", return_value=cfg):
            result = check_auth_status()
            assert result["authenticated"] is False
            assert result["storage_file_exists"] is False

    def test_storage_exists_fresh(self, tmp_path):
        state_file = tmp_path / "storage_state.json"
        state_file.write_text('{"cookies": [1,2,3]}')
        cfg = NotebookLMConfig(home_dir=tmp_path)
        with patch("notebooklm_automation.health.get_config", return_value=cfg), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = check_auth_status()
            assert result["storage_file_exists"] is True
            assert result["age_hours"] is not None
            assert result["authenticated"] is True


class TestSessionCookies:
    def test_no_file(self, tmp_path):
        cfg = NotebookLMConfig(home_dir=tmp_path)
        with patch("notebooklm_automation.health.get_config", return_value=cfg):
            assert get_session_cookies_count() == 0

    def test_with_cookies(self, tmp_path):
        state_file = tmp_path / "storage_state.json"
        state_file.write_text('{"cookies": [1,2,3,4,5]}')
        cfg = NotebookLMConfig(home_dir=tmp_path)
        with patch("notebooklm_automation.health.get_config", return_value=cfg):
            assert get_session_cookies_count() == 5


class TestRefreshHistory:
    def test_record_and_retrieve(self, tmp_path):
        cfg = NotebookLMConfig(home_dir=tmp_path)
        with patch("notebooklm_automation.health.get_config", return_value=cfg):
            _record_refresh_history({"success": True, "method": "test", "timestamp": "now"})
            history = get_refresh_history(limit=5)
            assert len(history) == 1
            assert history[0]["success"] is True

    def test_history_limit(self, tmp_path):
        cfg = NotebookLMConfig(home_dir=tmp_path)
        with patch("notebooklm_automation.health.get_config", return_value=cfg):
            for i in range(5):
                _record_refresh_history({"index": i})
            history = get_refresh_history(limit=3)
            assert len(history) == 3
            assert history[0]["index"] == 2

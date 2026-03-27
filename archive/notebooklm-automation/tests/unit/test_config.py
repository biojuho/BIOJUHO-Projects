"""Unit tests for config module."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from notebooklm_automation.config import NotebookLMConfig, get_config, reset_config


class TestConfig:
    def setup_method(self):
        reset_config()

    def test_defaults(self):
        cfg = NotebookLMConfig()
        assert cfg.api_port == 8788
        assert cfg.api_host == "0.0.0.0"
        assert cfg.session_refresh_threshold_hours == 20.0
        assert cfg.min_viral_score == 75

    def test_env_override(self):
        with patch.dict(os.environ, {"NOTEBOOKLM_API_PORT": "9999", "NOTEBOOKLM_MIN_VIRAL": "50"}):
            cfg = NotebookLMConfig()
            assert cfg.api_port == 9999
            assert cfg.min_viral_score == 50

    def test_storage_state_path(self):
        cfg = NotebookLMConfig()
        assert cfg.storage_state_file.name == "storage_state.json"
        assert cfg.health_log_file.name == "health_check.log"

    def test_singleton(self):
        reset_config()
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_reset(self):
        c1 = get_config()
        reset_config()
        c2 = get_config()
        assert c1 is not c2

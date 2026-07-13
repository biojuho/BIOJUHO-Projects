from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import notebooklm_health
import pytest


@pytest.mark.asyncio
async def test_health_check_healthy_when_authenticated_and_cli_reachable(tmp_path, monkeypatch):
    auth_status = {
        "authenticated": True,
        "needs_refresh": False,
        "age_hours": 1.0,
        "storage_file_exists": True,
        "last_modified": datetime.now().isoformat(),
    }
    monkeypatch.setattr(notebooklm_health, "HEALTH_LOG_FILE", tmp_path / "health.log")

    with (
        patch("notebooklm_health.check_auth_status", return_value=auth_status),
        patch("notebooklm_health._probe_notebooklm_cli", return_value=(True, 2)),
    ):
        result = await notebooklm_health.health_check()

    assert result["status"] == "healthy"
    assert result["api_reachable"] is True
    assert result["notebook_count"] == 2


@pytest.mark.asyncio
async def test_health_check_degraded_when_session_needs_refresh(tmp_path, monkeypatch):
    auth_status = {
        "authenticated": True,
        "needs_refresh": True,
        "age_hours": 22.0,
        "storage_file_exists": True,
        "last_modified": datetime.now().isoformat(),
    }
    monkeypatch.setattr(notebooklm_health, "HEALTH_LOG_FILE", tmp_path / "health.log")

    with (
        patch("notebooklm_health.check_auth_status", return_value=auth_status),
        patch("notebooklm_health._probe_notebooklm_cli", return_value=(True, 1)),
    ):
        result = await notebooklm_health.health_check()

    assert result["status"] == "degraded"
    assert result["api_reachable"] is True


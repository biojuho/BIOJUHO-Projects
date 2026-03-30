"""Unit tests for notebooklm_automation.alerts, execution_log, and templates."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

# ──────────────────────────────────────────────────
#  Alert System
# ──────────────────────────────────────────────────


class TestAlerts:
    """Tests for the alert system."""

    @pytest.mark.asyncio
    async def test_send_slack_alert(self):
        """Slack alert sends correctly with webhook URL."""
        from notebooklm_automation.alerts import AlertLevel, send_alert

        with (
            patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}),
            patch("notebooklm_automation.alerts._send_slack", new_callable=AsyncMock, return_value=True),
        ):
            result = await send_alert(
                AlertLevel.ERROR,
                "Test Error",
                details={"key": "value"},
                channels=["slack"],
            )
            assert result.get("slack") is True

    @pytest.mark.asyncio
    async def test_send_alert_no_channels(self):
        """Alert with no configured channels returns empty results."""
        from notebooklm_automation.alerts import AlertLevel, send_alert

        with patch.dict(os.environ, {}, clear=False):
            result = await send_alert(
                AlertLevel.INFO,
                "Test Info",
                channels=["slack"],
            )
            # No SLACK_WEBHOOK_URL set, so slack should fail
            assert isinstance(result, dict)

    def test_alert_level_enum(self):
        """AlertLevel enum has expected values."""
        from notebooklm_automation.alerts import AlertLevel

        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.ERROR.value == "error"
        assert AlertLevel.CRITICAL.value == "critical"


# ──────────────────────────────────────────────────
#  Execution Logger
# ──────────────────────────────────────────────────


class TestExecutionLogger:
    """Tests for the SQLite execution logger."""

    def test_start_and_complete_run(self, tmp_path):
        """Start and complete a run, then retrieve it."""
        from notebooklm_automation.execution_log import ExecutionLogger

        logger = ExecutionLogger(db_path=tmp_path / "test.db")

        run_id = logger.start_run("test-pipeline", {"file_name": "test.pdf"})
        assert isinstance(run_id, str)
        assert len(run_id) == 8

        logger.complete_run(run_id, success=True, result={"article_title": "Test"})

        runs = logger.get_recent_runs(limit=5)
        assert len(runs) == 1
        assert runs[0]["status"] == "success"
        assert runs[0]["pipeline_name"] == "test-pipeline"

    def test_failed_run_records_error(self, tmp_path):
        """Failed run correctly records the error."""
        from notebooklm_automation.execution_log import ExecutionLogger

        logger = ExecutionLogger(db_path=tmp_path / "test2.db")

        run_id = logger.start_run("test-pipeline", {})
        logger.complete_run(run_id, success=False, error="Connection timeout")

        runs = logger.get_recent_runs()
        assert runs[0]["status"] == "failed"
        assert "timeout" in runs[0]["error"]

    def test_daily_stats(self, tmp_path):
        """Daily stats aggregation returns proper structure."""
        from notebooklm_automation.execution_log import ExecutionLogger

        logger = ExecutionLogger(db_path=tmp_path / "test3.db")

        # Create a few runs
        for i in range(3):
            run_id = logger.start_run("stats-test", {"file_name": f"file{i}.pdf"})
            logger.complete_run(run_id, success=(i != 1), result={"article_chars": 1000})

        stats = logger.get_daily_stats(days=1)
        assert isinstance(stats, list)
        if stats:
            assert stats[0]["total_runs"] == 3
            assert stats[0]["success_count"] == 2
            assert stats[0]["fail_count"] == 1


# ──────────────────────────────────────────────────
#  Prompt Template Manager
# ──────────────────────────────────────────────────


class TestPromptTemplateManager:
    """Tests for the YAML prompt template system."""

    def test_default_template_loads(self):
        """Default template loads successfully."""
        from notebooklm_automation.templates import PromptTemplateManager

        mgr = PromptTemplateManager()
        prompt = mgr.build_article_prompt("", "Test content here")

        assert "Test content" in prompt
        assert "JSON" in prompt
        assert "한국어" in prompt or "블로그" in prompt

    def test_project_override(self, tmp_path):
        """Project-specific template overrides default."""
        # Create a custom template
        tmpl = tmp_path / "_default.yaml"
        tmpl.write_text("tone: 기본톤\nstyle: 기본스타일\nlanguage: 한국어\n", encoding="utf-8")

        project_tmpl = tmp_path / "MyProject.yaml"
        project_tmpl.write_text("tone: 프로젝트톤\nstyle: 프로젝트스타일\n", encoding="utf-8")

        from notebooklm_automation.templates import PromptTemplateManager

        mgr = PromptTemplateManager(templates_dir=tmp_path)
        prompt = mgr.build_article_prompt("MyProject", "Some content")

        assert "프로젝트톤" in prompt
        assert "프로젝트스타일" in prompt

    def test_fallback_to_default(self, tmp_path):
        """Unknown project falls back to default template."""
        tmpl = tmp_path / "_default.yaml"
        tmpl.write_text("tone: 기본톤\nlanguage: 한국어\n", encoding="utf-8")

        from notebooklm_automation.templates import PromptTemplateManager

        mgr = PromptTemplateManager(templates_dir=tmp_path)
        prompt = mgr.build_article_prompt("UnknownProject", "Content")

        assert "기본톤" in prompt

    def test_list_templates(self):
        """List available templates."""
        from notebooklm_automation.templates import PromptTemplateManager

        mgr = PromptTemplateManager()
        templates = mgr.list_templates()
        assert any("default" in t for t in templates)

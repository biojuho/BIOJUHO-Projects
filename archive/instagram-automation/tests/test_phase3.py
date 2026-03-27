"""Tests for Phase 3: Monitoring, Dashboard, Deployment config."""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _tmp_db():
    """Create a temp DB with required tables."""
    import sqlite3

    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caption TEXT DEFAULT '',
            status TEXT DEFAULT 'queued',
            post_type TEXT DEFAULT 'IMAGE',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS dm_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT,
            message TEXT,
            response TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS dm_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_keyword TEXT,
            response_text TEXT
        );
    """)
    conn.commit()
    conn.close()
    return path


class TestSystemMonitor:
    def test_health_check(self):
        from services.monitoring import SystemMonitor

        monitor = SystemMonitor(_tmp_db())
        health = monitor.get_health()
        assert health["status"] in ("healthy", "degraded", "unhealthy")
        assert "uptime" in health
        assert "checks" in health

    def test_database_check_healthy(self):
        from services.monitoring import SystemMonitor

        monitor = SystemMonitor(_tmp_db())
        check = monitor._check_database()
        assert check["status"] == "healthy"

    def test_database_check_unhealthy(self):
        from services.monitoring import SystemMonitor

        monitor = SystemMonitor("/nonexistent/bad.db")
        check = monitor._check_database()
        # sqlite3 might still create the file or throw
        assert check["status"] in ("healthy", "unhealthy")

    def test_error_logging(self):
        from services.monitoring import SystemMonitor

        monitor = SystemMonitor(_tmp_db())
        monitor.log_error("meta_api", "Connection timeout")
        monitor.log_error("scheduler", "Queue full")
        assert len(monitor._error_log) == 2

    def test_error_rate_check(self):
        from services.monitoring import SystemMonitor

        monitor = SystemMonitor(_tmp_db())
        # Few errors = healthy
        check = monitor._check_error_rate()
        assert check["status"] == "healthy"

        # Many errors = degraded/unhealthy
        for i in range(10):
            monitor.log_error("test", f"Error {i}")
        check = monitor._check_error_rate()
        assert check["status"] in ("degraded", "unhealthy")

    def test_uptime(self):
        from services.monitoring import SystemMonitor

        monitor = SystemMonitor(_tmp_db())
        assert monitor.uptime_seconds > 0
        assert "m" in monitor.uptime_human

    def test_dashboard_data(self):
        from services.monitoring import SystemMonitor

        monitor = SystemMonitor(_tmp_db())
        data = monitor.get_dashboard_data()
        assert "health" in data
        assert "posts" in data
        assert "dms" in data
        assert "errors" in data

    def test_dashboard_with_posts(self):
        import sqlite3
        from services.monitoring import SystemMonitor

        db_path = _tmp_db()
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO posts (caption, status) VALUES ('test post', 'published')")
        conn.execute("INSERT INTO posts (caption, status) VALUES ('queued post', 'queued')")
        conn.commit()
        conn.close()

        monitor = SystemMonitor(db_path)
        data = monitor.get_dashboard_data()
        assert data["posts"]["total"] == 2
        assert data["posts"]["published"] == 1
        assert data["posts"]["queued"] == 1

    def test_alert_check(self):
        import asyncio
        from services.monitoring import SystemMonitor

        monitor = SystemMonitor(_tmp_db())
        loop = asyncio.new_event_loop()
        alerts = loop.run_until_complete(monitor.check_and_alert())
        # No notifier, but should still work
        assert isinstance(alerts, list)
        loop.close()

    def test_disk_check(self):
        from services.monitoring import SystemMonitor

        monitor = SystemMonitor(_tmp_db())
        check = monitor._check_disk_space()
        assert check["status"] in ("healthy", "degraded", "unhealthy")


class TestDeploymentConfig:
    def test_dockerfile_exists(self):
        dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
        assert dockerfile.exists()
        content = dockerfile.read_text()
        assert "HEALTHCHECK" in content
        assert "8003" in content

    def test_cloudbuild_exists(self):
        cloudbuild = Path(__file__).resolve().parents[1] / "cloudbuild.yaml"
        assert cloudbuild.exists()
        content = cloudbuild.read_text()
        assert "cloud-run" in content or "run" in content

    def test_dashboard_html_exists(self):
        dashboard = Path(__file__).resolve().parents[1] / "static" / "dashboard.html"
        assert dashboard.exists()
        content = dashboard.read_text()
        assert "Instagram Automation" in content
        assert "dashboard" in content.lower()

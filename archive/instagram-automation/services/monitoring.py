"""Monitoring and health check system.

Tracks system health, API usage, content pipeline status,
and sends alerts via Telegram when thresholds are breached.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class HealthStatus:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class SystemMonitor:
    """Monitor system health, detect issues, and send alerts."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._start_time = time.monotonic()
        self._error_log: list[dict] = []
        self._alert_cooldown: dict[str, float] = {}
        self._alert_cooldown_seconds = 3600  # 1 hour between same alerts

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def uptime_human(self) -> str:
        s = int(self.uptime_seconds)
        days, s = divmod(s, 86400)
        hours, s = divmod(s, 3600)
        mins, s = divmod(s, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        parts.append(f"{mins}m")
        return " ".join(parts)

    def log_error(self, component: str, error: str) -> None:
        """Log an error for monitoring."""
        self._error_log.append({
            "component": component,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep last 100 errors
        if len(self._error_log) > 100:
            self._error_log = self._error_log[-100:]

    def get_health(self) -> dict:
        """Comprehensive health check."""
        from services.rate_limiter import MetaRateLimiter

        checks = {
            "database": self._check_database(),
            "meta_api": self._check_meta_api_health(),
            "disk_space": self._check_disk_space(),
            "recent_errors": self._check_error_rate(),
        }

        statuses = [c["status"] for c in checks.values()]
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall = HealthStatus.UNHEALTHY
        else:
            overall = HealthStatus.DEGRADED

        return {
            "status": overall,
            "uptime": self.uptime_human,
            "uptime_seconds": round(self.uptime_seconds),
            "timestamp": datetime.now().isoformat(),
            "checks": checks,
        }

    def _check_database(self) -> dict:
        """Check if database is accessible."""
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path, timeout=3)
            conn.execute("SELECT 1")
            conn.close()
            return {"status": HealthStatus.HEALTHY, "detail": "OK"}
        except Exception as e:
            return {"status": HealthStatus.UNHEALTHY, "detail": str(e)}

    def _check_meta_api_health(self) -> dict:
        """Check rate limiter status as proxy for API health."""
        try:
            from services.rate_limiter import MetaRateLimiter
            limiter = MetaRateLimiter()
            stats = limiter.get_stats()
            if stats["usage_pct"] > 90:
                return {
                    "status": HealthStatus.DEGRADED,
                    "detail": f"Rate limit at {stats['usage_pct']:.0f}%",
                }
            return {"status": HealthStatus.HEALTHY, "detail": f"Usage: {stats['usage_pct']:.0f}%"}
        except Exception as e:
            return {"status": HealthStatus.HEALTHY, "detail": "Rate limiter not initialized (OK at startup)"}

    def _check_disk_space(self) -> dict:
        """Check available disk space for image storage."""
        import shutil
        data_dir = Path(self.db_path).parent
        try:
            usage = shutil.disk_usage(data_dir)
            free_pct = usage.free / usage.total * 100
            if free_pct < 5:
                return {"status": HealthStatus.UNHEALTHY, "detail": f"Only {free_pct:.1f}% disk free"}
            if free_pct < 15:
                return {"status": HealthStatus.DEGRADED, "detail": f"{free_pct:.1f}% disk free"}
            return {"status": HealthStatus.HEALTHY, "detail": f"{free_pct:.0f}% disk free"}
        except Exception as e:
            return {"status": HealthStatus.HEALTHY, "detail": "Cannot check disk (OK in cloud)"}

    def _check_error_rate(self) -> dict:
        """Check recent error frequency."""
        cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
        recent = [e for e in self._error_log if e["timestamp"] > cutoff]
        count = len(recent)
        if count > 20:
            return {"status": HealthStatus.UNHEALTHY, "detail": f"{count} errors in last hour"}
        if count > 5:
            return {"status": HealthStatus.DEGRADED, "detail": f"{count} errors in last hour"}
        return {"status": HealthStatus.HEALTHY, "detail": f"{count} errors in last hour"}

    def get_dashboard_data(self) -> dict:
        """Get data for the management dashboard."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Post stats
        today = datetime.now().strftime("%Y-%m-%d")
        posts_today = conn.execute(
            "SELECT COUNT(*) as c FROM posts WHERE DATE(created_at) = ?", (today,)
        ).fetchone()["c"]
        posts_total = conn.execute("SELECT COUNT(*) as c FROM posts").fetchone()["c"]
        posts_published = conn.execute(
            "SELECT COUNT(*) as c FROM posts WHERE status = 'published'"
        ).fetchone()["c"]
        posts_queued = conn.execute(
            "SELECT COUNT(*) as c FROM posts WHERE status = 'queued'"
        ).fetchone()["c"]

        # Recent posts
        recent_posts = conn.execute(
            """SELECT id, caption, status, post_type, created_at
               FROM posts ORDER BY created_at DESC LIMIT 10"""
        ).fetchall()

        # DM stats
        dm_count = conn.execute("SELECT COUNT(*) as c FROM dm_log").fetchone()["c"]
        dm_rules = conn.execute("SELECT COUNT(*) as c FROM dm_rules").fetchone()["c"]

        conn.close()

        return {
            "health": self.get_health(),
            "posts": {
                "today": posts_today,
                "total": posts_total,
                "published": posts_published,
                "queued": posts_queued,
                "recent": [dict(r) for r in recent_posts],
            },
            "dms": {
                "total_handled": dm_count,
                "active_rules": dm_rules,
            },
            "errors": {
                "recent_count": len(self._error_log),
                "last_5": self._error_log[-5:] if self._error_log else [],
            },
        }

    async def check_and_alert(self, notifier=None) -> list[str]:
        """Run health checks and send alerts if needed.

        Returns list of alert messages sent.
        """
        health = self.get_health()
        alerts_sent = []

        for check_name, check_result in health["checks"].items():
            if check_result["status"] != HealthStatus.HEALTHY:
                alert_key = f"{check_name}:{check_result['status']}"

                # Cooldown check
                last_alert = self._alert_cooldown.get(alert_key, 0)
                if time.monotonic() - last_alert < self._alert_cooldown_seconds:
                    continue

                msg = (
                    f"⚠️ [IG Monitor] {check_name}: {check_result['status']}\n"
                    f"Detail: {check_result['detail']}"
                )

                if notifier:
                    try:
                        notifier.send(msg)
                        self._alert_cooldown[alert_key] = time.monotonic()
                        alerts_sent.append(msg)
                    except Exception as e:
                        logger.error("Alert send failed: %s", e)
                else:
                    logger.warning("Alert (no notifier): %s", msg)
                    alerts_sent.append(msg)

        return alerts_sent

"""Monitoring and Health Check Router.

Provides system health, scheduler status, dashboard data, and monitoring alerts.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dependencies import (
    get_database,
    get_monitor,
)
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from services.database import Database
from services.monitoring import SystemMonitor

logger = logging.getLogger(__name__)

# Router without prefix since routes are at root and various paths
router = APIRouter(tags=["monitoring"])

# Global APScheduler instance (defined in main.py)
# We need to access it for scheduler status
_scheduler_instance = None


def set_scheduler_instance(scheduler):
    """Set the global APScheduler instance from main.py.

    This should be called during app startup after APScheduler is initialized.
    """
    global _scheduler_instance
    _scheduler_instance = scheduler


@router.get("/")
async def health(db: Database = Depends(get_database)):
    """Basic health check.

    Returns system status, scheduler state, and queue information.
    """
    return {
        "status": "running",
        "service": "instagram-automation",
        "scheduler_active": _scheduler_instance is not None and _scheduler_instance.running,
        "posts_queued": len(db.get_queued_posts()),
        "posts_published_today": db.get_post_count_today(),
    }


@router.get("/api/health")
async def health_check_detailed(monitor: SystemMonitor = Depends(get_monitor)):
    """Detailed system health check.

    Returns comprehensive health metrics including database, API, and service status.
    """
    return monitor.get_health()


@router.get("/api/scheduler/status")
async def scheduler_status():
    """Get APScheduler job status.

    Returns the status of all scheduled jobs and their next run times.
    """
    if not _scheduler_instance or not _scheduler_instance.running:
        return {"running": False, "jobs": []}

    jobs = _scheduler_instance.get_jobs()
    return {
        "running": True,
        "jobs": [
            {
                "id": j.id,
                "next_run": str(j.next_run_time) if j.next_run_time else None,
            }
            for j in jobs
        ],
    }


@router.get("/api/dashboard")
async def dashboard_data(monitor: SystemMonitor = Depends(get_monitor)):
    """Full dashboard data.

    Returns aggregated data for the management dashboard including metrics,
    alerts, and system performance.
    """
    return monitor.get_dashboard_data()


@router.get("/api/monitoring/alerts")
async def trigger_alert_check(monitor: SystemMonitor = Depends(get_monitor)):
    """Manual alert check.

    Triggers a manual check of system health and sends alerts if thresholds
    are exceeded.
    """
    alerts = await monitor.check_and_alert()
    return {"alerts_sent": len(alerts), "messages": alerts}


@router.get("/dashboard")
async def serve_dashboard():
    """Serve the management dashboard HTML.

    Returns the static HTML dashboard for system monitoring and management.
    """
    dashboard_path = Path(__file__).resolve().parents[1] / "static" / "dashboard.html"
    if dashboard_path.exists():
        return FileResponse(dashboard_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Dashboard not found")

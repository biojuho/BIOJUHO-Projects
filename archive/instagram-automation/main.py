"""Instagram Automation System — FastAPI application.

Refactored structure with routers for better organization.

API organized by domain:
- webhook: Meta webhook handling
- posts: Content generation and publishing
- insights: Analytics and performance
- dm: DM automation
- calendar: Content calendar
- hashtags: Hashtag optimization
- ab_testing: A/B experiments
- external: External trigger API
- monitoring: Health checks and dashboard
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is in path for shared imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import dependencies and routers
from dependencies import (
    get_config,
    get_meta_api,
    get_scheduler,
    initialize_dependencies,
)
from routers import (
    ab_testing,
    calendar,
    dm,
    external,
    hashtags,
    insights,
    monitoring,
    posts,
    webhook,
)

logger = logging.getLogger(__name__)

# ---- APScheduler setup ----

_scheduler_instance = None


def _setup_apscheduler() -> None:
    """Configure APScheduler for automated tasks."""
    global _scheduler_instance
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger

        config = get_config()
        scheduler_service = get_scheduler()

        _scheduler_instance = AsyncIOScheduler(timezone=config.scheduler.timezone)

        # Daily content generation
        _scheduler_instance.add_job(
            scheduler_service.generate_daily_content,
            CronTrigger(hour=config.scheduler.content_gen_hour),
            id="daily_content_gen",
            replace_existing=True,
        )

        # Publish at optimal hours
        hours_str = ",".join(str(h) for h in config.scheduler.posting_hours)
        _scheduler_instance.add_job(
            scheduler_service.publish_next,
            CronTrigger(hour=hours_str),
            id="auto_publish",
            replace_existing=True,
        )

        # Insights collection
        _scheduler_instance.add_job(
            scheduler_service.collect_insights,
            IntervalTrigger(hours=config.scheduler.insights_interval_hours),
            id="collect_insights",
            replace_existing=True,
        )

        # Daily report
        _scheduler_instance.add_job(
            scheduler_service.send_daily_report,
            CronTrigger(hour=config.scheduler.report_hour),
            id="daily_report",
            replace_existing=True,
        )

        _scheduler_instance.start()
        logger.info("APScheduler started with %d jobs", len(_scheduler_instance.get_jobs()))

        # Make scheduler instance available to monitoring router
        from routers.monitoring import set_scheduler_instance

        set_scheduler_instance(_scheduler_instance)

    except ImportError:
        logger.warning("APScheduler not installed — scheduled jobs disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle.

    - Initialize all singleton dependencies
    - Start APScheduler for automated tasks
    - Shutdown scheduler and close connections on exit
    """
    # Initialize all dependencies
    initialize_dependencies()

    # Setup scheduler
    _setup_apscheduler()

    config = get_config()
    logger.info("Instagram Automation started (port=%d)", config.port)

    yield

    # Shutdown
    if _scheduler_instance:
        _scheduler_instance.shutdown(wait=False)

    meta_api = get_meta_api()
    await meta_api.close()

    logger.info("Instagram Automation stopped")


# ---- FastAPI app ----

app = FastAPI(
    title="Instagram Automation",
    description="Meta Graph API based 24/7 Instagram automation system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ---- Include all routers ----

app.include_router(webhook.router)
app.include_router(posts.router)
app.include_router(insights.router)
app.include_router(dm.router)
app.include_router(calendar.router)
app.include_router(hashtags.router)
app.include_router(ab_testing.router)
app.include_router(external.router)
app.include_router(monitoring.router)

# ---- Run server ----

if __name__ == "__main__":
    import uvicorn

    config = get_config()
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level="info",
    )

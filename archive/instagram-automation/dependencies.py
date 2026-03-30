"""Dependency injection for Instagram Automation.

Provides FastAPI dependencies for shared services.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import AppConfig
    from services.ab_testing import ABTestEngine
    from services.analytics import AnalyticsEngine
    from services.content_calendar import ContentCalendar
    from services.database import Database
    from services.dm_responder import DMResponder
    from services.external_trigger import ExternalTriggerHandler
    from services.hashtag_strategy import HashtagDB
    from services.meta_api import MetaGraphAPI
    from services.monitoring import SystemMonitor
    from services.scheduler import PostScheduler


# Lazy imports to avoid circular dependencies
def _lazy_import_config():
    from config import get_config

    return get_config()


def _lazy_import_database():
    from services.database import Database

    return Database


def _lazy_import_meta_api():
    from services.meta_api import MetaGraphAPI

    return MetaGraphAPI


def _lazy_import_scheduler():
    from services.scheduler import PostScheduler

    return PostScheduler


def _lazy_import_dm_responder():
    from services.dm_responder import DMResponder

    return DMResponder


def _lazy_import_analytics():
    from services.analytics import AnalyticsEngine

    return AnalyticsEngine


def _lazy_import_calendar():
    from services.content_calendar import ContentCalendar

    return ContentCalendar


def _lazy_import_hashtag_db():
    from services.hashtag_strategy import HashtagDB

    return HashtagDB


def _lazy_import_ab_engine():
    from services.ab_testing import ABTestEngine

    return ABTestEngine


def _lazy_import_monitor():
    from services.monitoring import SystemMonitor

    return SystemMonitor


def _lazy_import_trigger_handler():
    from services.external_trigger import ExternalTriggerHandler

    return ExternalTriggerHandler


# Singleton instances (cached)
_config_instance: AppConfig | None = None
_db_instance: Database | None = None
_meta_api_instance: MetaGraphAPI | None = None
_scheduler_instance: PostScheduler | None = None
_dm_responder_instance: DMResponder | None = None
_analytics_instance: AnalyticsEngine | None = None
_calendar_instance: ContentCalendar | None = None
_hashtag_db_instance: HashtagDB | None = None
_ab_engine_instance: ABTestEngine | None = None
_monitor_instance: SystemMonitor | None = None
_trigger_handler_instance: ExternalTriggerHandler | None = None


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Get application configuration (singleton)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = _lazy_import_config()
    return _config_instance


def get_database() -> Database:
    """Get database instance (singleton)."""
    global _db_instance
    if _db_instance is None:
        DatabaseClass = _lazy_import_database()
        _db_instance = DatabaseClass(get_config().db_path)
    return _db_instance


def get_meta_api() -> MetaGraphAPI:
    """Get Meta Graph API client (singleton)."""
    global _meta_api_instance
    if _meta_api_instance is None:
        MetaGraphAPIClass = _lazy_import_meta_api()
        _meta_api_instance = MetaGraphAPIClass(get_config().meta)
    return _meta_api_instance


def get_scheduler() -> PostScheduler:
    """Get post scheduler (singleton)."""
    global _scheduler_instance
    if _scheduler_instance is None:
        PostSchedulerClass = _lazy_import_scheduler()
        _scheduler_instance = PostSchedulerClass(get_config())
    return _scheduler_instance


def get_dm_responder() -> DMResponder:
    """Get DM responder (singleton)."""
    global _dm_responder_instance
    if _dm_responder_instance is None:
        DMResponderClass = _lazy_import_dm_responder()
        _dm_responder_instance = DMResponderClass(get_config())
    return _dm_responder_instance


def get_analytics() -> AnalyticsEngine:
    """Get analytics engine (singleton)."""
    global _analytics_instance
    if _analytics_instance is None:
        AnalyticsEngineClass = _lazy_import_analytics()
        _analytics_instance = AnalyticsEngineClass(get_config())
    return _analytics_instance


def get_calendar() -> ContentCalendar:
    """Get content calendar (singleton)."""
    global _calendar_instance
    if _calendar_instance is None:
        ContentCalendarClass = _lazy_import_calendar()
        _calendar_instance = ContentCalendarClass(get_config().db_path)
    return _calendar_instance


def get_hashtag_db() -> HashtagDB:
    """Get hashtag database (singleton)."""
    global _hashtag_db_instance
    if _hashtag_db_instance is None:
        HashtagDBClass = _lazy_import_hashtag_db()
        _hashtag_db_instance = HashtagDBClass(get_config().db_path)
    return _hashtag_db_instance


def get_ab_engine() -> ABTestEngine:
    """Get A/B testing engine (singleton)."""
    global _ab_engine_instance
    if _ab_engine_instance is None:
        ABTestEngineClass = _lazy_import_ab_engine()
        _ab_engine_instance = ABTestEngineClass(get_config().db_path)
    return _ab_engine_instance


def get_monitor() -> SystemMonitor:
    """Get system monitor (singleton)."""
    global _monitor_instance
    if _monitor_instance is None:
        SystemMonitorClass = _lazy_import_monitor()
        _monitor_instance = SystemMonitorClass(get_config().db_path)
    return _monitor_instance


def get_trigger_handler() -> ExternalTriggerHandler:
    """Get external trigger handler (singleton)."""
    global _trigger_handler_instance
    if _trigger_handler_instance is None:
        ExternalTriggerHandlerClass = _lazy_import_trigger_handler()
        _trigger_handler_instance = ExternalTriggerHandlerClass(
            get_calendar(), get_hashtag_db(), get_ab_engine(), get_database()
        )
    return _trigger_handler_instance


# Initialize all dependencies (called on app startup)
def initialize_dependencies() -> None:
    """Initialize all singleton dependencies.

    Call this during app startup (lifespan) to ensure all services are ready.
    """
    get_config()
    get_database()
    get_meta_api()
    get_scheduler()
    get_dm_responder()
    get_analytics()
    get_calendar()
    get_hashtag_db()
    get_ab_engine()
    get_monitor()
    get_trigger_handler()

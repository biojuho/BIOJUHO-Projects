"""DB Repositories Layer — 공용 import 및 유틸리티."""

import json
import sys
from datetime import datetime, timedelta

from loguru import logger as log

try:
    from shared.cache import get_cache
    _REDIS_OK = True
except ImportError:
    _REDIS_OK = False

try:
    from ..db_schema import (
        _backfill_fingerprints,
        _normalize_name,
        _normalize_volume,
        _PgAdapter,
        close_pg_pool,
        compute_fingerprint,
        db_transaction,
        get_connection,
        get_pg_pool,
        init_db,
        sqlite_write_lock,
    )
    from ..models import GeneratedThread, GeneratedTweet, RunResult, ScoredTrend
except ImportError:
    from db_schema import (
        _backfill_fingerprints,
        _normalize_name,
        _normalize_volume,
        _PgAdapter,
        close_pg_pool,
        compute_fingerprint,
        db_transaction,
        get_connection,
        get_pg_pool,
        init_db,
        sqlite_write_lock,
    )
    from models import GeneratedThread, GeneratedTweet, RunResult, ScoredTrend

_REVIEW_STATUS_BY_LIFECYCLE = {
    "drafted": "Draft",
    "ready": "Ready",
    "approved": "Approved",
    "published": "Published",
    "measured": "Published",
    "learned": "Published",
}

_WORKFLOW_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "drafted": {"ready"},
    "ready": {"approved"},
    "approved": {"published"},
    "published": {"measured", "learned"},
    "measured": {"learned"},
    "learned": set(),
}


def _json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _facade_module():
    for name in ("db", "automation.getdaytrends.db"):
        module = sys.modules.get(name)
        if module is not None:
            return module
    return None


def _redis_enabled() -> bool:
    facade = _facade_module()
    if facade is not None and hasattr(facade, "_REDIS_OK"):
        return bool(getattr(facade, "_REDIS_OK"))
    return _REDIS_OK


def _get_cache_client():
    facade = _facade_module()
    if facade is not None and hasattr(facade, "get_cache"):
        return facade.get_cache()
    if _REDIS_OK:
        return get_cache()
    return None

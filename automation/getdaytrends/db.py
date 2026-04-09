"""
getdaytrends v3.0 - Database Layer (Facade)
트렌드 히스토리 및 CRUD 유틸리티 함수.
db_layer 이하로 분리된 레포지토리를 통합 제공합니다.
"""

import json

from loguru import logger as log

try:
    from shared.cache import get_cache
    _REDIS_OK = True
except ImportError:
    _REDIS_OK = False

try:
    from .db_layer.pg_adapter import PgAdapter as _PgAdapter
    from .db_layer.connection import (
        close_pg_pool,
        db_transaction,
        get_connection,
        get_pg_pool,
        sqlite_write_lock,
    )
    from .db_schema import (
        _backfill_fingerprints,
        _normalize_name,
        _normalize_volume,
        compute_fingerprint,
        init_db,
    )
    from .models import GeneratedThread, GeneratedTweet, RunResult, ScoredTrend
    from .db_layer.run_repository import *
    from .db_layer.trend_repository import *
    from .db_layer.tweet_repository import *
    from .db_layer.metrics_repository import *
    from .db_layer.draft_repository import *
    from .db_layer.tap_repository import *
    from .db_layer.admin_repository import *
except ImportError:
    from db_layer.pg_adapter import PgAdapter as _PgAdapter
    from db_layer.connection import (
        close_pg_pool,
        db_transaction,
        get_connection,
        get_pg_pool,
        sqlite_write_lock,
    )
    from db_schema import (
        _backfill_fingerprints,
        _normalize_name,
        _normalize_volume,
        compute_fingerprint,
        init_db,
    )
    from models import GeneratedThread, GeneratedTweet, RunResult, ScoredTrend
    from db_layer.run_repository import *
    from db_layer.trend_repository import *
    from db_layer.tweet_repository import *
    from db_layer.metrics_repository import *
    from db_layer.draft_repository import *
    from db_layer.tap_repository import *
    from db_layer.admin_repository import *

_WORKFLOW_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "drafted": {"ready"},
    "ready": {"approved"},
    "approved": {"published"},
    "published": {"measured", "learned"},
    "measured": {"learned"},
    "learned": set(),
}

_REVIEW_STATUS_BY_LIFECYCLE = {
    "drafted": "Draft",
    "ready": "Ready",
    "approved": "Approved",
    "published": "Published",
    "measured": "Published",
    "learned": "Published",
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

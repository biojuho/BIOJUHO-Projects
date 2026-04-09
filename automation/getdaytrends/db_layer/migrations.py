"""
getdaytrends — Schema Migrations (v1~v11).
DB 스키마 버전 관리 및 마이그레이션 인프라.
db_schema.py에서 분리됨.
"""

from datetime import UTC, datetime

from loguru import logger as log

from .pg_adapter import PgAdapter

_CURRENT_SCHEMA_VERSION = 11


async def _get_schema_version(conn) -> int:
    """현재 DB 스키마 버전 조회. schema_version 테이블 없으면 0."""
    try:
        cursor = await conn.execute(
            "SELECT MAX(version) as v FROM schema_version"
        )
        row = await cursor.fetchone()
        v = row["v"] if row else None
        return v if v is not None else 0
    except Exception:
        return 0


async def _set_schema_version(conn, version: int, description: str) -> None:
    await conn.execute(
        "INSERT OR REPLACE INTO schema_version (version, description, applied_at) VALUES (?, ?, ?)",
        (version, description, datetime.now(UTC).isoformat()),
    )
    await conn.commit()


async def _table_columns(conn, table: str) -> set[str]:
    """테이블의 컬럼 이름 목록 반환 (SQLite PRAGMA / PostgreSQL information_schema 호환)."""
    if isinstance(conn, PgAdapter):
        cursor = await conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            (table,),
        )
        rows = await cursor.fetchall()
        return {r["column_name"] if isinstance(r, dict) else r[0] for r in rows}
    # SQLite
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    return {(row["name"] if isinstance(row, dict) else row[1]) for row in rows}


# ═══════════════════════════════════════════════════════
#  Individual Migration Functions
# ═══════════════════════════════════════════════════════


async def _migrate_v1(conn) -> None:
    """v1: tweets.content_type 추가 (단문/장문 구분)."""
    cols = await _table_columns(conn, "tweets")
    if "content_type" not in cols:
        await conn.execute("ALTER TABLE tweets ADD COLUMN content_type TEXT DEFAULT 'short'")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_run_type ON tweets(run_id, content_type)")
        await conn.commit()


async def _migrate_v2(conn) -> None:
    """v2: trends.fingerprint 추가 (캐시 키)."""
    cols = await _table_columns(conn, "trends")
    if "fingerprint" not in cols:
        await conn.execute("ALTER TABLE trends ADD COLUMN fingerprint TEXT DEFAULT ''")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_trends_fingerprint ON trends(fingerprint)")
        await conn.commit()
        # backfill은 db_schema에서 호출됨 (compute_fingerprint 의존)
        from ..db_schema import _backfill_fingerprints
        await _backfill_fingerprints(conn)


async def _migrate_v3(conn) -> None:
    """v3: tweets 성과추적 + A/B 변형 + 다국어 컬럼."""
    cols = await _table_columns(conn, "tweets")
    for col_name, col_def in [
        ("posted_at", "TEXT DEFAULT NULL"),
        ("x_tweet_id", "TEXT DEFAULT ''"),
        ("impressions", "INTEGER DEFAULT 0"),
        ("engagements", "INTEGER DEFAULT 0"),
        ("engagement_rate", "REAL DEFAULT 0.0"),
        ("variant_id", "TEXT DEFAULT ''"),
        ("language", "TEXT DEFAULT 'ko'"),
    ]:
        if col_name not in cols:
            await conn.execute(f"ALTER TABLE tweets ADD COLUMN {col_name} {col_def}")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_x_tweet_id ON tweets(x_tweet_id)")
    await conn.commit()


async def _migrate_v4(conn) -> None:
    """v4: trends 감성필터 + 교차검증 + 중연킥."""
    cols = await _table_columns(conn, "trends")
    for col_name, col_def in [
        ("sentiment", "TEXT DEFAULT 'neutral'"),
        ("safety_flag", "INTEGER DEFAULT 0"),
        ("cross_source_confidence", "INTEGER DEFAULT 0"),
        ("joongyeon_kick", "INTEGER DEFAULT 0"),
        ("joongyeon_angle", "TEXT DEFAULT ''"),
    ]:
        if col_name not in cols:
            await conn.execute(f"ALTER TABLE trends ADD COLUMN {col_name} {col_def}")
    await conn.commit()


async def _migrate_v5(conn) -> None:
    """v5: schema_version 테이블 자체 (이미 CREATE TABLE로 생성됨). 마커 전용."""
    pass


async def _migrate_v6(conn) -> None:
    """v6: 100x 스케일 빈번한 인덱스 추가."""
    # trends: 캐시 조회 최적화 (fingerprint + scored_at 복합)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_trends_fp_scored ON trends(fingerprint, scored_at)"
    )
    # tweets: cleanup/정리 쿼리 최적화
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tweets_generated_at ON tweets(generated_at)"
    )
    # tweets: 게시 상태 추적 최적화
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tweets_posted_at ON tweets(posted_at)"
    )
    await conn.commit()


async def _migrate_v7(conn) -> None:
    """v7: workflow V2 tables for review queue, manual publish, and feedback."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS trend_quarantine (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER REFERENCES runs(id),
            keyword          TEXT DEFAULT '',
            fingerprint      TEXT DEFAULT '',
            reason_code      TEXT NOT NULL,
            reason_detail    TEXT DEFAULT '',
            source_count     INTEGER DEFAULT 0,
            freshness_minutes INTEGER DEFAULT 0,
            payload_json     TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tq_reason_created ON trend_quarantine(reason_code, created_at);

        CREATE TABLE IF NOT EXISTS validated_trends (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            trend_id         TEXT NOT NULL UNIQUE,
            trend_row_id     INTEGER REFERENCES trends(id),
            run_id           INTEGER REFERENCES runs(id),
            keyword          TEXT NOT NULL,
            confidence_score REAL DEFAULT 0.0,
            source_count     INTEGER DEFAULT 0,
            evidence_refs    TEXT DEFAULT '[]',
            freshness_minutes INTEGER DEFAULT 0,
            dedup_fingerprint TEXT DEFAULT '',
            lifecycle_status TEXT DEFAULT 'validated',
            scoring_axes     TEXT DEFAULT '{}',
            scoring_reasons  TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_vt_keyword_status ON validated_trends(keyword, lifecycle_status);
        CREATE INDEX IF NOT EXISTS idx_vt_fingerprint ON validated_trends(dedup_fingerprint);

        CREATE TABLE IF NOT EXISTS draft_bundles (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL UNIQUE,
            trend_id         TEXT NOT NULL REFERENCES validated_trends(trend_id),
            trend_row_id     INTEGER REFERENCES trends(id),
            platform         TEXT NOT NULL,
            content_type     TEXT NOT NULL,
            body             TEXT NOT NULL,
            hashtags         TEXT DEFAULT '[]',
            prompt_version   TEXT DEFAULT '',
            generator_provider TEXT DEFAULT '',
            generator_model  TEXT DEFAULT '',
            source_evidence_ref TEXT DEFAULT '',
            degraded_mode    INTEGER DEFAULT 0,
            lifecycle_status TEXT DEFAULT 'drafted',
            review_status    TEXT DEFAULT 'Draft',
            qa_score         REAL DEFAULT 0.0,
            blocking_reasons TEXT DEFAULT '[]',
            notion_page_id   TEXT DEFAULT '',
            published_url    TEXT DEFAULT '',
            published_at     TEXT DEFAULT NULL,
            receipt_id       TEXT DEFAULT '',
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_db_status_platform ON draft_bundles(review_status, platform);
        CREATE INDEX IF NOT EXISTS idx_db_lifecycle ON draft_bundles(lifecycle_status, updated_at);

        CREATE TABLE IF NOT EXISTS qa_reports (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            total_score      REAL DEFAULT 0.0,
            passed           INTEGER DEFAULT 0,
            warnings         TEXT DEFAULT '[]',
            blocking_reasons TEXT DEFAULT '[]',
            report_payload   TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_qa_draft_created ON qa_reports(draft_id, created_at);

        CREATE TABLE IF NOT EXISTS review_decisions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            decision         TEXT NOT NULL,
            reviewed_by      TEXT DEFAULT '',
            reviewed_at      TEXT NOT NULL,
            review_note      TEXT DEFAULT '',
            source           TEXT DEFAULT 'manual',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rd_draft_created ON review_decisions(draft_id, created_at);

        CREATE TABLE IF NOT EXISTS publish_receipts (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id       TEXT NOT NULL UNIQUE,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            platform         TEXT NOT NULL,
            success          INTEGER DEFAULT 0,
            published_url    TEXT DEFAULT '',
            published_at     TEXT DEFAULT NULL,
            failure_code     TEXT DEFAULT '',
            failure_reason   TEXT DEFAULT '',
            collector_due_at TEXT DEFAULT NULL,
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pr_draft_created ON publish_receipts(draft_id, created_at);

        CREATE TABLE IF NOT EXISTS feedback_summaries (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id         TEXT NOT NULL REFERENCES draft_bundles(draft_id),
            receipt_id       TEXT NOT NULL REFERENCES publish_receipts(receipt_id),
            metric_window    TEXT DEFAULT '',
            impressions      INTEGER DEFAULT 0,
            engagements      INTEGER DEFAULT 0,
            clicks           INTEGER DEFAULT 0,
            collector_status TEXT DEFAULT '',
            strategy_notes   TEXT DEFAULT '',
            created_at       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_fs_receipt_created ON feedback_summaries(receipt_id, created_at);
    """)
    await conn.commit()


async def _migrate_v8(conn) -> None:
    """v8: TAP board snapshot tables for premium/public product feeds."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS tap_snapshots (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id        TEXT NOT NULL UNIQUE,
            target_country     TEXT DEFAULT '',
            total_detected     INTEGER DEFAULT 0,
            teaser_count       INTEGER DEFAULT 0,
            generated_at       TEXT NOT NULL,
            future_dependencies TEXT DEFAULT '[]',
            source             TEXT DEFAULT 'tap_service',
            created_at         TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_snapshots_country_created ON tap_snapshots(target_country, created_at);

        CREATE TABLE IF NOT EXISTS tap_snapshot_items (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id           TEXT NOT NULL REFERENCES tap_snapshots(snapshot_id) ON DELETE CASCADE,
            item_order            INTEGER DEFAULT 0,
            keyword               TEXT NOT NULL,
            source_country        TEXT DEFAULT '',
            target_countries      TEXT DEFAULT '[]',
            viral_score           INTEGER DEFAULT 0,
            priority              REAL DEFAULT 0.0,
            time_gap_hours        REAL DEFAULT 0.0,
            paywall_tier          TEXT DEFAULT 'premium',
            public_teaser         TEXT DEFAULT '',
            recommended_platforms TEXT DEFAULT '[]',
            recommended_angle     TEXT DEFAULT '',
            execution_notes       TEXT DEFAULT '[]',
            publish_window_json   TEXT DEFAULT '{}',
            revenue_play_json     TEXT DEFAULT '{}',
            created_at            TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_snapshot_items_snapshot_order ON tap_snapshot_items(snapshot_id, item_order);
    """)
    await conn.commit()


async def _migrate_v9(conn) -> None:
    """v9: TAP premium alert queue table for monetizable dispatch workflows."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS tap_alert_queue (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id           TEXT NOT NULL UNIQUE,
            snapshot_id        TEXT NOT NULL REFERENCES tap_snapshots(snapshot_id) ON DELETE CASCADE,
            dedupe_key         TEXT NOT NULL,
            target_country     TEXT DEFAULT '',
            keyword            TEXT NOT NULL,
            source_country     TEXT DEFAULT '',
            paywall_tier       TEXT DEFAULT 'premium',
            priority           REAL DEFAULT 0.0,
            viral_score        INTEGER DEFAULT 0,
            alert_message      TEXT DEFAULT '',
            metadata_json      TEXT DEFAULT '{}',
            lifecycle_status   TEXT DEFAULT 'queued',
            queued_at          TEXT NOT NULL,
            dispatched_at      TEXT DEFAULT NULL,
            last_attempt_at    TEXT DEFAULT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_alert_queue_status_country ON tap_alert_queue(lifecycle_status, target_country, queued_at);
        CREATE INDEX IF NOT EXISTS idx_tap_alert_queue_dedupe ON tap_alert_queue(dedupe_key, queued_at);
    """)
    await conn.commit()


async def _migrate_v10(conn) -> None:
    """v10: TAP deal-room funnel events for teaser/click/purchase learning."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS tap_deal_room_events (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id           TEXT NOT NULL UNIQUE,
            snapshot_id        TEXT DEFAULT '',
            keyword            TEXT NOT NULL,
            target_country     TEXT DEFAULT '',
            audience_segment   TEXT DEFAULT '',
            package_tier       TEXT DEFAULT 'premium_alert_bundle',
            offer_tier         TEXT DEFAULT 'premium',
            event_type         TEXT NOT NULL,
            price_anchor       TEXT DEFAULT '',
            checkout_handle    TEXT DEFAULT '',
            session_id         TEXT DEFAULT '',
            actor_id           TEXT DEFAULT '',
            revenue_value      REAL DEFAULT 0.0,
            metadata_json      TEXT DEFAULT '{}',
            created_at         TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_deal_room_events_keyword_type_created ON tap_deal_room_events(keyword, event_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_deal_room_events_country_package_created ON tap_deal_room_events(target_country, package_tier, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_deal_room_events_session_created ON tap_deal_room_events(session_id, created_at);
    """)
    await conn.commit()


async def _migrate_v11(conn) -> None:
    """v11: TAP checkout session ops table for Stripe session tracking."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS tap_checkout_sessions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            checkout_session_id TEXT NOT NULL UNIQUE,
            checkout_handle     TEXT DEFAULT '',
            snapshot_id         TEXT DEFAULT '',
            keyword             TEXT NOT NULL,
            target_country      TEXT DEFAULT '',
            audience_segment    TEXT DEFAULT '',
            package_tier        TEXT DEFAULT 'premium_alert_bundle',
            offer_tier          TEXT DEFAULT 'premium',
            session_status      TEXT DEFAULT 'created',
            payment_status      TEXT DEFAULT '',
            currency            TEXT DEFAULT 'usd',
            quoted_price_value  REAL DEFAULT 0.0,
            revenue_value       REAL DEFAULT 0.0,
            checkout_url        TEXT DEFAULT '',
            actor_id            TEXT DEFAULT '',
            stripe_customer_id  TEXT DEFAULT '',
            stripe_event_id     TEXT DEFAULT '',
            metadata_json       TEXT DEFAULT '{}',
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL,
            completed_at        TEXT DEFAULT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tap_checkout_sessions_status_created ON tap_checkout_sessions(session_status, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_checkout_sessions_keyword_created ON tap_checkout_sessions(keyword, created_at);
        CREATE INDEX IF NOT EXISTS idx_tap_checkout_sessions_handle_created ON tap_checkout_sessions(checkout_handle, created_at);
    """)
    await conn.commit()


# 마이그레이션 레지스트리 (버전, 설명, 함수)
_MIGRATIONS: list[tuple[int, str, any]] = [
    (1, "tweets.content_type column", _migrate_v1),
    (2, "trends.fingerprint column + index", _migrate_v2),
    (3, "tweets metrics + A/B + multi-country", _migrate_v3),
    (4, "trends sentiment filter + genealogy + dedup", _migrate_v4),
    (5, "schema_version table init", _migrate_v5),
    (6, "100x scale composite indexes", _migrate_v6),
    (7, "workflow V2 review queue tables", _migrate_v7),
    (8, "TAP product snapshot tables", _migrate_v8),
    (9, "TAP premium alert queue", _migrate_v9),
    (10, "TAP deal-room funnel events", _migrate_v10),
    (11, "TAP checkout session ops", _migrate_v11),
]


async def _reconcile_latest_schema(conn) -> None:
    """Backfill required columns when the schema marker drifted from actual columns."""
    await _migrate_v1(conn)
    await _migrate_v2(conn)
    await _migrate_v3(conn)
    await _migrate_v4(conn)
    await _migrate_v7(conn)
    await _migrate_v8(conn)
    await _migrate_v9(conn)
    await _migrate_v10(conn)
    await _migrate_v11(conn)


async def run_migrations(conn) -> None:
    """현재 버전 확인 후 미적용 마이그레이션 순차 실행."""
    current = await _get_schema_version(conn)

    if current >= _CURRENT_SCHEMA_VERSION:
        await _reconcile_latest_schema(conn)
        return

    # 기존 DB (schema_version 없이 이미 컬럼이 있는 경우) 상태 감지
    if current == 0:
        try:
            cols = await _table_columns(conn, "trends")
            if "joongyeon_angle" in cols:
                # v4까지 이미 적용된 기존 DB → v4로 점프
                current = 4
                for v in range(1, 5):
                    desc = next(d for ver, d, _ in _MIGRATIONS if ver == v)
                    await _set_schema_version(conn, v, f"{desc} (기존 감지)")
        except Exception:
            pass

    pending = [(v, d, fn) for v, d, fn in _MIGRATIONS if v > current]
    if not pending:
        # 최신인데 schema_version 엔트리만 없는 경우
        if current == 0:
            await _set_schema_version(conn, _CURRENT_SCHEMA_VERSION, "초기 설치")
        await _reconcile_latest_schema(conn)
        return

    for version, description, migrate_fn in pending:
        log.info(f"[DB Migration] v{version}: {description}")
        await migrate_fn(conn)
        await _set_schema_version(conn, version, description)

    await _reconcile_latest_schema(conn)

    log.info(f"[DB Migration] 완료: v{current} → v{_CURRENT_SCHEMA_VERSION}")

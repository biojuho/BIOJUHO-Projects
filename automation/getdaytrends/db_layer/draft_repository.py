"""Draft Repository"""

from datetime import datetime, timedelta

from . import (
    _WORKFLOW_STATUS_TRANSITIONS,
    _json_list,
    _json_text,
    _REDIS_OK,
    log,
    sqlite_write_lock,
)

async def _record_content_feedback_unlocked(
    conn,
    keyword: str,
    category: str = "",
    qa_score: float = 0.0,
    regenerated: bool = False,
    reason: str = "",
    content_age_hours: float = 0.0,
    freshness_grade: str = "unknown",
) -> None:
    """v6.0/v6.1: 콘텐츠 QA 피드백 + 최신성 기록."""
    try:
        await conn.execute(
            """INSERT INTO content_feedback (keyword, category, qa_score, regenerated, reason, content_age_hours, freshness_grade, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                keyword,
                category,
                qa_score,
                int(regenerated),
                reason,
                content_age_hours,
                freshness_grade,
                datetime.now().isoformat(),
            ),
        )
        await conn.commit()
    except Exception as e:
        log.debug(f"content_feedback 기록 실패 (무시): {e}")

async def record_content_feedback(
    conn,
    keyword: str,
    category: str = "",
    qa_score: float = 0.0,
    regenerated: bool = False,
    reason: str = "",
    content_age_hours: float = 0.0,
    freshness_grade: str = "unknown",
) -> None:
    async with sqlite_write_lock(conn):
        await _record_content_feedback_unlocked(
            conn,
            keyword,
            category=category,
            qa_score=qa_score,
            regenerated=regenerated,
            reason=reason,
            content_age_hours=content_age_hours,
            freshness_grade=freshness_grade,
        )

async def get_qa_summary(conn, days: int = 7) -> dict:
    """
    v15.0 Phase B: QA 메트릭 요약.
    반환: {total_feedbacks, avg_qa_score, regeneration_rate, by_category, recent_scores}
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    # 전체 집계
    cursor = await conn.execute(
        """SELECT COUNT(*) as total,
                  COALESCE(AVG(qa_score), 0.0) as avg_score,
                  COALESCE(SUM(regenerated), 0) as regen_count
           FROM content_feedback
           WHERE created_at >= ?""",
        (cutoff,),
    )
    row = await cursor.fetchone()
    total = dict(row).get("total", 0) if row else 0
    avg_score = dict(row).get("avg_score", 0.0) if row else 0.0
    regen_count = dict(row).get("regen_count", 0) if row else 0
    regen_rate = regen_count / total if total > 0 else 0.0

    # 카테고리별 분석
    cursor = await conn.execute(
        """SELECT category,
                  COUNT(*) as count,
                  ROUND(AVG(qa_score), 1) as avg_score
           FROM content_feedback
           WHERE created_at >= ? AND category != ''
           GROUP BY category""",
        (cutoff,),
    )
    cat_rows = await cursor.fetchall()
    by_category = {r["category"]: {"count": r["count"], "avg_score": r["avg_score"]} for r in cat_rows}

    # 최근 점수 (최대 10건)
    cursor = await conn.execute(
        """SELECT qa_score FROM content_feedback
           WHERE created_at >= ?
           ORDER BY created_at DESC LIMIT 10""",
        (cutoff,),
    )
    score_rows = await cursor.fetchall()
    recent_scores = [r["qa_score"] for r in score_rows]

    return {
        "total_feedbacks": total,
        "avg_qa_score": round(avg_score, 1),
        "regeneration_rate": round(regen_rate, 4),
        "by_category": by_category,
        "recent_scores": recent_scores,
    }

async def get_content_hashes(conn, hours: int = 24) -> set[str]:
    """
    v15.0 Phase B: 최근 N시간 내 생성된 콘텐츠의 핑거프린트 해시 집합 반환.
    콘텐츠 다양성 검증에 사용.
    """
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await conn.execute(
        """SELECT DISTINCT fingerprint FROM trends
           WHERE scored_at >= ? AND fingerprint != ''""",
        (cutoff,),
    )
    rows = await cursor.fetchall()
    return {r["fingerprint"] for r in rows}


async def record_trend_quarantine(
    conn,
    *,
    reason_code: str,
    reason_detail: str = "",
    keyword: str = "",
    fingerprint: str = "",
    source_count: int = 0,
    freshness_minutes: int = 0,
    payload: dict | None = None,
    run_id: int | None = None,
) -> int:
    async with sqlite_write_lock(conn):
        cursor = await conn.execute(
            """INSERT INTO trend_quarantine (
                   run_id, keyword, fingerprint, reason_code, reason_detail,
                   source_count, freshness_minutes, payload_json, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                keyword,
                fingerprint,
                reason_code,
                reason_detail,
                source_count,
                freshness_minutes,
                _json_text(payload or {}),
                datetime.now().isoformat(),
            ),
        )
        await conn.commit()
        return cursor.lastrowid

async def save_validated_trend(
    conn,
    *,
    trend_id: str,
    keyword: str,
    confidence_score: float = 0.0,
    source_count: int = 0,
    evidence_refs: list[str] | None = None,
    freshness_minutes: int = 0,
    dedup_fingerprint: str = "",
    lifecycle_status: str = "validated",
    scoring_axes: dict | None = None,
    scoring_reasons: dict | None = None,
    trend_row_id: int | None = None,
    run_id: int | None = None,
) -> str:
    now = datetime.now().isoformat()
    async with sqlite_write_lock(conn):
        await conn.execute(
            """INSERT INTO validated_trends (
                   trend_id, trend_row_id, run_id, keyword, confidence_score,
                   source_count, evidence_refs, freshness_minutes,
                   dedup_fingerprint, lifecycle_status, scoring_axes,
                   scoring_reasons, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(trend_id) DO UPDATE SET
                   trend_row_id=excluded.trend_row_id,
                   run_id=excluded.run_id,
                   keyword=excluded.keyword,
                   confidence_score=excluded.confidence_score,
                   source_count=excluded.source_count,
                   evidence_refs=excluded.evidence_refs,
                   freshness_minutes=excluded.freshness_minutes,
                   dedup_fingerprint=excluded.dedup_fingerprint,
                   lifecycle_status=excluded.lifecycle_status,
                   scoring_axes=excluded.scoring_axes,
                   scoring_reasons=excluded.scoring_reasons,
                   updated_at=excluded.updated_at""",
            (
                trend_id,
                trend_row_id,
                run_id,
                keyword,
                confidence_score,
                source_count,
                _json_text(evidence_refs or []),
                freshness_minutes,
                dedup_fingerprint,
                lifecycle_status,
                _json_text(scoring_axes or {}),
                _json_text(scoring_reasons or {}),
                now,
                now,
            ),
        )
        await conn.commit()
    return trend_id

async def save_draft_bundle(
    conn,
    *,
    draft_id: str,
    trend_id: str,
    platform: str,
    content_type: str,
    body: str,
    hashtags: list[str] | None = None,
    prompt_version: str = "",
    generator_provider: str = "",
    generator_model: str = "",
    source_evidence_ref: str = "",
    degraded_mode: bool = False,
    lifecycle_status: str = "drafted",
    review_status: str = "Draft",
    trend_row_id: int | None = None,
) -> str:
    now = datetime.now().isoformat()
    async with sqlite_write_lock(conn):
        await conn.execute(
            """INSERT INTO draft_bundles (
                   draft_id, trend_id, trend_row_id, platform, content_type,
                   body, hashtags, prompt_version, generator_provider,
                   generator_model, source_evidence_ref, degraded_mode,
                   lifecycle_status, review_status, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(draft_id) DO UPDATE SET
                   trend_id=excluded.trend_id,
                   trend_row_id=excluded.trend_row_id,
                   platform=excluded.platform,
                   content_type=excluded.content_type,
                   body=excluded.body,
                   hashtags=excluded.hashtags,
                   prompt_version=excluded.prompt_version,
                   generator_provider=excluded.generator_provider,
                   generator_model=excluded.generator_model,
                   source_evidence_ref=excluded.source_evidence_ref,
                   degraded_mode=excluded.degraded_mode,
                   updated_at=excluded.updated_at""",
            (
                draft_id,
                trend_id,
                trend_row_id,
                platform,
                content_type,
                body,
                _json_text(hashtags or []),
                prompt_version,
                generator_provider,
                generator_model,
                source_evidence_ref,
                int(degraded_mode),
                lifecycle_status,
                review_status,
                now,
                now,
            ),
        )
        await conn.commit()
    return draft_id

async def get_draft_bundle(conn, draft_id: str) -> dict | None:
    cursor = await conn.execute("SELECT * FROM draft_bundles WHERE draft_id = ? LIMIT 1", (draft_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None

async def update_draft_bundle_status(
    conn,
    *,
    draft_id: str,
    lifecycle_status: str,
    review_status: str | None = None,
    notion_page_id: str | None = None,
    published_url: str | None = None,
    published_at: str | None = None,
    receipt_id: str | None = None,
) -> None:
    # 읽기+검증+쓰기를 단일 lock 안에서 수행 (TOCTOU 방지)
    async with sqlite_write_lock(conn):
        row = await get_draft_bundle(conn, draft_id)
        if row is None:
            raise ValueError(f"unknown draft_id: {draft_id}")

        current = row.get("lifecycle_status", "drafted")
        if current != lifecycle_status:
            allowed = _WORKFLOW_STATUS_TRANSITIONS.get(current, set())
            if lifecycle_status not in allowed:
                raise ValueError(f"invalid draft transition: {current} -> {lifecycle_status}")

        await conn.execute(
            """UPDATE draft_bundles
               SET lifecycle_status = ?,
                   review_status = COALESCE(?, review_status),
                   notion_page_id = COALESCE(?, notion_page_id),
                   published_url = COALESCE(?, published_url),
                   published_at = COALESCE(?, published_at),
                   receipt_id = COALESCE(?, receipt_id),
                   updated_at = ?
               WHERE draft_id = ?""",
            (
                lifecycle_status,
                review_status,
                notion_page_id,
                published_url,
                published_at,
                receipt_id,
                datetime.now().isoformat(),
                draft_id,
            ),
        )
        await conn.commit()

async def save_qa_report(
    conn,
    *,
    draft_id: str,
    total_score: float,
    passed: bool,
    warnings: list[str] | None = None,
    blocking_reasons: list[str] | None = None,
    report_payload: dict | None = None,
) -> int:
    async with sqlite_write_lock(conn):
        cursor = await conn.execute(
            """INSERT INTO qa_reports (
                   draft_id, total_score, passed, warnings, blocking_reasons,
                   report_payload, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                draft_id,
                total_score,
                int(passed),
                _json_text(warnings or []),
                _json_text(blocking_reasons or []),
                _json_text(report_payload or {}),
                datetime.now().isoformat(),
            ),
        )
        await conn.execute(
            """UPDATE draft_bundles
               SET qa_score = ?,
                   blocking_reasons = ?,
                   updated_at = ?
               WHERE draft_id = ?""",
            (
                total_score,
                _json_text(blocking_reasons or []),
                datetime.now().isoformat(),
                draft_id,
            ),
        )
        await conn.commit()
        return cursor.lastrowid

async def promote_draft_to_ready(conn, draft_id: str) -> None:
    row = await get_draft_bundle(conn, draft_id)
    if row is None:
        raise ValueError(f"unknown draft_id: {draft_id}")
    blockers = _json_list(row.get("blocking_reasons"))
    if blockers:
        raise ValueError(f"draft has blocking reasons: {', '.join(blockers)}")
    if not (row.get("prompt_version") or "").strip():
        raise ValueError("draft missing prompt_version")
    if not (row.get("source_evidence_ref") or "").strip():
        raise ValueError("draft missing source_evidence_ref")
    await update_draft_bundle_status(
        conn,
        draft_id=draft_id,
        lifecycle_status="ready",
        review_status="Ready",
    )

async def save_review_decision(
    conn,
    *,
    draft_id: str,
    decision: str,
    reviewed_by: str = "",
    review_note: str = "",
    reviewed_at: str | None = None,
    source: str = "manual",
) -> int:
    normalized = decision.strip().lower()
    if normalized not in {"approved", "rejected", "expired"}:
        raise ValueError(f"unsupported review decision: {decision}")

    ts = reviewed_at or datetime.now().isoformat()
    async with sqlite_write_lock(conn):
        row = await get_draft_bundle(conn, draft_id)
        if row is None:
            raise ValueError(f"unknown draft_id: {draft_id}")

        next_lifecycle = row.get("lifecycle_status", "drafted")
        next_review_status = row.get("review_status", "Draft")
        if normalized == "approved":
            if next_lifecycle != "ready":
                raise ValueError("draft must be ready before approval")
            next_lifecycle = "approved"
            next_review_status = "Approved"
        elif normalized == "rejected":
            next_review_status = "Rejected"
        elif normalized == "expired":
            next_review_status = "Expired"

        cursor = await conn.execute(
            """INSERT INTO review_decisions (
                   draft_id, decision, reviewed_by, reviewed_at,
                   review_note, source, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (draft_id, normalized, reviewed_by, ts, review_note, source, datetime.now().isoformat()),
        )
        await conn.execute(
            """UPDATE draft_bundles
               SET lifecycle_status = ?, review_status = ?, updated_at = ?
               WHERE draft_id = ?""",
            (next_lifecycle, next_review_status, datetime.now().isoformat(), draft_id),
        )
        await conn.commit()
        return cursor.lastrowid

async def record_publish_receipt(
    conn,
    *,
    draft_id: str,
    platform: str,
    success: bool,
    published_url: str = "",
    published_at: str | None = None,
    failure_code: str = "",
    failure_reason: str = "",
    receipt_id: str = "",
) -> str:
    published_ts = published_at or datetime.now().isoformat()
    resolved_receipt_id = receipt_id or f"receipt-{draft_id[-8:]}-{int(datetime.now().timestamp())}"
    collector_due_at = (datetime.fromisoformat(published_ts) + timedelta(hours=48)).isoformat() if success else None

    async with sqlite_write_lock(conn):
        row = await get_draft_bundle(conn, draft_id)
        if row is None:
            raise ValueError(f"unknown draft_id: {draft_id}")
        if row.get("lifecycle_status") != "approved":
            raise ValueError("draft must be approved before publish receipt is recorded")

        await conn.execute(
            """INSERT INTO publish_receipts (
                   receipt_id, draft_id, platform, success, published_url,
                   published_at, failure_code, failure_reason,
                   collector_due_at, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                resolved_receipt_id,
                draft_id,
                platform,
                int(success),
                published_url,
                published_ts if success else None,
                failure_code,
                failure_reason,
                collector_due_at,
                datetime.now().isoformat(),
            ),
        )
        if success:
            await conn.execute(
                """UPDATE draft_bundles
                   SET lifecycle_status = 'published',
                       review_status = 'Published',
                       published_url = ?,
                       published_at = ?,
                       receipt_id = ?,
                       updated_at = ?
                   WHERE draft_id = ?""",
                (
                    published_url,
                    published_ts,
                    resolved_receipt_id,
                    datetime.now().isoformat(),
                    draft_id,
                ),
            )
        await conn.commit()
    return resolved_receipt_id

async def record_feedback_summary(
    conn,
    *,
    draft_id: str,
    metric_window: str,
    impressions: int = 0,
    engagements: int = 0,
    clicks: int = 0,
    collector_status: str = "",
    strategy_notes: str = "",
    receipt_id: str = "",
) -> int:
    row = await get_draft_bundle(conn, draft_id)
    if row is None:
        raise ValueError(f"unknown draft_id: {draft_id}")

    resolved_receipt_id = receipt_id or (row.get("receipt_id") or "")
    if not resolved_receipt_id:
        raise ValueError("publish receipt required before feedback summary")

    cursor = await conn.execute(
        "SELECT receipt_id FROM publish_receipts WHERE receipt_id = ? AND draft_id = ? LIMIT 1",
        (resolved_receipt_id, draft_id),
    )
    if await cursor.fetchone() is None:
        raise ValueError("publish receipt required before feedback summary")

    async with sqlite_write_lock(conn):
        cursor = await conn.execute(
            """INSERT INTO feedback_summaries (
                   draft_id, receipt_id, metric_window, impressions,
                   engagements, clicks, collector_status,
                   strategy_notes, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                draft_id,
                resolved_receipt_id,
                metric_window,
                impressions,
                engagements,
                clicks,
                collector_status,
                strategy_notes,
                datetime.now().isoformat(),
            ),
        )
        await conn.execute(
            """UPDATE draft_bundles
               SET lifecycle_status = 'learned',
                   updated_at = ?
               WHERE draft_id = ?""",
            (datetime.now().isoformat(), draft_id),
        )
        await conn.commit()
        return cursor.lastrowid

async def attach_draft_to_notion_page(conn, draft_id: str, notion_page_id: str, review_status: str = "Ready") -> None:
    row = await get_draft_bundle(conn, draft_id)
    if row is None:
        raise ValueError(f"unknown draft_id: {draft_id}")
    async with sqlite_write_lock(conn):
        await conn.execute(
            """UPDATE draft_bundles
               SET notion_page_id = ?, review_status = ?, updated_at = ?
               WHERE draft_id = ?""",
            (notion_page_id, review_status, datetime.now().isoformat(), draft_id),
        )
        await conn.commit()

async def get_review_queue_snapshot(conn, limit: int = 50) -> dict:
    status_cursor = await conn.execute(
        "SELECT review_status, COUNT(*) as count FROM draft_bundles GROUP BY review_status"
    )
    counts = {row["review_status"]: row["count"] for row in await status_cursor.fetchall()}
    items_cursor = await conn.execute(
        """SELECT draft_id, trend_id, platform, content_type, lifecycle_status,
                  review_status, qa_score, notion_page_id, published_url,
                  created_at, updated_at
           FROM draft_bundles
           ORDER BY updated_at DESC, created_at DESC
           LIMIT ?""",
        (limit,),
    )
    items = [dict(row) for row in await items_cursor.fetchall()]
    return {"counts": counts, "items": items}

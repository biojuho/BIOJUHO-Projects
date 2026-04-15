"""Dashboard — GetDayTrends + A/B Performance + Quality + QA routes."""

from __future__ import annotations

import json as _json
import os
from datetime import datetime

from fastapi import APIRouter

from db_utils import GDT_DB, _sqlite_read, _sqlite_scalar

router = APIRouter()


@router.get("/api/getdaytrends")
def getdaytrends():
    """GetDayTrends 실행 현황."""
    recent_runs = _sqlite_read(
        GDT_DB,
        """SELECT id, country, started_at, finished_at, trends_collected,
                  tweets_generated
           FROM runs ORDER BY id DESC LIMIT 30""",
    )
    daily_runs = _sqlite_read(
        GDT_DB,
        """SELECT DATE(started_at) as date, COUNT(*) as count,
                  SUM(trends_collected) as trends, SUM(tweets_generated) as tweets
           FROM runs
           WHERE started_at >= date('now', '-14 days')
           GROUP BY DATE(started_at)
           ORDER BY date""",
    )
    top_trends = _sqlite_read(
        GDT_DB,
        """SELECT keyword, viral_potential, volume_raw
           FROM trends
           ORDER BY id DESC LIMIT 10""",
    )
    total_runs = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM runs") or 0
    total_trends = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM trends") or 0
    total_tweets = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM tweets") or 0
    return {
        "total_runs": total_runs,
        "total_trends": total_trends,
        "total_tweets": total_tweets,
        "recent_runs": recent_runs,
        "daily_runs": daily_runs,
        "top_trends": top_trends,
    }


@router.get("/api/ab_performance")
def ab_performance():
    """A/B 패턴 성과."""
    hook_stats = _sqlite_read(
        GDT_DB,
        """SELECT hook_pattern, COUNT(*) as count,
                  AVG(engagement_rate) as avg_eng,
                  AVG(impressions) as avg_imp
           FROM tweet_performance
           WHERE hook_pattern != '' AND collected_at >= datetime('now', '-30 days')
           GROUP BY hook_pattern
           ORDER BY avg_eng DESC""",
    )
    kick_stats = _sqlite_read(
        GDT_DB,
        """SELECT kick_pattern, COUNT(*) as count,
                  AVG(engagement_rate) as avg_eng
           FROM tweet_performance
           WHERE kick_pattern != '' AND collected_at >= datetime('now', '-30 days')
           GROUP BY kick_pattern
           ORDER BY avg_eng DESC""",
    )
    angle_stats = _sqlite_read(
        GDT_DB,
        """SELECT angle_type, COUNT(*) as count,
                  AVG(engagement_rate) as avg_eng
           FROM tweet_performance
           WHERE angle_type != '' AND collected_at >= datetime('now', '-30 days')
           GROUP BY angle_type
           ORDER BY avg_eng DESC""",
    )
    total_samples = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM tweet_performance") or 0
    feedback_stats = _sqlite_read(
        GDT_DB,
        """SELECT
             COUNT(*) as total,
             AVG(qa_score) as avg_qa,
             SUM(CASE WHEN regenerated = 1 THEN 1 ELSE 0 END) as regenerated_count
           FROM content_feedback
           WHERE created_at >= datetime('now', '-30 days')""",
    )
    feedback_trend = _sqlite_read(
        GDT_DB,
        """SELECT DATE(created_at) as date, COUNT(*) as count, AVG(qa_score) as avg_qa
           FROM content_feedback
           WHERE created_at >= datetime('now', '-7 days')
           GROUP BY DATE(created_at)
           ORDER BY date""",
    )
    return {
        "total_samples": total_samples,
        "hook_stats": hook_stats,
        "kick_stats": kick_stats,
        "angle_stats": angle_stats,
        "feedback": feedback_stats[0] if feedback_stats else {},
        "feedback_trend": feedback_trend,
    }


@router.get("/api/qa_reports")
def qa_reports(limit: int = 50):
    """QA 리포트 상세."""
    rows = _sqlite_read(
        GDT_DB,
        """SELECT
             q.id, q.draft_id, q.total_score, q.passed,
             q.warnings, q.blocking_reasons, q.report_payload, q.created_at,
             d.trend_id, d.platform, d.content_type,
             d.lifecycle_status, d.review_status,
             t.keyword
           FROM qa_reports q
           LEFT JOIN draft_bundles d ON q.draft_id = d.draft_id
           LEFT JOIN validated_trends v ON d.trend_id = v.trend_id
           LEFT JOIN trends t ON v.trend_row_id = t.id
           ORDER BY q.created_at DESC
           LIMIT ?""",
        (min(limit, 200),),
    )
    for row in rows:
        for field in ("warnings", "blocking_reasons", "report_payload"):
            val = row.get(field)
            if isinstance(val, str):
                try:
                    row[field] = _json.loads(val)
                except (ValueError, TypeError):
                    pass

    total = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM qa_reports") or 0
    passed = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM qa_reports WHERE passed = 1") or 0
    avg_score = _sqlite_scalar(GDT_DB, "SELECT AVG(total_score) FROM qa_reports") or 0
    platform_stats = _sqlite_read(
        GDT_DB,
        """SELECT d.platform,
                  COUNT(*) as total,
                  SUM(CASE WHEN q.passed = 1 THEN 1 ELSE 0 END) as passed,
                  ROUND(AVG(q.total_score), 1) as avg_score
           FROM qa_reports q
           LEFT JOIN draft_bundles d ON q.draft_id = d.draft_id
           GROUP BY d.platform""",
    )
    daily_trend = _sqlite_read(
        GDT_DB,
        """SELECT DATE(q.created_at) as date,
                  COUNT(*) as total,
                  SUM(CASE WHEN q.passed = 1 THEN 1 ELSE 0 END) as passed,
                  ROUND(AVG(q.total_score), 1) as avg_score
           FROM qa_reports q
           WHERE q.created_at >= date('now', '-14 days')
           GROUP BY DATE(q.created_at)
           ORDER BY date""",
    )
    return {
        "summary": {
            "total_reports": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total * 100, 1) if total else 0,
            "avg_score": round(avg_score, 1),
        },
        "platform_stats": platform_stats,
        "daily_trend": daily_trend,
        "reports": rows,
    }


@router.get("/api/quality_overview")
def quality_overview():
    """품질 종합 대시보드."""
    qa_grade_dist = _sqlite_read(
        GDT_DB,
        """SELECT
             CASE
               WHEN total_score >= 90 THEN 'A (90+)'
               WHEN total_score >= 80 THEN 'B (80-89)'
               WHEN total_score >= 70 THEN 'C (70-79)'
               ELSE 'D (<70)'
             END as grade,
             COUNT(*) as count,
             ROUND(AVG(total_score), 1) as avg_score
           FROM qa_reports
           GROUP BY grade
           ORDER BY grade""",
    )
    blocking_reasons_raw = _sqlite_read(
        GDT_DB,
        """SELECT blocking_reasons
           FROM qa_reports
           WHERE passed = 0 AND blocking_reasons IS NOT NULL AND blocking_reasons != '[]'
           ORDER BY created_at DESC LIMIT 100""",
    )
    reason_counter: dict[str, int] = {}
    for row in blocking_reasons_raw:
        val = row.get("blocking_reasons", "")
        if isinstance(val, str):
            try:
                reasons = _json.loads(val)
            except (ValueError, TypeError):
                reasons = []
        else:
            reasons = val or []
        for r in reasons:
            reason_counter[str(r)[:80]] = reason_counter.get(str(r)[:80], 0) + 1
    top_blockers = sorted(reason_counter.items(), key=lambda x: x[1], reverse=True)[:10]

    lifecycle_dist = _sqlite_read(
        GDT_DB,
        """SELECT lifecycle_status, review_status, COUNT(*) as count
           FROM draft_bundles
           GROUP BY lifecycle_status, review_status
           ORDER BY count DESC""",
    )
    daily_production = _sqlite_read(
        GDT_DB,
        """SELECT DATE(created_at) as date,
                  COUNT(*) as drafts,
                  SUM(CASE WHEN review_status = 'Approved' THEN 1 ELSE 0 END) as approved,
                  SUM(CASE WHEN review_status = 'Rejected' THEN 1 ELSE 0 END) as rejected
           FROM draft_bundles
           WHERE created_at >= date('now', '-7 days')
           GROUP BY DATE(created_at)
           ORDER BY date""",
    )
    confidence_dist = _sqlite_read(
        GDT_DB,
        """SELECT
             CASE
               WHEN confidence_score >= 0.9 THEN 'Very High (0.9+)'
               WHEN confidence_score >= 0.7 THEN 'High (0.7-0.9)'
               WHEN confidence_score >= 0.5 THEN 'Medium (0.5-0.7)'
               ELSE 'Low (<0.5)'
             END as tier,
             COUNT(*) as count
           FROM validated_trends
           GROUP BY tier
           ORDER BY tier""",
    )
    return {
        "qa_grades": qa_grade_dist,
        "top_blocking_reasons": [{"reason": r, "count": c} for r, c in top_blockers],
        "lifecycle_distribution": lifecycle_dist,
        "daily_production": daily_production,
        "confidence_distribution": confidence_dist,
    }

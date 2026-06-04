"""Dashboard — GetDayTrends + A/B Performance + Quality + QA routes."""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any

from db_utils import GDT_DB, WORKSPACE, _sqlite_read, _sqlite_scalar
from fastapi import APIRouter

router = APIRouter()

SMOKE_REPORT_PATTERNS = ("var/smoke/*.json", "var/workspace-smoke*.json")
DEV_SERVER_STATUS_PATTERNS = ("var/dev-server-status*.json",)


def _relative_workspace_path(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def _latest_workspace_file(patterns: tuple[str, ...], *, skip_validated_status: bool = False) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in WORKSPACE.glob(pattern) if path.is_file())
    if skip_validated_status:
        filtered: list[Path] = []
        for path in candidates:
            try:
                payload = _json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                filtered.append(path)
                continue
            if not isinstance(payload, dict) or payload.get("status") != "validated":
                filtered.append(path)
        candidates = filtered
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _latest_workspace_smoke_report() -> Path | None:
    return _latest_workspace_file(SMOKE_REPORT_PATTERNS)


def _latest_dev_server_status_report() -> Path | None:
    return _latest_workspace_file(DEV_SERVER_STATUS_PATTERNS, skip_validated_status=True)


def _smoke_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        results = payload.get("results", [])
    else:
        results = payload
    if not isinstance(results, list):
        return []
    return [item for item in results if isinstance(item, dict)]


def _smoke_summary(payload: Any, results: list[dict[str, Any]]) -> dict[str, int]:
    if isinstance(payload, dict) and isinstance(payload.get("summary"), dict):
        summary = payload["summary"]
        return {
            "total": int(summary.get("total", len(results)) or 0),
            "completed": int(summary.get("completed", len(results)) or 0),
            "passed": int(summary.get("passed", sum(1 for item in results if item.get("ok"))) or 0),
            "failed": int(summary.get("failed", sum(1 for item in results if not item.get("ok"))) or 0),
            "remaining": int(summary.get("remaining", 0) or 0),
        }

    passed = sum(1 for item in results if item.get("ok"))
    failed = len(results) - passed
    return {
        "total": len(results),
        "completed": len(results),
        "passed": passed,
        "failed": failed,
        "remaining": 0,
    }


def _workspace_smoke_overview() -> dict[str, Any]:
    report_path = _latest_workspace_smoke_report()
    if report_path is None:
        return {
            "available": False,
            "status": "missing",
            "path": None,
            "schema_version": None,
            "generated_at": None,
            "duration_seconds": 0,
            "summary": {"total": 0, "completed": 0, "passed": 0, "failed": 0, "remaining": 0},
            "slowest_checks": [],
        }

    try:
        payload = _json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {
            "available": False,
            "status": "corrupt",
            "path": _relative_workspace_path(report_path),
            "schema_version": None,
            "generated_at": None,
            "duration_seconds": 0,
            "summary": {"total": 0, "completed": 0, "passed": 0, "failed": 0, "remaining": 0},
            "slowest_checks": [],
        }

    results = _smoke_results(payload)
    slowest = sorted(results, key=lambda item: float(item.get("elapsed_seconds") or 0), reverse=True)[:5]
    return {
        "available": True,
        "status": payload.get("status", "complete") if isinstance(payload, dict) else "complete",
        "path": _relative_workspace_path(report_path),
        "schema_version": payload.get("schema_version") if isinstance(payload, dict) else "legacy",
        "generated_at": payload.get("generated_at") if isinstance(payload, dict) else None,
        "duration_seconds": round(float(payload.get("duration_seconds", 0) or 0), 3)
        if isinstance(payload, dict)
        else 0,
        "summary": _smoke_summary(payload, results),
        "slowest_checks": [
            {
                "scope": str(item.get("scope", "")),
                "name": str(item.get("name", "")),
                "ok": bool(item.get("ok")),
                "returncode": int(item.get("returncode", 0) or 0),
                "elapsed_seconds": round(float(item.get("elapsed_seconds") or 0), 3),
            }
            for item in slowest
        ],
    }


def _empty_dev_server_status(status: str, path: str | None = None) -> dict[str, Any]:
    return {
        "available": False,
        "status": status,
        "path": path,
        "generated_at": None,
        "summary": {"total": 0, "ready": 0, "unready": 0},
        "targets": [],
        "unready_targets": [],
    }


def _dev_server_status_overview() -> dict[str, Any]:
    report_path = _latest_dev_server_status_report()
    if report_path is None:
        return _empty_dev_server_status("missing")

    try:
        payload = _json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return _empty_dev_server_status("corrupt", _relative_workspace_path(report_path))

    if not isinstance(payload, dict):
        return _empty_dev_server_status("corrupt", _relative_workspace_path(report_path))

    raw_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    raw_targets = payload.get("targets") if isinstance(payload.get("targets"), list) else []
    targets = []
    for item in raw_targets:
        if not isinstance(item, dict):
            continue
        target = {
            "id": str(item.get("id", "")),
            "label": str(item.get("label", item.get("id", ""))),
            "project": str(item.get("project", "")),
            "kind": str(item.get("kind", "")),
            "ok": bool(item.get("ok")),
            "status_code": item.get("status_code"),
            "url": str(item.get("url", "")),
            "error": str(item.get("error", "")) if item.get("error") else None,
        }
        targets.append(target)

    ready = int(raw_summary.get("ready", sum(1 for item in targets if item["ok"])) or 0)
    total = int(raw_summary.get("total", len(targets)) or 0)
    unready = int(raw_summary.get("unready", max(total - ready, 0)) or 0)
    return {
        "available": True,
        "status": str(payload.get("status", "unknown")),
        "path": _relative_workspace_path(report_path),
        "generated_at": payload.get("generated_at"),
        "summary": {"total": total, "ready": ready, "unready": unready},
        "targets": targets,
        "unready_targets": [target for target in targets if not target["ok"]][:5],
    }


@router.get("/api/getdaytrends")
async def getdaytrends():
    """GetDayTrends 실행 현황."""
    recent_runs = await _sqlite_read(
        GDT_DB,
        """SELECT id, country, started_at, finished_at, trends_collected,
                  tweets_generated
           FROM runs ORDER BY id DESC LIMIT 30""",
    )
    daily_runs = await _sqlite_read(
        GDT_DB,
        """SELECT DATE(started_at) as date, COUNT(*) as count,
                  SUM(trends_collected) as trends, SUM(tweets_generated) as tweets
           FROM runs
           WHERE started_at >= date('now', '-14 days')
           GROUP BY DATE(started_at)
           ORDER BY date""",
    )
    top_trends = await _sqlite_read(
        GDT_DB,
        """SELECT keyword, viral_potential, volume_raw
           FROM trends
           ORDER BY id DESC LIMIT 10""",
    )
    total_runs = await _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM runs") or 0
    total_trends = await _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM trends") or 0
    total_tweets = await _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM tweets") or 0
    return {
        "total_runs": total_runs,
        "total_trends": total_trends,
        "total_tweets": total_tweets,
        "recent_runs": recent_runs,
        "daily_runs": daily_runs,
        "top_trends": top_trends,
    }


@router.get("/api/ab_performance")
async def ab_performance():
    """A/B 패턴 성과."""
    hook_stats = await _sqlite_read(
        GDT_DB,
        """SELECT hook_pattern, COUNT(*) as count,
                  AVG(engagement_rate) as avg_eng,
                  AVG(impressions) as avg_imp
           FROM tweet_performance
           WHERE hook_pattern != '' AND collected_at >= datetime('now', '-30 days')
           GROUP BY hook_pattern
           ORDER BY avg_eng DESC""",
    )
    kick_stats = await _sqlite_read(
        GDT_DB,
        """SELECT kick_pattern, COUNT(*) as count,
                  AVG(engagement_rate) as avg_eng
           FROM tweet_performance
           WHERE kick_pattern != '' AND collected_at >= datetime('now', '-30 days')
           GROUP BY kick_pattern
           ORDER BY avg_eng DESC""",
    )
    angle_stats = await _sqlite_read(
        GDT_DB,
        """SELECT angle_type, COUNT(*) as count,
                  AVG(engagement_rate) as avg_eng
           FROM tweet_performance
           WHERE angle_type != '' AND collected_at >= datetime('now', '-30 days')
           GROUP BY angle_type
           ORDER BY avg_eng DESC""",
    )
    total_samples = await _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM tweet_performance") or 0
    feedback_stats = await _sqlite_read(
        GDT_DB,
        """SELECT
             COUNT(*) as total,
             AVG(qa_score) as avg_qa,
             SUM(CASE WHEN regenerated = 1 THEN 1 ELSE 0 END) as regenerated_count
           FROM content_feedback
           WHERE created_at >= datetime('now', '-30 days')""",
    )
    feedback_trend = await _sqlite_read(
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
async def qa_reports(limit: int = 50):
    """QA 리포트 상세."""
    rows = await _sqlite_read(
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

    total = await _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM qa_reports") or 0
    passed = await _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM qa_reports WHERE passed = 1") or 0
    avg_score = await _sqlite_scalar(GDT_DB, "SELECT AVG(total_score) FROM qa_reports") or 0
    platform_stats = await _sqlite_read(
        GDT_DB,
        """SELECT d.platform,
                  COUNT(*) as total,
                  SUM(CASE WHEN q.passed = 1 THEN 1 ELSE 0 END) as passed,
                  ROUND(AVG(q.total_score), 1) as avg_score
           FROM qa_reports q
           LEFT JOIN draft_bundles d ON q.draft_id = d.draft_id
           GROUP BY d.platform""",
    )
    daily_trend = await _sqlite_read(
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
async def quality_overview():
    """품질 종합 대시보드."""
    qa_grade_dist = await _sqlite_read(
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
    blocking_reasons_raw = await _sqlite_read(
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

    lifecycle_dist = await _sqlite_read(
        GDT_DB,
        """SELECT lifecycle_status, review_status, COUNT(*) as count
           FROM draft_bundles
           GROUP BY lifecycle_status, review_status
           ORDER BY count DESC""",
    )
    daily_production = await _sqlite_read(
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
    confidence_dist = await _sqlite_read(
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
        "workspace_smoke": _workspace_smoke_overview(),
        "dev_server_status": _dev_server_status_overview(),
    }

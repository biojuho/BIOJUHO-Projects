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
CREDENTIAL_BOUNDARY_PATTERNS = ("docs/reports/2026-06/EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_*.json",)
CREDENTIAL_LIVE_VERIFY_PATTERNS = ("docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_*.json",)
CREDENTIAL_OPERATOR_CHECKLIST_PATTERNS = ("docs/reports/2026-06/EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_*.json",)


def _relative_workspace_path(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


_MISSING = object()


def _present_value(mapping: dict[str, Any], key: str, default: Any = None) -> Any:
    value = mapping.get(key, _MISSING)
    return default if value is _MISSING or value is None else value


def _text_field(mapping: dict[str, Any], key: str, default: str = "") -> str:
    return str(_present_value(mapping, key, default))


def _int_field(mapping: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(_present_value(mapping, key, default))
    except (TypeError, ValueError):
        return default


def _bool_field(mapping: dict[str, Any], key: str, default: bool = False) -> bool:
    return bool(_present_value(mapping, key, default))


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


def _latest_mcp_trace_report() -> tuple[Path | None, dict[str, Any] | None]:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for pattern in SMOKE_REPORT_PATTERNS:
        for path in WORKSPACE.glob(pattern):
            if not path.is_file():
                continue
            try:
                payload = _json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if not isinstance(payload, dict):
                continue
            trace = payload.get("mcp_trace")
            if isinstance(trace, dict) and trace.get("enabled"):
                candidates.append((path, payload))
    if not candidates:
        return None, None
    return max(candidates, key=lambda item: item[0].stat().st_mtime)


def _latest_dev_server_status_report() -> Path | None:
    return _latest_workspace_file(DEV_SERVER_STATUS_PATTERNS, skip_validated_status=True)


def _latest_credential_boundary_report() -> Path | None:
    return _latest_workspace_file(CREDENTIAL_BOUNDARY_PATTERNS)


def _latest_credential_live_verify_report() -> Path | None:
    return _latest_workspace_file(CREDENTIAL_LIVE_VERIFY_PATTERNS)


def _latest_credential_operator_checklist_report() -> Path | None:
    return _latest_workspace_file(CREDENTIAL_OPERATOR_CHECKLIST_PATTERNS)


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


def _smoke_scope_summary(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("scope_summary"), dict):
        return payload["scope_summary"]
    return {}


def _smoke_mcp_trace(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("mcp_trace"), dict):
        return payload["mcp_trace"]
    return {
        "enabled": False,
        "completed": 0,
        "passed": 0,
        "failed": 0,
        "elapsed_seconds": 0,
        "checked_units": [],
        "command_kinds": {},
        "checks": [],
    }


def _workspace_smoke_overview() -> dict[str, Any]:
    report_path = _latest_workspace_smoke_report()
    if report_path is None:
        return {
            "available": False,
            "status": "missing",
            "path": None,
            "mcp_trace_path": None,
            "schema_version": None,
            "generated_at": None,
            "duration_seconds": 0,
            "summary": {"total": 0, "completed": 0, "passed": 0, "failed": 0, "remaining": 0},
            "scope_summary": {},
            "mcp_trace": _smoke_mcp_trace(None),
            "slowest_checks": [],
        }

    try:
        payload = _json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {
            "available": False,
            "status": "corrupt",
            "path": _relative_workspace_path(report_path),
            "mcp_trace_path": None,
            "schema_version": None,
            "generated_at": None,
            "duration_seconds": 0,
            "summary": {"total": 0, "completed": 0, "passed": 0, "failed": 0, "remaining": 0},
            "scope_summary": {},
            "mcp_trace": _smoke_mcp_trace(None),
            "slowest_checks": [],
        }

    results = _smoke_results(payload)
    slowest = sorted(results, key=lambda item: float(item.get("elapsed_seconds") or 0), reverse=True)[:5]
    mcp_trace_path = report_path
    mcp_trace_payload = payload
    if not _smoke_mcp_trace(payload).get("enabled"):
        fallback_path, fallback_payload = _latest_mcp_trace_report()
        if fallback_path is not None and fallback_payload is not None:
            mcp_trace_path = fallback_path
            mcp_trace_payload = fallback_payload
    return {
        "available": True,
        "status": payload.get("status", "complete") if isinstance(payload, dict) else "complete",
        "path": _relative_workspace_path(report_path),
        "mcp_trace_path": _relative_workspace_path(mcp_trace_path),
        "schema_version": payload.get("schema_version") if isinstance(payload, dict) else "legacy",
        "generated_at": payload.get("generated_at") if isinstance(payload, dict) else None,
        "duration_seconds": round(float(payload.get("duration_seconds", 0) or 0), 3)
        if isinstance(payload, dict)
        else 0,
        "summary": _smoke_summary(payload, results),
        "scope_summary": _smoke_scope_summary(payload),
        "mcp_trace": _smoke_mcp_trace(mcp_trace_payload),
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


def _empty_credential_boundaries(status: str, path: str | None = None) -> dict[str, Any]:
    return {
        "available": False,
        "status": status,
        "path": path,
        "generated_at": None,
        "registry_generated_at": None,
        "boundary_count": 0,
        "missing_required_env_count": 0,
        "missing_required_env": [],
        "status_counts": {},
        "boundaries": [],
        "next_unblock": None,
        "live_plan": [],
        "operator_checklist": _empty_credential_operator_checklist(status),
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


def _credential_next_unblock_overview() -> dict[str, Any] | None:
    report_path = _latest_credential_live_verify_report()
    if report_path is None:
        return None

    try:
        payload = _json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    raw_next = summary.get("next_unblock")
    if not isinstance(raw_next, dict):
        return None

    boundary_id = _text_field(raw_next, "boundary_id")
    raw_boundaries = payload.get("boundaries") if isinstance(payload.get("boundaries"), list) else []
    boundaries_by_id = {
        str(item.get("id", "")): item for item in raw_boundaries if isinstance(item, dict)
    }
    boundary = boundaries_by_id.get(boundary_id, {})
    raw_env_names = raw_next.get("env_names") if isinstance(raw_next.get("env_names"), list) else []
    raw_commands = (
        raw_next.get("verification_commands")
        if isinstance(raw_next.get("verification_commands"), list)
        else []
    )

    return {
        "boundary_id": boundary_id,
        "title": _text_field(boundary, "title", boundary_id),
        "plan_rank": _int_field(raw_next, "plan_rank"),
        "live_status": _text_field(raw_next, "live_status"),
        "env_names": [str(item) for item in raw_env_names][:6],
        "verification_command_count": len(raw_commands),
        "first_verification_command": str(raw_commands[0]) if raw_commands else "",
        "path": _relative_workspace_path(report_path),
    }


def _credential_live_plan_overview() -> list[dict[str, Any]]:
    report_path = _latest_credential_live_verify_report()
    if report_path is None:
        return []

    try:
        payload = _json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []

    if not isinstance(payload, dict):
        return []

    raw_boundaries = payload.get("boundaries") if isinstance(payload.get("boundaries"), list) else []
    plan_items: list[dict[str, Any]] = []
    for item in raw_boundaries:
        if not isinstance(item, dict):
            continue
        plan_rank = _int_field(item, "plan_rank")
        raw_commands = item.get("verification_commands") if isinstance(item.get("verification_commands"), list) else []
        missing_env = item.get("missing_required_env") if isinstance(item.get("missing_required_env"), list) else []
        plan_items.append(
            {
                "id": _text_field(item, "id"),
                "title": _text_field(item, "title", _text_field(item, "id")),
                "plan_rank": plan_rank,
                "live_status": _text_field(item, "live_status"),
                "registry_status": _text_field(item, "registry_status"),
                "verification_command_count": len(raw_commands),
                "missing_required_env_count": len(missing_env),
            }
        )

    plan_items.sort(key=lambda item: (item["plan_rank"] == 0, item["plan_rank"], item["title"].lower()))
    return plan_items[:6]


def _empty_credential_operator_checklist(status: str, path: str | None = None) -> dict[str, Any]:
    return {
        "available": False,
        "status": status,
        "path": path,
        "generated_at": None,
        "summary": {
            "item_count": 0,
            "ready_to_execute": 0,
            "blocked": 0,
            "next_boundary_id": None,
        },
        "items": [],
    }


def _credential_operator_checklist_overview() -> dict[str, Any]:
    report_path = _latest_credential_operator_checklist_report()
    if report_path is None:
        return _empty_credential_operator_checklist("missing")

    try:
        payload = _json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return _empty_credential_operator_checklist("corrupt", _relative_workspace_path(report_path))

    if not isinstance(payload, dict):
        return _empty_credential_operator_checklist("corrupt", _relative_workspace_path(report_path))

    raw_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    items: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        raw_steps = raw_item.get("checklist") if isinstance(raw_item.get("checklist"), list) else []
        raw_commands = raw_item.get("verify_after_unblock") if isinstance(raw_item.get("verify_after_unblock"), list) else []
        raw_env_names = raw_item.get("env_names") if isinstance(raw_item.get("env_names"), list) else []
        rank = _int_field(raw_item, "rank")
        steps = [
            {
                "id": _text_field(step, "id"),
                "label": _text_field(step, "label"),
                "state": _text_field(step, "state"),
                "detail": _text_field(step, "detail"),
            }
            for step in raw_steps
            if isinstance(step, dict)
        ]
        items.append(
            {
                "rank": rank,
                "boundary_id": _text_field(raw_item, "boundary_id"),
                "title": _text_field(raw_item, "title", _text_field(raw_item, "boundary_id")),
                "live_status": _text_field(raw_item, "live_status"),
                "ready_to_execute": bool(raw_item.get("ready_to_execute", False)),
                "blocked_reason": _text_field(raw_item, "blocked_reason"),
                "env_names": [str(item) for item in raw_env_names][:6],
                "checklist": steps[:4],
                "verification_command_count": len(raw_commands),
                "first_verification_command": str(raw_commands[0]) if raw_commands else "",
            }
        )

    items.sort(key=lambda item: (item["rank"] == 0, item["rank"], item["title"].lower()))
    return {
        "available": True,
        "status": str(payload.get("status", "unknown")),
        "path": _relative_workspace_path(report_path),
        "generated_at": payload.get("generated_at"),
        "summary": {
            "item_count": _int_field(raw_summary, "item_count", len(items)),
            "ready_to_execute": _int_field(raw_summary, "ready_to_execute"),
            "blocked": _int_field(raw_summary, "blocked"),
            "next_boundary_id": raw_summary.get("next_boundary_id"),
        },
        "items": items[:6],
    }


def _credential_boundary_overview() -> dict[str, Any]:
    report_path = _latest_credential_boundary_report()
    if report_path is None:
        return _empty_credential_boundaries("missing")

    try:
        payload = _json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return _empty_credential_boundaries("corrupt", _relative_workspace_path(report_path))

    if not isinstance(payload, dict):
        return _empty_credential_boundaries("corrupt", _relative_workspace_path(report_path))

    raw_boundaries = payload.get("boundaries") if isinstance(payload.get("boundaries"), list) else []
    boundaries = []
    for item in raw_boundaries:
        if not isinstance(item, dict):
            continue
        missing_env = item.get("missing_required_env") if isinstance(item.get("missing_required_env"), list) else []
        boundaries.append(
            {
                "id": _text_field(item, "id"),
                "title": _text_field(item, "title", _text_field(item, "id")),
                "status": _text_field(item, "status"),
                "owner": _text_field(item, "owner"),
                "missing_required_env_count": len(missing_env),
                "optional_env_available": _bool_field(item, "optional_env_available"),
                "evidence_count": _int_field(item, "evidence_count"),
            }
        )
    boundaries.sort(
        key=lambda item: (
            item["missing_required_env_count"] == 0,
            item["status"],
            item["title"].lower(),
        )
    )
    missing_required_env = (
        payload.get("missing_required_env") if isinstance(payload.get("missing_required_env"), list) else []
    )
    return {
        "available": True,
        "status": str(payload.get("status", "unknown")),
        "path": _relative_workspace_path(report_path),
        "generated_at": payload.get("generated_at"),
        "registry_generated_at": payload.get("registry_generated_at"),
        "boundary_count": _int_field(payload, "boundary_count", len(boundaries)),
        "missing_required_env_count": _int_field(payload, "missing_required_env_count"),
        "missing_required_env": [str(item) for item in missing_required_env][:8],
        "status_counts": payload.get("status_counts") if isinstance(payload.get("status_counts"), dict) else {},
        "boundaries": boundaries[:6],
        "next_unblock": _credential_next_unblock_overview(),
        "live_plan": _credential_live_plan_overview(),
        "operator_checklist": _credential_operator_checklist_overview(),
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
        "credential_boundaries": _credential_boundary_overview(),
    }

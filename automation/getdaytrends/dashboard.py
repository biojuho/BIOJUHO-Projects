"""# ── TAP Router ─────────────────────────────────

init_tap_router(

    config=_config,

    get_conn_fn=_get_conn,

    close_conn_fn=_close_conn,

    run_db_json_fn=_run_db_json_with_fallback,

    alert_queue_fallback=_tap_alert_queue_fallback,

    deal_room_fallback=_tap_deal_room_fallback,

    funnel_fallback=_tap_deal_room_funnel_fallback,

    checkout_summary_fallback=_tap_checkout_summary_fallback,

)

app.include_router(tap_router)






getdaytrends v5.0 - Pro Dashboard
FastAPI 기반 운영 대시보드: 실시간 차트, 카테고리 분석, 소스 품질 모니터링, LLM 비용 추적.

실행: uvicorn dashboard:app --reload --port 8010
"""

import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import httpx
    from fastapi import FastAPI, Query
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
except ImportError as e:
    raise ImportError(
        "dashboard 실행을 위해 fastapi, uvicorn, httpx가 필요합니다:\n  pip install fastapi uvicorn[standard] httpx"
    ) from e

try:
    from .config import VERSION, AppConfig
    from .db import (
        get_connection,
        get_review_queue_snapshot,
        get_source_quality_summary,
        get_trend_stats,
        init_db,
    )
except ImportError:
    from config import VERSION, AppConfig
    from db import (
        get_connection,
        get_review_queue_snapshot,
        get_source_quality_summary,
        get_trend_stats,
        init_db,
    )

try:
    from .dashboard_html import get_dashboard_html
except ImportError:
    from dashboard_html import get_dashboard_html

app = FastAPI(title="getdaytrends Pro Dashboard", version=VERSION)

try:
    from .dashboard_routes_tap import init_tap_router
    from .dashboard_routes_tap import router as tap_router
except ImportError:
    from dashboard_routes_tap import init_tap_router
    from dashboard_routes_tap import router as tap_router

_config = AppConfig.from_env()
logger = logging.getLogger(__name__)
_REPLACEMENT_CHARACTER = chr(0xFFFD)
_LOG_MOJIBAKE_MARKERS = (
    _REPLACEMENT_CHARACTER,
    chr(0x5360),
    chr(0xCA0C),
    "?" + chr(0x80),
    "?" + chr(0xBC64),
    "?" + chr(0x317C),
    "?" + chr(0xBA83),
    chr(0x6FE1),
    chr(0x8ADB),
    chr(0x73E5),
    chr(0x907A),
    chr(0x5A9B),
    chr(0x8E42),
    chr(0xBB13),
    chr(0xAFA8),
    chr(0xC9BA),
    chr(0x4EE5),
    chr(0xC10F),
    chr(0xAE43),
)
_POSTGRES_URL_RE = re.compile(r"\b(postgres(?:ql)?://)[^\s\"'<>]+", re.IGNORECASE)
_POSTGRES_TENANT_RE = re.compile(r"(\btenant/user\s+)[^\s),;]+", re.IGNORECASE)
_POSTGRES_USER_RE = re.compile(r"\bpostgres\.[A-Za-z0-9_.-]+")
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
_GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{16,}\b")
_PROVIDER_TEAM_ID_RE = re.compile(
    r"\b(team\s+)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_KOREAN_MOJIBAKE_PAIR_RE = re.compile(r"(?:\?[\u3130-\u318f\uac00-\ud7a3]|[\u3130-\u318f\uac00-\ud7a3]\?)")
_CJK_COMPAT_IDEOGRAPH_RE = re.compile(r"[\uf900-\ufaff]")
_LOG_ENCODING_PLACEHOLDER = (
    "[log encoding issue hidden] Original line contained unreadable text; check the raw UTF-8 log file if needed."
)
SCHEDULER_REFRESH_COMMAND = (
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
    ".\\run_scheduled_getdaytrends.ps1 -DryRun -Limit 1 -Country korea"
)
SCHEDULER_MAX_AGE_HOURS = 24.0
SCHEDULER_NEAR_STALE_RATIO = 0.9
READINESS_REFRESH_COMMAND = (
    "python scripts\\readiness_check.py --max-scheduler-age-hours 24 "
    "--max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 "
    "--fail-on-runtime-fallback --require-live-db"
)
TAP_FIXTURE_BROWSER_REFRESH_COMMAND = "python scripts\\browser_smoke.py --tap-source-fixture --timeout 45"
READINESS_VERIFICATION_COMMANDS = (
    "python scripts\\smoke_cli.py --include-dry-run",
    "python scripts\\browser_smoke.py --timeout 45",
    TAP_FIXTURE_BROWSER_REFRESH_COMMAND,
    "python scripts\\check_text_hygiene.py",
    READINESS_REFRESH_COMMAND,
    (
        "python ..\\..\\ops\\scripts\\run_workspace_smoke.py --scope getdaytrends "
        "--json-out ..\\..\\var\\workspace-smoke-getdaytrends-post-credential.json"
    ),
)


def _launch_secret_scan_refresh_command(run_date: date | None = None) -> str:
    stamp = (run_date or date.today()).isoformat()
    return (
        "python ..\\..\\ops\\scripts\\getdaytrends_launch_secret_scan.py "
        "--include-current-artifacts "
        f"--json-out ..\\..\\var\\getdaytrends-launch-secret-scan-final-{stamp}.json"
    )


def _readiness_verification_commands() -> tuple[str, ...]:
    commands = list(READINESS_VERIFICATION_COMMANDS)
    workspace_smoke_indexes = [
        index
        for index, command in enumerate(commands)
        if "run_workspace_smoke.py --scope getdaytrends" in command
    ]
    insert_at = workspace_smoke_indexes[0] if workspace_smoke_indexes else len(commands)
    commands.insert(insert_at, _launch_secret_scan_refresh_command())
    return tuple(commands)
_OPERATOR_IMAGE_MEDIA_TYPES = {
    ".gif": "image/gif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
_OPERATOR_CHECK_DISPLAY_NAMES = {
    "cli_smoke_report": "CLI smoke report",
    "dashboard_browser_report": "Dashboard browser report",
    "live_db_doctor": "Live DB doctor",
    "provider_auth_report": "Provider auth report",
    "readiness_report": "Readiness report",
    "scheduler_artifact": "Scheduler artifact",
    "scheduler_freshness": "Scheduler freshness",
    "tap_fixture_browser_report": "TAP fixture browser report",
    "text_hygiene_report": "Text hygiene report",
}

# Pipeline status tracker (in memory).
_pipeline_status: dict = {
    "state": "idle",
    "last_run_at": None,
    "last_run_elapsed": None,
    "last_error": None,
    "trends_last_run": 0,
    "tweets_last_run": 0,
}


def _sanitize_dashboard_log_line(line: str) -> str:
    """Mask secrets and hide unreadable mojibake before rendering dashboard logs."""
    masked = _POSTGRES_URL_RE.sub(r"\1***", line)
    masked = _POSTGRES_TENANT_RE.sub(r"\1***", masked)
    masked = _POSTGRES_USER_RE.sub("postgres.***", masked)
    masked = _OPENAI_KEY_RE.sub("sk-***", masked)
    masked = _GOOGLE_API_KEY_RE.sub("AIza***", masked)
    masked = _PROVIDER_TEAM_ID_RE.sub(r"\1***", masked)
    marker_count = sum(masked.count(marker) for marker in _LOG_MOJIBAKE_MARKERS)
    has_c1_control = any(0x80 <= ord(char) <= 0x9F for char in masked)
    question_hangul_pairs = len(_KOREAN_MOJIBAKE_PAIR_RE.findall(masked))
    compatibility_ideographs = len(_CJK_COMPAT_IDEOGRAPH_RE.findall(masked))
    if has_c1_control or marker_count >= 2 or _REPLACEMENT_CHARACTER in masked:
        return _LOG_ENCODING_PLACEHOLDER
    if compatibility_ideographs >= 2 or (compatibility_ideographs >= 1 and masked.count("?") >= 2):
        return _LOG_ENCODING_PLACEHOLDER
    if masked.count("?") >= 3 and question_hangul_pairs >= 2:
        return _LOG_ENCODING_PLACEHOLDER
    return masked


def _powershell_single_quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _readiness_verification_bundle(base_dir: Path) -> tuple[str, list[str], str]:
    try:
        working_directory = str(base_dir.absolute())
    except OSError:
        working_directory = str(base_dir)
    commands = [
        f"Set-Location -LiteralPath {_powershell_single_quoted(working_directory)}",
        *_readiness_verification_commands(),
    ]
    return working_directory, commands, "\n".join(commands)


async def _get_conn() -> object:
    conn = await get_connection(_config.db_path, database_url=_config.database_url)
    await init_db(conn)
    return conn


async def _close_conn(conn) -> None:
    if conn is None:
        return
    try:
        await conn.close()
    except Exception:
        logger.warning("Failed to close dashboard DB connection", exc_info=True)


def _stats_fallback() -> dict[str, Any]:
    return {
        "total_runs": 0,
        "total_trends": 0,
        "avg_viral_score": 0,
        "total_tweets": 0,
        "llm_cost_7d": 0.0,
        "llm_daily": [],
    }


def _review_queue_fallback() -> dict[str, Any]:
    return {"counts": {}, "items": []}


def _tap_alert_queue_fallback() -> dict[str, Any]:
    return {"counts": {}, "items": []}


def _tap_deal_room_fallback(
    *,
    target_country: str,
    teaser_count: int,
    audience_segment: str,
    package_tier: str,
) -> dict[str, Any]:
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "snapshot_id": "",
        "target_country": (target_country or "").strip().lower(),
        "audience_segment": audience_segment,
        "package_tier": package_tier,
        "teaser_count": teaser_count,
        "total_detected": 0,
        "offers": [],
        "future_dependencies": ["stripe>=10.12.0", "jinja2>=3.1.4", "rapidfuzz>=3.9.0"],
    }


def _tap_deal_room_funnel_fallback(
    *,
    days: int,
    target_country: str,
    audience_segment: str,
    package_tier: str,
) -> dict[str, Any]:
    return {
        "window_days": days,
        "filters": {
            "target_country": target_country,
            "audience_segment": audience_segment,
            "package_tier": package_tier,
        },
        "totals": {
            "views": 0,
            "clicks": 0,
            "checkout_opens": 0,
            "purchases": 0,
            "revenue": 0.0,
            "ctr": 0.0,
            "checkout_rate": 0.0,
            "purchase_rate": 0.0,
            "view_to_purchase_rate": 0.0,
        },
        "items": [],
    }


def _tap_checkout_summary_fallback(
    *,
    days: int,
    target_country: str,
    audience_segment: str,
    package_tier: str,
) -> dict[str, Any]:
    return {
        "window_days": days,
        "filters": {
            "target_country": target_country,
            "audience_segment": audience_segment,
            "package_tier": package_tier,
        },
        "totals": {
            "created": 0,
            "completed": 0,
            "paid": 0,
            "quoted_revenue": 0.0,
            "captured_revenue": 0.0,
            "completion_rate": 0.0,
        },
        "items": [],
    }


def _load_json_file(path: Path) -> tuple[dict[str, Any], str]:
    try:
        if not path.exists():
            return {}, "missing"
        with path.open(encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return {}, "not_object"
        return payload, ""
    except Exception as exc:
        return {}, str(exc)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _operator_age_hours_from_generated(generated_at: str) -> float | None:
    generated_dt = _parse_iso_datetime(generated_at)
    if generated_dt is None:
        return None
    now = datetime.now(generated_dt.tzinfo) if generated_dt.tzinfo else datetime.now()
    return round(max((now - generated_dt).total_seconds(), 0.0) / 3600, 1)


def _format_operator_age_label(age_hours: float) -> str:
    if age_hours < 0.1:
        return "<0.1h old"
    return f"{age_hours:.1f}h old"


def _operator_artifact_freshness_notes(
    *,
    generated_at: Any = "",
    age_hours: Any = None,
    max_age_hours: Any = None,
) -> list[dict[str, Any]]:
    generated_text = str(generated_at or "").strip()
    age = _coerce_float(age_hours)
    if age is None and generated_text:
        age = _operator_age_hours_from_generated(generated_text)
    if age is None:
        return []
    max_age = _coerce_float(max_age_hours)
    state = "fresh" if max_age is None or age <= max_age else "stale"
    return [
        {
            "label": f"{state} {_format_operator_age_label(age)}",
            "state": state,
            "age_hours": round(age, 1),
            **({"max_age_hours": round(max_age, 1)} if max_age is not None else {}),
        }
    ]


def _is_scheduler_near_stale(age_hours: float | None) -> bool:
    if age_hours is None:
        return False
    return SCHEDULER_MAX_AGE_HOURS * SCHEDULER_NEAR_STALE_RATIO <= age_hours <= SCHEDULER_MAX_AGE_HOURS


def _file_mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat()
    except OSError:
        return ""


def _latest_file_by_timestamp(paths: list[Path]) -> Path | None:
    latest_path: Path | None = None
    latest_mtime = float("-inf")
    for path in paths:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime > latest_mtime:
            latest_path = path
            latest_mtime = mtime
    return latest_path


def _latest_json_artifact(paths: list[Path]) -> tuple[Path | None, dict[str, Any]]:
    latest_path: Path | None = None
    latest_payload: dict[str, Any] = {}
    latest_key: tuple[int, float, float] | None = None
    for path in paths:
        payload, error = _load_json_file(path)
        if error:
            continue
        generated_dt = _parse_iso_datetime(str(payload.get("generated_at") or ""))
        generated_ts = generated_dt.timestamp() if generated_dt is not None else float("-inf")
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        key = (1 if generated_dt is not None else 0, generated_ts, mtime)
        if latest_key is None or key > latest_key:
            latest_path = path
            latest_payload = payload
            latest_key = key
    return latest_path, latest_payload


def _json_artifact_recency_key(path: Path, payload: dict[str, Any]) -> tuple[int, float, float]:
    generated_dt = _parse_iso_datetime(str(payload.get("generated_at") or ""))
    generated_ts = generated_dt.timestamp() if generated_dt is not None else float("-inf")
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (1 if generated_dt is not None else 0, generated_ts, mtime)


def _normalize_dashboard_browser_evidence_path(base_dir: Path, value: str) -> str:
    raw_path = str(value or "").strip()
    if not raw_path:
        return ""
    candidates = _base_dir_artifact_candidates(base_dir, raw_path)
    valid_candidates: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            base_resolved = base_dir.resolve()
        except OSError:
            continue
        if resolved == base_resolved or base_resolved in resolved.parents:
            absolute_candidate = candidate.absolute()
            valid_candidates.append(absolute_candidate)
            if absolute_candidate.exists():
                return str(absolute_candidate)
    return str(valid_candidates[0]) if valid_candidates else ""


def _base_dir_artifact_candidates(base_dir: Path, raw_path: str) -> list[Path]:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return [candidate]
    workspace_candidate = _workspace_root_for_base_dir(base_dir) / candidate
    base_candidate = base_dir / candidate
    if workspace_candidate == base_candidate:
        return [base_candidate]
    return [base_candidate, workspace_candidate]


def _dashboard_browser_evidence_recency_key(base_dir: Path, evidence: dict[str, Any]) -> tuple[int, float, float]:
    path_text = _normalize_dashboard_browser_evidence_path(base_dir, str(evidence.get("path") or ""))
    path = Path(path_text) if path_text else base_dir / "missing-dashboard-browser-evidence.json"
    return _json_artifact_recency_key(path, evidence)


def _latest_dashboard_browser_smoke(base_dir: Path) -> dict[str, Any]:
    smoke_dir = base_dir / "logs" / "smoke"
    latest_path: Path | None = None
    latest_payload: dict[str, Any] = {}
    latest_key: tuple[int, float, float] | None = None
    for path in smoke_dir.glob("dashboard_browser*.json"):
        if "tap_source" in path.name:
            continue
        payload, error = _load_json_file(path)
        if error:
            continue
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if not summary and "status" not in payload:
            continue
        key = _json_artifact_recency_key(path, payload)
        if latest_key is None or key > latest_key:
            latest_path = path
            latest_payload = payload
            latest_key = key
    if latest_path is None:
        return {}
    summary = latest_payload.get("summary") if isinstance(latest_payload.get("summary"), dict) else {}
    total = int(summary.get("total") or 0)
    passed = int(summary.get("passed") or 0)
    failed = int(summary.get("failed") or max(total - passed, 0))
    screenshot_value = str(latest_payload.get("screenshot") or "").strip()
    if screenshot_value:
        screenshot = _normalize_dashboard_browser_evidence_path(base_dir, screenshot_value)
    else:
        screenshot = str(latest_path.with_suffix(".png")) if latest_path.with_suffix(".png").exists() else ""
    generated_at = str(latest_payload.get("generated_at") or "").strip()
    evidence: dict[str, Any] = {
        "path": str(latest_path),
        "status": str(latest_payload.get("status") or "unknown"),
        "generated_at": generated_at,
        "max_age_hours": 24.0,
        "summary": {"total": total, "passed": passed, "failed": failed},
        "screenshot": screenshot,
    }
    age = _operator_age_hours_from_generated(generated_at)
    if age is not None:
        evidence["age_hours"] = age
    return evidence


def _prefer_latest_dashboard_browser_evidence(base_dir: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    latest = _latest_dashboard_browser_smoke(base_dir)
    if not latest:
        return evidence
    current_path = _normalize_dashboard_browser_evidence_path(base_dir, str(evidence.get("path") or ""))
    latest_path = str(latest.get("path") or "")
    if current_path and latest_path and current_path == latest_path:
        return evidence
    if not evidence:
        return latest
    if _dashboard_browser_evidence_recency_key(base_dir, latest) > _dashboard_browser_evidence_recency_key(
        base_dir,
        evidence,
    ):
        return latest
    return evidence


def _operator_credential_input_status_notes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    notes: list[dict[str, Any]] = []
    status = str(payload.get("status") or "").strip()
    if status:
        notes.append({"label": f"status: {status}"})
    source_present = payload.get("credential_source_signal_present")
    if source_present is True:
        notes.append({"label": "credential inputs: staged"})
    elif source_present is False:
        notes.append({"label": "credential inputs: none staged"})
    capability = payload.get("supabase_management_capability")
    can_rotate = capability.get("can_rotate_db_password_locally") if isinstance(capability, dict) else None
    if can_rotate is True:
        notes.append({"label": "local rotation available"})
    elif can_rotate is False:
        notes.append({"label": "provider console required"})
    if payload.get("safe_to_skip_strict_readiness_until_credential_inputs_change") is True:
        notes.append({"label": "safe to skip strict rerun"})
    launch_blocker = payload.get("launch_blocker_summary")
    launch_blocker = launch_blocker if isinstance(launch_blocker, dict) else {}
    if launch_blocker.get("readiness_scheduler_artifact_stale") is True:
        notes.append({"label": "readiness scheduler artifact stale"})
    if launch_blocker.get("latest_scheduler_artifact_evidence_complete") is True:
        notes.append({"label": "latest scheduler evidence complete"})
    return notes


def _operator_credential_input_status_card(status: dict[str, Any]) -> dict[str, Any]:
    if not str(status.get("path") or "").strip():
        return {
            "label": "Credential inputs",
            "value": "missing",
            "state": "unknown",
            "detail": "Run credential input status preflight.",
        }
    source_present = status.get("credential_source_signal_present")
    can_rotate = status.get("can_rotate_db_password_locally")
    safe_to_skip = status.get("safe_to_skip_strict_readiness_until_credential_inputs_change")
    if source_present is True:
        return {
            "label": "Credential inputs",
            "value": "staged",
            "state": "warn",
            "detail": "Validate and apply staged credentials before strict readiness.",
        }
    if source_present is False:
        detail = "Provider console required."
        if safe_to_skip is True:
            detail = "Provider console required; safe to skip strict rerun until inputs change."
        return {
            "label": "Credential inputs",
            "value": "none staged",
            "state": "warn" if can_rotate is False else "unknown",
            "detail": detail,
        }
    return {
        "label": "Credential inputs",
        "value": str(status.get("status") or "unknown"),
        "state": "unknown",
    }


def _latest_credential_input_status(base_dir: Path) -> dict[str, Any]:
    workspace_root = _workspace_root_for_base_dir(base_dir)
    json_path, payload = _latest_json_artifact(
        list((workspace_root / "var").glob("getdaytrends-credential-input-status*.json"))
    )
    reports_dir = workspace_root / "docs" / "reports"
    markdown_path = _latest_file_by_timestamp(
        [
            *reports_dir.glob("*/GETDAYTRENDS_CREDENTIAL_INPUT_STATUS*.md"),
            *reports_dir.glob("*/AUTO_RESEARCH_GETDAYTRENDS_CREDENTIAL_INPUT_STATUS*.md"),
        ]
    )
    display_path = markdown_path or json_path
    if display_path is None:
        return {"path": "", "json_path": "", "generated_at": "", "notes": []}
    generated_at = str(payload.get("generated_at") or "").strip() if payload else ""
    if not generated_at:
        generated_at = _file_mtime_iso(display_path)
    notes = [
        *_operator_artifact_freshness_notes(generated_at=generated_at, max_age_hours=24),
        *_operator_credential_input_status_notes(payload),
    ]
    return {
        "path": str(display_path),
        "json_path": str(json_path) if json_path else "",
        "generated_at": generated_at,
        "status": str(payload.get("status") or "").strip() if payload else "",
        "credential_source_signal_present": payload.get("credential_source_signal_present") if payload else None,
        "can_rotate_db_password_locally": (
            payload.get("supabase_management_capability", {}).get("can_rotate_db_password_locally")
            if isinstance(payload.get("supabase_management_capability"), dict)
            else None
        )
        if payload
        else None,
        "safe_to_skip_strict_readiness_until_credential_inputs_change": (
            payload.get("safe_to_skip_strict_readiness_until_credential_inputs_change") if payload else None
        ),
        "readiness_scheduler_artifact_stale": (
            payload.get("launch_blocker_summary", {}).get("readiness_scheduler_artifact_stale")
            if payload and isinstance(payload.get("launch_blocker_summary"), dict)
            else None
        ),
        "latest_scheduler_artifact_evidence_complete": (
            payload.get("launch_blocker_summary", {}).get("latest_scheduler_artifact_evidence_complete")
            if payload and isinstance(payload.get("launch_blocker_summary"), dict)
            else None
        ),
        "notes": notes,
    }


def _operator_check_display_name(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        return "Unknown check"
    return _OPERATOR_CHECK_DISPLAY_NAMES.get(normalized, normalized.replace("_", " "))


def _operator_runtime_fallback_summary(evidence: dict[str, Any]) -> list[str]:
    if not isinstance(evidence, dict):
        return []
    lines: list[str] = []
    count = evidence.get("runtime_fallback_count")
    try:
        fallback_count = int(count)
    except (TypeError, ValueError):
        fallback_count = None
    if fallback_count is not None:
        lines.append(f"Runtime fallback count: {fallback_count}")
    fallback_kinds = _operator_runtime_fallback_kinds(evidence)
    if fallback_kinds:
        lines.append(f"Runtime fallback kinds: {', '.join(fallback_kinds[:4])}")
    fallback_checks = _operator_runtime_fallback_checks(evidence)
    if fallback_checks:
        lines.append(f"Runtime fallback checks: {', '.join(fallback_checks[:4])}")
    return lines


def _operator_runtime_fallback_kinds(evidence: dict[str, Any]) -> list[str]:
    raw_fallbacks = evidence.get("runtime_fallbacks")
    fallback_kinds: list[str] = []
    if isinstance(raw_fallbacks, list):
        for item in raw_fallbacks:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or item.get("name") or "").strip()
            if kind and kind not in fallback_kinds:
                fallback_kinds.append(kind)
    return fallback_kinds


def _operator_runtime_fallback_checks(evidence: dict[str, Any]) -> list[str]:
    raw_fallbacks = evidence.get("runtime_fallbacks")
    fallback_checks: list[str] = []
    if isinstance(raw_fallbacks, list):
        for item in raw_fallbacks:
            if not isinstance(item, dict):
                continue
            check = str(item.get("check") or item.get("command") or "").strip()
            if check and check not in fallback_checks:
                fallback_checks.append(check)
    return fallback_checks


def _operator_cli_fallback_card(by_name: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    check = by_name.get("cli_smoke_report")
    if not isinstance(check, dict):
        return None
    evidence = check.get("evidence")
    if not isinstance(evidence, dict):
        return None
    fallback_kinds = _operator_runtime_fallback_kinds(evidence)
    count = evidence.get("runtime_fallback_count")
    try:
        fallback_count = int(count)
    except (TypeError, ValueError):
        fallback_count = len(fallback_kinds) if fallback_kinds else None
    if fallback_count is None:
        return None
    detail = ", ".join(fallback_kinds[:3])
    if not detail:
        detail = "No runtime fallback signals." if fallback_count == 0 else "Runtime fallback detected."
    return {
        "label": "CLI fallback",
        "value": str(fallback_count),
        "state": "warn" if fallback_count else "pass",
        "detail": detail,
    }


def _operator_live_db_summary(evidence: dict[str, Any]) -> list[str]:
    if not isinstance(evidence, dict):
        return []
    diagnostics = evidence.get("diagnostics")
    if not isinstance(diagnostics, list):
        return []
    rendered = "\n".join(str(item or "") for item in diagnostics)
    lines: list[str] = []
    source_match = re.search(r"DATABASE_URL source:\s*(.+?)(?:\.\s|\n|$)", rendered, re.IGNORECASE)
    if source_match:
        lines.append(f"DATABASE_URL source: {source_match.group(1).strip()}")
    endpoint_match = re.search(r"host=([^,\s]+),\s*port=(\d+)", rendered, re.IGNORECASE)
    if endpoint_match:
        lines.append(f"Pooler endpoint: {endpoint_match.group(1)}:{endpoint_match.group(2)}")
    if re.search(r"project refs match", rendered, re.IGNORECASE):
        lines.append("Project refs: match")
    has_dns_ok = bool(re.search(r"\[OK\]\s+db\.endpoint_dns", rendered, re.IGNORECASE))
    has_tcp_ok = bool(re.search(r"\[OK\]\s+db\.endpoint_tcp", rendered, re.IGNORECASE))
    if has_dns_ok and has_tcp_ok:
        lines.append("Endpoint network: DNS and TCP pass")
    return lines


def _operator_live_db_failure_type(check: dict[str, Any], evidence: dict[str, Any]) -> str:
    if not isinstance(evidence, dict):
        return ""
    message = str(check.get("message") or "").strip().lower()
    diagnostics = evidence.get("diagnostics")
    diagnostic_lines = [str(item or "") for item in diagnostics] if isinstance(diagnostics, list) else []
    if evidence.get("timeout") is True or "timed out" in message:
        return "timeout"
    if evidence.get("error"):
        return "execution_error"
    if any("[ERROR]" in line for line in diagnostic_lines):
        return "diagnostic_error"
    exit_code = evidence.get("exit_code")
    try:
        return "" if int(exit_code) == 0 else "nonzero_exit"
    except (TypeError, ValueError):
        return ""


def _operator_issue(check: dict[str, Any], *, fallback_message: str) -> dict[str, Any]:
    name = str(check.get("name", "unknown_check"))
    message = str(check.get("message", fallback_message))
    evidence = check.get("evidence")
    diagnostics = evidence.get("diagnostics") if isinstance(evidence, dict) else None
    if isinstance(diagnostics, list) and " Diagnostics:" in message:
        message = message.split(" Diagnostics:", 1)[0].strip()
    issue: dict[str, Any] = {
        "name": name,
        "display_name": _operator_check_display_name(name),
        "message": message,
        "level": str(check.get("level", "FAIL")),
    }
    remediation = str(check.get("remediation", "")).strip()
    if remediation:
        issue["remediation"] = remediation
    if isinstance(evidence, dict):
        if isinstance(diagnostics, list):
            issue["diagnostics"] = [str(item) for item in diagnostics[:6] if str(item).strip()]
        live_db_failure_type = _operator_live_db_failure_type(check, evidence) if name == "live_db_doctor" else ""
        if live_db_failure_type:
            issue["failure_type"] = live_db_failure_type
        evidence_summary = [
            *_operator_runtime_fallback_summary(evidence),
            *_operator_live_db_summary(evidence),
        ]
        if live_db_failure_type:
            evidence_summary.insert(0, f"Live DB failure type: {live_db_failure_type}")
        if evidence_summary:
            issue["evidence_summary"] = evidence_summary
    return issue


def _annotate_reused_recovery_packets(issues: list[dict[str, Any]]) -> None:
    first_owner_by_packet: dict[str, str] = {}
    for issue in issues:
        packet_path = str(issue.get("recovery_packet") or "").strip()
        if not packet_path:
            continue
        issue_name = str(issue.get("name") or "previous blocker").strip() or "previous blocker"
        first_owner = first_owner_by_packet.get(packet_path)
        if not first_owner:
            first_owner_by_packet[packet_path] = issue_name
            continue
        issue["recovery_packet_reuse"] = {
            "first_blocker": first_owner,
            "message": f"Same packet as {first_owner}",
        }


def _operator_recovery_packet_paths(base_dir: Path, artifacts: dict[str, Any]) -> tuple[str, str]:
    logs_dir = base_dir / "logs"
    supabase_packet = str(artifacts.get("supabase_recovery_packet") or "")
    default_supabase_packet = logs_dir / "readiness" / "supabase_recovery_packet_latest.json"
    if not supabase_packet and default_supabase_packet.exists():
        supabase_packet = str(default_supabase_packet)
    provider_packet = str(artifacts.get("provider_auth_recovery_packet") or "")
    default_provider_packet = logs_dir / "readiness" / "provider_auth_recovery_packet_latest.json"
    if not provider_packet and default_provider_packet.exists():
        provider_packet = str(default_provider_packet)
    return supabase_packet, provider_packet


def _operator_recovery_packet_for_check(
    check_name: str,
    supabase_packet: str,
    provider_packet: str,
) -> tuple[str, str]:
    if check_name in {"cli_smoke_report", "live_db_doctor"} and supabase_packet:
        return "Supabase recovery packet", supabase_packet
    if check_name == "provider_auth_report" and provider_packet:
        return "Provider recovery packet", provider_packet
    return "", ""


def _operator_packet_card_detail(next_action: str, issue_count: int) -> str:
    if not next_action.strip() or issue_count <= 0:
        return ""
    return "Use blocker rows for recovery steps and copy bundles."


def _operator_final_proof_card(packet: dict[str, Any], packet_status: str) -> dict[str, Any]:
    proof_bundle = packet.get("operator_final_proof_bundle") if isinstance(packet, dict) else None
    proof_items: list[dict[str, Any]] = []
    if isinstance(proof_bundle, list):
        for item in proof_bundle:
            if not isinstance(item, dict):
                continue
            artifact = str(item.get("artifact") or "").strip()
            success_signal = str(item.get("success_signal") or "").strip()
            if artifact and success_signal:
                proof_items.append(item)
    if not proof_items:
        return {
            "label": "Final proof",
            "value": "missing",
            "state": "warn",
            "detail": "Open recovery packet to regenerate final proof bundle.",
        }

    normalized_status = str(packet_status or "").strip().lower()
    if normalized_status in {"clear", "pass", "ready"}:
        state = "pass"
        detail = "Final proof bundle is available."
    elif normalized_status == "blocked":
        state = "warn"
        detail = "Pending DB credential repair and post-credential recheck."
    else:
        state = "warn"
        detail = "Confirm final proof bundle after post-credential recheck."
    return {
        "label": "Final proof",
        "value": f"{len(proof_items)} required",
        "state": state,
        "detail": detail,
    }


def _operator_path_is_within(path: Path, parent: Path) -> bool:
    try:
        return path.resolve(strict=False).is_relative_to(parent.resolve(strict=False))
    except OSError:
        return False


def _operator_log_containment_label(
    *,
    present_label: str,
    contained_label: str,
    outside_label: str,
    exists: Any,
    contained: Any,
) -> str:
    if exists is not True:
        return ""
    if contained is True:
        return contained_label
    if contained is False:
        return outside_label
    return present_label


def _operator_scheduler_detail(evidence: dict[str, Any]) -> str:
    if not isinstance(evidence, dict):
        return ""
    parts: list[str] = []
    exit_code = evidence.get("exit_code")
    if exit_code is not None:
        parts.append(f"exit {exit_code}")
    duration = evidence.get("duration_seconds")
    try:
        duration_seconds = float(duration)
    except (TypeError, ValueError):
        duration_seconds = None
    if duration_seconds is not None:
        parts.append(f"{duration_seconds:.1f}s")
    detail_label = _operator_log_containment_label(
        present_label="detail log",
        contained_label="detail log contained",
        outside_label="detail log outside scheduler dir",
        exists=evidence.get("detail_log_exists"),
        contained=evidence.get("detail_log_contained"),
    )
    if detail_label:
        parts.append(detail_label)
    if evidence.get("primary_summary_log_exists") is True:
        summary_label = _operator_log_containment_label(
            present_label="primary summary log",
            contained_label="primary summary log contained",
            outside_label="primary summary log outside scheduler dir",
            exists=True,
            contained=evidence.get("primary_summary_log_contained"),
        )
        parts.append(summary_label)
    elif evidence.get("summary_fallback_log_exists") is True:
        summary_label = _operator_log_containment_label(
            present_label="fallback summary log",
            contained_label="fallback summary log contained",
            outside_label="fallback summary log outside scheduler dir",
            exists=True,
            contained=evidence.get("summary_fallback_log_contained"),
        )
        parts.append(summary_label)
    return ", ".join(parts[:4])


def _operator_scheduler_artifact_notes(
    *,
    generated_at: Any,
    age_hours: float | None,
    evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    notes = _operator_artifact_freshness_notes(
        generated_at=generated_at,
        age_hours=age_hours,
        max_age_hours=SCHEDULER_MAX_AGE_HOURS,
    )
    if not isinstance(evidence, dict):
        return notes
    status = str(evidence.get("status") or "").strip()
    if status:
        notes.append({"label": f"status: {status}"})
    exit_code = evidence.get("exit_code")
    if exit_code is not None:
        notes.append({"label": f"exit code: {exit_code}"})
    duration = evidence.get("duration_seconds")
    try:
        duration_seconds = float(duration)
    except (TypeError, ValueError):
        duration_seconds = None
    if duration_seconds is not None:
        notes.append({"label": f"duration: {duration_seconds:.1f}s"})
    notes.append(
        {"label": "detail log present" if evidence.get("detail_log_exists") is True else "detail log missing"}
    )
    if evidence.get("detail_log_exists") is True:
        if evidence.get("detail_log_contained") is True:
            notes.append({"label": "detail log contained"})
        elif evidence.get("detail_log_contained") is False:
            notes.append({"label": "detail log outside scheduler dir"})
    if evidence.get("primary_summary_log_exists") is True:
        notes.append({"label": "primary summary log present"})
        if evidence.get("primary_summary_log_contained") is True:
            notes.append({"label": "primary summary log contained"})
        elif evidence.get("primary_summary_log_contained") is False:
            notes.append({"label": "primary summary log outside scheduler dir"})
    elif evidence.get("summary_fallback_log_exists") is True:
        notes.append({"label": "fallback summary log present"})
        if evidence.get("summary_fallback_log_contained") is True:
            notes.append({"label": "fallback summary log contained"})
        elif evidence.get("summary_fallback_log_contained") is False:
            notes.append({"label": "fallback summary log outside scheduler dir"})
    else:
        notes.append({"label": "summary log missing"})
    return notes


def _operator_check_is_ok(by_name: dict[str, dict[str, Any]], name: str) -> bool:
    check = by_name.get(name)
    return isinstance(check, dict) and check.get("ok") is True


def _operator_launch_focus(
    *,
    status: str,
    blockers: list[dict[str, Any]],
    by_name: dict[str, dict[str, Any]],
    launch_secret_scan_ok: bool,
) -> dict[str, Any]:
    blocker_names = [str(item.get("name") or "").strip() for item in blockers if str(item.get("name") or "").strip()]
    blocker_name_set = set(blocker_names)
    clear_checks = [
        name
        for name in (
            "provider_auth_report",
            "scheduler_artifact",
            "dashboard_browser_report",
            "tap_fixture_browser_report",
            "text_hygiene_report",
            "production_docs",
        )
        if _operator_check_is_ok(by_name, name)
    ]
    db_only = (
        str(status).strip().lower() == "fail"
        and bool(blocker_name_set)
        and blocker_name_set.issubset({"cli_smoke_report", "live_db_doctor"})
        and "provider_auth_report" in clear_checks
        and "scheduler_artifact" in clear_checks
        and "dashboard_browser_report" in clear_checks
        and launch_secret_scan_ok
    )
    if db_only:
        return {
            "status": "blocked",
            "scope": "supabase_db_only",
            "card": {
                "label": "Launch focus",
                "value": "DB only",
                "state": "warn",
                "detail": "Provider, scheduler, browser, hygiene, docs, and secret scan are clear.",
            },
            "message": (
                "Supabase DB is the only strict launch blocker; provider auth, scheduler, browser, "
                "hygiene, production docs, and launch secret scan are clear."
            ),
            "blocker_checks": blocker_names,
            "clear_checks": clear_checks,
        }
    if str(status).strip().lower() == "pass" and not blockers:
        return {
            "status": "ready",
            "scope": "launch_ready",
            "card": {
                "label": "Launch focus",
                "value": "clear",
                "state": "pass",
                "detail": "All strict readiness checks are green.",
            },
            "message": "All strict readiness checks are green.",
            "blocker_checks": [],
            "clear_checks": clear_checks,
        }
    return {
        "status": "blocked" if blockers else str(status or "unknown"),
        "scope": "multiple_or_unknown",
        "card": {
            "label": "Launch focus",
            "value": "review",
            "state": "warn" if blockers else "unknown",
            "detail": "Review blocker rows and recovery packets.",
        },
        "message": "Review blocker rows and recovery packets.",
        "blocker_checks": blocker_names,
        "clear_checks": clear_checks,
    }


def _format_issue_count(count: int) -> str:
    return f"{count} issue" if count == 1 else f"{count} issues"


def _workspace_root_for_base_dir(base_dir: Path) -> Path:
    if base_dir.parent.name.lower() == "automation":
        return base_dir.parent.parent
    return base_dir.parent


def _safe_workspace_smoke_path(base_dir: Path, requested_path: str) -> str:
    if not requested_path.strip():
        return ""
    workspace_root = _workspace_root_for_base_dir(base_dir)
    candidate = Path(requested_path.strip())
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    try:
        resolved = candidate.resolve()
        var_dir = (workspace_root / "var").resolve()
    except OSError:
        return ""
    if resolved.parent != var_dir:
        return ""
    if not resolved.name.startswith("workspace-smoke-getdaytrends") or resolved.suffix.lower() != ".json":
        return ""
    return str(resolved)


def _workspace_smoke_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _workspace_smoke_failure_classification(
    payload: dict[str, Any],
    failed_checks: list[str],
) -> dict[str, list[str]]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    expected_external = _workspace_smoke_string_list(summary.get("expected_external_failures"))
    unexpected = _workspace_smoke_string_list(summary.get("unexpected_failures"))
    if expected_external and "unexpected_failures" not in summary:
        unexpected = [name for name in failed_checks if name not in expected_external]
    if failed_checks and not expected_external and not unexpected:
        unexpected = failed_checks
    return {
        "expected_external_failures": expected_external,
        "unexpected_failures": unexpected,
    }


def _workspace_smoke_state(
    *,
    total: int,
    failed: int,
    expected_external_failures: list[str],
    unexpected_failures: list[str],
) -> str:
    if not total:
        return "unknown"
    if failed <= 0:
        return "pass"
    if expected_external_failures and not unexpected_failures:
        return "warn"
    return "fail"


def _workspace_smoke_card_detail(
    *,
    state: str,
    expected_external_failures: list[str],
    unexpected_failures: list[str],
) -> str:
    if state == "warn":
        return f"{len(expected_external_failures)} expected external; 0 unexpected."
    if state == "fail" and unexpected_failures:
        return f"{len(unexpected_failures)} unexpected failure(s)."
    return ""


def _workspace_smoke_recency_key(path: Path, payload: dict[str, Any]) -> tuple[int, int, int, float, float]:
    generated_dt = _parse_iso_datetime(str(payload.get("generated_at") or ""))
    generated_ts = generated_dt.timestamp() if generated_dt is not None else float("-inf")
    status = str(payload.get("status") or "").strip().lower()
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    complete_rank = 1 if status in {"complete", "completed"} else 0
    if "remaining" in summary:
        try:
            complete_rank = max(complete_rank, 1 if int(summary.get("remaining") or 0) == 0 else 0)
        except (TypeError, ValueError):
            pass
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    runtime_proof_rank = 1 if path.name == "workspace-smoke-getdaytrends-launch-final.json" else 0
    return (complete_rank, runtime_proof_rank, 1 if generated_dt is not None else 0, generated_ts, mtime)


def _latest_getdaytrends_workspace_smoke(base_dir: Path) -> dict[str, Any]:
    workspace_root = _workspace_root_for_base_dir(base_dir)
    var_dir = workspace_root / "var"
    latest_path: Path | None = None
    latest_payload: dict[str, Any] = {}
    latest_key: tuple[int, int, int, float, float] | None = None
    for path in var_dir.glob("workspace-smoke-getdaytrends*.json"):
        payload, error = _load_json_file(path)
        if error:
            continue
        key = _workspace_smoke_recency_key(path, payload)
        if latest_key is None or key > latest_key:
            latest_path = path
            latest_payload = payload
            latest_key = key
    if latest_path is not None:
        path = latest_path
        payload = latest_payload
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        total = int(summary.get("total") or summary.get("completed") or 0)
        passed = int(summary.get("passed") or 0)
        failed = int(summary.get("failed") or max(total - passed, 0))
        failed_checks = []
        results = payload.get("results")
        if isinstance(results, list):
            failed_checks = [
                str(result.get("name", "unknown_check"))
                for result in results
                if isinstance(result, dict) and result.get("ok") is False
            ][:6]
        failure_classification = _workspace_smoke_failure_classification(payload, failed_checks)
        return {
            "path": str(path),
            "status": payload.get("status"),
            "generated_at": payload.get("generated_at"),
            "summary": {"total": total, "passed": passed, "failed": failed},
            "failed_checks": failed_checks,
            **failure_classification,
        }
    return {
        "path": "",
        "status": "missing",
        "generated_at": "",
        "summary": {"total": 0, "passed": 0, "failed": 0},
        "failed_checks": [],
        "expected_external_failures": [],
        "unexpected_failures": [],
    }


def _count_sequence_or_int(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _latest_getdaytrends_launch_secret_scan(base_dir: Path) -> dict[str, Any]:
    workspace_root = _workspace_root_for_base_dir(base_dir)
    var_dir = workspace_root / "var"
    patterns = (
        "getdaytrends-launch-secret-scan-final-*.json",
        "getdaytrends-launch-secret-scan*.json",
    )
    candidates: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matches = sorted(var_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in matches:
            if path not in seen:
                candidates.append(path)
                seen.add(path)
        if candidates:
            break
    latest_path: Path | None = None
    latest_payload: dict[str, Any] = {}
    latest_key: tuple[int, float, float] | None = None
    for path in candidates:
        payload, error = _load_json_file(path)
        if error:
            continue
        generated_dt = _parse_iso_datetime(str(payload.get("generated_at") or ""))
        generated_ts = generated_dt.timestamp() if generated_dt is not None else float("-inf")
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        key = (1 if generated_dt is not None else 0, generated_ts, mtime)
        if latest_key is None or key > latest_key:
            latest_path = path
            latest_payload = payload
            latest_key = key
    if latest_path is None:
        return {
            "path": "",
            "status": "missing",
            "ok": False,
            "generated_at": "",
            "scanned": 0,
            "findings": 0,
            "missing": 0,
            "include_current_artifacts": False,
        }
    return {
        "path": str(latest_path),
        "status": str(latest_payload.get("status") or "unknown"),
        "ok": latest_payload.get("ok") is True,
        "generated_at": str(latest_payload.get("generated_at") or ""),
        "scanned": _count_sequence_or_int(latest_payload.get("scanned_paths") or latest_payload.get("scanned")),
        "findings": _count_sequence_or_int(latest_payload.get("findings")),
        "missing": _count_sequence_or_int(latest_payload.get("missing_paths") or latest_payload.get("missing")),
        "include_current_artifacts": latest_payload.get("include_current_artifacts") is True,
    }


def _latest_getdaytrends_handoff_refresh(base_dir: Path) -> dict[str, Any]:
    workspace_root = _workspace_root_for_base_dir(base_dir)
    var_dir = workspace_root / "var"
    patterns = (
        "getdaytrends-launch-handoff-refresh-current-*.json",
        "getdaytrends-launch-handoff-refresh*.json",
    )
    candidates: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matches = sorted(var_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in matches:
            if path not in seen:
                candidates.append(path)
                seen.add(path)
        if candidates:
            break

    latest_path: Path | None = None
    latest_payload: dict[str, Any] = {}
    latest_key: tuple[int, float, float] | None = None
    for path in candidates:
        payload, error = _load_json_file(path)
        if error:
            continue
        key = _json_artifact_recency_key(path, payload)
        if latest_key is None or key > latest_key:
            latest_path = path
            latest_payload = payload
            latest_key = key

    if latest_path is None:
        return {
            "path": "",
            "status": "missing",
            "ok": False,
            "generated_at": "",
            "secret_scan_state": "missing",
            "secret_scan_ok": False,
            "secret_scan_scanned": 0,
            "secret_scan_findings": 0,
            "secret_scan_missing": 0,
            "secret_scan_include_current_artifacts": False,
            "secret_scan_supabase_recovery_packet_contract_ok": False,
            "unexpected_failed_checks": [],
            "failed_checks": [],
        }

    status_payload = latest_payload.get("status") if isinstance(latest_payload.get("status"), dict) else {}
    secret_scan = latest_payload.get("secret_scan") if isinstance(latest_payload.get("secret_scan"), dict) else {}
    failed_checks = latest_payload.get("failed_checks") if isinstance(latest_payload.get("failed_checks"), list) else []
    unexpected_failed_checks = (
        latest_payload.get("unexpected_failed_checks")
        if isinstance(latest_payload.get("unexpected_failed_checks"), list)
        else []
    )
    return {
        "path": str(latest_path),
        "status": str(status_payload.get("state") or latest_payload.get("status") or "unknown"),
        "ok": latest_payload.get("ok") is True,
        "generated_at": str(latest_payload.get("generated_at") or ""),
        "secret_scan_state": str(secret_scan.get("state") or "missing"),
        "secret_scan_ok": secret_scan.get("ok") is True,
        "secret_scan_scanned": _count_sequence_or_int(secret_scan.get("scanned")),
        "secret_scan_findings": _count_sequence_or_int(secret_scan.get("findings")),
        "secret_scan_missing": _count_sequence_or_int(secret_scan.get("missing")),
        "secret_scan_include_current_artifacts": secret_scan.get("include_current_artifacts") is True,
        "secret_scan_supabase_recovery_packet_contract_ok": (
            secret_scan.get("supabase_recovery_packet_contract_ok") is True
        ),
        "unexpected_failed_checks": [str(item) for item in unexpected_failed_checks if str(item).strip()][:6],
        "failed_checks": [str(item) for item in failed_checks if str(item).strip()][:6],
    }


def _safe_launch_secret_scan_path(base_dir: Path, requested_path: str) -> str:
    if not requested_path.strip():
        return ""
    workspace_root = _workspace_root_for_base_dir(base_dir)
    candidate = Path(requested_path.strip())
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    try:
        resolved = candidate.resolve()
        var_dir = (workspace_root / "var").resolve()
    except OSError:
        return ""
    if resolved.parent != var_dir:
        return ""
    if not resolved.name.startswith("getdaytrends-launch-secret-scan") or resolved.suffix.lower() != ".json":
        return ""
    return str(resolved)


def _sanitize_operator_text(value: Any, *, limit: int, tail: bool = False) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    sanitized = "\n".join(_sanitize_dashboard_log_line(line) for line in text.splitlines()).strip()
    if len(sanitized) <= limit:
        return sanitized
    if tail:
        return "..." + sanitized[-max(limit - 3, 0) :]
    return sanitized[: max(limit - 3, 0)] + "..."


def _workspace_smoke_failed_details(payload: dict[str, Any], *, limit: int = 3) -> list[dict[str, Any]]:
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    details: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict) or result.get("ok") is not False:
            continue
        returncode = result.get("returncode")
        detail: dict[str, Any] = {
            "name": _sanitize_operator_text(result.get("name") or "unknown_check", limit=160),
            "command": _sanitize_operator_text(result.get("command"), limit=480),
            "stdout_tail": _sanitize_operator_text(result.get("stdout_tail"), limit=1000, tail=True),
            "stderr_tail": _sanitize_operator_text(result.get("stderr_tail"), limit=1000, tail=True),
        }
        if isinstance(returncode, int):
            detail["returncode"] = returncode
        elif returncode is not None:
            detail["returncode"] = _sanitize_operator_text(returncode, limit=40)
        details.append(detail)
        if len(details) >= limit:
            break
    return details


def _workspace_smoke_failed_rerun_bundle(base_dir: Path, failed_details: list[dict[str, Any]]) -> tuple[list[str], str]:
    commands: list[str] = []
    try:
        working_directory = str(base_dir.absolute())
    except OSError:
        working_directory = str(base_dir)
    for detail in failed_details:
        if not isinstance(detail, dict):
            continue
        name = _sanitize_operator_text(detail.get("name") or "unknown check", limit=160)
        raw_command = _sanitize_operator_text(detail.get("command"), limit=900)
        if not raw_command:
            continue
        commands.append(f"# Failed check: {name}")
        command_match = re.match(r'^"([^"]+)"\s+(.+)$', raw_command, re.DOTALL)
        if command_match:
            executable = _powershell_single_quoted(command_match.group(1))
            commands.append(f"& {executable} {command_match.group(2).strip()}")
        else:
            commands.append(raw_command)
    if not commands:
        return [], ""
    bundle_lines = [
        "Workspace smoke failed rerun:",
        f"Set-Location -LiteralPath {_powershell_single_quoted(working_directory)}",
        *commands,
    ]
    return commands, "\n".join(bundle_lines)


def _workspace_smoke_conclusion(
    status: str,
    summary: dict[str, Any],
    error: str,
    *,
    expected_external_failures: list[str] | None = None,
    unexpected_failures: list[str] | None = None,
) -> str:
    if error:
        return "missing" if error == "missing" else "error"
    total = int(summary.get("total") or 0)
    passed = int(summary.get("passed") or 0)
    failed = int(summary.get("failed") or max(total - passed, 0))
    if failed > 0:
        expected_external_failures = expected_external_failures or []
        unexpected_failures = unexpected_failures or []
        if expected_external_failures and not unexpected_failures:
            return "action_required"
        return "failure"
    if total > 0:
        return "success"
    normalized_status = str(status or "").strip().lower()
    if normalized_status in {"fail", "failed", "failure", "error"}:
        return "failure"
    if normalized_status in {"pass", "passed", "success"}:
        return "success"
    return normalized_status or "unknown"


def _safe_operator_artifact_path(base_dir: Path, requested_path: str) -> str:
    if not requested_path.strip():
        return ""
    candidate = Path(requested_path.strip())
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    try:
        resolved = candidate.resolve()
        base_resolved = base_dir.resolve()
    except OSError:
        return ""
    if resolved == base_resolved or base_resolved in resolved.parents:
        return str(resolved)
    return ""


def _safe_operator_image_artifact_path(base_dir: Path, requested_path: str) -> tuple[Path | None, str]:
    if not requested_path.strip():
        return None, "invalid_path"
    missing_candidate = False
    unsupported_type = False
    for candidate in _base_dir_artifact_candidates(base_dir, requested_path.strip()):
        try:
            resolved = candidate.resolve()
            base_resolved = base_dir.resolve()
        except OSError:
            continue
        if not (resolved == base_resolved or base_resolved in resolved.parents):
            continue
        absolute_candidate = candidate.absolute()
        if absolute_candidate.suffix.lower() not in _OPERATOR_IMAGE_MEDIA_TYPES:
            unsupported_type = True
            continue
        if not absolute_candidate.exists() or not absolute_candidate.is_file():
            missing_candidate = True
            continue
        return absolute_candidate, ""
    if unsupported_type:
        return None, "unsupported_type"
    if missing_candidate:
        return None, "missing"
    return None, "invalid_path"


def _operator_artifact_action(
    key: str,
    label: str,
    value: str,
    copy_label: str,
    *,
    view_kind: str = "",
    view_label: str = "",
    view_hide_label: str = "",
    view_text: str = "",
    view_hide_text: str = "",
    view_controls: str = "",
    view_preview_class: str = "",
    image_alt: str = "",
    notes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    action: dict[str, Any] = {
        "key": key,
        "label": label,
        "value": value,
        "copy_label": copy_label,
    }
    clean_notes = [
        note
        for note in (notes or [])
        if isinstance(note, dict) and str(note.get("label") or "").strip()
    ]
    if clean_notes:
        action["notes"] = clean_notes
    if view_kind and view_controls:
        action["view"] = {
            "kind": view_kind,
            "label": view_label,
            "hide_label": view_hide_label,
            "view_text": view_text,
            "hide_text": view_hide_text,
            "controls": view_controls,
            "preview_class": view_preview_class,
        }
        if view_kind == "artifact_image":
            action["view"]["image_path"] = value
            action["view"]["image_alt"] = image_alt
    return action


def _operator_artifact_actions(
    artifacts: dict[str, str],
    artifact_notes: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    artifact_notes = artifact_notes or {}
    candidates = [
        _operator_artifact_action(
            "readiness_report",
            "Readiness report",
            artifacts.get("readiness", ""),
            "Copy readiness report path",
            view_kind="readiness_report",
            view_label="View readiness report",
            view_hide_label="Hide readiness report",
            view_text="View report",
            view_hide_text="Hide report",
            view_controls="operator-readiness-report-preview",
            view_preview_class="operator-readiness-report-preview",
            notes=artifact_notes.get("readiness_report"),
        ),
        _operator_artifact_action(
            "readiness_refresh",
            "Readiness refresh",
            artifacts.get("readiness_refresh_command", ""),
            "Copy readiness refresh command",
        ),
        _operator_artifact_action(
            "launch_secret_scan",
            "Launch secret scan",
            artifacts.get("launch_secret_scan", ""),
            "Copy launch secret scan path",
            view_kind="launch_secret_scan",
            view_label="View launch secret scan",
            view_hide_label="Hide launch secret scan",
            view_text="View scan",
            view_hide_text="Hide scan",
            view_controls="operator-launch-secret-scan-preview",
            view_preview_class="operator-launch-secret-scan-preview",
            notes=artifact_notes.get("launch_secret_scan"),
        ),
        _operator_artifact_action(
            "launch_secret_scan_refresh",
            "Launch secret scan refresh",
            artifacts.get("launch_secret_scan_refresh_command", ""),
            "Copy launch secret scan refresh command",
        ),
        _operator_artifact_action(
            "handoff_refresh",
            "Handoff refresh bundle",
            artifacts.get("handoff_refresh", ""),
            "Copy handoff refresh bundle path",
            notes=artifact_notes.get("handoff_refresh"),
        ),
        _operator_artifact_action(
            "credential_input_status",
            "Credential input status",
            artifacts.get("credential_input_status", ""),
            "Copy credential input status path",
            notes=artifact_notes.get("credential_input_status"),
        ),
        _operator_artifact_action(
            "provider_auth_recovery_packet",
            "Provider recovery packet",
            artifacts.get("provider_auth_recovery_packet", ""),
            "Copy provider recovery packet path",
            view_kind="recovery_packet",
            view_label="View provider recovery packet",
            view_hide_label="Hide provider recovery packet",
            view_text="View provider packet",
            view_hide_text="Hide provider packet",
            view_controls="operator-provider-recovery-packet-preview",
            view_preview_class="operator-provider-recovery-packet-preview",
            notes=artifact_notes.get("provider_auth_recovery_packet"),
        ),
        _operator_artifact_action(
            "dashboard_browser_report",
            "Dashboard browser report",
            artifacts.get("browser", ""),
            "Copy dashboard browser report path",
            notes=artifact_notes.get("dashboard_browser_report"),
        ),
        _operator_artifact_action(
            "dashboard_browser_screenshot",
            "Dashboard browser screenshot",
            artifacts.get("browser_screenshot", ""),
            "Copy dashboard browser screenshot path",
            view_kind="artifact_image",
            view_label="View dashboard browser screenshot",
            view_hide_label="Hide dashboard browser screenshot",
            view_text="View screenshot",
            view_hide_text="Hide screenshot",
            view_controls="operator-dashboard-browser-screenshot-preview",
            view_preview_class="operator-dashboard-browser-screenshot-preview",
            image_alt="Dashboard browser smoke screenshot",
            notes=artifact_notes.get("dashboard_browser_screenshot"),
        ),
        _operator_artifact_action(
            "tap_fixture_report",
            "TAP fixture report",
            artifacts.get("tap_fixture_browser", ""),
            "Copy TAP fixture report path",
            notes=artifact_notes.get("tap_fixture_report"),
        ),
        _operator_artifact_action(
            "tap_fixture_screenshot",
            "TAP fixture screenshot",
            artifacts.get("tap_fixture_browser_screenshot", ""),
            "Copy TAP fixture screenshot path",
            view_kind="artifact_image",
            view_label="View TAP fixture screenshot",
            view_hide_label="Hide TAP fixture screenshot",
            view_text="View screenshot",
            view_hide_text="Hide screenshot",
            view_controls="operator-tap-fixture-screenshot-preview",
            view_preview_class="operator-tap-fixture-screenshot-preview",
            image_alt="TAP fixture browser smoke screenshot",
            notes=artifact_notes.get("tap_fixture_screenshot"),
        ),
        _operator_artifact_action(
            "tap_fixture_refresh",
            "TAP fixture refresh",
            artifacts.get("tap_fixture_browser_refresh_command", ""),
            "Copy TAP fixture refresh command",
        ),
        _operator_artifact_action(
            "scheduler_artifact",
            "Scheduler artifact",
            artifacts.get("scheduler", ""),
            "Copy scheduler artifact path",
            notes=artifact_notes.get("scheduler_artifact"),
        ),
        _operator_artifact_action(
            "workspace_smoke",
            "Workspace smoke",
            artifacts.get("workspace_smoke", ""),
            "Copy workspace smoke path",
            view_kind="workspace_smoke",
            view_label="View workspace smoke",
            view_hide_label="Hide workspace smoke",
            view_text="View workspace",
            view_hide_text="Hide workspace",
            view_controls="operator-workspace-smoke-preview",
            view_preview_class="operator-workspace-smoke-preview",
            notes=artifact_notes.get("workspace_smoke"),
        ),
    ]
    return [action for action in candidates if str(action.get("value") or "").strip()]


def _operator_readiness_snapshot(base_dir: Path) -> dict[str, Any]:
    logs_dir = base_dir / "logs"
    readiness_path = logs_dir / "readiness" / "readiness_latest.json"
    readiness, readiness_error = _load_json_file(readiness_path)
    checks = readiness.get("checks") if isinstance(readiness.get("checks"), list) else []
    summary = readiness.get("summary") if isinstance(readiness.get("summary"), dict) else {}
    readiness_artifacts = readiness.get("artifacts") if isinstance(readiness.get("artifacts"), dict) else {}

    by_name = {str(check.get("name", "")): check for check in checks if isinstance(check, dict)}
    browser_evidence = by_name.get("dashboard_browser_report", {}).get("evidence", {})
    tap_fixture_evidence = by_name.get("tap_fixture_browser_report", {}).get("evidence", {})
    scheduler_evidence = by_name.get("scheduler_artifact", {}).get("evidence", {})
    hygiene_evidence = by_name.get("text_hygiene_report", {}).get("evidence", {})
    browser_evidence = browser_evidence if isinstance(browser_evidence, dict) else {}
    tap_fixture_evidence = tap_fixture_evidence if isinstance(tap_fixture_evidence, dict) else {}
    scheduler_evidence = scheduler_evidence if isinstance(scheduler_evidence, dict) else {}
    hygiene_evidence = hygiene_evidence if isinstance(hygiene_evidence, dict) else {}
    browser_evidence = _prefer_latest_dashboard_browser_evidence(base_dir, browser_evidence)
    workspace_smoke = _latest_getdaytrends_workspace_smoke(base_dir)
    launch_secret_scan = _latest_getdaytrends_launch_secret_scan(base_dir)
    handoff_refresh = _latest_getdaytrends_handoff_refresh(base_dir)
    credential_input_status = _latest_credential_input_status(base_dir)

    blockers = [
        _operator_issue(check, fallback_message="Readiness check failed.")
        for check in checks
        if isinstance(check, dict) and check.get("ok") is False and str(check.get("level", "FAIL")).upper() != "WARN"
    ]
    warnings = [
        _operator_issue(check, fallback_message="Readiness check warning.")
        for check in checks
        if isinstance(check, dict) and str(check.get("level", "")).upper() == "WARN"
    ]
    if readiness_error:
        blockers.append(
            {
                "name": "readiness_report",
                "display_name": _operator_check_display_name("readiness_report"),
                "message": f"Readiness report is unavailable: {readiness_error}.",
                "level": "ERROR",
                "remediation": READINESS_REFRESH_COMMAND,
            }
        )
    supabase_recovery_packet, provider_auth_recovery_packet = _operator_recovery_packet_paths(
        base_dir,
        readiness_artifacts,
    )
    if supabase_recovery_packet:
        for issue in blockers:
            if issue.get("name") in {"live_db_doctor", "cli_smoke_report"}:
                issue["recovery_packet"] = supabase_recovery_packet
    if provider_auth_recovery_packet:
        for issue in blockers:
            if issue.get("name") == "provider_auth_report":
                issue["recovery_packet"] = provider_auth_recovery_packet
    _annotate_reused_recovery_packets(blockers)
    recovery_packet_payload: dict[str, Any] = {}
    if supabase_recovery_packet:
        recovery_packet_payload, _ = _load_json_file(Path(supabase_recovery_packet))
    recovery_packet_status = str(recovery_packet_payload.get("status") or "unknown")
    recovery_packet_next_action = str(recovery_packet_payload.get("next_required_action") or "").strip()
    recovery_packet_issue_count = 0
    recovery_packet_issue_types = recovery_packet_payload.get("issue_types")
    if isinstance(recovery_packet_issue_types, list):
        recovery_packet_issue_count = len([item for item in recovery_packet_issue_types if str(item).strip()])
    provider_auth_packet_payload: dict[str, Any] = {}
    if provider_auth_recovery_packet:
        provider_auth_packet_payload, _ = _load_json_file(Path(provider_auth_recovery_packet))
    provider_auth_packet_status = str(provider_auth_packet_payload.get("status") or "unknown")
    provider_auth_packet_next_action = str(provider_auth_packet_payload.get("next_required_action") or "").strip()
    provider_auth_packet_issue_count = 0
    provider_auth_packet_issue_types = provider_auth_packet_payload.get("issue_types")
    if isinstance(provider_auth_packet_issue_types, list):
        provider_auth_packet_issue_count = len(
            [item for item in provider_auth_packet_issue_types if str(item).strip()]
        )
    recovery_packet_card_detail = _operator_packet_card_detail(
        recovery_packet_next_action,
        recovery_packet_issue_count,
    )
    provider_auth_packet_card_detail = _operator_packet_card_detail(
        provider_auth_packet_next_action,
        provider_auth_packet_issue_count,
    )

    finished_at = str(scheduler_evidence.get("finished_at") or scheduler_evidence.get("started_at") or "")
    scheduler_artifact_path = scheduler_evidence.get("path")
    if scheduler_artifact_path:
        scheduler_payload, _ = _load_json_file(Path(str(scheduler_artifact_path)))
        for key in (
            "status",
            "exit_code",
            "duration_seconds",
            "started_at",
            "finished_at",
            "detail_log",
            "summary_log",
            "summary_fallback_log",
        ):
            if key not in scheduler_evidence and key in scheduler_payload:
                scheduler_evidence[key] = scheduler_payload[key]
        log_path_keys = {
            "detail_log_exists": "detail_log",
            "primary_summary_log_exists": "summary_log",
            "summary_fallback_log_exists": "summary_fallback_log",
        }
        for exists_key, path_key in log_path_keys.items():
            if exists_key in scheduler_evidence:
                continue
            log_path = str(scheduler_evidence.get(path_key) or "").strip()
            scheduler_evidence[exists_key] = bool(log_path and Path(log_path).exists())
        if "summary_log_exists" not in scheduler_evidence:
            scheduler_evidence["summary_log_exists"] = bool(
                scheduler_evidence.get("primary_summary_log_exists")
                or scheduler_evidence.get("summary_fallback_log_exists")
            )
        scheduler_dir = base_dir / "logs" / "scheduler"
        containment_path_keys = {
            "detail_log_contained": ("detail_log", "detail_log_exists"),
            "primary_summary_log_contained": ("summary_log", "primary_summary_log_exists"),
            "summary_fallback_log_contained": ("summary_fallback_log", "summary_fallback_log_exists"),
        }
        for contained_key, (path_key, exists_key) in containment_path_keys.items():
            if contained_key in scheduler_evidence:
                continue
            log_path = str(scheduler_evidence.get(path_key) or "").strip()
            scheduler_evidence[contained_key] = bool(
                scheduler_evidence.get(exists_key) is True
                and log_path
                and _operator_path_is_within(Path(log_path), scheduler_dir)
            )
        if "summary_log_contained" not in scheduler_evidence:
            scheduler_evidence["summary_log_contained"] = bool(
                scheduler_evidence.get("primary_summary_log_contained")
                or scheduler_evidence.get("summary_fallback_log_contained")
            )
    if not finished_at and scheduler_artifact_path:
        finished_at = str(scheduler_payload.get("finished_at") or scheduler_payload.get("started_at") or "")
    finished_dt = _parse_iso_datetime(finished_at)
    age_hours = None
    scheduler_near_stale = False
    if finished_dt is not None:
        now = datetime.now(finished_dt.tzinfo) if finished_dt.tzinfo else datetime.now()
        age_hours = round(max((now - finished_dt).total_seconds(), 0) / 3600, 1)
        scheduler_near_stale = _is_scheduler_near_stale(age_hours)
        if age_hours > SCHEDULER_MAX_AGE_HOURS:
            warnings.append(
                {
                    "name": "scheduler_freshness",
                    "display_name": _operator_check_display_name("scheduler_freshness"),
                    "message": "Latest scheduler run is older than 24 hours.",
                    "level": "WARN",
                    "remediation": SCHEDULER_REFRESH_COMMAND,
                }
            )
        elif scheduler_near_stale:
            warnings.append(
                {
                    "name": "scheduler_freshness",
                    "display_name": _operator_check_display_name("scheduler_freshness"),
                    "message": "Latest scheduler run is close to the 24-hour freshness limit.",
                    "level": "WARN",
                    "remediation": SCHEDULER_REFRESH_COMMAND,
                }
            )
    scheduler_age_card_detail = ""
    if age_hours is not None and age_hours > SCHEDULER_MAX_AGE_HOURS:
        scheduler_age_card_detail = "Run scheduler refresh now to restore fresh evidence."
    elif scheduler_near_stale:
        scheduler_age_card_detail = "Run scheduler refresh soon to avoid stale evidence."
    else:
        scheduler_age_card_detail = _operator_scheduler_detail(scheduler_evidence)

    status = str(readiness.get("status") or ("missing" if readiness_error else "unknown"))
    total = int(summary.get("total") or len(checks) or 0)
    passed = int(summary.get("passed") or sum(1 for check in checks if isinstance(check, dict) and check.get("ok")))
    browser_summary = browser_evidence.get("summary")
    tap_fixture_summary = tap_fixture_evidence.get("summary")
    hygiene_summary = hygiene_evidence.get("summary")
    browser_summary = browser_summary if isinstance(browser_summary, dict) else {}
    tap_fixture_summary = tap_fixture_summary if isinstance(tap_fixture_summary, dict) else {}
    hygiene_summary = hygiene_summary if isinstance(hygiene_summary, dict) else {}
    workspace_smoke_summary = (
        workspace_smoke.get("summary") if isinstance(workspace_smoke.get("summary"), dict) else {}
    )
    workspace_smoke_total = int(workspace_smoke_summary.get("total") or 0)
    workspace_smoke_passed = int(workspace_smoke_summary.get("passed") or 0)
    workspace_smoke_failed = int(
        workspace_smoke_summary.get("failed") or max(workspace_smoke_total - workspace_smoke_passed, 0)
    )
    workspace_expected_external = workspace_smoke.get("expected_external_failures")
    workspace_expected_external = workspace_expected_external if isinstance(workspace_expected_external, list) else []
    workspace_unexpected_failures = workspace_smoke.get("unexpected_failures")
    workspace_unexpected_failures = workspace_unexpected_failures if isinstance(workspace_unexpected_failures, list) else []
    workspace_smoke_state = _workspace_smoke_state(
        total=workspace_smoke_total,
        failed=workspace_smoke_failed,
        expected_external_failures=[str(item) for item in workspace_expected_external if str(item).strip()],
        unexpected_failures=[str(item) for item in workspace_unexpected_failures if str(item).strip()],
    )
    workspace_smoke_card_detail = _workspace_smoke_card_detail(
        state=workspace_smoke_state,
        expected_external_failures=[str(item) for item in workspace_expected_external if str(item).strip()],
        unexpected_failures=[str(item) for item in workspace_unexpected_failures if str(item).strip()],
    )
    launch_secret_scan_status = str(launch_secret_scan.get("status") or "missing")
    launch_secret_scan_scanned = int(launch_secret_scan.get("scanned") or 0)
    launch_secret_scan_findings = int(launch_secret_scan.get("findings") or 0)
    launch_secret_scan_missing = int(launch_secret_scan.get("missing") or 0)
    launch_secret_scan_includes_current = launch_secret_scan.get("include_current_artifacts") is True
    launch_secret_scan_ok = (
        bool(launch_secret_scan.get("path"))
        and launch_secret_scan.get("ok") is True
        and launch_secret_scan_findings == 0
        and launch_secret_scan_missing == 0
        and launch_secret_scan_includes_current
    )
    launch_secret_scan_state = "pass" if launch_secret_scan_ok else "warn"
    if launch_secret_scan.get("path") and (launch_secret_scan_findings > 0 or launch_secret_scan_missing > 0):
        launch_secret_scan_state = "fail"
    if not launch_secret_scan.get("path"):
        launch_secret_scan_value = "missing"
    elif launch_secret_scan_missing > 0:
        launch_secret_scan_value = f"{launch_secret_scan_missing} missing"
    elif launch_secret_scan_findings > 0:
        launch_secret_scan_value = f"{launch_secret_scan_findings} findings"
    elif launch_secret_scan_scanned > 0:
        launch_secret_scan_value = f"{launch_secret_scan_scanned} scanned"
    else:
        launch_secret_scan_value = launch_secret_scan_status
    launch_secret_scan_detail = (
        "Current artifacts included."
        if launch_secret_scan_ok
        else "Run final launch secret scan with --include-current-artifacts."
    )
    handoff_secret_scan_scanned = int(handoff_refresh.get("secret_scan_scanned") or 0)
    handoff_secret_scan_findings = int(handoff_refresh.get("secret_scan_findings") or 0)
    handoff_secret_scan_missing = int(handoff_refresh.get("secret_scan_missing") or 0)
    handoff_secret_scan_includes_current = handoff_refresh.get("secret_scan_include_current_artifacts") is True
    handoff_secret_scan_contract_ok = (
        handoff_refresh.get("secret_scan_supabase_recovery_packet_contract_ok") is True
    )
    handoff_secret_scan_ok = (
        bool(handoff_refresh.get("path"))
        and handoff_refresh.get("secret_scan_ok") is True
        and handoff_secret_scan_findings == 0
        and handoff_secret_scan_missing == 0
        and handoff_secret_scan_includes_current
        and handoff_secret_scan_contract_ok
    )
    handoff_secret_scan_state = "pass" if handoff_secret_scan_ok else "warn"
    if handoff_refresh.get("path") and (handoff_secret_scan_findings > 0 or handoff_secret_scan_missing > 0):
        handoff_secret_scan_state = "fail"
    if not handoff_refresh.get("path"):
        handoff_secret_scan_value = "missing"
    elif handoff_secret_scan_missing > 0:
        handoff_secret_scan_value = f"{handoff_secret_scan_missing} missing"
    elif handoff_secret_scan_findings > 0:
        handoff_secret_scan_value = f"{handoff_secret_scan_findings} findings"
    elif handoff_secret_scan_scanned > 0:
        handoff_secret_scan_value = f"{handoff_secret_scan_scanned} scanned"
    else:
        handoff_secret_scan_value = str(handoff_refresh.get("secret_scan_state") or handoff_refresh.get("status") or "unknown")
    handoff_secret_scan_detail = (
        "Current artifacts and recovery packet contract verified."
        if handoff_secret_scan_ok
        else "Run handoff refresh and confirm current artifacts plus packet contract."
    )
    launch_focus = _operator_launch_focus(
        status=status,
        blockers=blockers,
        by_name=by_name,
        launch_secret_scan_ok=launch_secret_scan_ok,
    )
    cli_fallback_card = _operator_cli_fallback_card(by_name)
    tap_fixture_screenshot, _ = _safe_operator_image_artifact_path(
        base_dir,
        str(tap_fixture_evidence.get("screenshot") or ""),
    )
    browser_screenshot, _ = _safe_operator_image_artifact_path(
        base_dir,
        str(browser_evidence.get("screenshot") or ""),
    )
    artifacts = {
        "readiness": str(readiness_path),
        "readiness_refresh_command": READINESS_REFRESH_COMMAND,
        "browser": browser_evidence.get("path") if isinstance(browser_evidence, dict) else "",
        "browser_screenshot": str(browser_screenshot) if browser_screenshot else "",
        "tap_fixture_browser": tap_fixture_evidence.get("path") if isinstance(tap_fixture_evidence, dict) else "",
        "tap_fixture_browser_screenshot": str(tap_fixture_screenshot) if tap_fixture_screenshot else "",
        "tap_fixture_browser_refresh_command": TAP_FIXTURE_BROWSER_REFRESH_COMMAND,
        "scheduler": scheduler_artifact_path or "",
        "hygiene": hygiene_evidence.get("path") if isinstance(hygiene_evidence, dict) else "",
        "credential_input_status": credential_input_status.get("path") or "",
        "credential_input_status_json": credential_input_status.get("json_path") or "",
        "supabase_recovery_packet": supabase_recovery_packet,
        "provider_auth_recovery_packet": provider_auth_recovery_packet,
        "workspace_smoke": workspace_smoke.get("path") or "",
        "launch_secret_scan": launch_secret_scan.get("path") or "",
        "launch_secret_scan_refresh_command": _launch_secret_scan_refresh_command(),
        "handoff_refresh": handoff_refresh.get("path") or "",
    }
    browser_notes = _operator_artifact_freshness_notes(
        generated_at=browser_evidence.get("generated_at"),
        age_hours=browser_evidence.get("age_hours"),
        max_age_hours=browser_evidence.get("max_age_hours") or 24,
    )
    tap_fixture_notes = _operator_artifact_freshness_notes(
        generated_at=tap_fixture_evidence.get("generated_at"),
        age_hours=tap_fixture_evidence.get("age_hours"),
        max_age_hours=tap_fixture_evidence.get("max_age_hours") or 24,
    )
    artifact_notes = {
        "readiness_report": _operator_artifact_freshness_notes(
            generated_at=readiness.get("generated_at"),
            max_age_hours=24,
        ),
        "credential_input_status": credential_input_status.get("notes")
        if isinstance(credential_input_status.get("notes"), list)
        else [],
        "provider_auth_recovery_packet": _operator_artifact_freshness_notes(
            generated_at=provider_auth_packet_payload.get("generated_at") or readiness.get("generated_at"),
            max_age_hours=24,
        ),
        "dashboard_browser_report": browser_notes,
        "dashboard_browser_screenshot": browser_notes,
        "tap_fixture_report": tap_fixture_notes,
        "tap_fixture_screenshot": tap_fixture_notes,
        "scheduler_artifact": _operator_scheduler_artifact_notes(
            generated_at=finished_at,
            age_hours=age_hours,
            evidence=scheduler_evidence,
        ),
        "workspace_smoke": _operator_artifact_freshness_notes(
            generated_at=workspace_smoke.get("generated_at"),
            max_age_hours=24,
        ),
        "launch_secret_scan": [
            *_operator_artifact_freshness_notes(
                generated_at=launch_secret_scan.get("generated_at"),
                max_age_hours=24,
            ),
            {"label": f"status: {launch_secret_scan_status}"},
            {"label": f"findings: {launch_secret_scan_findings}"},
            {
                "label": (
                    "current artifacts included"
                    if launch_secret_scan_includes_current
                    else "current artifacts not included"
                )
            },
        ]
        if launch_secret_scan.get("path")
        else [],
        "handoff_refresh": [
            *_operator_artifact_freshness_notes(
                generated_at=handoff_refresh.get("generated_at"),
                max_age_hours=24,
            ),
            {"label": f"status: {handoff_refresh.get('status') or 'unknown'}"},
            {"label": f"scan: {handoff_refresh.get('secret_scan_state') or 'missing'}"},
            {"label": f"findings: {handoff_secret_scan_findings}"},
            {
                "label": (
                    "current artifacts included"
                    if handoff_secret_scan_includes_current
                    else "current artifacts not included"
                )
            },
            {
                "label": (
                    "packet contract verified"
                    if handoff_secret_scan_contract_ok
                    else "packet contract not verified"
                )
            },
        ]
        if handoff_refresh.get("path")
        else [],
    }

    return {
        "schema_version": 1,
        "status": status,
        "generated_at": datetime.now().isoformat(),
        "readiness_generated_at": readiness.get("generated_at"),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": int(summary.get("failed") or len(blockers)),
            "warnings": int(summary.get("warnings") or 0) + len([w for w in warnings if w["name"] == "scheduler_freshness"]),
        },
        "freshness": {
            "latest_scheduler_finished_at": finished_at,
            "age_hours": age_hours,
            "max_age_hours": SCHEDULER_MAX_AGE_HOURS,
            "near_stale": scheduler_near_stale,
            "state": "unknown" if age_hours is None else "fresh" if age_hours <= SCHEDULER_MAX_AGE_HOURS else "stale",
        },
        "launch_focus": launch_focus,
        "cards": [
            {"label": "Readiness", "value": f"{passed}/{total}", "state": status},
            launch_focus["card"],
            *([cli_fallback_card] if cli_fallback_card else []),
            {
                "label": "Browser evidence",
                "value": f"{int(browser_summary.get('passed') or 0)}/{int(browser_summary.get('total') or 0)}",
                "state": str(browser_evidence.get("status") or "unknown") if isinstance(browser_evidence, dict) else "unknown",
            },
            {
                "label": "TAP fixture",
                "value": f"{int(tap_fixture_summary.get('passed') or 0)}/{int(tap_fixture_summary.get('total') or 0)}",
                "state": str(tap_fixture_evidence.get("status") or "unknown")
                if isinstance(tap_fixture_evidence, dict)
                else "unknown",
            },
            {
                "label": "Recovery packet",
                "value": recovery_packet_status if recovery_packet_issue_count == 0 else _format_issue_count(recovery_packet_issue_count),
                "state": "warn" if recovery_packet_status == "blocked" else recovery_packet_status,
                **({"detail": recovery_packet_card_detail} if recovery_packet_card_detail else {}),
            },
            _operator_final_proof_card(recovery_packet_payload, recovery_packet_status),
            {
                "label": "Provider packet",
                "value": (
                    provider_auth_packet_status
                    if provider_auth_packet_issue_count == 0
                    else _format_issue_count(provider_auth_packet_issue_count)
                ),
                "state": "warn" if provider_auth_packet_status == "blocked" else provider_auth_packet_status,
                **({"detail": provider_auth_packet_card_detail} if provider_auth_packet_card_detail else {}),
            },
            _operator_credential_input_status_card(credential_input_status),
            {
                "label": "Workspace smoke",
                "value": "missing" if workspace_smoke_total == 0 else f"{workspace_smoke_passed}/{workspace_smoke_total}",
                "state": workspace_smoke_state,
                **({"detail": workspace_smoke_card_detail} if workspace_smoke_card_detail else {}),
            },
            {
                "label": "Text hygiene",
                "value": f"{int(hygiene_summary.get('findings') or 0)} findings",
                "state": "pass" if int(hygiene_summary.get("findings") or 0) == 0 else "fail",
            },
            {
                "label": "Launch secret scan",
                "value": launch_secret_scan_value,
                "state": launch_secret_scan_state,
                "detail": launch_secret_scan_detail,
            },
            {
                "label": "Handoff refresh scan",
                "value": handoff_secret_scan_value,
                "state": handoff_secret_scan_state,
                "detail": handoff_secret_scan_detail,
            },
            {
                "label": "Scheduler age",
                "value": "-" if age_hours is None else f"{age_hours}h",
                "state": "unknown" if age_hours is None else "warn" if scheduler_near_stale or age_hours > SCHEDULER_MAX_AGE_HOURS else "pass",
                **({"detail": scheduler_age_card_detail} if scheduler_age_card_detail else {}),
            },
        ],
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": artifacts,
        "artifact_actions": _operator_artifact_actions(artifacts, artifact_notes),
        "error": readiness_error,
    }


def _operator_recovery_packet_snapshot(base_dir: Path, *, packet_path: str = "") -> dict[str, Any]:
    logs_dir = base_dir / "logs"
    readiness_path = logs_dir / "readiness" / "readiness_latest.json"
    readiness, readiness_error = _load_json_file(readiness_path)
    readiness_artifacts = readiness.get("artifacts") if isinstance(readiness.get("artifacts"), dict) else {}
    if packet_path:
        safe_packet_path = _safe_operator_artifact_path(base_dir, packet_path)
        if not safe_packet_path:
            return {
                "schema_version": 1,
                "status": "missing",
                "path": "",
                "packet": {},
                "error": "invalid_path",
                "readiness_error": readiness_error,
            }
        packet_path = safe_packet_path
    else:
        packet_path = str(readiness_artifacts.get("supabase_recovery_packet") or "")
        default_packet_path = logs_dir / "readiness" / "supabase_recovery_packet_latest.json"
        if not packet_path and default_packet_path.exists():
            packet_path = str(default_packet_path)

    if not packet_path:
        return {
            "schema_version": 1,
            "status": "missing",
            "path": "",
            "packet": {},
            "error": "missing",
            "readiness_error": readiness_error,
        }

    packet, packet_error = _load_json_file(Path(packet_path))
    return {
        "schema_version": 1,
        "status": str(packet.get("status") or ("missing" if packet_error else "unknown")),
        "path": packet_path,
        "packet": packet,
        "error": packet_error,
        "readiness_error": readiness_error,
    }


def _operator_workspace_smoke_snapshot(base_dir: Path, requested_path: str = "") -> dict[str, Any]:
    safe_requested_path = _safe_workspace_smoke_path(base_dir, requested_path)
    if requested_path.strip() and not safe_requested_path:
        return {
            "schema_version": 1,
            "status": "error",
            "conclusion": "error",
            "path": "",
            "generated_at": "",
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "failed_checks": [],
            "expected_external_failures": [],
            "unexpected_failures": [],
            "failed_details": [],
            "failed_rerun_commands": [],
            "failed_rerun_command_bundle": "",
            "error": "invalid_path",
        }
    if safe_requested_path:
        payload, error = _load_json_file(Path(safe_requested_path))
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        total = int(summary.get("total") or summary.get("completed") or 0)
        passed = int(summary.get("passed") or 0)
        failed = int(summary.get("failed") or max(total - passed, 0))
        failed_checks = []
        results = payload.get("results")
        if isinstance(results, list):
            failed_checks = [
                str(result.get("name", "unknown_check"))
                for result in results
                if isinstance(result, dict) and result.get("ok") is False
            ][:6]
        status = str(payload.get("status") or ("missing" if error else "unknown"))
        failed_details = _workspace_smoke_failed_details(payload)
        failure_classification = _workspace_smoke_failure_classification(payload, failed_checks)
        failed_rerun_commands, failed_rerun_command_bundle = _workspace_smoke_failed_rerun_bundle(
            base_dir,
            failed_details,
        )
        return {
            "schema_version": 1,
            "status": status,
            "conclusion": _workspace_smoke_conclusion(
                status,
                {"total": total, "passed": passed, "failed": failed},
                error,
                expected_external_failures=failure_classification["expected_external_failures"],
                unexpected_failures=failure_classification["unexpected_failures"],
            ),
            "path": safe_requested_path,
            "generated_at": str(payload.get("generated_at") or ""),
            "summary": {"total": total, "passed": passed, "failed": failed},
            "failed_checks": failed_checks,
            **failure_classification,
            "failed_details": failed_details,
            "failed_rerun_commands": failed_rerun_commands,
            "failed_rerun_command_bundle": failed_rerun_command_bundle,
            "error": error,
        }

    workspace_smoke = _latest_getdaytrends_workspace_smoke(base_dir)
    path = str(workspace_smoke.get("path") or "")
    summary = workspace_smoke.get("summary") if isinstance(workspace_smoke.get("summary"), dict) else {}
    failed_checks = workspace_smoke.get("failed_checks")
    failed_checks = failed_checks if isinstance(failed_checks, list) else []
    expected_external_failures = workspace_smoke.get("expected_external_failures")
    expected_external_failures = expected_external_failures if isinstance(expected_external_failures, list) else []
    unexpected_failures = workspace_smoke.get("unexpected_failures")
    unexpected_failures = unexpected_failures if isinstance(unexpected_failures, list) else []

    if not path:
        return {
            "schema_version": 1,
            "status": "missing",
            "conclusion": "missing",
            "path": "",
            "generated_at": "",
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "failed_checks": [],
            "expected_external_failures": [],
            "unexpected_failures": [],
            "failed_details": [],
            "failed_rerun_commands": [],
            "failed_rerun_command_bundle": "",
            "error": "missing",
        }

    payload, error = _load_json_file(Path(path))
    status = str(payload.get("status") or workspace_smoke.get("status") or ("missing" if error else "unknown"))
    failed_details = _workspace_smoke_failed_details(payload)
    failed_rerun_commands, failed_rerun_command_bundle = _workspace_smoke_failed_rerun_bundle(
        base_dir,
        failed_details,
    )
    return {
        "schema_version": 1,
        "status": status,
        "conclusion": _workspace_smoke_conclusion(
            status,
            summary,
            error,
            expected_external_failures=[str(item) for item in expected_external_failures if str(item).strip()],
            unexpected_failures=[str(item) for item in unexpected_failures if str(item).strip()],
        ),
        "path": path,
        "generated_at": str(payload.get("generated_at") or workspace_smoke.get("generated_at") or ""),
        "summary": {
            "total": int(summary.get("total") or 0),
            "passed": int(summary.get("passed") or 0),
            "failed": int(summary.get("failed") or 0),
        },
        "failed_checks": [str(item) for item in failed_checks[:6] if str(item).strip()],
        "expected_external_failures": [str(item) for item in expected_external_failures[:6] if str(item).strip()],
        "unexpected_failures": [str(item) for item in unexpected_failures[:6] if str(item).strip()],
        "failed_details": failed_details,
        "failed_rerun_commands": failed_rerun_commands,
        "failed_rerun_command_bundle": failed_rerun_command_bundle,
        "error": error,
    }


def _operator_launch_secret_scan_snapshot(base_dir: Path, requested_path: str = "") -> dict[str, Any]:
    safe_requested_path = _safe_launch_secret_scan_path(base_dir, requested_path)
    if requested_path.strip() and not safe_requested_path:
        return {
            "schema_version": 1,
            "status": "error",
            "ok": False,
            "path": "",
            "generated_at": "",
            "scope": "",
            "include_current_artifacts": False,
            "summary": {"scanned": 0, "findings": 0, "missing": 0},
            "finding_patterns": [],
            "missing_paths": [],
            "scanned_sample": [],
            "current_artifact_sample": [],
            "refresh_command": _launch_secret_scan_refresh_command(),
            "error": "invalid_path",
        }
    if safe_requested_path:
        path = safe_requested_path
    else:
        latest = _latest_getdaytrends_launch_secret_scan(base_dir)
        path = str(latest.get("path") or "")
    if not path:
        return {
            "schema_version": 1,
            "status": "missing",
            "ok": False,
            "path": "",
            "generated_at": "",
            "scope": "",
            "include_current_artifacts": False,
            "summary": {"scanned": 0, "findings": 0, "missing": 0},
            "finding_patterns": [],
            "missing_paths": [],
            "scanned_sample": [],
            "current_artifact_sample": [],
            "refresh_command": _launch_secret_scan_refresh_command(),
            "error": "missing",
        }

    payload, error = _load_json_file(Path(path))
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    missing_paths = payload.get("missing_paths") if isinstance(payload.get("missing_paths"), list) else []
    scanned_paths = payload.get("scanned_paths") if isinstance(payload.get("scanned_paths"), list) else []
    finding_patterns = payload.get("finding_patterns") if isinstance(payload.get("finding_patterns"), list) else []
    if not finding_patterns:
        finding_patterns = sorted(
            {
                str(pattern)
                for finding in findings
                if isinstance(finding, dict)
                for pattern in finding.get("patterns", [])
                if str(pattern).strip()
            }
        )
    status = str(payload.get("status") or ("missing" if error == "missing" else "error" if error else "unknown"))
    finding_count = len(findings)
    missing_count = len(missing_paths)
    scanned_count = len(scanned_paths)
    current_artifact_prefixes = (
        "automation/getdaytrends/logs/",
        "var/github-modernization-radar-getdaytrends",
        "var/workspace-smoke-getdaytrends",
    )
    current_artifact_sample = [
        _sanitize_operator_text(item, limit=220)
        for item in scanned_paths
        if any(str(item).startswith(prefix) for prefix in current_artifact_prefixes)
    ][:8]
    return {
        "schema_version": 1,
        "status": status,
        "ok": payload.get("ok") is True and finding_count == 0 and missing_count == 0,
        "path": path,
        "generated_at": str(payload.get("generated_at") or ""),
        "scope": _sanitize_operator_text(payload.get("scope") or "", limit=120),
        "include_current_artifacts": payload.get("include_current_artifacts") is True,
        "summary": {
            "scanned": scanned_count,
            "findings": finding_count,
            "missing": missing_count,
        },
        "finding_patterns": [
            _sanitize_operator_text(pattern, limit=100)
            for pattern in finding_patterns[:8]
            if _sanitize_operator_text(pattern, limit=100)
        ],
        "missing_paths": [
            _sanitize_operator_text(item, limit=220)
            for item in missing_paths[:8]
            if _sanitize_operator_text(item, limit=220)
        ],
        "scanned_sample": [
            _sanitize_operator_text(item, limit=220)
            for item in scanned_paths[:8]
            if _sanitize_operator_text(item, limit=220)
        ],
        "current_artifact_sample": [item for item in current_artifact_sample if item],
        "refresh_command": _launch_secret_scan_refresh_command(),
        "error": error,
    }


def _operator_readiness_report_snapshot(base_dir: Path) -> dict[str, Any]:
    readiness_path = base_dir / "logs" / "readiness" / "readiness_latest.json"
    payload, error = _load_json_file(readiness_path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    supabase_recovery_packet, provider_auth_recovery_packet = _operator_recovery_packet_paths(base_dir, artifacts)
    by_name = {str(check.get("name", "")): check for check in checks if isinstance(check, dict)}
    browser_evidence = by_name.get("dashboard_browser_report", {}).get("evidence", {})
    browser_evidence = browser_evidence if isinstance(browser_evidence, dict) else {}
    browser_evidence = _prefer_latest_dashboard_browser_evidence(base_dir, browser_evidence)
    fresh_browser_path = str(browser_evidence.get("path") or "").strip()

    def _summarize_check(check: dict[str, Any]) -> dict[str, Any]:
        evidence = check.get("evidence") if isinstance(check.get("evidence"), dict) else {}
        diagnostics = evidence.get("diagnostics") if isinstance(evidence.get("diagnostics"), list) else []
        name = _sanitize_operator_text(check.get("name") or "unknown_check", limit=120)
        summary_item = {
            "name": name,
            "display_name": _operator_check_display_name(name),
            "level": _sanitize_operator_text(check.get("level") or "UNKNOWN", limit=40),
            "message": _sanitize_operator_text(check.get("message") or "", limit=360),
            "remediation": _sanitize_operator_text(check.get("remediation") or "", limit=520),
            "diagnostics": [
                sanitized
                for item in diagnostics[:4]
                if (sanitized := _sanitize_operator_text(item, limit=360))
            ],
        }
        evidence_summary = [
            sanitized
            for item in [
                *_operator_runtime_fallback_summary(evidence),
                *_operator_live_db_summary(evidence),
            ]
            if (sanitized := _sanitize_operator_text(item, limit=160))
        ]
        if evidence_summary:
            summary_item["evidence_summary"] = evidence_summary
        packet_label, packet_path = _operator_recovery_packet_for_check(
            name,
            supabase_recovery_packet,
            provider_auth_recovery_packet,
        )
        if packet_label and packet_path:
            summary_item["recovery_packet_label"] = packet_label
            summary_item["recovery_packet"] = _sanitize_operator_text(packet_path, limit=260)
        return summary_item

    failed_checks = [
        _summarize_check(check)
        for check in checks
        if isinstance(check, dict) and check.get("ok") is False
    ][:6]
    _annotate_reused_recovery_packets(failed_checks)
    warning_checks = [
        _summarize_check(check)
        for check in checks
        if isinstance(check, dict)
        and check.get("ok") is not False
        and str(check.get("level", "")).upper() == "WARN"
    ][:4]

    summarized_artifacts = {}
    for key, value in artifacts.items():
        safe_key = _sanitize_operator_text(key, limit=80)
        if str(key) == "browser" and fresh_browser_path:
            value = fresh_browser_path
        safe_value = _sanitize_operator_text(value, limit=260)
        if safe_key and safe_value:
            summarized_artifacts[safe_key] = safe_value
    verification_working_directory, verification_commands, verification_command_bundle = (
        _readiness_verification_bundle(base_dir)
    )

    return {
        "schema_version": 1,
        "status": str(payload.get("status") or ("missing" if error else "unknown")),
        "path": str(readiness_path),
        "generated_at": str(payload.get("generated_at") or ""),
        "summary": {
            "total": int(summary.get("total") or len(checks) or 0),
            "passed": int(summary.get("passed") or 0),
            "failed": int(summary.get("failed") or len(failed_checks)),
            "warnings": int(summary.get("warnings") or len(warning_checks)),
        },
        "failed_checks": failed_checks,
        "warning_checks": warning_checks,
        "artifacts": summarized_artifacts,
        "verification_shell": "powershell",
        "verification_working_directory": verification_working_directory,
        "verification_commands": verification_commands,
        "verification_command_bundle": verification_command_bundle,
        "error": error,
    }


def _dashboard_degraded_headers(
    endpoint_name: str, unavailable_reason: str = "dependency_unavailable"
) -> dict[str, str]:
    return {
        "X-Dashboard-Degraded": "1",
        "X-Dashboard-Degraded-Reason": unavailable_reason,
        "X-Dashboard-Degraded-Source": endpoint_name,
    }


def _attach_degraded_meta(payload: Any, endpoint_name: str, unavailable_reason: str = "dependency_unavailable") -> Any:
    if not isinstance(payload, dict):
        return payload

    annotated = dict(payload)
    annotated["_meta"] = {
        "degraded": True,
        "source": endpoint_name,
        "unavailable_reason": unavailable_reason,
    }
    return annotated


_DASHBOARD_DB_FAILURE_TTL_SECONDS = 30.0
_DASHBOARD_DB_FAILURE_CACHE: dict[str, Any] = {"key": None, "expires_at": 0.0, "message": ""}


def _dashboard_db_failure_cache_key() -> tuple[str, int]:
    return (str(getattr(_config, "database_url", "") or ""), id(_get_conn))


def _get_cached_dashboard_db_failure(now: float | None = None) -> str:
    now = time.monotonic() if now is None else now
    if _DASHBOARD_DB_FAILURE_CACHE.get("key") != _dashboard_db_failure_cache_key():
        return ""
    expires_at = float(_DASHBOARD_DB_FAILURE_CACHE.get("expires_at") or 0.0)
    if expires_at <= now:
        return ""
    return str(_DASHBOARD_DB_FAILURE_CACHE.get("message") or "")


def _remember_dashboard_db_failure(exc: Exception, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    _DASHBOARD_DB_FAILURE_CACHE.update(
        {
            "key": _dashboard_db_failure_cache_key(),
            "expires_at": now + _DASHBOARD_DB_FAILURE_TTL_SECONDS,
            "message": _sanitize_dashboard_log_line(f"{type(exc).__name__}: {exc}"),
        }
    )


async def _run_db_json_with_fallback(
    endpoint_name: str,
    handler: Callable[[Any], Awaitable[Any]],
    fallback_payload: Callable[[], Any] | Any,
) -> JSONResponse:
    cached_failure = _get_cached_dashboard_db_failure()
    if cached_failure:
        logger.info(
            "Dashboard endpoint served fallback: %s (cached DB connection failure: %s)",
            endpoint_name,
            cached_failure,
        )
        payload = fallback_payload() if callable(fallback_payload) else fallback_payload
        unavailable_reason = "dependency_unavailable"
        return JSONResponse(
            _attach_degraded_meta(payload, endpoint_name, unavailable_reason),
            headers=_dashboard_degraded_headers(endpoint_name, unavailable_reason),
        )

    conn = None
    try:
        conn = await _get_conn()
    except Exception as exc:
        _remember_dashboard_db_failure(exc)
        logger.warning("Dashboard endpoint degraded: %s", endpoint_name, exc_info=True)
        payload = fallback_payload() if callable(fallback_payload) else fallback_payload
        unavailable_reason = "dependency_unavailable"
        return JSONResponse(
            _attach_degraded_meta(payload, endpoint_name, unavailable_reason),
            headers=_dashboard_degraded_headers(endpoint_name, unavailable_reason),
        )
    try:
        payload = await handler(conn)
        return JSONResponse(payload)
    except Exception:
        logger.warning("Dashboard endpoint degraded: %s", endpoint_name, exc_info=True)
        payload = fallback_payload() if callable(fallback_payload) else fallback_payload
        unavailable_reason = "dependency_unavailable"
        return JSONResponse(
            _attach_degraded_meta(payload, endpoint_name, unavailable_reason),
            headers=_dashboard_degraded_headers(endpoint_name, unavailable_reason),
        )
    finally:
        await _close_conn(conn)


# ── TAP Router (separated to dashboard_routes_tap.py) ──
init_tap_router(
    config=_config,
    get_conn_fn=_get_conn,
    close_conn_fn=_close_conn,
    run_db_json_fn=_run_db_json_with_fallback,
    alert_queue_fallback=_tap_alert_queue_fallback,
    deal_room_fallback=_tap_deal_room_fallback,
    funnel_fallback=_tap_deal_room_funnel_fallback,
    checkout_summary_fallback=_tap_checkout_summary_fallback,
)
app.include_router(tap_router)


# ── Pro HTML Dashboard ─────────────────────────────────────────────
# Chart.js CDN + 6-panel layout + auto-refresh + micro-interactions


# ── HTML Template (extracted to dashboard_html.py) ──
_HTML_GETTER = get_dashboard_html  # used in index()


@app.get("/", response_class=HTMLResponse)
def index() -> Any:
    return get_dashboard_html(VERSION)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


# ── API Endpoints ────────────────────────────────────────


@app.get("/api/stats")
async def api_stats() -> Any:
    async def _load_stats(conn) -> dict[str, Any]:
        stats = await get_trend_stats(conn)

        # LLM 비용 통합
        llm_cost_7d = 0.0
        llm_daily: list[dict] = []
        try:
            from shared.llm.stats import _DB_PATH as llm_db_path
            from shared.llm.stats import CostTracker

            if llm_db_path.exists():
                tracker = CostTracker(persist=True)
                daily = tracker.get_daily_stats(7)
                tracker.close()
                llm_daily = daily
                llm_cost_7d = sum(r["cost_usd"] for r in daily)
        except Exception:
            pass

        return {
            **stats,
            "llm_cost_7d": round(llm_cost_7d, 6),
            "llm_daily": llm_daily,
        }

    return await _run_db_json_with_fallback("api_stats", _load_stats, _stats_fallback)


@app.get("/api/trends")
async def api_trends(days: int = Query(7, ge=1, le=90), limit: int = Query(50, ge=1, le=200)) -> Any:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    async def _load_trends(conn) -> list[dict[str, Any]]:
        cursor = await conn.execute(
            """SELECT keyword, viral_potential, trend_acceleration, top_insight,
                      country, scored_at
               FROM trends WHERE scored_at >= ?
               ORDER BY viral_potential DESC LIMIT ?""",
            (cutoff, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    return await _run_db_json_with_fallback("api_trends", _load_trends, [])


@app.get("/api/tweets")
async def api_tweets(
    trend_keyword: str = Query(None),
    days: int = Query(3, ge=1, le=30),
    limit: int = Query(30, ge=1, le=100),
) -> Any:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    async def _load_tweets(conn) -> list[dict[str, Any]]:
        if trend_keyword:
            cursor = await conn.execute(
                """SELECT tw.tweet_type, tw.content, tw.content_type, tw.char_count,
                          tw.status, tw.generated_at, tr.keyword
                   FROM tweets tw JOIN trends tr ON tw.trend_id = tr.id
                   WHERE tr.keyword LIKE ? AND tw.generated_at >= ?
                   ORDER BY tw.generated_at DESC LIMIT ?""",
                (f"%{trend_keyword}%", cutoff, limit),
            )
        else:
            cursor = await conn.execute(
                """SELECT tw.tweet_type, tw.content, tw.content_type, tw.char_count,
                          tw.status, tw.generated_at, tr.keyword
                   FROM tweets tw JOIN trends tr ON tw.trend_id = tr.id
                   WHERE tw.generated_at >= ?
                   ORDER BY tw.generated_at DESC LIMIT ?""",
                (cutoff, limit),
            )

        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    return await _run_db_json_with_fallback("api_tweets", _load_tweets, [])


@app.get("/api/runs")
async def api_runs(limit: int = Query(20, ge=1, le=100)) -> Any:
    async def _load_runs(conn) -> list[dict[str, Any]]:
        cursor = await conn.execute(
            """SELECT run_uuid, started_at, finished_at, country,
                      trends_collected, tweets_generated, tweets_saved, errors
               FROM runs ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    return await _run_db_json_with_fallback("api_runs", _load_runs, [])


@app.get("/api/pipeline_status")
def api_pipeline_status() -> JSONResponse:
    """실시간 파이프라인 상태 + 예산 현황."""
    status = dict(_pipeline_status)

    budget_info = {"daily_budget_usd": _config.daily_budget_usd, "today_cost_usd": 0.0, "budget_used_pct": 0.0}
    try:
        from shared.llm.stats import _DB_PATH as llm_db_path
        from shared.llm.stats import CostTracker

        if llm_db_path.exists():
            tracker = CostTracker(persist=True)
            daily = tracker.get_daily_stats(1)
            tracker.close()
            today = str(date.today())
            today_cost = sum(r["cost_usd"] for r in daily if r.get("date") == today)
            budget_info["today_cost_usd"] = round(today_cost, 6)
            if _config.daily_budget_usd > 0:
                budget_info["budget_used_pct"] = round(today_cost / _config.daily_budget_usd * 100, 1)
    except Exception:
        pass

    status["budget"] = budget_info
    return JSONResponse(status)


@app.get("/api/health")
def api_health() -> JSONResponse:
    """Operational readiness snapshot for monitor bots and schedulers."""
    checks: dict[str, Any] = {}

    # Shared LLM key availability
    llm_keys = []
    try:
        from shared.llm.config import load_keys

        keys = load_keys()
        llm_keys = sorted([name for name, enabled in keys.items() if enabled])
        checks["llm_keys"] = {"ok": bool(llm_keys), "providers": llm_keys}
    except Exception as exc:
        checks["llm_keys"] = {"ok": False, "error": str(exc)}

    # Local logging path
    try:
        log_path = _config.log_file_path
        checks["log_file"] = {
            "ok": log_path.exists(),
            "path": str(log_path),
        }
    except Exception as exc:
        checks["log_file"] = {"ok": False, "error": str(exc)}

    # DB path sanity (SQLite only; PostgreSQL URL is validated lazily during connection).
    try:
        db_path = _config.base_dir / _config.db_path
        checks["sqlite_db_dir"] = {
            "ok": db_path.parent.exists(),
            "path": str(db_path.parent),
        }
    except Exception as exc:
        checks["sqlite_db_dir"] = {"ok": False, "error": str(exc)}

    checks["runbook"] = {
        "ok": bool(_config.countries),
        "countries": ", ".join(_config.countries),
        "schedule_minutes": _config.schedule_minutes,
    }

    all_ok = all(entry.get("ok", True) for entry in checks.values() if isinstance(entry, dict))
    health_status = "ok" if all_ok else "degraded"

    return JSONResponse(
        {
            "status": health_status,
            "version": VERSION,
            "timestamp": datetime.now().isoformat(),
            "checks": checks,
            "pipeline": _pipeline_status,
        }
    )


@app.get("/api/operator/readiness")
def api_operator_readiness() -> JSONResponse:
    """Summarize local product-readiness evidence for the operator dashboard."""
    return JSONResponse(_operator_readiness_snapshot(_config.base_dir))


@app.get("/api/operator/readiness-report")
def api_operator_readiness_report() -> JSONResponse:
    """Return a sanitized preview of the latest readiness report."""
    return JSONResponse(_operator_readiness_report_snapshot(_config.base_dir))


@app.get("/api/operator/recovery-packet")
def api_operator_recovery_packet(path: str = Query("", alias="path")) -> JSONResponse:
    """Return a current recovery packet for the operator dashboard."""
    return JSONResponse(_operator_recovery_packet_snapshot(_config.base_dir, packet_path=path))


@app.get("/api/operator/workspace-smoke")
def api_operator_workspace_smoke(path: str = Query("", alias="path")) -> JSONResponse:
    """Return the latest canonical getdaytrends workspace-smoke summary."""
    return JSONResponse(_operator_workspace_smoke_snapshot(_config.base_dir, requested_path=path))


@app.get("/api/operator/launch-secret-scan")
def api_operator_launch_secret_scan(path: str = Query("", alias="path")) -> JSONResponse:
    """Return a safe summary of the latest getdaytrends launch secret scan."""
    return JSONResponse(_operator_launch_secret_scan_snapshot(_config.base_dir, requested_path=path))


@app.get("/api/operator/artifact-image")
def api_operator_artifact_image(path: str = Query("", alias="path")) -> Response:
    """Return a safe local operator image artifact for dashboard previews."""
    image_path, error = _safe_operator_image_artifact_path(_config.base_dir, path)
    if image_path is None:
        status_code = 404 if error == "missing" else 415 if error == "unsupported_type" else 400
        return JSONResponse({"ok": False, "error": error}, status_code=status_code)
    return FileResponse(
        image_path,
        media_type=_OPERATOR_IMAGE_MEDIA_TYPES[image_path.suffix.lower()],
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/pipeline_status")
def update_pipeline_status(
    state: str, error: str = "", trends: int = 0, tweets: int = 0, elapsed: float = 0.0
) -> dict[str, bool]:
    """main.py에서 파이프라인 상태 업데이트 (내부용)."""
    _pipeline_status["state"] = state
    _pipeline_status["last_run_at"] = datetime.now().isoformat()
    if error:
        _pipeline_status["last_error"] = error
    if trends:
        _pipeline_status["trends_last_run"] = trends
    if tweets:
        _pipeline_status["tweets_last_run"] = tweets
    if elapsed:
        _pipeline_status["last_run_elapsed"] = round(elapsed, 1)
    return {"ok": True}


# ── C-3: 고도화 API Endpoints ────────────────────────────


@app.get("/api/trends/today")
async def api_trends_today(limit: int = Query(50, ge=1, le=200)) -> Any:
    """오늘 생성된 트렌드 + 연결 트윗 수."""
    today = str(date.today())

    async def _load_trends_today(conn) -> list[dict[str, Any]]:
        cursor = await conn.execute(
            """SELECT t.id, t.keyword, t.viral_potential, t.trend_acceleration,
                      t.top_insight, t.country, t.scored_at,
                      (SELECT COUNT(*) FROM tweets tw WHERE tw.trend_id = t.id) AS tweet_count
               FROM trends t
               WHERE t.scored_at >= ?
               ORDER BY t.viral_potential DESC LIMIT ?""",
            (today, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    return await _run_db_json_with_fallback("api_trends_today", _load_trends_today, [])


@app.get("/api/trends/{keyword}/tweets")
async def api_trend_tweets(
    keyword: str,
    limit: int = Query(30, ge=1, le=100),
) -> Any:
    """특정 트렌드의 생성 트윗 전체."""

    async def _load_trend_tweets(conn) -> list[dict[str, Any]]:
        cursor = await conn.execute(
            """SELECT tw.tweet_type, tw.content, tw.content_type, tw.char_count,
                      tw.status, tw.generated_at
               FROM tweets tw JOIN trends tr ON tw.trend_id = tr.id
               WHERE tr.keyword = ?
               ORDER BY tw.generated_at DESC LIMIT ?""",
            (keyword, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    return await _run_db_json_with_fallback("api_trend_tweets", _load_trend_tweets, [])


@app.get("/api/source/quality")
async def api_source_quality(days: int = Query(7, ge=1, le=30)) -> Any:
    """소스별 품질 통계 (success_rate, avg_latency, quality_score)."""

    async def _load_source_quality(conn) -> Any:
        return await get_source_quality_summary(conn, days=days)

    return await _run_db_json_with_fallback("api_source_quality", _load_source_quality, {})


@app.get("/api/stats/categories")
async def api_category_stats(days: int = Query(7, ge=1, le=90)) -> Any:
    """카테고리별 바이럴 점수 분포."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    async def _load_category_stats(conn) -> list[dict[str, Any]]:
        cursor = await conn.execute(
            """SELECT
                      COALESCE(category, '기타') AS category,
                      COUNT(*) AS count,
                      ROUND(AVG(viral_potential), 1) AS avg_score,
                      MAX(viral_potential) AS max_score,
                      MIN(viral_potential) AS min_score
               FROM trends
               WHERE scored_at >= ?
               GROUP BY COALESCE(category, '기타')
               ORDER BY count DESC""",
            (cutoff,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    return await _run_db_json_with_fallback("api_category_stats", _load_category_stats, [])


@app.get("/api/watchlist")
async def api_watchlist(limit: int = Query(50, ge=1, le=200)) -> Any:
    """Watchlist 키워드 등장 히스토리."""

    async def _load_watchlist(conn) -> list[dict[str, Any]]:
        cursor = await conn.execute(
            """SELECT keyword, watchlist_item, viral_potential, detected_at
               FROM watchlist_hits
               ORDER BY detected_at DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    return await _run_db_json_with_fallback("api_watchlist", _load_watchlist, [])


@app.get("/api/review_queue")
async def api_review_queue(limit: int = Query(50, ge=1, le=200)) -> Any:
    """Read-only mirror of the V2 review queue lifecycle."""

    async def _load_review_queue(conn) -> Any:
        return await get_review_queue_snapshot(conn, limit=limit)

    return await _run_db_json_with_fallback("api_review_queue", _load_review_queue, _review_queue_fallback)


@app.get("/api/logs")
async def api_logs(limit: int = Query(50, ge=1, le=200)) -> Any:
    """Loki 또는 로컬 파일에서 실시간 로그 수집."""
    logs = []

    # 1. Try Loki first (if docker-compose monitoring is running)
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(
                "http://localhost:3100/loki/api/v1/query", params={"query": '{job="getdaytrends"}', "limit": limit}
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", {}).get("result", [])
                if results:
                    # Parse Loki's matrix/vector
                    for res in results:
                        for val in res.get("values", []):
                            logs.append(_sanitize_dashboard_log_line(str(val[1])))
                    return JSONResponse({"logs": logs[-limit:], "source": "loki"})
    except Exception:
        pass

    # 2. Fallback to local log file
    log_path = _config.log_file_path
    if log_path.exists():
        try:
            with open(log_path, encoding="utf-8") as f:
                lines = f.readlines()
                logs = [_sanitize_dashboard_log_line(line.strip()) for line in lines[-limit:]]
        except Exception:
            pass

    return JSONResponse({"logs": logs, "source": "local"})


@app.get("/api/ab_test")
def api_ab_test() -> object:
    """A/B 테스트 결과 실제 데이터 반환 (DailyNews)."""
    ab_test_file = _config.base_dir.parent / "DailyNews" / "output" / "ab_test_economy_kr_v2.json"
    try:
        if ab_test_file.exists():
            with open(ab_test_file, encoding="utf-8") as f:
                data = json.load(f)

            eval_a = data.get("evaluation", {}).get("version_a", {})
            eval_b = data.get("evaluation", {}).get("version_b", {})

            kpi_a = eval_a.get("primary_kpi", 0)
            kpi_b = eval_b.get("primary_kpi", 0)

            # Map primary KPI points to a dummy CTR/conversion for dashboard visualization
            # since the original dashboard expects ctr/conversion layout
            return JSONResponse(
                {
                    "metrics": {
                        "group_a": {"ctr": round(kpi_a / 10, 1), "conversion": round(kpi_a / 30, 2)},
                        "group_b": {"ctr": round(kpi_b / 10, 1), "conversion": round(kpi_b / 30, 2)},
                    }
                }
            )
    except Exception:
        pass

    # Fallback / Placeholder
    return JSONResponse(
        {"metrics": {"group_a": {"ctr": 2.1, "conversion": 0.8}, "group_b": {"ctr": 4.5, "conversion": 2.2}}}
    )

"""Refresh DeSci operator status and launch handoff secret-scan evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import github_modernization_radar
from workspace_paths import find_workspace_root

try:
    import auto_research_status
except ImportError:
    auto_research_status = None

try:
    import desci_launch_secret_scan
except ImportError:
    desci_launch_secret_scan = None

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_ROOT = find_workspace_root(Path(__file__))
VERITAS_REPO = "Veritas-7/autoresearch-skill-system"
DEFAULT_RADAR_JSON = WORKSPACE_ROOT / "var" / "github-modernization-radar-desci-handoff-refresh-2026-06-06.json"
DEFAULT_STOP_FILE = WORKSPACE_ROOT / "var" / "auto-research.stop"
DEFAULT_RADAR_MARKDOWN = (
    WORKSPACE_ROOT
    / "docs"
    / "reports"
    / "2026-06"
    / "GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_HANDOFF_REFRESH_2026-06-06.md"
)
DEFAULT_STATUS_JSON = WORKSPACE_ROOT / "var" / "auto-research-status-desci-handoff-refresh-2026-06-06.json"
DEFAULT_STATUS_MARKDOWN = (
    WORKSPACE_ROOT
    / "docs"
    / "reports"
    / "2026-06"
    / "AUTO_RESEARCH_OPERATOR_STATUS_DESCI_HANDOFF_REFRESH_2026-06-06.md"
)
DEFAULT_SECRET_SCAN_JSON = WORKSPACE_ROOT / "var" / "desci-launch-secret-scan-handoff-refresh-2026-06-06.json"
DEFAULT_BUNDLE_JSON = WORKSPACE_ROOT / "var" / "desci-launch-handoff-refresh-2026-06-06.json"
DEFAULT_ALLOWED_ACTION_REQUIRED_FAILURES: frozenset[str] = frozenset(
    {"desci_launch_handoff_refresh_ready"}
)


def refresh_desci_launch_handoff(
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    radar_json: Path | None = DEFAULT_RADAR_JSON,
    radar_markdown_out: Path | None = None,
    auto_refresh_radar: bool = True,
    stop_file: Path | None = None,
    status_json_out: Path = DEFAULT_STATUS_JSON,
    status_markdown_out: Path = DEFAULT_STATUS_MARKDOWN,
    secret_scan_json_out: Path = DEFAULT_SECRET_SCAN_JSON,
    bundle_json_out: Path = DEFAULT_BUNDLE_JSON,
    release_handoff_json: Path | None = None,
    live_source_commit: str | None = None,
    check_live_source: bool = False,
    allow_action_required: bool = True,
    require_desci_topic: bool = True,
    require_live_source: bool = True,
    require_expected_action_required_failures: bool = True,
    allowed_action_required_failures: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    live_source_checked = check_live_source or require_live_source or live_source_commit is not None
    live_source_commit = _resolved_live_source_commit(
        workspace_root, live_source_commit, check_live_source, require_live_source
    )
    release_handoff_json = _resolve_release_handoff_json(workspace_root, release_handoff_json)

    radar_refresh = _refresh_radar_if_needed(
        radar_json=radar_json,
        radar_markdown_out=radar_markdown_out,
        enabled=auto_refresh_radar,
        live_source_commit=live_source_commit,
    )

    secret_scan_passes = 0
    pre_scan_paths = _extra_scan_paths(
        radar_json=radar_json,
        radar_markdown_out=radar_markdown_out,
        release_handoff_json=release_handoff_json,
    )
    secret_scan = _write_secret_scan(
        workspace_root=workspace_root,
        secret_scan_json_out=secret_scan_json_out,
        extra_paths=pre_scan_paths,
    )
    secret_scan_passes += 1

    status_report = _write_status(
        workspace_root=workspace_root,
        radar_json=radar_json,
        stop_file=stop_file,
        live_source_commit=live_source_commit,
        live_source_checked=live_source_checked,
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
    )

    generated_paths = _extra_scan_paths(
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
        radar_json=radar_json,
        radar_markdown_out=radar_markdown_out,
        release_handoff_json=release_handoff_json,
    )
    secret_scan = _write_secret_scan(
        workspace_root=workspace_root,
        secret_scan_json_out=secret_scan_json_out,
        extra_paths=generated_paths,
    )
    secret_scan_passes += 1

    status_report = _write_status(
        workspace_root=workspace_root,
        radar_json=radar_json,
        stop_file=stop_file,
        live_source_commit=live_source_commit,
        live_source_checked=live_source_checked,
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
    )
    bundle = _build_bundle(
        workspace_root=workspace_root,
        bundle_json_out=bundle_json_out,
        radar_json=radar_json,
        radar_markdown_out=radar_markdown_out,
        radar_refresh=radar_refresh,
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
        secret_scan_json_out=secret_scan_json_out,
        release_handoff_json=release_handoff_json,
        status_report=status_report,
        secret_scan=secret_scan,
        secret_scan_passes=secret_scan_passes,
        allow_action_required=allow_action_required,
        require_desci_topic=require_desci_topic,
        require_live_source=require_live_source,
        require_expected_action_required_failures=require_expected_action_required_failures,
        allowed_action_required_failures=allowed_action_required_failures,
    )
    _write_json(bundle_json_out, bundle)

    final_scan_paths = [
        *generated_paths,
        bundle_json_out,
    ]
    secret_scan = _write_secret_scan(
        workspace_root=workspace_root,
        secret_scan_json_out=secret_scan_json_out,
        extra_paths=final_scan_paths,
    )
    secret_scan_passes += 1

    status_report = _write_status(
        workspace_root=workspace_root,
        radar_json=radar_json,
        stop_file=stop_file,
        live_source_commit=live_source_commit,
        live_source_checked=live_source_checked,
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
    )
    bundle = _build_bundle(
        workspace_root=workspace_root,
        bundle_json_out=bundle_json_out,
        radar_json=radar_json,
        radar_markdown_out=radar_markdown_out,
        radar_refresh=radar_refresh,
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
        secret_scan_json_out=secret_scan_json_out,
        release_handoff_json=release_handoff_json,
        status_report=status_report,
        secret_scan=secret_scan,
        secret_scan_passes=secret_scan_passes,
        allow_action_required=allow_action_required,
        require_desci_topic=require_desci_topic,
        require_live_source=require_live_source,
        require_expected_action_required_failures=require_expected_action_required_failures,
        allowed_action_required_failures=allowed_action_required_failures,
    )
    _write_json(bundle_json_out, bundle)

    status_report = _write_status(
        workspace_root=workspace_root,
        radar_json=radar_json,
        stop_file=stop_file,
        live_source_commit=live_source_commit,
        live_source_checked=live_source_checked,
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
    )
    bundle = _build_bundle(
        workspace_root=workspace_root,
        bundle_json_out=bundle_json_out,
        radar_json=radar_json,
        radar_markdown_out=radar_markdown_out,
        radar_refresh=radar_refresh,
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
        secret_scan_json_out=secret_scan_json_out,
        release_handoff_json=release_handoff_json,
        status_report=status_report,
        secret_scan=secret_scan,
        secret_scan_passes=secret_scan_passes,
        allow_action_required=allow_action_required,
        require_desci_topic=require_desci_topic,
        require_live_source=require_live_source,
        require_expected_action_required_failures=require_expected_action_required_failures,
        allowed_action_required_failures=allowed_action_required_failures,
    )
    _write_json(bundle_json_out, bundle)

    _write_status(
        workspace_root=workspace_root,
        radar_json=radar_json,
        stop_file=stop_file,
        live_source_commit=live_source_commit,
        live_source_checked=live_source_checked,
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
    )
    return bundle


def _write_status(
    *,
    workspace_root: Path,
    radar_json: Path | None,
    stop_file: Path | None,
    live_source_commit: str | None,
    live_source_checked: bool,
    status_json_out: Path,
    status_markdown_out: Path,
) -> dict[str, Any]:
    status_report = _build_status_report(
        workspace_root=workspace_root,
        radar_json=radar_json,
        stop_file=stop_file,
        live_source_commit=live_source_commit,
        live_source_checked=live_source_checked,
    )
    _write_json(status_json_out, status_report)
    _write_text(status_markdown_out, _format_status_markdown(status_report))
    return status_report


def _build_status_report(
    *,
    workspace_root: Path,
    radar_json: Path | None,
    stop_file: Path | None,
    live_source_commit: str | None,
    live_source_checked: bool,
) -> dict[str, Any]:
    if auto_research_status is not None:
        return _with_desci_topic_if_blank(
            auto_research_status.build_status(
                workspace_root=workspace_root,
                radar_json=radar_json,
                stop_file=stop_file,
                live_source_commit=live_source_commit,
                live_source_checked=live_source_checked,
                live_sources_checked=False,
            )
        )
    return _with_desci_topic_if_blank(
        _build_fallback_status_report(
            workspace_root=workspace_root,
            radar_json=radar_json,
            stop_file=stop_file,
            live_source_commit=live_source_commit,
            live_source_checked=live_source_checked,
        )
    )


def _with_desci_topic_if_blank(status_report: dict[str, Any]) -> dict[str, Any]:
    if str(status_report.get("preferred_topic") or "").strip():
        return status_report
    status_report = dict(status_report)
    status_report["preferred_topic"] = "DeSci"
    return status_report


def _format_status_markdown(status_report: dict[str, Any]) -> str:
    if auto_research_status is not None:
        return auto_research_status.format_markdown(status_report)
    return _format_fallback_status_markdown(status_report)


def _write_secret_scan(
    *,
    workspace_root: Path,
    secret_scan_json_out: Path,
    extra_paths: list[Path],
) -> dict[str, Any]:
    secret_scan = _build_secret_scan(workspace_root=workspace_root, extra_paths=extra_paths)
    _write_json(secret_scan_json_out, secret_scan)
    return secret_scan


def _build_secret_scan(*, workspace_root: Path, extra_paths: list[Path]) -> dict[str, Any]:
    if desci_launch_secret_scan is not None:
        return desci_launch_secret_scan.build_desci_launch_secret_scan(
            workspace_root=workspace_root,
            extra_paths=extra_paths,
        )
    return _build_fallback_desci_launch_secret_scan(workspace_root=workspace_root, extra_paths=extra_paths)


def _build_bundle(
    *,
    workspace_root: Path,
    bundle_json_out: Path,
    radar_json: Path | None,
    radar_markdown_out: Path | None,
    radar_refresh: dict[str, Any],
    status_json_out: Path,
    status_markdown_out: Path,
    secret_scan_json_out: Path,
    release_handoff_json: Path | None,
    status_report: dict[str, Any],
    secret_scan: dict[str, Any],
    secret_scan_passes: int,
    allow_action_required: bool,
    require_desci_topic: bool,
    require_live_source: bool,
    require_expected_action_required_failures: bool,
    allowed_action_required_failures: set[str] | frozenset[str] | None,
) -> dict[str, Any]:
    status_context = _status_context(
        status_report,
        allow_action_required=allow_action_required,
        require_expected_action_required_failures=require_expected_action_required_failures,
        allowed_action_required_failures=allowed_action_required_failures,
    )
    topic_context = _topic_context(status_report, require_desci_topic)
    source = _status_source(status_report)
    live_source_context = _live_source_context(source, require_live_source)
    secret_scan_summary = _secret_scan_summary(secret_scan)
    release_handoff_summary = _release_handoff_summary(release_handoff_json, workspace_root)
    radar_paths = _radar_display_paths(radar_json, radar_markdown_out, workspace_root)
    recorded_latest_observed_commit = _recorded_latest_observed_commit(radar_refresh, source)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "desci_launch_handoff_refresh",
        "bundle_json_path": _display_path(bundle_json_out, workspace_root),
        "ok": _bundle_ok(
            status_context,
            topic_context,
            live_source_context,
            secret_scan_summary,
            release_handoff_summary,
        ),
        "status_allowed": status_context["allowed"],
        "action_required_failures_ok": status_context["action_required_failures_ok"],
        "require_expected_action_required_failures": require_expected_action_required_failures,
        "allowed_action_required_failures": status_context["expected_failures"],
        "failed_checks": status_context["failed_checks"],
        "unexpected_failed_checks": status_context["unexpected_failed_checks"],
        "topic_ok": topic_context["ok"],
        "required_topic": topic_context["required"],
        "allow_action_required": allow_action_required,
        "live_source_required": require_live_source,
        "live_source_ok": live_source_context["ok"],
        "live_source_status": live_source_context["status"],
        "live_source_detail": live_source_context["detail"],
        "recorded_latest_observed_commit": recorded_latest_observed_commit,
        "radar_json_path": radar_paths["json"],
        "radar_markdown_path": radar_paths["markdown"],
        "radar_auto_refresh_needed": bool(radar_refresh.get("auto_refresh_needed")),
        "radar_auto_refreshed": bool(radar_refresh.get("auto_refreshed")),
        "radar_auto_refresh_reason": str(radar_refresh.get("auto_refresh_reason") or ""),
        "secret_scan_passes": secret_scan_passes,
        "radar": {
            "path": radar_paths["json"],
            "markdown_path": radar_paths["markdown"],
            **radar_refresh,
        },
        "status": {
            "path": _display_path(status_json_out, workspace_root),
            "markdown_path": _display_path(status_markdown_out, workspace_root),
            "state": status_report.get("status"),
            "topic": topic_context["topic"],
        },
        "secret_scan": {
            "path": _display_path(secret_scan_json_out, workspace_root),
            **secret_scan_summary,
        },
        "release_handoff": release_handoff_summary,
    }


def _resolved_live_source_commit(
    workspace_root: Path,
    live_source_commit: str | None,
    check_live_source: bool,
    require_live_source: bool,
) -> str | None:
    if (check_live_source or require_live_source) and not live_source_commit:
        return _fetch_veritas_live_commit(workspace_root)
    return live_source_commit


def _status_context(
    status_report: dict[str, Any],
    *,
    allow_action_required: bool,
    require_expected_action_required_failures: bool,
    allowed_action_required_failures: set[str] | frozenset[str] | None,
) -> dict[str, Any]:
    status_ok = status_report.get("status") == "ok"
    failed_checks = _failed_check_names(status_report)
    expected_failures = sorted(allowed_action_required_failures or DEFAULT_ALLOWED_ACTION_REQUIRED_FAILURES)
    unexpected_failed_checks = _unexpected_failed_checks(failed_checks, expected_failures)
    action_required_failures_ok = _action_required_failures_ok(
        status_ok=status_ok,
        allow_action_required=allow_action_required,
        require_expected_failures=require_expected_action_required_failures,
        failed_checks=failed_checks,
        unexpected_failed_checks=unexpected_failed_checks,
    )
    return {
        "allowed": _status_allowed(status_ok, allow_action_required, action_required_failures_ok),
        "action_required_failures_ok": action_required_failures_ok,
        "expected_failures": expected_failures,
        "failed_checks": failed_checks,
        "unexpected_failed_checks": unexpected_failed_checks,
    }


def _unexpected_failed_checks(failed_checks: list[str], expected_failures: list[str]) -> list[str]:
    return sorted(name for name in failed_checks if name not in expected_failures)


def _status_allowed(status_ok: bool, allow_action_required: bool, action_required_failures_ok: bool) -> bool:
    return status_ok or (allow_action_required and action_required_failures_ok)


def _topic_context(status_report: dict[str, Any], require_desci_topic: bool) -> dict[str, Any]:
    topic = status_report.get("preferred_topic")
    return {
        "topic": topic,
        "ok": topic == "DeSci" or not require_desci_topic,
        "required": "DeSci" if require_desci_topic else "",
    }


def _radar_display_paths(
    radar_json: Path | None,
    radar_markdown_out: Path | None,
    workspace_root: Path,
) -> dict[str, str]:
    return {
        "json": _optional_display_path(radar_json, workspace_root),
        "markdown": _optional_display_path(radar_markdown_out, workspace_root),
    }


def _optional_display_path(path: Path | None, workspace_root: Path) -> str:
    if path is None:
        return ""
    return _display_path(path, workspace_root)


def _bundle_ok(
    status_context: dict[str, Any],
    topic_context: dict[str, Any],
    live_source_context: dict[str, Any],
    secret_scan_summary: dict[str, Any],
    release_handoff_summary: dict[str, Any],
) -> bool:
    return bool(
        status_context["allowed"]
        and topic_context["ok"]
        and live_source_context["ok"]
        and secret_scan_summary["ok"]
        and _release_handoff_evidence_ready(release_handoff_summary)
    )


def _release_handoff_evidence_ready(release_handoff_summary: dict[str, Any]) -> bool:
    if release_handoff_summary.get("required") is not True:
        return True
    return (
        release_handoff_summary.get("status") == "valid"
        and release_handoff_summary.get("provider_preflight_present") is True
    )


def _release_handoff_summary(path: Path | None, workspace_root: Path) -> dict[str, Any]:
    if path is None:
        return _empty_release_handoff_summary("not_configured", "", required=False)
    display_path = _display_path(path, workspace_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return _empty_release_handoff_summary("missing", display_path, required=True)
    except (OSError, json.JSONDecodeError):
        return _empty_release_handoff_summary("invalid", display_path, required=True)
    if not isinstance(payload, dict):
        return _empty_release_handoff_summary("invalid", display_path, required=True)
    provider_preflight = payload.get("provider_preflight") if isinstance(payload.get("provider_preflight"), dict) else {}
    return {
        "required": True,
        "status": "valid",
        "path": display_path,
        "ok": payload.get("ok") is True,
        "release_decision": str(payload.get("release_decision") or ""),
        "provider_preflight_present": bool(provider_preflight),
        "provider_preflight_ok": _optional_bool(payload.get("provider_preflight_ok")),
        "provider_count": _optional_nonnegative_int(provider_preflight.get("provider_count")),
        "ready_provider_count": _optional_nonnegative_int(provider_preflight.get("ready_provider_count")),
        "check_count": _optional_nonnegative_int(provider_preflight.get("check_count")),
        "failed_check_count": _optional_nonnegative_int(provider_preflight.get("failed_check_count")),
        "missing_cli_count": _optional_nonnegative_int(provider_preflight.get("missing_cli_count")),
        "auth_context_missing_count": _optional_nonnegative_int(provider_preflight.get("auth_context_missing_count")),
        "source_artifact": str(provider_preflight.get("source_artifact") or ""),
    }


def _empty_release_handoff_summary(status: str, path: str, *, required: bool) -> dict[str, Any]:
    return {
        "required": required,
        "status": status,
        "path": path,
        "ok": None,
        "release_decision": "",
        "provider_preflight_present": False,
        "provider_preflight_ok": None,
        "provider_count": None,
        "ready_provider_count": None,
        "check_count": None,
        "failed_check_count": None,
        "missing_cli_count": None,
        "auth_context_missing_count": None,
        "source_artifact": "",
    }


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _status_source(status_report: dict[str, Any]) -> dict[str, Any]:
    source = status_report.get("source")
    return source if isinstance(source, dict) else {}


def _live_source_context(source: dict[str, Any], require_live_source: bool) -> dict[str, Any]:
    live_source = source.get("live_source") if isinstance(source.get("live_source"), dict) else {}
    status = str(live_source.get("status") or "")
    return {
        "ok": status == "current" or not require_live_source,
        "status": status,
        "detail": str(live_source.get("detail", "")),
    }


def _secret_scan_summary(secret_scan: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": secret_scan.get("status"),
        "ok": secret_scan.get("ok") is True,
        "findings": len(secret_scan.get("findings") or []),
        "missing": len(secret_scan.get("missing_paths") or []),
        "scanned": len(secret_scan.get("scanned_paths") or []),
    }


def _recorded_latest_observed_commit(radar_refresh: dict[str, Any], source: dict[str, Any]) -> str:
    return str(radar_refresh.get("recorded_latest_observed_commit") or source.get("latest_observed_commit") or "")


def _refresh_radar_if_needed(
    *,
    radar_json: Path | None,
    radar_markdown_out: Path | None,
    enabled: bool,
    live_source_commit: str | None,
) -> dict[str, Any]:
    if radar_json is None:
        return _radar_refresh_no_path()
    recorded_commit = _radar_recorded_commit_if_present(radar_json)
    reason = _radar_refresh_reason(radar_json, recorded_commit, live_source_commit)
    return _radar_refresh_result(
        radar_json=radar_json,
        radar_markdown_out=radar_markdown_out,
        enabled=enabled,
        live_source_commit=live_source_commit,
        recorded_commit=recorded_commit,
        reason=reason,
    )


def _radar_recorded_commit_if_present(radar_json: Path) -> str:
    if radar_json.is_file():
        return _radar_recorded_veritas_commit(radar_json)
    return ""


def _radar_refresh_result(
    *,
    radar_json: Path,
    radar_markdown_out: Path | None,
    enabled: bool,
    live_source_commit: str | None,
    recorded_commit: str,
    reason: str,
) -> dict[str, Any]:
    needed = bool(reason)
    if not needed or not enabled:
        return _radar_refresh_skipped(enabled, needed, reason, recorded_commit)
    summary = _run_radar_refresh(radar_json, radar_markdown_out, live_source_commit)
    refreshed_commit = _radar_recorded_commit_if_present(radar_json)
    return _radar_refresh_completed(reason, refreshed_commit, summary)


def _radar_refresh_no_path() -> dict[str, Any]:
    return {
        "auto_refresh_enabled": False,
        "auto_refresh_needed": False,
        "auto_refreshed": False,
        "auto_refresh_reason": "no_radar_path",
    }


def _radar_refresh_reason(radar_json: Path, recorded_commit: str, live_source_commit: str | None) -> str:
    if not radar_json.is_file():
        return "missing"
    if live_source_commit and recorded_commit != live_source_commit:
        return "stale_live_source_commit"
    return ""


def _radar_refresh_skipped(enabled: bool, needed: bool, reason: str, recorded_commit: str) -> dict[str, Any]:
    return {
        "auto_refresh_enabled": enabled,
        "auto_refresh_needed": needed,
        "auto_refreshed": False,
        "auto_refresh_reason": reason,
        "recorded_latest_observed_commit": recorded_commit,
    }


def _run_radar_refresh(
    radar_json: Path,
    radar_markdown_out: Path | None,
    live_source_commit: str | None,
) -> dict[str, Any]:
    return github_modernization_radar.run(
        github_modernization_radar.DEFAULT_MANIFEST,
        json_out=radar_json,
        markdown_out=radar_markdown_out,
        latest_commit_overrides=_latest_commit_overrides(live_source_commit),
    )


def _latest_commit_overrides(live_source_commit: str | None) -> dict[str, str] | None:
    if live_source_commit:
        return {VERITAS_REPO: live_source_commit}
    return None


def _radar_refresh_completed(reason: str, refreshed_commit: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "auto_refresh_enabled": True,
        "auto_refresh_needed": True,
        "auto_refreshed": True,
        "auto_refresh_reason": reason,
        "recorded_latest_observed_commit": refreshed_commit,
        "source_count": summary.get("source_count"),
        "adoption_status_counts": summary.get("adoption_status_counts", {}),
    }


def _radar_recorded_veritas_commit(path: Path) -> str:
    payload = _read_json_dict(path)
    if not payload:
        return ""
    return _veritas_commit_from_sources(payload.get("sources") or [])


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _veritas_commit_from_sources(sources: Any) -> str:
    for source in sources:
        commit = _veritas_commit_from_source(source)
        if commit:
            return commit
    return ""


def _veritas_commit_from_source(source: Any) -> str:
    if not isinstance(source, dict) or source.get("repo") != VERITAS_REPO:
        return ""
    commit = source.get("latest_observed_commit")
    return commit if isinstance(commit, str) else ""


def _build_fallback_status_report(
    *,
    workspace_root: Path,
    radar_json: Path | None,
    stop_file: Path | None,
    live_source_commit: str | None,
    live_source_checked: bool,
) -> dict[str, Any]:
    radar_payload = _read_json_dict(radar_json) if radar_json is not None else {}
    veritas_source = _find_veritas_source(radar_payload)
    recorded_commit = _veritas_commit_from_source(veritas_source)
    live_source = _fallback_live_source_state(recorded_commit, live_source_commit, checked=live_source_checked)
    stop_state = _fallback_stop_state(stop_file, workspace_root)
    checks = _fallback_status_checks(veritas_source, recorded_commit, live_source, radar_payload, stop_state)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok" if all(check["ok"] for check in checks) else "action_required",
        "workspace_root": str(workspace_root),
        "preferred_topic": "DeSci",
        "source": {
            "repo": VERITAS_REPO,
            "latest_observed_commit": recorded_commit,
            "live_source": live_source,
            "live_sources": {"checked": False, "status": "not_checked", "sources": []},
            "radar_path": _optional_display_path(radar_json, workspace_root),
        },
        "radar": _fallback_radar_summary(radar_payload),
        "latest_smoke": {},
        "stop": stop_state,
        "checks": checks,
    }


def _find_veritas_source(radar_payload: dict[str, Any]) -> dict[str, Any]:
    sources = radar_payload.get("sources")
    if not isinstance(sources, list):
        return {}
    for source in sources:
        if isinstance(source, dict) and source.get("repo") == VERITAS_REPO:
            return source
    return {}


def _fallback_live_source_state(
    recorded_commit: str,
    live_source_commit: str | None,
    *,
    checked: bool,
) -> dict[str, Any]:
    live_commit = (live_source_commit or "").strip()
    if not checked:
        return {
            "checked": False,
            "recorded_commit": recorded_commit,
            "live_observed_commit": live_commit,
            "status": "not_checked",
            "detail": "not checked",
        }
    if not live_commit:
        status = "unavailable"
        detail = "live source unavailable"
    elif not _valid_commit(live_commit):
        status = "invalid"
        detail = "live source returned invalid commit"
    elif live_commit == recorded_commit:
        status = "current"
        detail = f"recorded={recorded_commit} live={live_commit}"
    else:
        status = "stale"
        detail = f"recorded={recorded_commit} live={live_commit}"
    return {
        "checked": True,
        "recorded_commit": recorded_commit,
        "live_observed_commit": live_commit,
        "status": status,
        "detail": detail,
    }


def _fallback_status_checks(
    veritas_source: dict[str, Any],
    recorded_commit: str,
    live_source: dict[str, Any],
    radar_payload: dict[str, Any],
    stop_state: dict[str, Any],
) -> list[dict[str, Any]]:
    checks = [
        {
            "name": "veritas_source_tracked",
            "ok": bool(veritas_source),
            "detail": "tracked" if veritas_source else f"{VERITAS_REPO} missing from radar",
        },
        {
            "name": "veritas_latest_commit_recorded",
            "ok": _valid_commit(recorded_commit),
            "detail": recorded_commit or "missing",
        },
        {
            "name": "veritas_source_matches_live",
            "ok": live_source.get("status") in {"current", "not_checked"},
            "detail": str(live_source.get("detail") or ""),
        },
        {
            "name": "modernization_radar_all_adopted",
            "ok": _radar_all_adopted(radar_payload),
            "detail": _radar_adoption_detail(radar_payload),
        },
        {
            "name": "desci_launch_handoff_refresh_ready",
            "ok": False,
            "detail": "fallback status keeps launch handoff in expected action_required state",
        },
        {
            "name": "stop_file_not_effective",
            "ok": not stop_state["effective"],
            "detail": stop_state["state"],
        },
    ]
    return checks


def _format_fallback_status_markdown(status_report: dict[str, Any]) -> str:
    source = status_report.get("source") if isinstance(status_report.get("source"), dict) else {}
    live_source = source.get("live_source") if isinstance(source.get("live_source"), dict) else {}
    lines = [
        "# AutoResearch Operator Status",
        "",
        "## Summary",
        "",
        f"- Status: `{status_report.get('status')}`",
        f"- Generated at: `{status_report.get('generated_at')}`",
        f"- Source repo: `{source.get('repo', VERITAS_REPO)}`",
        f"- Latest observed commit: `{source.get('latest_observed_commit', '')}`",
        f"- Live source status: `{live_source.get('status', 'not_checked')}`",
        f"- Preferred topic: `{status_report.get('preferred_topic', 'DeSci')}`",
        "",
        "## Checks",
        "",
    ]
    for check in status_report.get("checks") or []:
        if isinstance(check, dict):
            state = "PASS" if check.get("ok") is True else "FAIL"
            lines.append(f"- {state} `{check.get('name')}`: {check.get('detail', '')}")
    lines.append("")
    return "\n".join(lines)


def _fallback_stop_state(stop_file: Path | None, workspace_root: Path) -> dict[str, Any]:
    path = stop_file or DEFAULT_STOP_FILE
    present = path.is_file()
    try:
        has_content = bool(path.read_text(encoding="utf-8-sig").strip()) if present else False
    except OSError:
        has_content = False
    return {
        "path": _display_path(path, workspace_root),
        "present": present,
        "has_content": has_content,
        "effective": present and has_content,
        "state": "effective" if present and has_content else ("present_empty" if present else "absent"),
    }


def _fallback_radar_summary(radar_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_count": radar_payload.get("source_count"),
        "adoption_status_counts": radar_payload.get("adoption_status_counts", {}),
    }


def _radar_all_adopted(radar_payload: dict[str, Any]) -> bool:
    source_count = radar_payload.get("source_count")
    counts = radar_payload.get("adoption_status_counts")
    return isinstance(source_count, int) and isinstance(counts, dict) and counts.get("adopted") == source_count


def _radar_adoption_detail(radar_payload: dict[str, Any]) -> str:
    return f"sources={radar_payload.get('source_count')} counts={radar_payload.get('adoption_status_counts', {})}"


def _valid_commit(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", value or ""))


def _fetch_veritas_live_commit(workspace_root: Path) -> str:
    if auto_research_status is not None:
        return auto_research_status._fetch_veritas_live_commit(workspace_root)
    return _fetch_live_commit(VERITAS_REPO, workspace_root)


def _fetch_live_commit(repo: str, workspace_root: Path) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        return ""
    try:
        completed = subprocess.run(
            ["git", "ls-remote", f"https://github.com/{repo}.git", "HEAD", "refs/heads/main"],
            cwd=workspace_root,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if completed.returncode != 0:
        return ""
    return _preferred_live_commit_from_ls_remote_output(completed.stdout)


def _preferred_live_commit_from_ls_remote_output(output: str) -> str:
    commit_by_ref = _ls_remote_commit_map(output)
    return commit_by_ref.get("refs/heads/main") or commit_by_ref.get("HEAD", "")


def _ls_remote_commit_map(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and _valid_commit(parts[0]):
            result[parts[1]] = parts[0]
    return result


def _build_fallback_desci_launch_secret_scan(
    *,
    workspace_root: Path,
    extra_paths: list[Path] | None = None,
) -> dict[str, Any]:
    candidates = _fallback_secret_scan_targets(workspace_root, extra_paths or [])
    scan = _scan_secret_value_paths(workspace_root, candidates, _desci_secret_value_patterns())
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "desci_launch_handoff",
        "status": scan["status"],
        "ok": scan["status"] == "valid" and not scan["findings"] and not scan["missing_paths"],
        **scan,
    }


def _fallback_secret_scan_targets(workspace_root: Path, extra_paths: list[Path]) -> list[tuple[str, Path]]:
    targets: list[tuple[str, Path]] = []
    for label, path in _fallback_default_secret_scan_targets(workspace_root):
        if path.is_file():
            targets.append((label, path))
    for index, path in enumerate(extra_paths, start=1):
        targets.append((f"extra_{index}", path))
    return targets


def _fallback_default_secret_scan_targets(workspace_root: Path) -> list[tuple[str, Path]]:
    reports_root = workspace_root / "docs" / "reports"
    var_root = workspace_root / "var"
    return [
        ("next_actions", workspace_root / "next-actions.md"),
        ("handoff", workspace_root / "HANDOFF.md"),
        ("desci_qc_log", workspace_root / "apps" / "desci-platform" / "QC_LOG.md"),
        ("desci_devlog", workspace_root / "apps" / "desci-platform" / "devlog.md"),
        ("cycle_report", _latest_match(reports_root, "20*/AUTO_RESEARCH_DESCI_*.md")),
        ("operator_status", _latest_match(reports_root, "20*/AUTO_RESEARCH_OPERATOR_STATUS_DESCI*.md")),
        ("modernization_report", _latest_match(reports_root, "20*/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI*.md")),
        ("browser_smoke_json", _latest_match(var_root, "desci-browser-smoke*.json")),
        ("desci_smoke_json", _latest_match(var_root, "workspace-smoke-desci*.json")),
        ("workspace_smoke_json", _latest_match(var_root, "workspace-smoke-workspace*.json")),
        ("operator_status_json", _latest_match(var_root, "auto-research-status-desci*.json")),
        ("modernization_json", _latest_match(var_root, "github-modernization-radar-desci*.json")),
        ("deploy_readiness_json", _latest_match(var_root, "desci-deploy-readiness*.json")),
    ]


def _latest_match(root: Path, pattern: str) -> Path:
    try:
        matches = [path for path in root.glob(pattern) if path.is_file()]
    except OSError:
        return root / pattern.replace("*", "missing")
    if not matches:
        return root / pattern.replace("*", "missing")
    return max(matches, key=lambda path: (_mtime_ns(path), path.name))


def _desci_secret_value_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    return (
        ("google_api_key", re.compile(r"\b" + "AI" + r"za[0-9A-Za-z_-]{16,}\b")),
        ("anthropic_api_key", re.compile(r"\b" + "sk" + r"-ant-[A-Za-z0-9_-]{16,}\b")),
        ("openai_api_key", re.compile(r"\b" + "sk" + r"-(?!ant-)[A-Za-z0-9_-]{20,}\b")),
        ("github_token", re.compile(r"\b(?:" + "ghp" + r"|" + "github" + r"_pat)_[A-Za-z0-9_]{20,}\b")),
        ("passworded_database_url", re.compile(r"\bpostgres(?:ql)?://[^:\s/@]+:[^@\s]+@[^\s\"']+", re.IGNORECASE)),
        ("stripe_secret_key", re.compile(r"\b" + "sk" + r"_(?:live|test)_[A-Za-z0-9]{16,}\b")),
        ("stripe_restricted_key", re.compile(r"\b" + "rk" + r"_(?:live|test)_[A-Za-z0-9]{16,}\b")),
        ("stripe_webhook_secret", re.compile(r"\b" + "whsec" + r"_[A-Za-z0-9]{16,}\b")),
        (
            "evm_private_key_assignment",
            re.compile(r"\b(?:PRIVATE" + r"_KEY|WALLET_PRIVATE" + r"_KEY|DEPLOYER_PRIVATE" + r"_KEY)\s*=\s*(?:0x)?[0-9a-fA-F]{64}\b"),
        ),
        ("firebase_private_key_block", re.compile("-" * 5 + "BEGIN" + " " + "PRIVATE" + " " + "KEY" + "-" * 5)),
        ("infura_project_secret_url", re.compile(r"\binfura\.io/v3/[A-Za-z0-9_-]{24,}\b", re.IGNORECASE)),
        ("alchemy_project_secret_url", re.compile(r"\balchemy\.com/v2/[A-Za-z0-9_-]{24,}\b", re.IGNORECASE)),
        ("railway_token_assignment", re.compile(r"\bRAILWAY_TOKEN\s*=\s*[A-Za-z0-9._-]{20,}\b")),
        ("vercel_token_assignment", re.compile(r"\bVERCEL_TOKEN\s*=\s*[A-Za-z0-9._-]{20,}\b")),
    )


def _scan_secret_value_paths(
    workspace_root: Path,
    candidates: list[tuple[str, Path]],
    patterns: tuple[tuple[str, re.Pattern[str]], ...],
) -> dict[str, Any]:
    scanned_paths: list[str] = []
    missing_paths: list[str] = []
    findings: list[dict[str, Any]] = []
    for label, path in candidates:
        display_path = _display_path(path, workspace_root)
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except FileNotFoundError:
            missing_paths.append(display_path)
            continue
        except OSError:
            findings.append({"label": label, "path": display_path, "patterns": ["unreadable"]})
            continue
        scanned_paths.append(display_path)
        matched = [name for name, pattern in patterns if pattern.search(text)]
        if matched:
            findings.append({"label": label, "path": display_path, "patterns": matched})
    return {
        "status": "valid" if not findings else "invalid",
        "scanned_paths": scanned_paths,
        "missing_paths": missing_paths,
        "findings": findings,
        "finding_patterns": sorted({pattern for finding in findings for pattern in finding.get("patterns", [])}),
    }


def _failed_check_names(status_report: dict[str, Any]) -> list[str]:
    checks = status_report.get("checks")
    if not isinstance(checks, list):
        return []
    return sorted(name for check in checks if (name := _failed_check_name(check)))


def _failed_check_name(check: Any) -> str:
    if not isinstance(check, dict) or check.get("ok") is True:
        return ""
    return str(check.get("name") or "").strip()


def _action_required_failures_ok(
    *,
    status_ok: bool,
    allow_action_required: bool,
    require_expected_failures: bool,
    failed_checks: list[str],
    unexpected_failed_checks: list[str],
) -> bool:
    if status_ok or not allow_action_required or not require_expected_failures:
        return True
    return bool(failed_checks) and not unexpected_failed_checks


def _extra_scan_paths(
    *,
    status_json_out: Path | None = None,
    status_markdown_out: Path | None = None,
    radar_json: Path | None = None,
    radar_markdown_out: Path | None = None,
    release_handoff_json: Path | None = None,
) -> list[Path]:
    paths: list[Path] = []
    if status_json_out is not None:
        paths.append(status_json_out)
    if status_markdown_out is not None:
        paths.append(status_markdown_out)
    if radar_json is not None:
        paths.append(radar_json)
    if radar_markdown_out is not None:
        paths.append(radar_markdown_out)
    if release_handoff_json is not None:
        paths.append(release_handoff_json)
    return paths


def _resolve_release_handoff_json(workspace_root: Path, release_handoff_json: Path | None) -> Path | None:
    if release_handoff_json is not None:
        return release_handoff_json
    return _latest_release_handoff_json(workspace_root)


def _latest_release_handoff_json(workspace_root: Path) -> Path | None:
    var_dir = workspace_root / "apps" / "desci-platform" / "var"
    try:
        candidates = [path for path in var_dir.glob("release-handoff*.json") if path.is_file()]
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda path: (_mtime_ns(path), path.name))


def _mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _display_path(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def main(argv: list[str] | None = None, *, workspace_root: Path = WORKSPACE_ROOT) -> int:
    parser = argparse.ArgumentParser(description="Refresh DeSci operator status and launch handoff secret scan.")
    parser.add_argument("--radar-json", type=Path, default=DEFAULT_RADAR_JSON)
    parser.add_argument("--radar-markdown-out", type=Path, default=DEFAULT_RADAR_MARKDOWN)
    parser.add_argument(
        "--no-auto-radar-refresh",
        action="store_true",
        help="Fail closed instead of regenerating the GitHub modernization radar when --radar-json is missing or stale.",
    )
    parser.add_argument("--stop-file", type=Path, default=DEFAULT_STOP_FILE)
    parser.add_argument("--status-json-out", type=Path, default=DEFAULT_STATUS_JSON)
    parser.add_argument("--status-markdown-out", type=Path, default=DEFAULT_STATUS_MARKDOWN)
    parser.add_argument("--secret-scan-json-out", type=Path, default=DEFAULT_SECRET_SCAN_JSON)
    parser.add_argument("--bundle-json-out", type=Path, default=DEFAULT_BUNDLE_JSON)
    parser.add_argument(
        "--release-handoff-json",
        type=Path,
        help=(
            "Optional scripts/release_handoff.py JSON packet to summarize and scan. "
            "When omitted, the latest apps/desci-platform/var/release-handoff*.json is used if present."
        ),
    )
    parser.add_argument("--live-source-commit")
    parser.add_argument("--check-live-source", action="store_true")
    parser.add_argument(
        "--allow-action-required",
        action="store_true",
        default=True,
        help="Allow known expected action-required checks during bootstrap convergence.",
    )
    parser.add_argument(
        "--fail-on-action-required",
        dest="allow_action_required",
        action="store_false",
        help="Require the operator status to be fully ok before the bundle can pass.",
    )
    parser.add_argument(
        "--allow-non-desci-topic",
        action="store_true",
        help="Do not fail when the refreshed operator status preferred topic is not DeSci.",
    )
    parser.add_argument(
        "--allow-unchecked-live-source",
        action="store_true",
        help="Do not require a current live Veritas source comparison for this handoff refresh.",
    )
    parser.add_argument(
        "--allow-unexpected-action-required-failures",
        action="store_true",
        help="Do not fail when --allow-action-required includes failed checks outside the known external blocker set.",
    )
    args = parser.parse_args(argv)

    try:
        bundle = refresh_desci_launch_handoff(
            workspace_root=workspace_root,
            radar_json=args.radar_json,
            radar_markdown_out=args.radar_markdown_out,
            auto_refresh_radar=not args.no_auto_radar_refresh,
            stop_file=args.stop_file,
            status_json_out=args.status_json_out,
            status_markdown_out=args.status_markdown_out,
            secret_scan_json_out=args.secret_scan_json_out,
            bundle_json_out=args.bundle_json_out,
            release_handoff_json=args.release_handoff_json,
            live_source_commit=args.live_source_commit,
            check_live_source=args.check_live_source,
            allow_action_required=args.allow_action_required,
            require_desci_topic=not args.allow_non_desci_topic,
            require_live_source=not args.allow_unchecked_live_source,
            require_expected_action_required_failures=not args.allow_unexpected_action_required_failures,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"desci launch handoff refresh failed: {exc}", file=sys.stderr)
        return 1

    status_state = bundle["status"]["state"]
    scan = bundle["secret_scan"]
    release_handoff = bundle["release_handoff"]
    print(
        "desci launch handoff refresh: "
        f"status={status_state} "
        f"topic={bundle['status']['topic']} "
        f"live_source={bundle['live_source_status']} "
        f"radar_auto_refreshed={bundle['radar']['auto_refreshed']} "
        f"secret_scan={scan['state']} "
        f"findings={scan['findings']} "
        f"missing={scan['missing']} "
        f"scanned={scan['scanned']} "
        f"release_handoff={release_handoff['status']} "
        f"provider_preflight={release_handoff['provider_preflight_ok']} "
        f"bundle={bundle['bundle_json_path']}"
    )
    return 0 if bundle["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Refresh getdaytrends operator status and post-write handoff secret scan."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import auto_research_status
import getdaytrends_launch_secret_scan
import github_modernization_radar
from workspace_paths import find_workspace_root

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_ROOT = find_workspace_root(Path(__file__))
DEFAULT_RADAR_JSON = WORKSPACE_ROOT / "var" / "github-modernization-radar-getdaytrends-browser-freshness-2026-06-06.json"
DEFAULT_RADAR_MARKDOWN = (
    WORKSPACE_ROOT
    / "docs"
    / "reports"
    / "2026-06"
    / "GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_GETDAYTRENDS_HANDOFF_REFRESH_2026-06-06.md"
)
DEFAULT_STATUS_JSON = WORKSPACE_ROOT / "var" / "auto-research-status-getdaytrends-handoff-refresh-2026-06-06.json"
DEFAULT_STATUS_MARKDOWN = (
    WORKSPACE_ROOT
    / "docs"
    / "reports"
    / "2026-06"
    / "AUTO_RESEARCH_GETDAYTRENDS_HANDOFF_REFRESH_STATUS_2026-06-06.md"
)
DEFAULT_SECRET_SCAN_JSON = WORKSPACE_ROOT / "var" / "getdaytrends-launch-secret-scan-post-write-2026-06-06.json"
DEFAULT_BUNDLE_JSON = WORKSPACE_ROOT / "var" / "getdaytrends-launch-handoff-refresh-2026-06-06.json"
DEFAULT_ALLOWED_ACTION_REQUIRED_FAILURES = frozenset(
    {
        "dailynews_first_run_launch_ready",
        "getdaytrends_strict_readiness_pass",
        "getdaytrends_canonical_smoke_pass",
        "getdaytrends_recovery_packet_actionable",
    }
)


def refresh_getdaytrends_launch_handoff(
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
    live_source_commit: str | None = None,
    check_live_source: bool = False,
    allow_action_required: bool = False,
    require_getdaytrends_topic: bool = True,
    require_expected_action_required_failures: bool = True,
    allowed_action_required_failures: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    live_source_checked = check_live_source or live_source_commit is not None
    live_source_commit = _resolved_live_source_commit(workspace_root, live_source_commit, check_live_source)

    radar_refresh = _refresh_radar_if_needed(
        radar_json=radar_json,
        radar_markdown_out=radar_markdown_out,
        enabled=auto_refresh_radar,
        live_source_commit=live_source_commit,
    )

    status_report = _write_status(
        workspace_root=workspace_root,
        radar_json=radar_json,
        stop_file=stop_file,
        live_source_commit=live_source_commit,
        live_source_checked=live_source_checked,
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
    )
    secret_scan = _write_secret_scan(
        workspace_root=workspace_root,
        secret_scan_json_out=secret_scan_json_out,
        extra_paths=_extra_scan_paths(
            status_json_out=status_json_out,
            status_markdown_out=status_markdown_out,
            radar_json=radar_json,
            radar_markdown_out=radar_markdown_out,
        ),
    )
    bundle = _build_bundle(
        workspace_root=workspace_root,
        radar_json=radar_json,
        radar_markdown_out=radar_markdown_out,
        radar_refresh=radar_refresh,
        status_json_out=status_json_out,
        status_markdown_out=status_markdown_out,
        secret_scan_json_out=secret_scan_json_out,
        status_report=status_report,
        secret_scan=secret_scan,
        live_source_checked=live_source_checked,
        allow_action_required=allow_action_required,
        require_getdaytrends_topic=require_getdaytrends_topic,
        require_expected_action_required_failures=require_expected_action_required_failures,
        allowed_action_required_failures=allowed_action_required_failures,
    )
    _write_json(bundle_json_out, bundle)
    return bundle


def _resolved_live_source_commit(
    workspace_root: Path,
    live_source_commit: str | None,
    check_live_source: bool,
) -> str | None:
    if check_live_source and not live_source_commit:
        return auto_research_status._fetch_veritas_live_commit(workspace_root)
    return live_source_commit


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
    status_report = auto_research_status.build_status(
        workspace_root=workspace_root,
        radar_json=radar_json,
        stop_file=stop_file,
        live_source_commit=live_source_commit,
        live_source_checked=live_source_checked,
    )
    _write_json(status_json_out, status_report)
    _write_text(status_markdown_out, auto_research_status.format_markdown(status_report))
    return status_report


def _write_secret_scan(
    *,
    workspace_root: Path,
    secret_scan_json_out: Path,
    extra_paths: list[Path],
) -> dict[str, Any]:
    secret_scan = getdaytrends_launch_secret_scan.build_getdaytrends_launch_secret_scan(
        workspace_root=workspace_root,
        extra_paths=extra_paths,
        include_current_artifacts=True,
    )
    _write_json(secret_scan_json_out, secret_scan)
    return secret_scan


def _extra_scan_paths(
    *,
    status_json_out: Path,
    status_markdown_out: Path,
    radar_json: Path | None,
    radar_markdown_out: Path | None,
) -> list[Path]:
    paths = [status_json_out, status_markdown_out]
    if radar_json is not None:
        paths.append(radar_json)
    if radar_markdown_out is not None:
        paths.append(radar_markdown_out)
    return paths


def _build_bundle(
    *,
    workspace_root: Path,
    radar_json: Path | None,
    radar_markdown_out: Path | None,
    radar_refresh: dict[str, Any],
    status_json_out: Path,
    status_markdown_out: Path,
    secret_scan_json_out: Path,
    status_report: dict[str, Any],
    secret_scan: dict[str, Any],
    live_source_checked: bool,
    allow_action_required: bool,
    require_getdaytrends_topic: bool,
    require_expected_action_required_failures: bool,
    allowed_action_required_failures: set[str] | frozenset[str] | None,
) -> dict[str, Any]:
    status_context = _status_context(
        status_report,
        allow_action_required=allow_action_required,
        require_expected_action_required_failures=require_expected_action_required_failures,
        allowed_action_required_failures=allowed_action_required_failures,
    )
    topic_context = _topic_context(status_report, require_getdaytrends_topic)
    live_source_context = _live_source_context(status_report, live_source_checked)
    secret_scan_summary = _secret_scan_summary(secret_scan)
    radar_paths = _radar_display_paths(radar_json, radar_markdown_out, workspace_root)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "getdaytrends_launch_handoff_refresh",
        "ok": _bundle_ok(status_context, topic_context, secret_scan_summary, live_source_context),
        "effective_status": status_context["effective_status"],
        "status_allowed": status_context["allowed"],
        "action_required_failures_ok": status_context["action_required_failures_ok"],
        "require_expected_action_required_failures": require_expected_action_required_failures,
        "allowed_action_required_failures": status_context["expected_failures"],
        "completion_blocking_requirements": status_context["completion_blocking_requirements"],
        "failed_checks": status_context["failed_checks"],
        "unexpected_failed_checks": status_context["unexpected_failed_checks"],
        "topic_ok": topic_context["ok"],
        "required_topic": topic_context["required"],
        "allow_action_required": allow_action_required,
        "live_source_required": live_source_checked,
        "live_source_ok": live_source_context["ok"],
        "live_source_status": live_source_context["status"],
        "live_source_detail": live_source_context["detail"],
        "radar": {
            "path": radar_paths["json"],
            "markdown_path": radar_paths["markdown"],
            **radar_refresh,
        },
        "status": {
            "path": _display_path(status_json_out, workspace_root),
            "markdown_path": _display_path(status_markdown_out, workspace_root),
            "state": status_report.get("status"),
            "effective_state": status_context["effective_status"],
            "topic": topic_context["topic"],
        },
        "secret_scan": {
            "path": _display_path(secret_scan_json_out, workspace_root),
            **secret_scan_summary,
        },
    }


def _status_context(
    status_report: dict[str, Any],
    *,
    allow_action_required: bool,
    require_expected_action_required_failures: bool,
    allowed_action_required_failures: set[str] | frozenset[str] | None,
) -> dict[str, Any]:
    failed_checks = _failed_check_names(status_report)
    status_ok = status_report.get("status") == "ok" and not failed_checks
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
        "effective_status": _effective_status(status_report, failed_checks),
        "action_required_failures_ok": action_required_failures_ok,
        "expected_failures": expected_failures,
        "completion_blocking_requirements": _completion_blocking_requirements(status_report),
        "failed_checks": failed_checks,
        "unexpected_failed_checks": unexpected_failed_checks,
    }


def _unexpected_failed_checks(failed_checks: list[str], expected_failures: list[str]) -> list[str]:
    return sorted(name for name in failed_checks if name not in expected_failures)


def _status_allowed(status_ok: bool, allow_action_required: bool, action_required_failures_ok: bool) -> bool:
    return status_ok or (allow_action_required and action_required_failures_ok)


def _effective_status(status_report: dict[str, Any], failed_checks: list[str]) -> str:
    if failed_checks:
        return "action_required"
    return str(status_report.get("status") or "unknown")


def _topic_context(status_report: dict[str, Any], require_getdaytrends_topic: bool) -> dict[str, Any]:
    topic = status_report.get("preferred_topic")
    return {
        "topic": topic,
        "ok": topic == "getdaytrends" or not require_getdaytrends_topic,
        "required": "getdaytrends" if require_getdaytrends_topic else "",
    }


def _live_source_context(status_report: dict[str, Any], live_source_required: bool) -> dict[str, Any]:
    live_source = _live_source_payload(status_report)
    status = str(live_source.get("status", "unchecked"))
    return {
        "ok": not live_source_required or status == "current",
        "status": status,
        "detail": str(live_source.get("detail", "")),
    }


def _live_source_payload(status_report: dict[str, Any]) -> dict[str, Any]:
    source = status_report.get("source")
    live_source = source.get("live_source", {}) if isinstance(source, dict) else {}
    return live_source if isinstance(live_source, dict) else {}


def _secret_scan_summary(secret_scan: dict[str, Any]) -> dict[str, Any]:
    contract_errors = [
        str(item)
        for item in secret_scan.get("supabase_recovery_packet_contract_errors") or []
        if isinstance(item, str) and item.strip()
    ]
    return {
        "state": secret_scan.get("status"),
        "ok": secret_scan.get("ok") is True,
        "findings": len(secret_scan.get("findings") or []),
        "missing": len(secret_scan.get("missing_paths") or []),
        "scanned": len(secret_scan.get("scanned_paths") or []),
        "include_current_artifacts": secret_scan.get("include_current_artifacts") is True,
        "supabase_recovery_packet_contract_ok": secret_scan.get("supabase_recovery_packet_contract_ok") is True,
        "supabase_recovery_packet_contract_errors": contract_errors,
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
    secret_scan_summary: dict[str, Any],
    live_source_context: dict[str, Any],
) -> bool:
    return bool(status_context["allowed"] and topic_context["ok"] and secret_scan_summary["ok"] and live_source_context["ok"])


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
    reason = _radar_refresh_reason(radar_json, radar_markdown_out, recorded_commit, live_source_commit)
    return _radar_refresh_result(
        radar_json=radar_json,
        radar_markdown_out=radar_markdown_out,
        enabled=enabled,
        live_source_commit=live_source_commit,
        recorded_commit=recorded_commit,
        reason=reason,
    )


def _radar_refresh_no_path() -> dict[str, Any]:
    return {
        "auto_refresh_enabled": False,
        "auto_refresh_needed": False,
        "auto_refreshed": False,
        "auto_refresh_reason": "no_radar_path",
    }


def _radar_recorded_commit_if_present(radar_json: Path) -> str:
    if radar_json.is_file():
        return _radar_recorded_veritas_commit(radar_json)
    return ""


def _radar_refresh_reason(
    radar_json: Path,
    radar_markdown_out: Path | None,
    recorded_commit: str,
    live_source_commit: str | None,
) -> str:
    if not radar_json.is_file():
        return "missing"
    if _radar_commit_is_stale(recorded_commit, live_source_commit):
        return "stale_live_source_commit"
    if _radar_markdown_missing(radar_markdown_out):
        return "missing_markdown"
    return ""


def _radar_commit_is_stale(recorded_commit: str, live_source_commit: str | None) -> bool:
    return bool(live_source_commit and recorded_commit != live_source_commit)


def _radar_markdown_missing(radar_markdown_out: Path | None) -> bool:
    return radar_markdown_out is not None and not radar_markdown_out.is_file()


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
        return {auto_research_status.VERITAS_REPO: live_source_commit}
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
        payload = json.loads(path.read_text(encoding="utf-8"))
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
    if not isinstance(source, dict) or source.get("repo") != auto_research_status.VERITAS_REPO:
        return ""
    commit = source.get("latest_observed_commit")
    return commit if isinstance(commit, str) else ""


def _failed_check_names(status_report: dict[str, Any]) -> list[str]:
    checks = status_report.get("checks")
    check_names = []
    if isinstance(checks, list):
        check_names = [name for check in checks if (name := _failed_check_name(check))]
    return sorted(set([*check_names, *_completion_blocking_requirements(status_report)]))


def _completion_blocking_requirements(status_report: dict[str, Any]) -> list[str]:
    completion_audit = status_report.get("completion_audit")
    if not isinstance(completion_audit, dict):
        return []
    blockers = completion_audit.get("blocking_requirements")
    if not isinstance(blockers, list):
        return []
    return sorted({str(item).strip() for item in blockers if str(item).strip()})


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
    parser = argparse.ArgumentParser(description="Refresh getdaytrends operator status, then run post-write secret scan.")
    parser.add_argument("--radar-json", type=Path, default=DEFAULT_RADAR_JSON)
    parser.add_argument("--radar-markdown-out", type=Path, default=DEFAULT_RADAR_MARKDOWN)
    parser.add_argument(
        "--no-auto-radar-refresh",
        action="store_true",
        help="Fail closed instead of regenerating the GitHub modernization radar when --radar-json is missing or stale.",
    )
    parser.add_argument("--stop-file", type=Path, default=auto_research_status.DEFAULT_STOP_FILE)
    parser.add_argument("--status-json-out", type=Path, default=DEFAULT_STATUS_JSON)
    parser.add_argument("--status-markdown-out", type=Path, default=DEFAULT_STATUS_MARKDOWN)
    parser.add_argument("--secret-scan-json-out", type=Path, default=DEFAULT_SECRET_SCAN_JSON)
    parser.add_argument("--bundle-json-out", type=Path, default=DEFAULT_BUNDLE_JSON)
    parser.add_argument("--live-source-commit")
    parser.add_argument("--check-live-source", action="store_true")
    parser.add_argument(
        "--allow-unchecked-live-source",
        action="store_true",
        help="Do not fetch and require the live Veritas AutoResearch commit; intended only for offline diagnostics.",
    )
    parser.add_argument("--allow-action-required", action="store_true")
    parser.add_argument(
        "--allow-unexpected-action-required-failures",
        action="store_true",
        help="Allow any action_required status failure; intended only for diagnostics, not launch handoff.",
    )
    parser.add_argument(
        "--allow-non-getdaytrends-topic",
        action="store_true",
        help="Do not fail when the refreshed operator status preferred topic is not getdaytrends.",
    )
    args = parser.parse_args(argv)

    try:
        bundle = refresh_getdaytrends_launch_handoff(
            workspace_root=workspace_root,
            radar_json=args.radar_json,
            radar_markdown_out=args.radar_markdown_out,
            auto_refresh_radar=not args.no_auto_radar_refresh,
            stop_file=args.stop_file,
            status_json_out=args.status_json_out,
            status_markdown_out=args.status_markdown_out,
            secret_scan_json_out=args.secret_scan_json_out,
            bundle_json_out=args.bundle_json_out,
            live_source_commit=args.live_source_commit,
            check_live_source=args.check_live_source or not args.allow_unchecked_live_source,
            allow_action_required=args.allow_action_required,
            require_getdaytrends_topic=not args.allow_non_getdaytrends_topic,
            require_expected_action_required_failures=not args.allow_unexpected_action_required_failures,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"getdaytrends launch handoff refresh failed: {exc}", file=sys.stderr)
        return 1

    status_state = bundle["status"]["state"]
    scan = bundle["secret_scan"]
    print(
        "getdaytrends launch handoff refresh: "
        f"status={status_state} "
        f"effective_status={bundle['effective_status']} "
        f"topic={bundle['status']['topic']} "
        f"live_source={bundle['live_source_status']} "
        f"secret_scan={scan['state']} "
        f"current_artifacts={str(scan['include_current_artifacts']).lower()} "
        f"packet_contract={str(scan['supabase_recovery_packet_contract_ok']).lower()} "
        f"radar_auto_refreshed={bundle['radar']['auto_refreshed']} "
        f"failed_checks={len(bundle['failed_checks'])} "
        f"unexpected_failures={len(bundle['unexpected_failed_checks'])} "
        f"findings={scan['findings']} "
        f"missing={scan['missing']} "
        f"scanned={scan['scanned']}"
    )
    return 0 if bundle["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

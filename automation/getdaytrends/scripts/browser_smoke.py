"""Run a live browser smoke for the getdaytrends dashboard."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROJECT_ROOT / "logs" / "smoke" / "dashboard_browser_latest.json"
DEFAULT_SCREENSHOT = PROJECT_ROOT / "logs" / "smoke" / "dashboard_browser_latest.png"
DEFAULT_TAP_SOURCE_REPORT = PROJECT_ROOT / "logs" / "smoke" / "dashboard_browser_tap_source_evidence.json"
DEFAULT_TAP_SOURCE_SCREENSHOT = PROJECT_ROOT / "logs" / "smoke" / "dashboard_browser_tap_source_evidence.png"
DEFAULT_TAP_SOURCE_FIXTURE_DB = PROJECT_ROOT / "logs" / "smoke" / "tap_source_evidence_fixture.db"
SAFE_DATABASE_UPDATE_FRAGMENTS = (
    "getdaytrends_update_credentials.py --database-url-stdin",
    "getdaytrends_update_credentials.py --database-url-stdin --write",
)
SAFE_PROVIDER_UPDATE_FRAGMENTS = (
    "GETDAYTRENDS_NEW_OPENAI_API_KEY",
    "GETDAYTRENDS_NEW_GOOGLE_API_KEY",
    "getdaytrends_update_credentials.py",
    "getdaytrends_update_credentials.py --write",
)
SUPABASE_REFERENCE_URL = "https://supabase.com/docs/guides/database/connecting-to-postgres"
SUPABASE_CIRCUIT_BREAKER_REFERENCE_URL = (
    "https://supabase.com/docs/guides/troubleshooting/"
    "supavisor-error-circuit-breaker-open-after-password-rotation-0fdb72"
)
MICROSOFT_SCHTASKS_QUERY_REFERENCE_URL = (
    "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-query"
)
MICROSOFT_SCHTASKS_CHANGE_REFERENCE_URL = (
    "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-change"
)
W3C_WCAG_TARGET_SIZE_MINIMUM_URL = "https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html"
W3C_WCAG_FOCUS_ORDER_URL = "https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html"
OPENAI_REFERENCE_URL = "https://developers.openai.com/api/docs/guides/production-best-practices#api-keys"
GOOGLE_AI_REFERENCE_URL = "https://ai.google.dev/gemini-api/docs/api-key"
REPLACEMENT_CHARACTER = chr(0xFFFD)
MOJIBAKE_MARKERS = (
    REPLACEMENT_CHARACTER,
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
MOJIBAKE_MARKERS = MOJIBAKE_MARKERS + tuple(chr(codepoint) for codepoint in range(0x80, 0xA0))
KOREAN_MOJIBAKE_PAIR_RE = re.compile(r"(?:\?[\u3130-\u318f\uac00-\ud7a3]|[\u3130-\u318f\uac00-\ud7a3]\?)")
CJK_COMPAT_IDEOGRAPH_RE = re.compile(r"[\uf900-\ufaff]")


def _visible_mojibake_markers(text: str) -> list[str]:
    markers = [marker for marker in MOJIBAKE_MARKERS if marker in text]
    if REPLACEMENT_CHARACTER in text:
        markers.append("replacement-character")
    compatibility_ideographs = len(CJK_COMPAT_IDEOGRAPH_RE.findall(text))
    if compatibility_ideographs >= 2 or (compatibility_ideographs >= 1 and text.count("?") >= 2):
        markers.append("compat-ideograph-mojibake")
    if text.count("?") >= 3 and len(KOREAN_MOJIBAKE_PAIR_RE.findall(text)) >= 2:
        markers.append("question-hangul-mojibake")
    return sorted(set(markers))


@dataclass(frozen=True)
class BrowserRun:
    ok: bool
    checks: list[dict[str, Any]]
    console_errors: list[str]
    console_warnings: list[str]
    page_errors: list[str]
    request_failures: list[str]
    screenshot: str


def _get_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _http_get(url: str, timeout: float = 2.0) -> tuple[int | None, str]:
    request = Request(url, headers={"User-Agent": "getdaytrends-browser-smoke/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(4000).decode("utf-8", errors="replace")
            return int(response.status), body
    except URLError as exc:
        return None, str(exc)
    except OSError as exc:
        return None, str(exc)


def _wait_for_server(base_url: str, timeout_seconds: float) -> tuple[bool, list[dict[str, Any]]]:
    deadline = time.monotonic() + timeout_seconds
    attempts: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        status, body = _http_get(base_url)
        attempts.append({"status": status, "body_tail": body[-240:]})
        if status == 200 and "getdaytrends Pro" in body:
            return True, attempts
        time.sleep(0.35)
    return False, attempts


def _tail(path: Path, limit: int = 4000) -> str:
    try:
        return _mask_sensitive_text(path.read_text(encoding="utf-8", errors="replace")[-limit:])
    except OSError:
        return ""


def _mask_sensitive_text(text: str) -> str:
    masked = re.sub(r"\b(postgres(?:ql)?://)[^\s\"'<>]+", r"\1***", text, flags=re.IGNORECASE)
    masked = re.sub(r"(\btenant/user\s+)[^\s),;]+", r"\1***", masked, flags=re.IGNORECASE)
    masked = re.sub(r"\bpostgres\.[A-Za-z0-9_.-]+", "postgres.***", masked)
    masked = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "sk-***", masked)
    masked = re.sub(r"\bAIza[0-9A-Za-z_-]{16,}\b", "AIza***", masked)
    masked = re.sub(
        r"\b(team\s+)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        r"\1***",
        masked,
        flags=re.IGNORECASE,
    )
    return masked


def _sanitize_log_file(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    masked = _mask_sensitive_text(text)
    if masked != text:
        path.write_text(masked, encoding="utf-8")


def _dashboard_degraded_log_sources(paths: list[Path]) -> list[str]:
    sources: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        sources.extend(re.findall(r"Dashboard endpoint degraded:\s*([A-Za-z0-9_./:-]+)", text))
    return sorted(set(sources))


def _safe_log_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return label[:96] or "dashboard_browser_server"


def _resolve_output_paths(
    report_path: Path | None,
    screenshot_path: Path | None,
    *,
    tap_source_fixture: bool,
) -> tuple[Path, Path]:
    default_report = DEFAULT_TAP_SOURCE_REPORT if tap_source_fixture else DEFAULT_REPORT
    default_screenshot = DEFAULT_TAP_SOURCE_SCREENSHOT if tap_source_fixture else DEFAULT_SCREENSHOT
    return report_path or default_report, screenshot_path or default_screenshot


def _server_env_overrides(*, local_db_only: bool, tap_source_fixture_db: Path | None = None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if local_db_only or tap_source_fixture_db is not None:
        overrides["DATABASE_URL"] = ""
    if tap_source_fixture_db is not None:
        overrides.update(
            {
                "DB_PATH": str(tap_source_fixture_db),
                "DEFAULT_COUNTRIES": "korea,united-states",
                "DEFAULT_COUNTRY": "korea",
                "TAP_SNAPSHOT_MAX_AGE_MINUTES": "0",
            }
        )
    return overrides


async def _seed_tap_source_evidence_fixture_async(db_path: Path) -> None:
    import aiosqlite

    try:
        from db import init_db
    except ImportError:
        sys.path.insert(0, str(PROJECT_ROOT))
        from db import init_db

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = await aiosqlite.connect(db_path)
    try:
        conn.row_factory = aiosqlite.Row
        await init_db(conn)
        now = datetime.now().isoformat()
        cursor = await conn.execute(
            """INSERT INTO runs (
                   run_uuid, started_at, country, trends_collected, trends_scored, tweets_generated
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            ("browser-smoke-tap-source-evidence", now, "korea", 2, 2, 0),
        )
        run_id = cursor.lastrowid
        rows = [
            (
                "browser smoke source signal",
                "korea",
                91,
                "Fixture source evidence: Korean outlets surfaced this trend before the US board.",
            ),
            (
                "us control market signal",
                "united-states",
                72,
                "Fixture control signal for the target market.",
            ),
        ]
        for rank, (keyword, country, viral, top_insight) in enumerate(rows, start=1):
            await conn.execute(
                """INSERT INTO trends (
                       run_id, keyword, rank, volume_raw, volume_numeric, viral_potential,
                       trend_acceleration, top_insight, suggested_angles, best_hook_starter,
                       country, sources, scored_at, fingerprint, cross_source_confidence
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    keyword,
                    rank,
                    "fixture",
                    10000,
                    viral,
                    "+25%",
                    top_insight,
                    '["Lead with the source gap"]',
                    "The source signal is moving before the target market catches up.",
                    country,
                    '["browser-smoke-fixture"]',
                    now,
                    f"browser-smoke-{country}-{rank}",
                    2,
                ),
            )
        await conn.commit()
    finally:
        await conn.close()


def _seed_tap_source_evidence_fixture(db_path: Path) -> None:
    asyncio.run(_seed_tap_source_evidence_fixture_async(db_path))


def _start_server(
    host: str,
    port: int,
    python_exe: str,
    *,
    env_overrides: Mapping[str, str] | None = None,
    log_label: str = "dashboard_browser_server",
) -> tuple[subprocess.Popen[str], Path, Path]:
    log_dir = PROJECT_ROOT / "logs" / "smoke"
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_label = _safe_log_label(log_label)
    stdout_path = log_dir / f"{safe_label}.out.log"
    stderr_path = log_dir / f"{safe_label}.err.log"
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    env = os.environ.copy()
    env.setdefault("ALLOW_SQLITE_FALLBACK", "true")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    for key, value in (env_overrides or {}).items():
        env[key] = value
    proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "dashboard:app", "--host", host, "--port", str(port), "--log-level", "info"],
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
        stdout=stdout_handle,
        stderr=stderr_handle,
    )
    # The handles are owned by the child process after spawn.
    stdout_handle.close()
    stderr_handle.close()
    return proc, stdout_path, stderr_path


def _stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=8)


def _record_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _tap_preset_state_ok(state: list[Mapping[str, Any]], expected_text: str) -> bool:
    if not state:
        return False
    pressed_count = sum(item.get("pressed") == "true" for item in state)
    active_count = sum(bool(item.get("active")) for item in state)
    if pressed_count != 1 or active_count != 1:
        return False
    for item in state:
        if item.get("pressed") not in {"true", "false"}:
            return False
        if item.get("type") != "button":
            return False
        if (item.get("pressed") == "true") != bool(item.get("active")):
            return False
    return any(
        item.get("text") == expected_text and item.get("pressed") == "true" and item.get("active") is True
        for item in state
    )


def _tap_preset_state_summary(state: list[Mapping[str, Any]], expected_text: str) -> dict[str, Any]:
    active_labels = [str(item.get("text") or "") for item in state if item.get("pressed") == "true"]
    inactive_labels = [str(item.get("text") or "") for item in state if item.get("pressed") == "false"]
    heights = [int(item.get("height") or 0) for item in state]
    return {
        "expected_active": expected_text,
        "active_labels": active_labels,
        "inactive_labels": inactive_labels,
        "active_label_matches_ok": active_labels == [expected_text],
        "pressed_active_consistent_ok": all(
            (item.get("pressed") == "true") == bool(item.get("active")) for item in state
        ),
        "all_button_types_ok": all(item.get("type") == "button" for item in state),
        "aria_labels_ok": all(
            item.get("ariaLabel") == f"Apply TAP target market preset: {item.get('text')}" for item in state
        ),
        "min_target_height": min(heights) if heights else 0,
        "target_height_ok": bool(heights) and min(heights) >= 28,
    }


def _tap_alert_action_group_gaps(state: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    expected_groups = {
        "presetActions": "TAP target market preset actions",
        "presetOptions": "TAP target market presets",
        "alertActions": "TAP alert queue actions",
    }
    for key, expected_label in expected_groups.items():
        group = state.get(key, {})
        if not isinstance(group, Mapping) or not group.get("exists"):
            gaps.append(f"{key}: missing group")
            continue
        if group.get("role") != "group":
            gaps.append(f"{key}: missing group role")
        if group.get("label") != expected_label:
            gaps.append(f"{key}: group label changed")
        if int(group.get("minButtonHeight") or 0) < 28:
            gaps.append(f"{key}: target height below 28px")
        if any(button_type != "button" for button_type in group.get("buttonTypes", [])):
            gaps.append(f"{key}: button type missing")

    preset_options = state.get("presetOptions", {})
    preset_buttons = preset_options.get("buttons", []) if isinstance(preset_options, Mapping) else []
    if len(preset_buttons) < 4:
        gaps.append("presetOptions: missing preset buttons")
    for button in preset_buttons:
        text = str(button.get("text", "")).strip()
        label = str(button.get("ariaLabel", "")).strip()
        if label != f"Apply TAP target market preset: {text}":
            gaps.append(f"presetOptions: aria label changed for {text or 'unknown'}")
        if button.get("pressed") not in {"true", "false"}:
            gaps.append(f"presetOptions: aria-pressed missing for {text or 'unknown'}")

    preset_actions = state.get("presetActions", {})
    if isinstance(preset_actions, Mapping):
        labels_by_id = {
            button.get("id"): button.get("ariaLabel")
            for button in preset_actions.get("buttons", [])
        }
        if labels_by_id.get("tap-save-preset-btn") != "Save TAP target market preset":
            gaps.append("presetActions: save aria label changed")
        if labels_by_id.get("tap-clear-presets-btn") != "Reset TAP target market presets":
            gaps.append("presetActions: reset aria label changed")

    alert_actions = state.get("alertActions", {})
    if isinstance(alert_actions, Mapping):
        expected_alert_buttons = [
            ("tap-dispatch-btn", "Dispatch queued", "Dispatch queued TAP alerts"),
            ("tap-dry-run-btn", "Dry run", "Dry run TAP alert dispatch"),
            ("tap-refresh-btn", "Refresh queue", "Refresh TAP alert queue"),
        ]
        alert_buttons = alert_actions.get("buttons", [])
        observed = [
            (button.get("id"), button.get("text"), button.get("ariaLabel"))
            for button in alert_buttons
        ]
        if observed != expected_alert_buttons:
            gaps.append("alertActions: button order or labels changed")
    return gaps


def _tap_alert_filter_control_gaps(state: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not state.get("exists"):
        return ["filters: missing group"]
    if state.get("role") != "group":
        gaps.append("filters: missing group role")
    if state.get("label") != "TAP alert queue filters":
        gaps.append("filters: group label changed")

    expected_controls = [
        ("tap-target-country", "input", "Target market", "tap-target-country-label"),
        ("tap-alert-lifecycle", "select", "Lifecycle", "tap-alert-lifecycle-label"),
        ("tap-alert-limit", "select", "Batch size", "tap-alert-limit-label"),
    ]
    controls = state.get("controls", [])
    observed = [
        (control.get("id"), control.get("tag"), control.get("labelText"), control.get("labelledBy"))
        for control in controls
    ]
    if observed != expected_controls:
        gaps.append("filters: control order or label references changed")
    if len(controls) != len(expected_controls):
        gaps.append("filters: missing controls")
    for control in controls:
        control_id = str(control.get("id") or "unknown")
        label_text = str(control.get("labelText") or "")
        if control.get("labelledByText") != label_text:
            gaps.append(f"filters: labelled text mismatch for {control_id}")
        associated_labels = control.get("associatedLabels", [])
        if label_text not in associated_labels:
            gaps.append(f"filters: native label association missing for {control_id}")
        if int(control.get("height") or 0) < 28:
            gaps.append(f"filters: target height below 28px for {control_id}")
    return gaps


def _operator_rendering_gaps(operator_text: str, issues: list[dict[str, Any]]) -> list[str]:
    rendered = operator_text.lower()
    gaps: list[str] = []
    for issue in issues:
        name = str(issue.get("name", "")).strip()
        message = str(issue.get("message", "")).strip()
        remediation = str(issue.get("remediation", "")).strip()
        for field_name, value in (("name", name), ("message", message), ("remediation", remediation)):
            if value and value.lower() not in rendered:
                gaps.append(f"{name or 'unknown'} missing {field_name}: {value[:120]}")
        evidence_summary = issue.get("evidence_summary")
        if isinstance(evidence_summary, list):
            for value in evidence_summary:
                text = str(value or "").strip()
                if text and not _operator_evidence_summary_rendered(rendered, text):
                    gaps.append(f"{name or 'unknown'} missing evidence summary: {text[:120]}")
    return gaps


def _operator_evidence_summary_rendered(rendered_text_lower: str, expected_text: str) -> bool:
    expected_lower = expected_text.lower()
    if expected_lower in rendered_text_lower:
        return True
    if expected_lower.startswith("endpoint network:"):
        return all(fragment in rendered_text_lower for fragment in ("endpoint network", "dns", "tcp", "pass"))
    return False


def _operator_supabase_recovery_gaps(operator_text: str, issues: list[dict[str, Any]]) -> list[str]:
    live_db_issue = next((issue for issue in issues if str(issue.get("name", "")) == "live_db_doctor"), None)
    if not live_db_issue:
        return []

    rendered = operator_text.lower()
    diagnostics = live_db_issue.get("diagnostics")
    live_db_message = str(live_db_issue.get("message", "")).lower()
    timeout_without_diagnostics = "timed out" in live_db_message and not diagnostics
    expected_fragments = [
        ("same supabase project", ("same supabase project", "supabase project ref")),
        ("database_url", ("database_url",)),
        ("pooler", ("pooler",)),
        ("main.py --doctor --require-live-db", ("main.py --doctor --require-live-db",)),
        ("getdaytrends_update_credentials.py --database-url-stdin", ("getdaytrends_update_credentials.py --database-url-stdin",)),
        (
            "getdaytrends_update_credentials.py --database-url-stdin --write",
            ("getdaytrends_update_credentials.py --database-url-stdin --write",),
        ),
    ]
    if not timeout_without_diagnostics:
        expected_fragments.insert(0, ("supabase_url", ("supabase_url",)))
    gaps = [
        f"missing recovery fragment: {label}"
        for label, alternatives in expected_fragments
        if not any(fragment in rendered for fragment in alternatives)
    ]
    if "verification bundle. rerun python" in rendered or "verification bundle. then rerun python" in rendered:
        gaps.append("supabase remediation repeats rerun guidance")
    if "without fallback. dry-run" in operator_text:
        gaps.append("supabase remediation starts sentence with lowercase dry-run")

    if isinstance(diagnostics, list):
        for marker in ("db.endpoint_dns", "db.endpoint_tcp", "db.live_postgres"):
            if any(marker in str(item) for item in diagnostics) and marker not in rendered:
                gaps.append(f"missing diagnostic marker: {marker}")
    recovery_packet = str(live_db_issue.get("recovery_packet", "")).strip()
    if recovery_packet:
        if "recovery packet" not in rendered:
            gaps.append("missing recovery packet label")
        if recovery_packet.lower() not in rendered:
            gaps.append(f"missing recovery packet path: {recovery_packet[:120]}")
    return gaps


def _operator_provider_auth_gaps(operator_text: str, issues: list[dict[str, Any]]) -> list[str]:
    provider_issue = next((issue for issue in issues if str(issue.get("name", "")) == "provider_auth_report"), None)
    if not provider_issue:
        return []

    rendered = operator_text.lower()
    expected_fragments = (
        "provider_auth_report",
        "provider authentication",
        "rotate or revoke",
        "smoke_cli.py --include-dry-run",
    )
    gaps = [f"missing provider auth fragment: {fragment}" for fragment in expected_fragments if fragment not in rendered]
    if "verification bundle. then rerun" in rendered:
        gaps.append("provider auth remediation repeats rerun guidance")
    recovery_packet = str(provider_issue.get("recovery_packet", "")).strip()
    if recovery_packet and recovery_packet.lower() not in rendered:
        gaps.append(f"missing provider auth recovery packet path: {recovery_packet[:120]}")
    return gaps


def _operator_recovery_packet_reuse_gaps(operator_text: str, issues: list[dict[str, Any]]) -> list[str]:
    rendered = operator_text.lower()
    first_owner_by_packet: dict[str, str] = {}
    gaps: list[str] = []
    for issue in issues:
        packet_path = str(issue.get("recovery_packet", "")).strip()
        if not packet_path:
            continue
        issue_name = str(issue.get("name", "")).strip() or "unknown"
        first_owner = first_owner_by_packet.get(packet_path)
        if not first_owner:
            first_owner_by_packet[packet_path] = issue_name
            continue
        reuse = issue.get("recovery_packet_reuse")
        if not isinstance(reuse, dict):
            gaps.append(f"missing reused recovery packet metadata for {issue_name}")
            continue
        expected_message = str(reuse.get("message") or f"Same packet as {first_owner}").strip()
        if reuse.get("first_blocker") != first_owner:
            gaps.append(f"wrong reused recovery packet owner for {issue_name}")
        if expected_message.lower() not in rendered:
            gaps.append(f"missing reused recovery packet label: {expected_message}")
    return gaps


def _fragment_gaps(text: str, fragments: tuple[str, ...], label: str) -> list[str]:
    rendered = text.lower()
    return [f"missing {label} fragment: {fragment}" for fragment in fragments if fragment.lower() not in rendered]


def _reference_link_present(links: list[dict[str, Any]], label: str, url: str) -> bool:
    return any(
        str(link.get("text", "")).strip() == label
        and str(link.get("href", "")).strip() == url
        and str(link.get("target", "")).strip() == "_blank"
        and "noopener" in str(link.get("rel", "")).lower()
        and "noreferrer" in str(link.get("rel", "")).lower()
        for link in links
        if isinstance(link, dict)
    )


def _recovery_next_action_secret_gaps(text: str, label: str) -> list[str]:
    if re.search(r"\bpostgres(?:ql)?://[^\s\"'<>]+|\bsk-[A-Za-z0-9_-]{8,}\b|\bAIza[0-9A-Za-z_-]{16,}\b", text):
        return [f"{label} next action contains secret-shaped value"]
    return []


def _copy_payload_secret_gaps(text: str, label: str) -> list[str]:
    gaps: list[str] = []
    if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", text, re.IGNORECASE):
        gaps.append(f"{label} contains raw postgres URL")
    if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", text, re.IGNORECASE):
        gaps.append(f"{label} contains raw tenant user")
    if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", text):
        gaps.append(f"{label} contains raw OpenAI-style key")
    if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", text):
        gaps.append(f"{label} contains raw Google API-style key")
    return gaps


def _supabase_recovery_next_action_gaps(next_action_text: str) -> list[str]:
    gaps = _fragment_gaps(
        next_action_text,
        (
            "Pause scheduled/background getdaytrends clients",
            "Set SUPABASE_URL",
            "DATABASE_URL",
            "Transaction pooler",
            *SAFE_DATABASE_UPDATE_FRAGMENTS,
            "verification bundle",
        ),
        "supabase next action",
    )
    rendered = next_action_text.lower()
    if not any(
        fragment in rendered
        for fragment in (
            "rotate or correct",
            "rotating or applying",
            "current database password",
        )
    ):
        gaps.append("missing supabase next action fragment: rotate or correct")
    return gaps + _recovery_next_action_secret_gaps(next_action_text, "supabase")


def _provider_recovery_next_action_gaps(next_action_text: str) -> list[str]:
    gaps = _fragment_gaps(
        next_action_text,
        (
            "provider key",
            ".env",
            "production secret store",
            *SAFE_PROVIDER_UPDATE_FRAGMENTS,
            "verification bundle",
        ),
        "provider next action",
    )
    rendered = next_action_text.lower()
    if "fresh scoped key" not in rendered and not ("model" in rendered and "billing" in rendered):
        gaps.append("missing provider next action fragment: fresh scoped key or provider model/billing permissions")
    return gaps + _recovery_next_action_secret_gaps(next_action_text, "provider")


def _provider_recovery_preview_gaps(preview_text: str) -> list[str]:
    gaps = _fragment_gaps(
        preview_text,
        (
            "Packet status:",
            "Generated:",
            "Readiness",
            "Next action:",
            "Copy recovery next action",
            "Issue types:",
            "Issue count:",
            "Blocking checks:",
            "Blocking check count:",
            "provider_auth_report",
            "Provider auth failures:",
            "Required env:",
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY",
            *SAFE_PROVIDER_UPDATE_FRAGMENTS,
            "References:",
            "OpenAI API key production guidance",
            "Google AI Gemini API key guide",
            "Verification cwd:",
            "Launch success:",
            "provider_auth_failure_count 0",
            "without leaked-key",
            "Canonical getdaytrends workspace smoke reports all configured checks PASS",
            "Checklist:",
            "fresh scoped provider key",
            "Verify:",
            "smoke_cli.py --include-dry-run",
        ),
        "provider preview",
    )
    rendered = preview_text.lower()
    if "provider.api_key_leaked" in rendered:
        gaps.extend(
            _fragment_gaps(
                preview_text,
                ("Revoke any leaked provider key", "provider.api_key_leaked"),
                "provider preview",
            )
        )
    elif "provider.permission_denied" in rendered:
        gaps.extend(
            _fragment_gaps(
                preview_text,
                ("provider.permission_denied", "provider project", "model", "billing"),
                "provider preview",
            )
        )
    else:
        gaps.append("missing provider preview fragment: provider issue type")
    if "cli_smoke_report" in rendered:
        gaps.append("provider preview should not list cli_smoke_report")
    return gaps


def _provider_recovery_bundle_gaps(bundle_text: str) -> list[str]:
    gaps = _fragment_gaps(
        bundle_text,
        (
            "# getdaytrends provider credential recovery bundle",
            "## Next required action",
            "## Current blocker summary",
            "Provider auth failure count:",
            "## Evidence freshness",
            "## Launch success criteria",
            "provider_auth_failure_count 0",
            "without leaked-key",
            "Strict readiness reports status pass",
            "Canonical getdaytrends workspace smoke reports all configured checks PASS",
            "## Env template",
            "OPENAI_API_KEY=<rotated_openai_key_if_used>",
            "GOOGLE_API_KEY=<rotated_google_ai_key_if_used>",
            *SAFE_PROVIDER_UPDATE_FRAGMENTS,
            "## Recovery checklist",
            "fresh scoped provider key",
            "production secret store",
            "model permissions",
            "## References",
            "OpenAI API key production guidance",
            OPENAI_REFERENCE_URL,
            "Google AI Gemini API key guide",
            GOOGLE_AI_REFERENCE_URL,
            "## Verification commands",
            "Set-Location -LiteralPath",
            "smoke_cli.py --include-dry-run",
            "run_workspace_smoke.py --scope getdaytrends",
            "workspace-smoke-getdaytrends-operator-recheck.json",
        ),
        "provider bundle",
    )
    rendered = bundle_text.lower()
    if "provider.api_key_leaked" in rendered:
        gaps.extend(
            _fragment_gaps(
                bundle_text,
                ("Revoke any leaked provider key", "provider.api_key_leaked"),
                "provider bundle",
            )
        )
    elif "provider.permission_denied" in rendered:
        gaps.extend(
            _fragment_gaps(
                bundle_text,
                ("provider.permission_denied", "provider project", "model", "billing"),
                "provider bundle",
            )
        )
    elif "issue types: -" not in rendered:
        gaps.append("missing provider bundle fragment: provider issue type")
    if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b|\bAIza[0-9A-Za-z_-]{16,}\b", bundle_text):
        gaps.append("provider bundle contains secret-shaped key")
    if "workspace-smoke-getdaytrends-launch-final.json" in bundle_text:
        gaps.append("provider bundle uses launch-final workspace smoke target")
    return gaps


def _provider_recovery_env_gaps(env_text: str) -> list[str]:
    gaps = _fragment_gaps(
        env_text,
        (
            "fresh scoped keys only",
            "OPENAI_API_KEY=<rotated_openai_key_if_used>",
            "GOOGLE_API_KEY=<rotated_google_ai_key_if_used>",
            "production secret store",
        ),
        "provider env",
    )
    if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b|\bAIza[0-9A-Za-z_-]{16,}\b", env_text):
        gaps.append("provider env contains secret-shaped key")
    return gaps


def _provider_recovery_checklist_gaps(checklist_text: str) -> list[str]:
    return _fragment_gaps(
        checklist_text,
        (
            "Required env:",
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY",
            "fresh scoped provider key",
            "production secret store",
            *SAFE_PROVIDER_UPDATE_FRAGMENTS,
            "model permissions",
            "smoke_cli.py --include-dry-run",
            "provider_auth_failure_count is 0",
        ),
        "provider checklist",
    )


def _provider_recovery_verify_gaps(command_text: str) -> list[str]:
    gaps = _fragment_gaps(
        command_text,
        (
            "Set-Location -LiteralPath",
            "smoke_cli.py --include-dry-run",
            "browser_smoke.py --timeout 45",
            "readiness_check.py",
            "--fail-on-runtime-fallback --require-live-db",
            "run_workspace_smoke.py --scope getdaytrends",
            "workspace-smoke-getdaytrends-operator-recheck.json",
        ),
        "provider verify",
    )
    if "workspace-smoke-getdaytrends-launch-final.json" in command_text:
        gaps.append("provider verify uses launch-final workspace smoke target")
    return gaps


DASHBOARD_CONTENT_READY_JS = """() => {
    const textIds = ['operator-readiness', 'operator-blockers', 'tap-board', 'tap-alert-list', 'tap-deal-room', 't-body'];
    return textIds.every(id => {
        const node = document.getElementById(id);
        return Boolean(node && (node.innerText || '').trim().length > 0);
    });
}"""

DASHBOARD_CORE_STATE_JS = """() => {
    const textIds = ['operator-readiness', 'operator-blockers', 'tap-board', 'tap-alert-list', 'tap-deal-room', 't-body'];
    const state = {};
    const kpi = document.getElementById('kpi-grid');
    state['kpi-grid'] = Boolean(kpi && kpi.getClientRects().length > 0);
    for (const id of textIds) {
        const node = document.getElementById(id);
        state[id] = Boolean(node && (node.innerText || '').trim().length > 0);
    }
    return state;
}"""

TAP_PRESET_BUTTON_STATE_JS = """() => Array.from(document.querySelectorAll('#tap-preset-strip button')).map(button => ({
    text: (button.textContent || '').trim(),
    ariaLabel: button.getAttribute('aria-label') || '',
    pressed: button.getAttribute('aria-pressed') || '',
    active: button.classList.contains('tap-preset-btn-active'),
    type: button.getAttribute('type') || '',
    height: Math.round(button.getBoundingClientRect().height),
}))"""

TAP_ALERT_ACTION_GROUP_STATE_JS = """() => {
    const buttonState = (button) => ({
        id: button.id || '',
        text: (button.textContent || '').trim(),
        ariaLabel: button.getAttribute('aria-label') || '',
        pressed: button.getAttribute('aria-pressed') || '',
        type: button.getAttribute('type') || '',
        width: Math.round(button.getBoundingClientRect().width),
        height: Math.round(button.getBoundingClientRect().height),
    });
    const groupState = (selector) => {
        const node = document.querySelector(selector);
        const buttons = node ? Array.from(node.querySelectorAll('button')).map(buttonState) : [];
        return {
            exists: Boolean(node),
            role: node?.getAttribute('role') || '',
            label: node?.getAttribute('aria-label') || '',
            buttonTexts: buttons.map(button => button.text),
            buttonLabels: buttons.map(button => button.ariaLabel),
            buttonTypes: buttons.map(button => button.type),
            buttonHeights: buttons.map(button => button.height),
            minButtonHeight: buttons.length ? Math.min(...buttons.map(button => button.height)) : 0,
            buttons,
        };
    };
    return {
        presetActions: groupState('[data-tap-preset-actions="true"]'),
        presetOptions: groupState('[data-tap-preset-options="true"]'),
        alertActions: groupState('[data-tap-alert-actions="true"]'),
    };
}"""

TAP_ALERT_FILTER_CONTROL_STATE_JS = """() => {
    const node = document.querySelector('[data-tap-alert-filters="true"]');
    const controls = node ? Array.from(node.querySelectorAll('input, select')).map(control => {
        const labelledBy = control.getAttribute('aria-labelledby') || '';
        const labelledByText = labelledBy
            ? (document.getElementById(labelledBy)?.textContent || '').trim()
            : '';
        return {
            id: control.id || '',
            tag: control.tagName.toLowerCase(),
            labelText: (control.closest('.tap-control')?.querySelector('label')?.textContent || '').trim(),
            labelledBy,
            labelledByText,
            associatedLabels: Array.from(control.labels || []).map(label => (label.textContent || '').trim()),
            height: Math.round(control.getBoundingClientRect().height),
            width: Math.round(control.getBoundingClientRect().width),
        };
    }) : [];
    return {
        exists: Boolean(node),
        role: node?.getAttribute('role') || '',
        label: node?.getAttribute('aria-label') || '',
        controls,
    };
}"""

DASHBOARD_BUTTON_TYPE_STATE_JS = """() => Array.from(document.querySelectorAll('button')).map(button => ({
    id: button.id || '',
    label: (button.textContent || button.getAttribute('aria-label') || '').trim(),
    type: button.getAttribute('type') || '',
    className: button.className || '',
})).filter(button => button.type !== 'button')"""

DASHBOARD_MAIN_LANDMARK_JS = """() => {
    const main = document.getElementById('dashboard-main');
    const visibleMains = Array.from(document.querySelectorAll('main')).filter(node => !node.hidden);
    const skip = document.querySelector('a.skip-link[href="#dashboard-main"]');
    return {
        mainCount: visibleMains.length,
        mainId: main?.id || '',
        mainTag: main?.tagName || '',
        mainTabIndex: main?.getAttribute('tabindex') || '',
        skipText: (skip?.textContent || '').trim(),
        skipHref: skip?.getAttribute('href') || '',
        skipFirstBodyChild: document.body.firstElementChild === skip,
        containsKpi: Boolean(main?.querySelector('#kpi-grid')),
        containsTable: Boolean(main?.querySelector('.table-wrap table')),
        headerInsideMain: Boolean(main?.querySelector('header')),
        footerInsideMain: Boolean(main?.querySelector('.footer')),
    };
}"""

DASHBOARD_MAIN_SKIP_ACTIVATION_JS = """() => {
    const main = document.getElementById('dashboard-main');
    const skip = document.querySelector('a.skip-link[href="#dashboard-main"]');
    return {
        hash: window.location.hash || '',
        activeElementId: document.activeElement?.id || '',
        activeElementTag: document.activeElement?.tagName || '',
        mainFocused: document.activeElement === main,
        skipExists: Boolean(skip),
        mainExists: Boolean(main),
    };
}"""

DASHBOARD_STATUS_PILL_LIVE_REGION_JS = """() => {
    const node = document.getElementById('status-pill');
    return {
        exists: Boolean(node),
        role: node?.getAttribute('role') || '',
        live: node?.getAttribute('aria-live') || '',
        atomic: node?.getAttribute('aria-atomic') || '',
        label: node?.getAttribute('aria-label') || '',
        text: (node?.textContent || '').trim(),
        className: node?.className || '',
        visible: Boolean(node?.getClientRects().length),
        hasTabIndex: Boolean(node?.hasAttribute('tabindex')),
        focused: document.activeElement === node,
    };
}"""

DASHBOARD_FOOTER_LANDMARK_JS = """() => {
    const main = document.getElementById('dashboard-main');
    const footer = document.querySelector('footer.footer');
    return {
        footerCount: document.querySelectorAll('footer.footer').length,
        footerTag: footer?.tagName || '',
        footerClass: footer?.className || '',
        footerText: (footer?.textContent || '').trim(),
        footerRole: footer?.getAttribute('role') || '',
        footerBodyChild: footer?.parentElement === document.body,
        footerInsideMain: Boolean(main?.querySelector('footer.footer')),
        legacyDivFooterCount: document.querySelectorAll('div.footer').length,
        visible: Boolean(footer?.getClientRects().length),
    };
}"""

DASHBOARD_LOG_VIEWER_LIVE_REGION_JS = """() => {
    const node = document.getElementById('log-viewer');
    const entries = Array.from(node?.children || []).map(child => (child.textContent || '').trim()).filter(Boolean);
    return {
        exists: Boolean(node),
        role: node?.getAttribute('role') || '',
        live: node?.getAttribute('aria-live') || '',
        atomic: node?.getAttribute('aria-atomic') || '',
        relevant: node?.getAttribute('aria-relevant') || '',
        label: node?.getAttribute('aria-label') || '',
        text: (node?.innerText || '').trim(),
        entryCount: entries.length,
        firstEntry: entries[0] || '',
        visible: Boolean(node?.getClientRects().length),
        scrollable: Boolean(node && node.scrollHeight >= node.clientHeight),
        focused: document.activeElement === node,
        hasTabIndex: Boolean(node?.hasAttribute('tabindex')),
    };
}"""

DASHBOARD_WARNING_BANNER_DETAILS_JS = """() => {
    const banner = document.getElementById('dashboard-warning-banner');
    const status = document.getElementById('dashboard-warning-status');
    const details = banner?.querySelector('details.dashboard-warning-details');
    const summary = details?.querySelector('summary');
    const summaryBox = summary?.getBoundingClientRect();
    const copyButton = banner?.querySelector("[aria-label='Copy degraded endpoint details']");
    const readinessCopyButton = banner?.querySelector("[aria-label='Copy fallback readiness refresh command']");
    const copyText = copyButton?.dataset.copyText || '';
    const readinessCopyText = readinessCopyButton?.dataset.copyText || '';
    const copyLineCount = Math.max(0, copyText.split(/\\n/).filter(Boolean).length - 1);
    const rows = Array.from(details?.querySelectorAll('.dashboard-warning-list li') || []).map(row => ({
        label: (row.querySelector('strong')?.innerText || '').trim(),
        text: (row.innerText || '').trim(),
        path: (row.querySelector('code')?.innerText || '').trim(),
        meta: (row.querySelector('.dashboard-warning-meta')?.innerText || '').trim(),
    }));
    const rowLabels = rows.map(row => row.label).filter(Boolean);
    const duplicateLabels = rowLabels.filter((label, index) => rowLabels.indexOf(label) !== index);
    return {
        visible: Boolean(banner?.classList.contains('show') && banner.getClientRects().length),
        bannerRole: banner?.getAttribute('role') || '',
        statusExists: Boolean(status),
        statusRole: status?.getAttribute('role') || '',
        statusLive: status?.getAttribute('aria-live') || '',
        statusAtomic: status?.getAttribute('aria-atomic') || '',
        statusText: (status?.innerText || '').trim(),
        detailsExists: Boolean(details),
        detailsOpen: Boolean(details?.open),
        detailsText: (details?.innerText || '').trim(),
        summaryText: (summary?.innerText || '').trim(),
        summaryHeight: Math.round(summaryBox?.height || 0),
        summaryWidth: Math.round(summaryBox?.width || 0),
        copyButtonExists: Boolean(copyButton),
        copyButtonType: copyButton?.getAttribute('type') || '',
        copyButtonText: (copyButton?.innerText || '').trim(),
        copyButtonResult: copyButton?.dataset.copyResult || '',
        readinessCopyButtonExists: Boolean(readinessCopyButton),
        readinessCopyButtonType: readinessCopyButton?.getAttribute('type') || '',
        readinessCopyButtonText: (readinessCopyButton?.innerText || '').trim(),
        readinessCopyButtonResult: readinessCopyButton?.dataset.copyResult || '',
        readinessCopyText,
        copyLineCount,
        copyText,
        rowCount: rows.length,
        duplicateLabels: Array.from(new Set(duplicateLabels)),
        rows,
        focusedElementTag: document.activeElement?.tagName || '',
        focusedElementText: (document.activeElement?.innerText || '').trim(),
    };
}"""

DASHBOARD_CHART_CANVAS_ACCESSIBILITY_JS = """() => Array.from(document.querySelectorAll('canvas')).map(canvas => ({
    id: canvas.id || '',
    role: canvas.getAttribute('role') || '',
    label: canvas.getAttribute('aria-label') || '',
    fallbackText: (canvas.textContent || '').trim(),
    visible: Boolean(canvas.getClientRects().length),
}))"""

DASHBOARD_TRENDS_TABLE_ACCESSIBILITY_JS = """() => {
    const table = document.querySelector('.table-wrap table');
    const caption = table?.querySelector('caption') || null;
    return {
        hasTable: Boolean(table),
        captionText: (caption?.textContent || '').trim(),
        captionClass: caption?.className || '',
        captionFirstChild: table?.firstElementChild === caption,
        headerTexts: Array.from(table?.querySelectorAll('thead th') || []).map(th => (th.textContent || '').trim()),
        headerScopes: Array.from(table?.querySelectorAll('thead th') || []).map(th => th.getAttribute('scope') || ''),
        bodyId: table?.querySelector('tbody')?.id || '',
    };
}"""

DASHBOARD_MOBILE_LAYOUT_STATE_JS = """() => {
    const viewportWidth = document.documentElement.clientWidth;
    const docScrollWidth = document.documentElement.scrollWidth;
    const ignoredScrollableSelector = '.table-wrap';
    const offenders = Array.from(document.querySelectorAll('body *')).map((element) => {
        const rect = element.getBoundingClientRect();
        const insideExpectedScroller = Boolean(element.closest(ignoredScrollableSelector));
        const internalOverflowPx = element.scrollWidth - element.clientWidth;
        const outsideViewport = !insideExpectedScroller && (rect.right > viewportWidth + 1 || rect.left < -1);
        const internalOverflow = !insideExpectedScroller && internalOverflowPx > 1;
        return {
            tag: element.tagName.toLowerCase(),
            id: element.id || '',
            className: typeof element.className === 'string' ? element.className : '',
            text: (element.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
            scrollWidth: element.scrollWidth,
            clientWidth: element.clientWidth,
            overflowRight: Math.round(rect.right - viewportWidth),
            internalOverflowPx: Math.round(internalOverflowPx),
            internalOverflow,
            outsideViewport,
            insideExpectedScroller,
        };
    }).filter(item => item.outsideViewport || item.internalOverflow).slice(0, 16);
    const actionButtonIssues = Array.from(document.querySelectorAll('.operator-action')).flatMap((action, actionIndex) => {
        const actionRect = action.getBoundingClientRect();
        return Array.from(action.querySelectorAll('button')).map((button) => {
            const rect = button.getBoundingClientRect();
            const outsideAction = rect.right > actionRect.right + 1 || rect.left < actionRect.left - 1;
            const outsideViewport = rect.right > viewportWidth + 1 || rect.left < -1;
            return {
                actionIndex,
                label: button.getAttribute('aria-label') || button.textContent.trim(),
                left: Math.round(rect.left),
                right: Math.round(rect.right),
                outsideAction,
                outsideViewport,
            };
        }).filter(item => item.outsideAction || item.outsideViewport);
    });
    const recoveryAction = Array.from(document.querySelectorAll('.operator-action'))
        .find(action => (action.querySelector('.operator-action-label')?.textContent || '').trim() === 'Recovery packet'
            && action.querySelectorAll('button').length >= 5);
    const recoveryRowActionGroups = Array.from(document.querySelectorAll('#operator-blockers [data-recovery-row-actions="true"]')).map(group => {
        const buttons = Array.from(group.querySelectorAll('button')).map(button => {
            const rect = button.getBoundingClientRect();
            return {
                text: (button.innerText || '').trim(),
                type: button.getAttribute('type') || '',
                width: Math.round(rect.width),
                height: Math.round(rect.height),
            };
        });
        return {
            role: group.getAttribute('role') || '',
            label: group.getAttribute('aria-label') || '',
            buttonTexts: buttons.map(button => button.text),
            buttonTypes: buttons.map(button => button.type),
            buttonHeights: buttons.map(button => button.height),
            minButtonHeight: buttons.length ? Math.min(...buttons.map(button => button.height)) : 0,
            buttons,
        };
    });
    const artifactActionGroups = Array.from(document.querySelectorAll('#operator-artifacts [data-artifact-action-group="true"]')).map(group => {
        const action = group.closest('.operator-action');
        const buttons = Array.from(group.querySelectorAll('button')).map(button => {
            const rect = button.getBoundingClientRect();
            return {
                text: (button.innerText || '').trim(),
                ariaLabel: button.getAttribute('aria-label') || '',
                type: button.getAttribute('type') || '',
                width: Math.round(rect.width),
                height: Math.round(rect.height),
            };
        });
        return {
            key: action?.getAttribute('data-artifact-key') || '',
            role: group.getAttribute('role') || '',
            label: group.getAttribute('aria-label') || '',
            buttonTexts: buttons.map(button => button.text),
            buttonLabels: buttons.map(button => button.ariaLabel),
            buttonTypes: buttons.map(button => button.type),
            buttonHeights: buttons.map(button => button.height),
            minButtonHeight: buttons.length ? Math.min(...buttons.map(button => button.height)) : 0,
            buttons,
        };
    });
    return {
        viewportWidth,
        docScrollWidth,
        overflowPx: Math.max(0, docScrollWidth - viewportWidth),
        offenderCount: offenders.length,
        offenders,
        actionButtonIssueCount: actionButtonIssues.length,
        actionButtonIssues,
        recoveryActionButtonCount: recoveryAction ? recoveryAction.querySelectorAll('button').length : 0,
        recoveryRowActionGroups,
        artifactActionGroups,
        tableWrapScrollWidth: document.querySelector('.table-wrap')?.scrollWidth || 0,
        tableWrapClientWidth: document.querySelector('.table-wrap')?.clientWidth || 0,
    };
}"""

TAP_ALERT_STATUS_LIVE_REGION_JS = """() => {
    const node = document.getElementById('tap-alert-status');
    return {
        role: node?.getAttribute('role') || '',
        live: node?.getAttribute('aria-live') || '',
        atomic: node?.getAttribute('aria-atomic') || '',
        busy: node?.getAttribute('aria-busy') || '',
        text: (node?.innerText || '').trim(),
    };
}"""

TAP_CHECKOUT_RETURN_STATE_JS = """() => {
    const node = document.getElementById('tap-checkout-return-notice');
    const clear = document.getElementById('tap-checkout-return-clear-btn');
    const verify = document.getElementById('tap-checkout-session-status-btn');
    const status = document.getElementById('tap-checkout-session-status');
    const actionGroup = node?.querySelector('[data-tap-checkout-return-actions="true"]') || null;
    const actionButtons = Array.from(actionGroup?.querySelectorAll('button') || []).map(button => {
      const rect = button.getBoundingClientRect();
      return {
        text: (button.innerText || '').trim(),
        ariaLabel: button.getAttribute('aria-label') || '',
        type: button.getAttribute('type') || '',
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    });
    return {
      visible: Boolean(node && !node.hidden),
      role: node?.getAttribute('role') || '',
      live: node?.getAttribute('aria-live') || '',
      atomic: node?.getAttribute('aria-atomic') || '',
      className: node?.className || '',
      text: (node?.innerText || '').trim(),
      clearButtonType: clear?.getAttribute('type') || '',
      verifyButtonType: verify?.getAttribute('type') || '',
      verifyButtonText: (verify?.innerText || '').trim(),
      statusRole: status?.getAttribute('role') || '',
      statusLive: status?.getAttribute('aria-live') || '',
      statusAtomic: status?.getAttribute('aria-atomic') || '',
      statusText: (status?.innerText || '').trim(),
      actionGroup: {
        role: actionGroup?.getAttribute('role') || '',
        label: actionGroup?.getAttribute('aria-label') || '',
        buttonTexts: actionButtons.map(button => button.text),
        buttonLabels: actionButtons.map(button => button.ariaLabel),
        buttonTypes: actionButtons.map(button => button.type),
        minButtonHeight: actionButtons.length ? Math.min(...actionButtons.map(button => button.height)) : 0,
        buttons: actionButtons,
      },
      url: window.location.href,
    };
}"""

TAP_CHECKOUT_SESSION_STATUS_VERIFY_JS = """async () => {
    const button = document.getElementById('tap-checkout-session-status-btn');
    const statusNode = document.getElementById('tap-checkout-session-status');
    window.__gdtTapCheckoutSessionStatusCalls = [];
    const previousFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const url = String(args[0]);
      const options = args[1] || {};
      const response = await previousFetch(...args);
      if (url.includes('/api/tap/deal-room/checkout/session/')) {
        let responseBody = {};
        try {
          responseBody = await response.clone().json();
        } catch (error) {
          responseBody = {parse_error: String(error)};
        }
        window.__gdtTapCheckoutSessionStatusCalls.push({
          url,
          method: String(options.method || 'GET').toUpperCase(),
          status: response.status,
          ok: response.ok,
          response_body: responseBody,
        });
      }
      return response;
    };
    if (button) button.click();
    const startedAt = Date.now();
    while (Date.now() - startedAt < 5000) {
      await new Promise(resolve => setTimeout(resolve, 120));
      const settled = button?.getAttribute('aria-busy') !== 'true' && !button?.disabled;
      const hasStatus = Boolean((statusNode?.innerText || '').trim());
      const hasCall = (window.__gdtTapCheckoutSessionStatusCalls || []).length > 0;
      if (settled && (hasStatus || hasCall)) break;
    }
    window.fetch = previousFetch;
    return {
      had_button: Boolean(button),
      button_type: button?.getAttribute('type') || '',
      button_label: (button?.innerText || '').trim(),
      button_disabled_after: Boolean(button?.disabled),
      button_busy_after: button?.getAttribute('aria-busy') || '',
      status_role: statusNode?.getAttribute('role') || '',
      status_live: statusNode?.getAttribute('aria-live') || '',
      status_atomic: statusNode?.getAttribute('aria-atomic') || '',
      status_text: (statusNode?.innerText || '').trim(),
      toast_text: document.getElementById('toast')?.textContent || '',
      toast_type: document.getElementById('toast')?.dataset.lastToastType || '',
      calls: window.__gdtTapCheckoutSessionStatusCalls || [],
    };
}"""

TAP_SOURCE_NOTES_STATE_JS = """async () => {
    const response = await fetch('/api/tap/opportunities?limit=6&teaser_count=2&target_country=united-states');
    const payload = await response.json();
    const items = Array.isArray(payload.items) ? payload.items : [];
    const expectedNotes = items
      .flatMap(item => Array.isArray(item.execution_notes) ? item.execution_notes.filter(Boolean).slice(0, 2) : []);
    const renderedText = document.getElementById('tap-board')?.innerText || '';
    const renderedNoteCount = document.querySelectorAll('#tap-board .tap-notes').length;
    return {
      degraded: Boolean(payload._meta?.degraded),
      item_count: items.length,
      expected_notes: expectedNotes,
      rendered_note_count: renderedNoteCount,
      rendered_text: renderedText.slice(0, 1200),
      matched_notes: expectedNotes.filter(note => renderedText.includes(note)),
    };
}"""

TAP_SOURCE_FIXTURE_RESTORE_LIVE_MARKET_JS = """async () => {
    const target = document.getElementById('tap-target-country');
    const lifecycle = document.getElementById('tap-alert-lifecycle');
    const limit = document.getElementById('tap-alert-limit');
    if (target) target.value = 'united-states';
    if (lifecycle) lifecycle.value = 'queued';
    if (limit) limit.value = '5';
    if (typeof syncTapOpsView === 'function') {
      await syncTapOpsView();
    } else {
      document.getElementById('tap-refresh-btn')?.click();
      await new Promise(resolve => setTimeout(resolve, 1200));
    }
    const boardText = document.getElementById('tap-board')?.innerText || '';
    const dealRoomText = document.getElementById('tap-deal-room')?.innerText || '';
    return {
      targetCountry: target?.value || '',
      lifecycleValue: lifecycle?.value || '',
      statusText: (document.getElementById('tap-alert-status')?.innerText || '').trim(),
      boardText: boardText.slice(0, 1200),
      dealRoomText: dealRoomText.slice(0, 1200),
      sourceNoteCount: document.querySelectorAll('#tap-board .tap-notes').length,
      offerCardCount: document.querySelectorAll('#tap-deal-room .tap-deal-offer-card').length,
      emptyCardCount: document.querySelectorAll('#tap-deal-room .tap-deal-empty-card').length,
    };
}"""

TAP_DEAL_ROOM_OPS_STATE_JS = """() => {
    const panel = document.getElementById('tap-deal-room');
    const ops = document.getElementById('tap-deal-ops-summary');
    const labels = Array.from(document.querySelectorAll('#tap-deal-room .tap-deal-metric-label'))
      .map(node => (node.innerText || '').trim());
    const values = Array.from(document.querySelectorAll('#tap-deal-room .tap-deal-metric-value'))
      .map(node => (node.innerText || '').trim());
    const offerActionGroups = Array.from(document.querySelectorAll('#tap-deal-room .tap-deal-offer-card [data-tap-offer-actions="true"]'))
      .map(group => {
        const buttons = Array.from(group.querySelectorAll('button')).map(button => {
          const rect = button.getBoundingClientRect();
          return {
            text: (button.innerText || '').trim(),
            ariaLabel: button.getAttribute('aria-label') || '',
            type: button.getAttribute('type') || '',
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          };
        });
        return {
          role: group.getAttribute('role') || '',
          label: group.getAttribute('aria-label') || '',
          offerName: group.getAttribute('data-offer-name') || '',
          buttonTexts: buttons.map(button => button.text),
          buttonLabels: buttons.map(button => button.ariaLabel),
          buttonTypes: buttons.map(button => button.type),
          minButtonHeight: buttons.length ? Math.min(...buttons.map(button => button.height)) : 0,
          buttons,
        };
      });
    return {
      text: (panel?.innerText || '').trim().slice(0, 1200),
      has_ops_summary: Boolean(ops),
      labels,
      values,
      offer_card_count: document.querySelectorAll('#tap-deal-room .tap-deal-offer-card').length,
      empty_card_count: document.querySelectorAll('#tap-deal-room .tap-deal-empty-card').length,
      offer_action_groups: offerActionGroups,
      track_buttons: Array.from(document.querySelectorAll('#tap-deal-room .tap-deal-offer-card button'))
        .map(button => ({type: button.getAttribute('type') || '', label: (button.innerText || '').trim(), ariaLabel: button.getAttribute('aria-label') || ''})),
      checkout_buttons: Array.from(document.querySelectorAll('#tap-deal-room .tap-deal-offer-card [data-tap-checkout-index]'))
        .map(button => ({type: button.getAttribute('type') || '', label: (button.innerText || '').trim(), ariaLabel: button.getAttribute('aria-label') || ''})),
    };
}"""

TAP_DEAL_ROOM_TRACK_CLICK_STATE_JS = """async () => {
    const button = Array.from(document.querySelectorAll('#tap-deal-room .tap-deal-offer-card button'))
      .find(candidate => (candidate.innerText || '').trim() === 'Track click');
    const beforeSummary = await fetch('/api/tap/deal-room/funnel?days=30&target_country=united-states&audience_segment=creator&package_tier=premium_alert_bundle')
      .then(response => response.json())
      .catch(error => ({error: String(error)}));
    window.__gdtTapDealRoomEventCalls = [];
    const previousFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const url = String(args[0]);
      const options = args[1] || {};
      const response = await previousFetch(...args);
      if (url.includes('/api/tap/deal-room/events')) {
        window.__gdtTapDealRoomEventCalls.push({
          url,
          method: String(options.method || 'GET').toUpperCase(),
          status: response.status,
          ok: response.ok,
        });
      }
      return response;
    };
    if (button) button.click();
    await new Promise(resolve => setTimeout(resolve, 900));
    const afterSummary = await fetch('/api/tap/deal-room/funnel?days=30&target_country=united-states&audience_segment=creator&package_tier=premium_alert_bundle')
      .then(response => response.json())
      .catch(error => ({error: String(error)}));
    return {
      had_button: Boolean(button),
      button_type: button?.getAttribute('type') || '',
      button_label: (button?.innerText || '').trim(),
      event_calls: window.__gdtTapDealRoomEventCalls || [],
      toast_text: document.getElementById('toast')?.textContent || '',
      before_clicks: beforeSummary?.totals?.clicks ?? null,
      after_clicks: afterSummary?.totals?.clicks ?? null,
      after_items: Array.isArray(afterSummary?.items) ? afterSummary.items.slice(0, 3) : [],
    };
}"""

TAP_DEAL_ROOM_CHECKOUT_OPEN_STATE_JS = """async () => {
    const button = document.querySelector('#tap-deal-room .tap-deal-offer-card [data-tap-checkout-index]');
    window.__gdtTapDealRoomCheckoutCalls = [];
    window.__gdtTapDealRoomCheckoutOpens = [];
    const previousFetch = window.fetch.bind(window);
    const previousOpen = window.open;
    window.open = (url, target, features) => {
      window.__gdtTapDealRoomCheckoutOpens.push({url: String(url), target: String(target || ''), features: String(features || '')});
      return {opener: null};
    };
    window.fetch = async (...args) => {
      const url = String(args[0]);
      const options = args[1] || {};
      const response = await previousFetch(...args);
      if (url.includes('/api/tap/deal-room/checkout')) {
        let requestBody = {};
        let responseBody = {};
        try {
          requestBody = JSON.parse(String(options.body || '{}'));
        } catch (error) {
          requestBody = {parse_error: String(error)};
        }
        try {
          responseBody = await response.clone().json();
        } catch (error) {
          responseBody = {parse_error: String(error)};
        }
        window.__gdtTapDealRoomCheckoutCalls.push({
          url,
          method: String(options.method || 'GET').toUpperCase(),
          status: response.status,
          ok: response.ok,
          request_body: requestBody,
          response_body: responseBody,
        });
      }
      return response;
    };
    if (button) button.click();
    await new Promise(resolve => setTimeout(resolve, 900));
    window.fetch = previousFetch;
    window.open = previousOpen;
    return {
      had_button: Boolean(button),
      button_type: button?.getAttribute('type') || '',
      button_label: (button?.innerText || '').trim(),
      button_disabled_after: Boolean(button?.disabled),
      button_busy_after: button?.getAttribute('aria-busy') || '',
      checkout_calls: window.__gdtTapDealRoomCheckoutCalls || [],
      open_calls: window.__gdtTapDealRoomCheckoutOpens || [],
      toast_text: document.getElementById('toast')?.textContent || '',
      toast_type: document.getElementById('toast')?.dataset.lastToastType || '',
      warning_banner: document.getElementById('dashboard-warning-banner')?.innerText || '',
    };
}"""

DASHBOARD_FIXTURE_ENDPOINTS_STATE_JS = """async () => {
    const paths = ['/api/stats/categories'];
    const results = [];
    for (const path of paths) {
      const response = await fetch(path);
      let payload = null;
      try {
        payload = await response.json();
      } catch (error) {
        payload = {parse_error: String(error)};
      }
      results.push({
        path,
        status: response.status,
        degraded_header: response.headers.get('x-dashboard-degraded') || '',
        degraded_source_header: response.headers.get('x-dashboard-degraded-source') || '',
        degraded_meta: Boolean(payload && !Array.isArray(payload) && payload._meta?.degraded),
        payload_kind: Array.isArray(payload) ? 'array' : typeof payload,
        item_count: Array.isArray(payload) ? payload.length : null,
      });
    }
    return results;
}"""


def _run_browser(
    base_url: str,
    screenshot_path: Path,
    timeout_ms: int,
    *,
    require_tap_source_notes: bool = False,
) -> BrowserRun:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    checks: list[dict[str, Any]] = []
    console_errors: list[str] = []
    console_warnings: list[str] = []
    page_errors: list[str] = []
    request_failures: list[str] = []
    allow_checkout_503_console_error = False
    same_origin = base_url.rstrip("/")

    def _probe_operator_preview_busy(
        page: Any,
        *,
        button_selector: str,
        preview_selector: str,
        url_fragment: str,
        loading_text: str,
        loaded_text: str,
    ) -> tuple[bool, dict[str, Any]]:
        detail: dict[str, Any] = {
            "button_selector": button_selector,
            "preview_selector": preview_selector,
            "url_fragment": url_fragment,
        }
        button = page.locator(button_selector).first
        if button.count() < 1:
            detail["available"] = False
            return False, detail
        if button.get_attribute("aria-expanded") == "true":
            button.click()
            page.wait_for_timeout(120)
        target_controls = str(button.get_attribute("aria-controls") or "").strip()
        state_button_selector = f"[aria-controls='{target_controls}']" if target_controls else button_selector
        detail["target_controls"] = target_controls

        page.evaluate(
            """({ urlFragment }) => {
                if (window.__gdtOperatorBusyFetch) {
                    window.fetch = window.__gdtOperatorBusyFetch;
                }
                window.__gdtOperatorBusyFetch = window.fetch;
                window.__gdtOperatorBusyCalls = 0;
                window.fetch = async (...args) => {
                    const url = String(args[0] || '');
                    if (url.includes(urlFragment)) {
                        window.__gdtOperatorBusyCalls += 1;
                        await new Promise(resolve => setTimeout(resolve, 450));
                    }
                    return window.__gdtOperatorBusyFetch(...args);
                };
            }""",
            {"urlFragment": url_fragment},
        )

        loaded = False
        try:
            before = page.evaluate(
                """({ buttonSelector, previewSelector }) => {
                    const button = document.querySelector(buttonSelector);
                    const controls = button?.getAttribute('aria-controls') || '';
                    const preview = previewSelector
                        ? document.querySelector(previewSelector)
                        : controls
                        ? document.getElementById(controls)
                        : null;
                    return {
                        buttonText: (button?.innerText || '').trim(),
                        buttonBusy: button?.getAttribute('aria-busy') || '',
                        buttonExpanded: button?.getAttribute('aria-expanded') || '',
                        previewBusy: preview?.getAttribute('aria-busy') || '',
                        previewHidden: Boolean(preview?.hidden),
                        previewText: (preview?.innerText || '').trim(),
                    };
                }""",
                {"buttonSelector": state_button_selector, "previewSelector": preview_selector},
            )
            button.click()
            page.wait_for_timeout(90)
            during = page.evaluate(
                """({ buttonSelector, previewSelector }) => {
                    const button = document.querySelector(buttonSelector);
                    const controls = button?.getAttribute('aria-controls') || '';
                    const preview = previewSelector
                        ? document.querySelector(previewSelector)
                        : controls
                        ? document.getElementById(controls)
                        : null;
                    return {
                        buttonText: (button?.innerText || '').trim(),
                        buttonBusy: button?.getAttribute('aria-busy') || '',
                        buttonExpanded: button?.getAttribute('aria-expanded') || '',
                        previewBusy: preview?.getAttribute('aria-busy') || '',
                        previewHidden: Boolean(preview?.hidden),
                        previewText: (preview?.innerText || '').trim(),
                        fetchCalls: window.__gdtOperatorBusyCalls || 0,
                    };
                }""",
                {"buttonSelector": state_button_selector, "previewSelector": preview_selector},
            )
            try:
                page.wait_for_function(
                    """({ buttonSelector, previewSelector, loadedText }) => {
                        const button = document.querySelector(buttonSelector);
                        const controls = button?.getAttribute('aria-controls') || '';
                        const preview = previewSelector
                            ? document.querySelector(previewSelector)
                            : controls
                            ? document.getElementById(controls)
                            : null;
                        return (preview?.innerText || '').includes(loadedText);
                    }""",
                    arg={
                        "buttonSelector": state_button_selector,
                        "previewSelector": preview_selector,
                        "loadedText": loaded_text,
                    },
                    timeout=timeout_ms,
                )
                loaded = True
            except PlaywrightTimeoutError:
                loaded = False
            after = page.evaluate(
                """({ buttonSelector, previewSelector }) => {
                    const button = document.querySelector(buttonSelector);
                    const controls = button?.getAttribute('aria-controls') || '';
                    const preview = previewSelector
                        ? document.querySelector(previewSelector)
                        : controls
                        ? document.getElementById(controls)
                        : null;
                    return {
                        buttonText: (button?.innerText || '').trim(),
                        buttonBusy: button?.getAttribute('aria-busy') || '',
                        buttonExpanded: button?.getAttribute('aria-expanded') || '',
                        previewBusy: preview?.getAttribute('aria-busy') || '',
                        previewHidden: Boolean(preview?.hidden),
                        previewText: (preview?.innerText || '').trim().slice(0, 220),
                        fetchCalls: window.__gdtOperatorBusyCalls || 0,
                    };
                }""",
                {"buttonSelector": state_button_selector, "previewSelector": preview_selector},
            )
        finally:
            page.evaluate(
                """() => {
                    if (window.__gdtOperatorBusyFetch) {
                        window.fetch = window.__gdtOperatorBusyFetch;
                        delete window.__gdtOperatorBusyFetch;
                    }
                    delete window.__gdtOperatorBusyCalls;
                }"""
            )

        state_button = page.locator(state_button_selector).first
        if state_button.get_attribute("aria-expanded") == "true":
            state_button.click()
            page.wait_for_timeout(120)
        collapsed = page.evaluate(
            """({ buttonSelector, previewSelector }) => {
                const button = document.querySelector(buttonSelector);
                const controls = button?.getAttribute('aria-controls') || '';
                const preview = previewSelector
                    ? document.querySelector(previewSelector)
                    : controls
                    ? document.getElementById(controls)
                    : null;
                return {
                    buttonText: (button?.innerText || '').trim(),
                    buttonBusy: button?.getAttribute('aria-busy') || '',
                    buttonExpanded: button?.getAttribute('aria-expanded') || '',
                    previewBusy: preview?.getAttribute('aria-busy') || '',
                    previewHidden: Boolean(preview?.hidden),
                    previewText: (preview?.innerText || '').trim(),
                };
            }""",
            {"buttonSelector": state_button_selector, "previewSelector": preview_selector},
        )
        before_collapsed_ok = (
            before.get("buttonBusy") == "false"
            and before.get("previewBusy") == "false"
            and before.get("buttonExpanded") == "false"
            and before.get("previewHidden") is True
            and before.get("previewText") == ""
        )
        during_busy_visible_ok = (
            during.get("buttonBusy") == "true"
            and during.get("previewBusy") == "true"
            and during.get("buttonExpanded") == "true"
            and during.get("previewHidden") is False
            and loading_text in during.get("previewText", "")
        )
        after_loaded_visible_ok = (
            loaded
            and after.get("buttonBusy") == "false"
            and after.get("previewBusy") == "false"
            and after.get("buttonExpanded") == "true"
            and after.get("previewHidden") is False
            and loaded_text in after.get("previewText", "")
        )
        collapsed_preview_hidden_ok = (
            collapsed.get("buttonBusy") == "false"
            and collapsed.get("previewBusy") == "false"
            and collapsed.get("buttonExpanded") == "false"
            and collapsed.get("previewHidden") is True
            and collapsed.get("previewText") == ""
        )
        fetch_call_count = max(int(during.get("fetchCalls") or 0), int(after.get("fetchCalls") or 0))
        detail.update(
            {
                "expected_mode": "operator_preview_busy_state_lifecycle",
                "before_collapsed_ok": before_collapsed_ok,
                "during_busy_visible_ok": during_busy_visible_ok,
                "after_loaded_visible_ok": after_loaded_visible_ok,
                "collapsed_preview_hidden_ok": collapsed_preview_hidden_ok,
                "loaded_text_seen": loaded,
                "fetch_call_count": fetch_call_count,
                "loading_text": loading_text,
                "loaded_text": loaded_text,
            }
        )
        ok = (
            before_collapsed_ok
            and during_busy_visible_ok
            and after_loaded_visible_ok
            and collapsed_preview_hidden_ok
        )
        return ok, detail

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1100},
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()

        page.on(
            "console",
            lambda msg: (
                console_errors.append(msg.text)
                if msg.type == "error"
                else console_warnings.append(msg.text)
                if msg.type == "warning"
                else None
            ),
        )
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on(
            "requestfailed",
            lambda request: request_failures.append(f"{request.url} :: {request.failure}")
            if request.url.startswith(same_origin)
            else None,
        )

        page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_selector("#tap-refresh-btn", timeout=timeout_ms)
        try:
            page.wait_for_function(DASHBOARD_CONTENT_READY_JS, timeout=timeout_ms)
        except PlaywrightTimeoutError:
            pass

        title = page.locator("header h1").inner_text(timeout=timeout_ms)
        _record_check(checks, "desktop_header_visible", "getdaytrends Pro" in title, title)

        main_landmark_state = page.evaluate(DASHBOARD_MAIN_LANDMARK_JS)
        page.locator(".skip-link").focus()
        page.keyboard.press("Enter")
        try:
            page.wait_for_function(
                "() => window.location.hash === '#dashboard-main' && document.activeElement?.id === 'dashboard-main'",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        main_skip_activation_state = page.evaluate(DASHBOARD_MAIN_SKIP_ACTIVATION_JS)
        main_landmark_contract_ok = (
            main_landmark_state.get("mainCount") == 1
            and main_landmark_state.get("mainId") == "dashboard-main"
            and main_landmark_state.get("mainTag") == "MAIN"
            and main_landmark_state.get("mainTabIndex") == "-1"
        )
        main_skip_link_contract_ok = (
            main_landmark_state.get("skipText") == "Skip to dashboard content"
            and main_landmark_state.get("skipHref") == "#dashboard-main"
            and main_landmark_state.get("skipFirstBodyChild") is True
        )
        main_content_inside_landmark_ok = (
            main_landmark_state.get("containsKpi") is True
            and main_landmark_state.get("containsTable") is True
        )
        main_chrome_outside_main_ok = (
            main_landmark_state.get("headerInsideMain") is False
            and main_landmark_state.get("footerInsideMain") is False
        )
        main_skip_activation_ok = (
            main_skip_activation_state.get("hash") == "#dashboard-main"
            and main_skip_activation_state.get("mainFocused") is True
        )
        _record_check(
            checks,
            "dashboard_main_landmark_accessible",
            main_landmark_contract_ok
            and main_skip_link_contract_ok
            and main_content_inside_landmark_ok
            and main_chrome_outside_main_ok
            and main_skip_activation_ok,
            {
                "expected_mode": "dashboard_main_landmark_skip_link_contract",
                "main_landmark_contract_ok": main_landmark_contract_ok,
                "skip_link_contract_ok": main_skip_link_contract_ok,
                "content_inside_landmark_ok": main_content_inside_landmark_ok,
                "chrome_outside_main_ok": main_chrome_outside_main_ok,
                "skip_activation_ok": main_skip_activation_ok,
                "visible_main_count": main_landmark_state.get("mainCount"),
                "main_id": main_landmark_state.get("mainId"),
                "active_element_id": main_skip_activation_state.get("activeElementId"),
            },
        )

        status_pill_live_region_state = page.evaluate(DASHBOARD_STATUS_PILL_LIVE_REGION_JS)
        status_pill_live_region_contract_ok = (
            status_pill_live_region_state.get("exists") is True
            and status_pill_live_region_state.get("role") == "status"
            and status_pill_live_region_state.get("live") == "polite"
            and status_pill_live_region_state.get("atomic") == "true"
        )
        status_pill_label_ok = status_pill_live_region_state.get("label") == "Dashboard status"
        status_pill_state_text_ok = status_pill_live_region_state.get("text") in {
            "Idle",
            "Running",
            "Error",
            "Unknown",
            "Loading",
        }
        status_pill_visible_style_ok = (
            "status-pill" in status_pill_live_region_state.get("className", "")
            and status_pill_live_region_state.get("visible") is True
        )
        status_pill_passive_region_ok = (
            status_pill_live_region_state.get("hasTabIndex") is False
            and status_pill_live_region_state.get("focused") is False
        )
        _record_check(
            checks,
            "dashboard_status_pill_live_region",
            status_pill_live_region_contract_ok
            and status_pill_label_ok
            and status_pill_state_text_ok
            and status_pill_visible_style_ok
            and status_pill_passive_region_ok,
            {
                "expected_mode": "dashboard_status_pill_passive_live_region",
                "live_region_contract_ok": status_pill_live_region_contract_ok,
                "label_ok": status_pill_label_ok,
                "state_text_ok": status_pill_state_text_ok,
                "visible_style_ok": status_pill_visible_style_ok,
                "passive_status_region_ok": status_pill_passive_region_ok,
                "status_text": status_pill_live_region_state.get("text"),
                "class_name": status_pill_live_region_state.get("className"),
            },
        )

        footer_landmark_state = page.evaluate(DASHBOARD_FOOTER_LANDMARK_JS)
        footer_contentinfo_landmark_ok = (
            footer_landmark_state.get("footerCount") == 1
            and footer_landmark_state.get("footerTag") == "FOOTER"
            and "footer" in footer_landmark_state.get("footerClass", "")
            and footer_landmark_state.get("footerRole") == ""
            and footer_landmark_state.get("visible") is True
        )
        footer_content_text_ok = "getdaytrends Pro Dashboard" in footer_landmark_state.get("footerText", "")
        footer_body_level_ok = (
            footer_landmark_state.get("footerBodyChild") is True
            and footer_landmark_state.get("footerInsideMain") is False
        )
        footer_legacy_div_absent_ok = footer_landmark_state.get("legacyDivFooterCount") == 0
        _record_check(
            checks,
            "dashboard_footer_contentinfo_landmark",
            footer_contentinfo_landmark_ok
            and footer_content_text_ok
            and footer_body_level_ok
            and footer_legacy_div_absent_ok,
            {
                "expected_mode": "dashboard_footer_body_level_contentinfo_landmark",
                "contentinfo_landmark_ok": footer_contentinfo_landmark_ok,
                "content_text_ok": footer_content_text_ok,
                "body_level_footer_ok": footer_body_level_ok,
                "legacy_div_footer_absent_ok": footer_legacy_div_absent_ok,
                "footer_count": footer_landmark_state.get("footerCount"),
                "footer_tag": footer_landmark_state.get("footerTag"),
                "footer_class": footer_landmark_state.get("footerClass"),
            },
        )

        log_viewer_live_region_state = page.evaluate(DASHBOARD_LOG_VIEWER_LIVE_REGION_JS)
        log_viewer_live_region_contract_ok = (
            log_viewer_live_region_state.get("exists") is True
            and log_viewer_live_region_state.get("role") == "log"
            and log_viewer_live_region_state.get("live") == "polite"
            and log_viewer_live_region_state.get("atomic") == "false"
            and log_viewer_live_region_state.get("relevant") == "additions text"
        )
        log_viewer_label_ok = log_viewer_live_region_state.get("label") == "Pipeline logs"
        log_viewer_visible_entries_ok = (
            log_viewer_live_region_state.get("visible") is True
            and log_viewer_live_region_state.get("entryCount", 0) >= 1
        )
        log_viewer_passive_region_ok = (
            log_viewer_live_region_state.get("focused") is False
            and log_viewer_live_region_state.get("hasTabIndex") is False
        )
        _record_check(
            checks,
            "dashboard_log_viewer_live_region",
            log_viewer_live_region_contract_ok
            and log_viewer_label_ok
            and log_viewer_visible_entries_ok
            and log_viewer_passive_region_ok,
            {
                "expected_mode": "dashboard_log_viewer_passive_live_region",
                "live_region_contract_ok": log_viewer_live_region_contract_ok,
                "label_ok": log_viewer_label_ok,
                "visible_entries_ok": log_viewer_visible_entries_ok,
                "passive_log_region_ok": log_viewer_passive_region_ok,
                "entry_count": log_viewer_live_region_state.get("entryCount"),
                "scrollable": log_viewer_live_region_state.get("scrollable"),
            },
        )

        initial_preset_state = page.evaluate(TAP_PRESET_BUTTON_STATE_JS)
        page.locator("#tap-target-country").fill("")
        page.locator("#tap-save-preset-btn").click()
        tap_empty_preset_detail: dict[str, Any] = {}
        try:
            page.wait_for_function(
                """() => {
                    const toast = document.getElementById('toast');
                    return toast
                        && toast.dataset.lastToastType === 'error'
                        && toast.dataset.lastToastRole === 'alert'
                        && toast.dataset.lastToastLive === 'assertive'
                        && toast.textContent.includes('Enter a market before saving a preset.');
                }""",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        tap_empty_preset_detail = page.evaluate(
            """() => {
                const toast = document.getElementById('toast');
                return {
                    targetMarket: document.getElementById('tap-target-country')?.value || '',
                    toastText: toast?.textContent || '',
                    lastType: toast?.dataset.lastToastType || '',
                    lastRole: toast?.dataset.lastToastRole || '',
                    lastLive: toast?.dataset.lastToastLive || '',
                    role: toast?.getAttribute('role') || '',
                    live: toast?.getAttribute('aria-live') || '',
                };
            }"""
        )
        _record_check(
            checks,
            "tap_empty_preset_save_feedback",
            tap_empty_preset_detail.get("targetMarket") == ""
            and tap_empty_preset_detail.get("toastText") == "Enter a market before saving a preset."
            and tap_empty_preset_detail.get("lastType") == "error"
            and tap_empty_preset_detail.get("lastRole") == "alert"
            and tap_empty_preset_detail.get("lastLive") == "assertive",
            tap_empty_preset_detail,
        )

        page.locator("#tap-target-country").fill("united-states")
        try:
            page.wait_for_function(
                "() => document.getElementById('tap-target-country')?.value === 'united-states'",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        before_save_preset_detail = page.evaluate(
            """() => ({
                targetMarket: document.getElementById('tap-target-country')?.value || '',
                storage: localStorage.getItem('getdaytrends.tap-target-presets') || '',
                toastText: document.getElementById('toast')?.innerText || '',
            })"""
        )
        page.locator("#tap-save-preset-btn").evaluate("(button) => button.click()")
        try:
            page.wait_for_function(
                """() => Array.from(document.querySelectorAll('#tap-preset-strip button'))
                    .some(button => (button.textContent || '').trim() === 'UNITED-STATES'
                        && button.getAttribute('aria-pressed') === 'true'
                        && button.classList.contains('tap-preset-btn-active'))
                    && (document.getElementById('tap-alert-status')?.innerText || '').includes('for UNITED-STATES')
                    && (document.getElementById('toast')?.innerText || '').trim() === 'Saved and applied preset for UNITED-STATES.'""",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        after_save_preset_state = page.evaluate(TAP_PRESET_BUTTON_STATE_JS)
        after_save_preset_detail = page.evaluate(
            """() => ({
                targetMarket: document.getElementById('tap-target-country')?.value || '',
                storage: localStorage.getItem('getdaytrends.tap-target-presets') || '',
                toastText: document.getElementById('toast')?.innerText || '',
                statusText: document.getElementById('tap-alert-status')?.innerText || '',
            })"""
        )
        _record_check(
            checks,
            "tap_preset_pressed_state",
            _tap_preset_state_ok(initial_preset_state, "ALL")
            and _tap_preset_state_ok(after_save_preset_state, "UNITED-STATES")
            and "for UNITED-STATES" in after_save_preset_detail.get("statusText", "")
            and after_save_preset_detail.get("toastText") == "Saved and applied preset for UNITED-STATES.",
            {
                "expected_mode": "tap_target_market_preset_pressed_state",
                "initial_preset": _tap_preset_state_summary(initial_preset_state, "ALL"),
                "before_save_target_market": before_save_preset_detail.get("targetMarket", ""),
                "before_save_storage_empty_ok": before_save_preset_detail.get("storage") == "",
                "after_save_preset": _tap_preset_state_summary(after_save_preset_state, "UNITED-STATES"),
                "after_save_target_market": after_save_preset_detail.get("targetMarket", ""),
                "after_save_storage_has_market_ok": "united-states" in after_save_preset_detail.get("storage", ""),
                "after_save_toast_ok": after_save_preset_detail.get("toastText")
                == "Saved and applied preset for UNITED-STATES.",
                "after_save_status_for_target_ok": "for UNITED-STATES"
                in after_save_preset_detail.get("statusText", ""),
            },
        )
        page.locator("#tap-clear-presets-btn").evaluate("(button) => button.click()")
        try:
            page.wait_for_function(
                """() => Array.from(document.querySelectorAll('#tap-preset-strip button'))
                    .some(button => (button.textContent || '').trim() === 'ALL'
                        && button.getAttribute('aria-pressed') === 'true'
                        && button.classList.contains('tap-preset-btn-active'))
                    && (document.getElementById('tap-target-country')?.value || '') === ''
                    && (document.getElementById('tap-alert-status')?.innerText || '').startsWith('0 queued alert(s) loaded')
                    && !(document.getElementById('tap-alert-status')?.innerText || '').includes('for UNITED-STATES')
                    && (document.getElementById('toast')?.innerText || '').trim() === 'Preset markets reset and filter cleared.'""",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        after_reset_preset_state = page.evaluate(TAP_PRESET_BUTTON_STATE_JS)
        after_reset_preset_detail = page.evaluate(
            """() => ({
                targetMarket: document.getElementById('tap-target-country')?.value || '',
                storage: localStorage.getItem('getdaytrends.tap-target-presets') || '',
                toastText: document.getElementById('toast')?.innerText || '',
                statusText: document.getElementById('tap-alert-status')?.innerText || '',
            })"""
        )
        _record_check(
            checks,
            "tap_reset_presets_clears_filter",
            _tap_preset_state_ok(after_reset_preset_state, "ALL")
            and after_reset_preset_detail.get("targetMarket") == ""
            and str(after_reset_preset_detail.get("statusText", "")).startswith("0 queued alert(s) loaded")
            and "for UNITED-STATES" not in str(after_reset_preset_detail.get("statusText", ""))
            and after_reset_preset_detail.get("toastText") == "Preset markets reset and filter cleared.",
            {
                "expected_mode": "tap_target_market_preset_reset_to_all",
                "after_reset_preset": _tap_preset_state_summary(after_reset_preset_state, "ALL"),
                "target_market_cleared_ok": after_reset_preset_detail.get("targetMarket") == "",
                "storage_preserves_default_markets_ok": all(
                    market in after_reset_preset_detail.get("storage", "")
                    for market in ('""', "korea", "united-states", "japan")
                ),
                "reset_toast_ok": after_reset_preset_detail.get("toastText")
                == "Preset markets reset and filter cleared.",
                "status_reset_ok": str(after_reset_preset_detail.get("statusText", "")).startswith(
                    "0 queued alert(s) loaded"
                )
                and "for UNITED-STATES" not in str(after_reset_preset_detail.get("statusText", "")),
                "carbon_filtering_reference": "https://carbondesignsystem.com/patterns/filtering/",
            },
        )
        page.locator("#tap-target-country").fill("korea")
        page.locator("#tap-refresh-btn").click()
        try:
            page.wait_for_function(
                """() => Array.from(document.querySelectorAll('#tap-preset-strip button'))
                    .some(button => (button.textContent || '').trim() === 'KOREA'
                        && button.getAttribute('aria-pressed') === 'true'
                        && button.classList.contains('tap-preset-btn-active'))
                    && (document.getElementById('tap-alert-status')?.innerText || '').includes('for KOREA')""",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        typed_target_refresh_preset_state = page.evaluate(TAP_PRESET_BUTTON_STATE_JS)
        typed_target_refresh_detail = page.evaluate(
            """() => ({
                targetMarket: document.getElementById('tap-target-country')?.value || '',
                statusText: document.getElementById('tap-alert-status')?.innerText || '',
                allPressed: document.querySelector('#tap-preset-strip button')?.getAttribute('aria-pressed') || '',
            })"""
        )
        _record_check(
            checks,
            "tap_typed_target_refresh_updates_preset_state",
            _tap_preset_state_ok(typed_target_refresh_preset_state, "KOREA")
            and typed_target_refresh_detail.get("targetMarket") == "korea"
            and "for KOREA" in str(typed_target_refresh_detail.get("statusText", ""))
            and typed_target_refresh_detail.get("allPressed") == "false",
            {
                "expected_mode": "tap_typed_target_refresh_preset_state",
                "typed_refresh_preset": _tap_preset_state_summary(typed_target_refresh_preset_state, "KOREA"),
                "target_market_applied_ok": typed_target_refresh_detail.get("targetMarket") == "korea",
                "status_for_target_ok": "for KOREA" in str(typed_target_refresh_detail.get("statusText", "")),
                "all_preset_inactive_ok": typed_target_refresh_detail.get("allPressed") == "false",
                "carbon_filter_state_reference": "https://carbondesignsystem.com/patterns/filtering/",
            },
        )
        page.locator("#tap-target-country").fill("japan")
        page.locator("#tap-target-country").press("Enter")
        try:
            page.wait_for_function(
                "() => (document.getElementById('tap-alert-status')?.innerText || '').includes('for JAPAN')",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        after_enter_japan_state = page.evaluate(TAP_PRESET_BUTTON_STATE_JS)
        after_enter_japan_detail = page.evaluate(
            """() => ({
                targetMarket: document.getElementById('tap-target-country')?.value || '',
                statusText: document.getElementById('tap-alert-status')?.innerText || '',
                activeElementId: document.activeElement?.id || '',
            })"""
        )
        page.locator("#tap-target-country").fill("united-states")
        page.locator("#tap-target-country").press("Enter")
        try:
            page.wait_for_function(
                "() => (document.getElementById('tap-alert-status')?.innerText || '').includes('for UNITED-STATES')",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        after_enter_restore_state = page.evaluate(TAP_PRESET_BUTTON_STATE_JS)
        after_enter_restore_detail = page.evaluate(
            """() => ({
                targetMarket: document.getElementById('tap-target-country')?.value || '',
                statusText: document.getElementById('tap-alert-status')?.innerText || '',
                activeElementId: document.activeElement?.id || '',
            })"""
        )
        _record_check(
            checks,
            "tap_target_market_enter_key_apply",
            after_enter_japan_detail.get("targetMarket") == "japan"
            and "for JAPAN" in after_enter_japan_detail.get("statusText", "")
            and _tap_preset_state_ok(after_enter_japan_state, "JAPAN")
            and after_enter_japan_detail.get("activeElementId") == "tap-target-country"
            and after_enter_restore_detail.get("targetMarket") == "united-states"
            and "for UNITED-STATES" in after_enter_restore_detail.get("statusText", "")
            and _tap_preset_state_ok(after_enter_restore_state, "UNITED-STATES")
            and after_enter_restore_detail.get("activeElementId") == "tap-target-country",
            {
                "expected_mode": "tap_target_market_enter_key_preset_apply",
                "after_japan_preset": _tap_preset_state_summary(after_enter_japan_state, "JAPAN"),
                "after_japan_target_market_ok": after_enter_japan_detail.get("targetMarket") == "japan",
                "after_japan_status_ok": "for JAPAN" in after_enter_japan_detail.get("statusText", ""),
                "after_japan_focus_retained_ok": after_enter_japan_detail.get("activeElementId")
                == "tap-target-country",
                "after_restore_preset": _tap_preset_state_summary(after_enter_restore_state, "UNITED-STATES"),
                "after_restore_target_market_ok": after_enter_restore_detail.get("targetMarket") == "united-states",
                "after_restore_status_ok": "for UNITED-STATES"
                in after_enter_restore_detail.get("statusText", ""),
                "after_restore_focus_retained_ok": after_enter_restore_detail.get("activeElementId")
                == "tap-target-country",
            },
        )
        tap_filter_control_state = page.evaluate(TAP_ALERT_FILTER_CONTROL_STATE_JS)
        tap_filter_control_gaps = _tap_alert_filter_control_gaps(tap_filter_control_state)
        _record_check(
            checks,
            "tap_alert_queue_filter_labels",
            not tap_filter_control_gaps,
            {
                "filters": tap_filter_control_state,
                "gaps": tap_filter_control_gaps,
                "wcag_labels_or_instructions_reference": "https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html",
                "w3c_labeling_controls_reference": "https://www.w3.org/WAI/tutorials/forms/labels/",
            },
        )
        page.locator("#tap-target-country").fill("zz-empty-dispatch")
        page.select_option("#tap-alert-lifecycle", "")
        page.select_option("#tap-alert-limit", "5")
        page.locator("#tap-refresh-btn").click()
        try:
            page.wait_for_function(
                """() => {
                    const target = document.querySelector('#tap-target-country')?.value || '';
                    const lifecycle = document.querySelector('#tap-alert-lifecycle')?.value || '';
                    const status = document.querySelector('#tap-alert-status')?.textContent || '';
                    const title = document.querySelector('#tap-alert-list .tap-alert-title')?.textContent || '';
                    return target === 'zz-empty-dispatch'
                        && lifecycle === ''
                        && status.startsWith('0 alert(s) loaded')
                        && status.includes('for ZZ-EMPTY-DISPATCH')
                        && title.startsWith('No alerts')
                        && !status.includes('queued alert(s) loaded');
                }""",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        tap_all_states_empty_copy = page.evaluate(
            """() => ({
                lifecycleValue: document.querySelector('#tap-alert-lifecycle')?.value || '',
                statusText: (document.querySelector('#tap-alert-status')?.textContent || '').trim(),
                emptyTitle: (document.querySelector('#tap-alert-list .tap-alert-title')?.textContent || '').trim(),
                emptyBody: (document.querySelector('#tap-alert-list .tap-alert-body')?.textContent || '').trim(),
            })"""
        )
        _record_check(
            checks,
            "tap_alert_all_states_empty_copy",
            tap_all_states_empty_copy.get("lifecycleValue") == ""
            and str(tap_all_states_empty_copy.get("statusText", "")).startswith("0 alert(s) loaded")
            and str(tap_all_states_empty_copy.get("emptyTitle", "")).startswith("No alerts")
            and "Fresh TAP signals" in str(tap_all_states_empty_copy.get("emptyBody", ""))
            and "No all alerts" not in str(tap_all_states_empty_copy.get("emptyTitle", ""))
            and "0 all alert(s)" not in str(tap_all_states_empty_copy.get("statusText", "")),
            {
                "all_states_empty_copy": tap_all_states_empty_copy,
                "carbon_empty_states_reference": "https://carbondesignsystem.com/patterns/empty-states-pattern",
                "stackoverflow_empty_states_reference": "https://stackoverflow.design/system/components/empty-states",
            },
        )
        page.locator("#tap-target-country").fill("united-states")
        page.select_option("#tap-alert-lifecycle", "queued")
        page.select_option("#tap-alert-limit", "6")
        page.locator("#tap-refresh-btn").click()
        try:
            page.wait_for_function(
                """() => {
                    const target = document.querySelector('#tap-target-country')?.value || '';
                    const status = document.querySelector('#tap-alert-status')?.textContent || '';
                    return target === 'united-states'
                        && status.includes('queued alert(s) loaded')
                        && status.includes('for UNITED-STATES');
                }""",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        tap_action_group_state = page.evaluate(TAP_ALERT_ACTION_GROUP_STATE_JS)
        tap_action_group_gaps = _tap_alert_action_group_gaps(tap_action_group_state)
        _record_check(
            checks,
            "tap_alert_queue_action_groups",
            not tap_action_group_gaps,
            {
                "groups": tap_action_group_state,
                "gaps": tap_action_group_gaps,
                "wcag_target_size_minimum_reference": W3C_WCAG_TARGET_SIZE_MINIMUM_URL,
            },
        )
        buttons_without_type = page.evaluate(DASHBOARD_BUTTON_TYPE_STATE_JS)
        _record_check(
            checks,
            "dashboard_buttons_have_explicit_type",
            not buttons_without_type,
            {"buttons_without_type": buttons_without_type},
        )
        page.locator("#tap-target-country").fill("zz-empty-dispatch")
        page.locator("#tap-alert-lifecycle").select_option("")
        page.locator("#tap-alert-limit").select_option("5")
        page.locator("#tap-refresh-btn").click()
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
                const originalFetch = window.fetch.bind(window);
                window.__gdtTapDispatchCalls = [];
                window.fetch = async (...args) => {
                    const url = String(args[0]);
                    if (url.includes('/api/tap/alerts/dispatch')) {
                        window.__gdtTapDispatchCalls.push({
                            url,
                            disabledAtCall: Boolean(document.getElementById('tap-dry-run-btn')?.disabled),
                            busyAtCall: document.getElementById('tap-alert-status')?.getAttribute('aria-busy') || '',
                        });
                        await new Promise(resolve => window.setTimeout(resolve, 650));
                    }
                    return originalFetch(...args);
                };
            }"""
        )
        page.locator("#tap-dry-run-btn").click()
        try:
            page.wait_for_function(
                """() => {
                    const ids = ['tap-dispatch-btn', 'tap-dry-run-btn', 'tap-refresh-btn'];
                    return document.getElementById('tap-alert-status')?.getAttribute('aria-busy') === 'true'
                        && ids.every(id => document.getElementById(id)?.disabled === true)
                        && (document.getElementById('tap-alert-status')?.innerText || '').trim() === 'Running dry run...';
                }""",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        tap_dispatch_busy_state = page.evaluate(
            """() => {
                const ids = ['tap-dispatch-btn', 'tap-dry-run-btn', 'tap-refresh-btn'];
                return {
                    statusBusy: document.getElementById('tap-alert-status')?.getAttribute('aria-busy') || '',
                    statusText: (document.getElementById('tap-alert-status')?.innerText || '').trim(),
                    controls: ids.map(id => ({
                        id,
                        disabled: Boolean(document.getElementById(id)?.disabled),
                    })),
                    dispatchCalls: window.__gdtTapDispatchCalls || [],
                };
            }"""
        )
        try:
            page.wait_for_function(
                "() => (document.getElementById('tap-alert-status')?.innerText || '').trim() !== 'Running dry run...'",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            page.wait_for_timeout(1200)

        status_text = page.locator("#tap-alert-status").inner_text(timeout=timeout_ms)
        _record_check(checks, "tap_controls_clickable", bool(status_text.strip()), status_text)
        try:
            page.wait_for_function(
                "() => document.getElementById('tap-alert-status')?.getAttribute('aria-busy') === 'false'",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        status_text = page.locator("#tap-alert-status").inner_text(timeout=timeout_ms)
        tap_status_live_region = page.evaluate(TAP_ALERT_STATUS_LIVE_REGION_JS)
        dispatch_inflight_call_seen = any(
            call.get("disabledAtCall") is True and call.get("busyAtCall") == "true"
            for call in tap_dispatch_busy_state.get("dispatchCalls", [])
        )
        tap_dispatch_ready_state = page.evaluate(
            """() => {
                const ids = ['tap-dispatch-btn', 'tap-dry-run-btn', 'tap-refresh-btn'];
                return {
                    statusBusy: document.getElementById('tap-alert-status')?.getAttribute('aria-busy') || '',
                    statusText: (document.getElementById('tap-alert-status')?.innerText || '').trim(),
                    controls: ids.map(id => ({
                        id,
                        disabled: Boolean(document.getElementById(id)?.disabled),
                    })),
                    dispatchCalls: window.__gdtTapDispatchCalls || [],
                };
            }"""
        )
        tap_dispatch_busy_controls_disabled_ok = all(
            control.get("disabled") is True for control in tap_dispatch_busy_state.get("controls", [])
        )
        tap_dispatch_ready_controls_enabled_ok = all(
            control.get("disabled") is False for control in tap_dispatch_ready_state.get("controls", [])
        )
        tap_dispatch_busy_phase_ok = (
            tap_dispatch_busy_state.get("statusBusy") == "true"
            and tap_dispatch_busy_state.get("statusText") == "Running dry run..."
            and tap_dispatch_busy_controls_disabled_ok
        )
        tap_dispatch_call_count = len(tap_dispatch_busy_state.get("dispatchCalls", []))
        _record_check(
            checks,
            "tap_dispatch_busy_state",
            (tap_dispatch_busy_phase_ok or dispatch_inflight_call_seen)
            and tap_dispatch_call_count == 1
            and tap_dispatch_ready_state.get("statusBusy") == "false"
            and tap_dispatch_ready_controls_enabled_ok,
            {
                "expected_mode": "tap_dispatch_dry_run_busy_ready_state",
                "busy_phase_ok": tap_dispatch_busy_phase_ok,
                "busy_status_text_ok": tap_dispatch_busy_state.get("statusText") == "Running dry run...",
                "busy_controls_disabled_ok": tap_dispatch_busy_controls_disabled_ok,
                "dispatch_inflight_call_seen": dispatch_inflight_call_seen,
                "dispatch_call_count": tap_dispatch_call_count,
                "ready_state_ok": tap_dispatch_ready_state.get("statusBusy") == "false",
                "ready_controls_enabled_ok": tap_dispatch_ready_controls_enabled_ok,
                "ready_status_text": tap_dispatch_ready_state.get("statusText", ""),
                "control_ids": [control.get("id") for control in tap_dispatch_ready_state.get("controls", [])],
            },
        )
        _record_check(
            checks,
            "tap_alert_status_live_region",
            tap_status_live_region.get("role") == "status"
            and tap_status_live_region.get("live") == "polite"
            and tap_status_live_region.get("atomic") == "true"
            and tap_status_live_region.get("busy") == "false"
            and bool(tap_status_live_region.get("text")),
            tap_status_live_region,
        )
        page.locator("#tap-dispatch-btn").click()
        try:
            page.wait_for_function(
                """() => (document.getElementById('tap-alert-status')?.innerText || '').trim() === 'No queued TAP alerts to dispatch.'
                    && document.getElementById('tap-alert-status')?.getAttribute('aria-busy') === 'false'""",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        tap_empty_dispatch_feedback = page.evaluate(
            """() => {
                const statusText = (document.getElementById('tap-alert-status')?.innerText || '').trim();
                const toastText = (document.getElementById('toast')?.innerText || '').trim();
                const outcomesText = (document.getElementById('tap-outcome-list')?.innerText || '').trim();
                return {
                    statusText,
                    toastText,
                    outcomesText,
                    badFinishedCopy: /Dispatch finished: 0 sent, 0 failed/.test(`${statusText} ${toastText}`),
                    busy: document.getElementById('tap-alert-status')?.getAttribute('aria-busy') || '',
                };
            }"""
        )
        _record_check(
            checks,
            "tap_empty_dispatch_feedback",
            tap_empty_dispatch_feedback.get("statusText") == "No queued TAP alerts to dispatch."
            and tap_empty_dispatch_feedback.get("toastText") == "No queued TAP alerts to dispatch."
            and "No dispatch attempts yet" in str(tap_empty_dispatch_feedback.get("outcomesText", ""))
            and tap_empty_dispatch_feedback.get("badFinishedCopy") is False
            and tap_empty_dispatch_feedback.get("busy") == "false",
            {
                "expected_mode": "tap_empty_dispatch_no_queued_alerts_feedback",
                "status_text_ok": tap_empty_dispatch_feedback.get("statusText")
                == "No queued TAP alerts to dispatch.",
                "toast_text_ok": tap_empty_dispatch_feedback.get("toastText")
                == "No queued TAP alerts to dispatch.",
                "outcomes_empty_state_ok": "No dispatch attempts yet"
                in str(tap_empty_dispatch_feedback.get("outcomesText", "")),
                "no_finished_copy_ok": tap_empty_dispatch_feedback.get("badFinishedCopy") is False,
                "not_busy_ok": tap_empty_dispatch_feedback.get("busy") == "false",
                "wcag_status_messages_reference": "https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html",
            },
        )
        if require_tap_source_notes:
            tap_fixture_restore_state = page.evaluate(TAP_SOURCE_FIXTURE_RESTORE_LIVE_MARKET_JS)
            _record_check(
                checks,
                "tap_source_fixture_restored_live_market",
                tap_fixture_restore_state.get("targetCountry") == "united-states"
                and tap_fixture_restore_state.get("lifecycleValue") == "queued"
                and "for UNITED-STATES" in str(tap_fixture_restore_state.get("statusText", ""))
                and "Source signal:" in str(tap_fixture_restore_state.get("boardText", ""))
                and "ZZ-EMPTY-DISPATCH" not in str(tap_fixture_restore_state.get("boardText", ""))
                and "ZZ-EMPTY-DISPATCH" not in str(tap_fixture_restore_state.get("dealRoomText", ""))
                and int(tap_fixture_restore_state.get("sourceNoteCount") or 0) > 0
                and int(tap_fixture_restore_state.get("offerCardCount") or 0) > 0,
                tap_fixture_restore_state,
            )
        tap_deal_room_ops = page.evaluate(TAP_DEAL_ROOM_OPS_STATE_JS)
        expected_deal_room_labels = {
            "views",
            "clicks",
            "checkouts",
            "purchases",
            "revenue",
            "checkout completion",
        }
        deal_room_labels = {str(label).strip().lower() for label in tap_deal_room_ops.get("labels", [])}
        tap_offer_groups = tap_deal_room_ops.get("offer_action_groups", [])
        tap_offer_group_gaps: list[str] = []
        offer_card_count = int(tap_deal_room_ops.get("offer_card_count") or 0)
        if offer_card_count:
            if len(tap_offer_groups) != offer_card_count:
                tap_offer_group_gaps.append("offer action group count mismatch")
            for index, group in enumerate(tap_offer_groups):
                button_texts = group.get("buttonTexts", [])
                button_labels = group.get("buttonLabels", [])
                if group.get("role") != "group":
                    tap_offer_group_gaps.append(f"offer {index}: missing group role")
                if not str(group.get("label") or "").strip().endswith(" offer actions"):
                    tap_offer_group_gaps.append(f"offer {index}: missing action group label")
                if not str(group.get("offerName") or "").strip():
                    tap_offer_group_gaps.append(f"offer {index}: missing offer name")
                if not button_texts or button_texts[0] != "Track click":
                    tap_offer_group_gaps.append(f"offer {index}: track action not first")
                if not button_labels or not str(button_labels[0] or "").startswith("Track offer click: "):
                    tap_offer_group_gaps.append(f"offer {index}: track action aria label missing offer name")
                if int(group.get("minButtonHeight") or 0) < 28:
                    tap_offer_group_gaps.append(f"offer {index}: target height below 28px")
                if not all(button_type == "button" for button_type in group.get("buttonTypes", [])):
                    tap_offer_group_gaps.append(f"offer {index}: button type missing")
                if len(button_texts) > 1 and not all(
                    ":" in str(label or "") for label in button_labels[1:]
                ):
                    tap_offer_group_gaps.append(f"offer {index}: checkout action aria label missing offer name")
        elif require_tap_source_notes:
            tap_offer_group_gaps.append("fixture offer card missing")
        _record_check(
            checks,
            "tap_deal_room_ops_summary",
            tap_deal_room_ops.get("has_ops_summary") is True
            and expected_deal_room_labels.issubset(deal_room_labels)
            and len(tap_deal_room_ops.get("values", [])) >= len(expected_deal_room_labels)
            and (
                int(tap_deal_room_ops.get("offer_card_count") or 0) > 0
                or int(tap_deal_room_ops.get("empty_card_count") or 0) > 0
            )
            and all(button.get("type") == "button" for button in tap_deal_room_ops.get("track_buttons", []))
            and not tap_offer_group_gaps,
            {**tap_deal_room_ops, "offer_action_group_gaps": tap_offer_group_gaps},
        )
        chart_canvas_state = page.evaluate(DASHBOARD_CHART_CANVAS_ACCESSIBILITY_JS)
        _record_check(
            checks,
            "dashboard_chart_canvases_accessible",
            len(chart_canvas_state) >= 5
            and all(item.get("role") == "img" for item in chart_canvas_state)
            and all(bool(str(item.get("label", "")).strip()) for item in chart_canvas_state)
            and all(bool(str(item.get("fallbackText", "")).strip()) for item in chart_canvas_state)
            and all(item.get("visible") for item in chart_canvas_state),
            chart_canvas_state,
        )
        trends_table_state = page.evaluate(DASHBOARD_TRENDS_TABLE_ACCESSIBILITY_JS)
        required_table_headers = ["#", "Keyword", "Viral", "Country", "Acceleration", "Insight", "Scored at"]
        _record_check(
            checks,
            "dashboard_trends_table_accessible",
            trends_table_state.get("hasTable") is True
            and trends_table_state.get("captionText") == "Latest scored trends"
            and "visually-hidden" in trends_table_state.get("captionClass", "")
            and trends_table_state.get("captionFirstChild") is True
            and trends_table_state.get("headerTexts") == required_table_headers
            and trends_table_state.get("headerScopes") == ["col"] * len(required_table_headers)
            and trends_table_state.get("bodyId") == "t-body",
            trends_table_state,
        )
        page.wait_for_function(DASHBOARD_CONTENT_READY_JS, timeout=timeout_ms)
        core_state = page.evaluate(DASHBOARD_CORE_STATE_JS)
        _record_check(
            checks,
            "core_panels_visible",
            all(bool(value) for value in core_state.values()),
            core_state,
        )
        fallback_banner_before = page.evaluate(DASHBOARD_WARNING_BANNER_DETAILS_JS)
        fallback_banner_after = fallback_banner_before
        fallback_copy_clipboard = ""
        fallback_readiness_clipboard = ""
        if fallback_banner_before.get("visible") and fallback_banner_before.get("detailsExists"):
            page.locator("#dashboard-warning-banner summary").first.click()
            page.wait_for_timeout(120)
            fallback_copy_buttons = page.locator("[aria-label='Copy degraded endpoint details']")
            if fallback_copy_buttons.count() >= 1:
                fallback_copy_buttons.first.click()
                try:
                    page.wait_for_function(
                        "() => (document.querySelector(\"[aria-label='Copy degraded endpoint details']\")?.innerText || '').trim() === 'Copied'",
                        timeout=timeout_ms,
                    )
                except PlaywrightTimeoutError:
                    pass
                try:
                    fallback_copy_clipboard = page.evaluate("() => navigator.clipboard.readText()")
                except Exception as exc:
                    fallback_copy_clipboard = f"clipboard_read_failed: {exc}"
            fallback_readiness_buttons = page.locator("[aria-label='Copy fallback readiness refresh command']")
            if fallback_readiness_buttons.count() >= 1:
                fallback_readiness_buttons.first.click()
                try:
                    page.wait_for_function(
                        "() => (document.querySelector(\"[aria-label='Copy fallback readiness refresh command']\")?.innerText || '').trim() === 'Copied'",
                        timeout=timeout_ms,
                    )
                except PlaywrightTimeoutError:
                    pass
                try:
                    fallback_readiness_clipboard = page.evaluate("() => navigator.clipboard.readText()")
                except Exception as exc:
                    fallback_readiness_clipboard = f"clipboard_read_failed: {exc}"
            fallback_banner_after = page.evaluate(DASHBOARD_WARNING_BANNER_DETAILS_JS)
        fallback_rows = fallback_banner_after.get("rows", [])
        fallback_copy_text = str(fallback_banner_after.get("copyText") or "")
        fallback_readiness_copy_text = str(fallback_banner_after.get("readinessCopyText") or "")
        normalized_fallback_clipboard = str(fallback_copy_clipboard).replace("\r\n", "\n").replace("\r", "\n")
        normalized_fallback_readiness_clipboard = str(fallback_readiness_clipboard).replace("\r\n", "\n").replace("\r", "\n")
        fallback_banner_visible = bool(fallback_banner_after.get("visible"))
        fallback_expected_mode = (
            "dashboard_fallback_banner_collapsed_then_expanded"
            if fallback_banner_visible
            else "dashboard_fallback_banner_not_visible"
        )
        fallback_status_live_region_ok = (
            fallback_banner_after.get("statusRole") == "status"
            and fallback_banner_after.get("statusLive") == "polite"
            and fallback_banner_after.get("statusAtomic") == "true"
            and "Fallback data mode" in fallback_banner_after.get("statusText", "")
            and "safe fallback data" in fallback_banner_after.get("statusText", "")
        )
        fallback_initial_details_collapsed_ok = fallback_banner_before.get("detailsOpen") is False
        fallback_expanded_details_open_ok = (
            fallback_banner_after.get("detailsExists") is True
            and fallback_banner_after.get("detailsOpen") is True
            and fallback_banner_after.get("summaryText") == "View degraded endpoint details"
        )
        fallback_summary_target_size_ok = int(fallback_banner_after.get("summaryHeight") or 0) >= 28
        fallback_copy_actions_ok = (
            fallback_banner_after.get("copyButtonExists") is True
            and fallback_banner_after.get("copyButtonType") == "button"
            and fallback_banner_after.get("copyButtonText") in {"Copied", "Copy endpoints"}
            and fallback_banner_after.get("copyButtonResult") == "copied"
            and fallback_banner_after.get("readinessCopyButtonExists") is True
            and fallback_banner_after.get("readinessCopyButtonType") == "button"
            and fallback_banner_after.get("readinessCopyButtonText") in {"Copied", "Copy readiness refresh"}
            and fallback_banner_after.get("readinessCopyButtonResult") == "copied"
        )
        fallback_copy_payload_has_recovery_paths_ok = (
            fallback_copy_text.startswith("Fallback data mode:")
            and "/api/" in fallback_copy_text
            and "reason " in fallback_copy_text
            and "Supabase recovery packet" in fallback_banner_after.get("detailsText", "")
            and "supabase_recovery_packet_latest.json" in fallback_banner_after.get("detailsText", "")
            and "Readiness refresh:" in fallback_banner_after.get("detailsText", "")
            and "Supabase recovery packet | logs\\readiness\\supabase_recovery_packet_latest.json" in fallback_copy_text
            and "Readiness refresh | python scripts\\readiness_check.py" in fallback_copy_text
            and "--fail-on-runtime-fallback --require-live-db" in fallback_copy_text
        )
        fallback_readiness_copy_command_ok = (
            fallback_readiness_copy_text.startswith("python scripts\\readiness_check.py")
            and "--fail-on-runtime-fallback --require-live-db" in fallback_readiness_copy_text
        )
        fallback_copy_payload_compact_ok = int(fallback_banner_after.get("copyLineCount") or 0) <= 15
        fallback_clipboard_matches_ok = normalized_fallback_clipboard == fallback_copy_text
        fallback_readiness_clipboard_matches_ok = (
            normalized_fallback_readiness_clipboard == fallback_readiness_copy_text
        )
        fallback_rows_labeled_ok = (
            int(fallback_banner_after.get("rowCount") or 0) >= 1
            and any(str(row.get("path", "")).startswith("/api/") for row in fallback_rows)
            and all("reason " in str(row.get("meta", "")) for row in fallback_rows if row.get("meta"))
        )
        fallback_duplicate_labels_absent_ok = not fallback_banner_after.get("duplicateLabels")
        fallback_banner_ok = (
            not fallback_banner_visible
            or (
                fallback_banner_after.get("bannerRole") == ""
                and fallback_status_live_region_ok
                and fallback_initial_details_collapsed_ok
                and fallback_expanded_details_open_ok
                and fallback_summary_target_size_ok
                and fallback_copy_actions_ok
                and fallback_copy_payload_has_recovery_paths_ok
                and fallback_readiness_copy_command_ok
                and fallback_copy_payload_compact_ok
                and fallback_clipboard_matches_ok
                and fallback_readiness_clipboard_matches_ok
                and fallback_rows_labeled_ok
                and fallback_duplicate_labels_absent_ok
            )
        )
        _record_check(
            checks,
            "dashboard_fallback_banner_details",
            fallback_banner_ok,
            {
                "expected_mode": fallback_expected_mode,
                "banner_state": "visible" if fallback_banner_visible else "not_visible",
                "status_live_region_ok": not fallback_banner_visible or fallback_status_live_region_ok,
                "initial_details_collapsed_ok": not fallback_banner_visible or fallback_initial_details_collapsed_ok,
                "expanded_details_open_ok": not fallback_banner_visible or fallback_expanded_details_open_ok,
                "summary_target_size_ok": not fallback_banner_visible or fallback_summary_target_size_ok,
                "copy_actions_ok": not fallback_banner_visible or fallback_copy_actions_ok,
                "copy_payload_has_recovery_paths_ok": (
                    not fallback_banner_visible or fallback_copy_payload_has_recovery_paths_ok
                ),
                "readiness_copy_command_ok": not fallback_banner_visible or fallback_readiness_copy_command_ok,
                "copy_payload_compact_ok": not fallback_banner_visible or fallback_copy_payload_compact_ok,
                "clipboard_matches_ok": not fallback_banner_visible or fallback_clipboard_matches_ok,
                "readiness_clipboard_matches_ok": (
                    not fallback_banner_visible or fallback_readiness_clipboard_matches_ok
                ),
                "rows_labeled_ok": not fallback_banner_visible or fallback_rows_labeled_ok,
                "duplicate_labels_absent_ok": not fallback_banner_visible or fallback_duplicate_labels_absent_ok,
                "copy_payload_line_count": fallback_banner_after.get("copyLineCount"),
                "row_count": fallback_banner_after.get("rowCount"),
                "raw_detail": "omitted",
                "wcag_target_size_minimum_reference": W3C_WCAG_TARGET_SIZE_MINIMUM_URL,
            },
        )
        if require_tap_source_notes:
            tap_notes_state = page.evaluate(TAP_SOURCE_NOTES_STATE_JS)
            _record_check(
                checks,
                "tap_source_notes_rendered",
                bool(
                    tap_notes_state.get("expected_notes")
                    and tap_notes_state.get("matched_notes")
                    and int(tap_notes_state.get("rendered_note_count") or 0) > 0
                    and not tap_notes_state.get("degraded")
                ),
                tap_notes_state,
            )
            fixture_endpoint_states = page.evaluate(DASHBOARD_FIXTURE_ENDPOINTS_STATE_JS)
            degraded_endpoints = [
                state
                for state in fixture_endpoint_states
                if int(state.get("status") or 0) >= 500
                or state.get("degraded_header")
                or state.get("degraded_meta")
            ]
            _record_check(
                checks,
                "fixture_endpoints_not_degraded",
                not degraded_endpoints,
                {"endpoints": fixture_endpoint_states, "degraded": degraded_endpoints},
            )
            tap_deal_click_state = page.evaluate(TAP_DEAL_ROOM_TRACK_CLICK_STATE_JS)
            deal_room_event_calls = tap_deal_click_state.get("event_calls", [])
            first_deal_room_event = deal_room_event_calls[0] if deal_room_event_calls else {}
            before_clicks = tap_deal_click_state.get("before_clicks")
            after_clicks = tap_deal_click_state.get("after_clicks")
            _record_check(
                checks,
                "tap_deal_room_track_click_event",
                tap_deal_click_state.get("had_button") is True
                and tap_deal_click_state.get("button_type") == "button"
                and first_deal_room_event.get("method") == "POST"
                and int(first_deal_room_event.get("status") or 0) == 200
                and first_deal_room_event.get("ok") is True
                and "event_type=click" in str(first_deal_room_event.get("url", ""))
                and after_clicks is not None
                and before_clicks is not None
                and int(after_clicks) > int(before_clicks)
                and "Offer click tracked" in tap_deal_click_state.get("toast_text", ""),
                tap_deal_click_state,
            )
            tap_deal_checkout_state = page.evaluate(TAP_DEAL_ROOM_CHECKOUT_OPEN_STATE_JS)
            checkout_calls = tap_deal_checkout_state.get("checkout_calls", [])
            first_checkout_call = checkout_calls[0] if checkout_calls else {}
            checkout_request = first_checkout_call.get("request_body", {})
            checkout_response = first_checkout_call.get("response_body", {})
            allow_checkout_503_console_error = (
                int(first_checkout_call.get("status") or 0) == 503
                and "STRIPE_SECRET_KEY is not configured" in str(checkout_response.get("error", ""))
            )
            _record_check(
                checks,
                "tap_deal_room_checkout_open_recovery",
                tap_deal_checkout_state.get("had_button") is True
                and tap_deal_checkout_state.get("button_type") == "button"
                and first_checkout_call.get("method") == "POST"
                and int(first_checkout_call.get("status") or 0) == 503
                and first_checkout_call.get("ok") is False
                and str(checkout_request.get("checkout_handle", "")).startswith("stripe:")
                and checkout_request.get("target_country") == "united-states"
                and bool(str(checkout_request.get("keyword", "")).strip())
                and bool(str(checkout_request.get("price_anchor", "")).strip())
                and checkout_response.get("ok") is False
                and "STRIPE_SECRET_KEY is not configured" in str(checkout_response.get("error", ""))
                and not tap_deal_checkout_state.get("open_calls")
                and tap_deal_checkout_state.get("button_disabled_after") is False
                and tap_deal_checkout_state.get("button_busy_after") == "false"
                and tap_deal_checkout_state.get("toast_type") == "error"
                and "Checkout unavailable" in tap_deal_checkout_state.get("toast_text", "")
                and "STRIPE_SECRET_KEY is not configured" in tap_deal_checkout_state.get("toast_text", ""),
                tap_deal_checkout_state,
            )
        try:
            page.evaluate(
                """async () => {
                    if (typeof loadOperatorReadiness === 'function') {
                        await loadOperatorReadiness();
                    }
                }"""
            )
        except Exception:
            pass
        operator_text = page.locator("#operator-readiness").inner_text(timeout=timeout_ms)
        operator_blockers_text = page.locator("#operator-blockers").inner_text(timeout=timeout_ms)
        operator_payload = page.evaluate(
            """async () => {
                const response = await fetch('/api/operator/readiness');
                return await response.json();
            }"""
        )
        operator_payload_cards = operator_payload.get("cards")
        operator_payload_cards = operator_payload_cards if isinstance(operator_payload_cards, list) else []
        operator_issues = [
            issue
            for bucket in ("blockers", "warnings")
            for issue in operator_payload.get(bucket, [])
            if isinstance(issue, dict)
        ]
        recovery_packet_paths = [
            str(issue.get("recovery_packet", "")).strip()
            for issue in operator_issues
            if str(issue.get("recovery_packet", "")).strip()
        ]
        has_recovery_packets = bool(recovery_packet_paths)
        launch_focus = operator_payload.get("launch_focus")
        launch_focus = launch_focus if isinstance(launch_focus, dict) else {}
        operator_gaps = _operator_rendering_gaps(operator_blockers_text, operator_issues)
        operator_text_lower = operator_text.lower()
        _record_check(
            checks,
            "operator_readiness_visible",
            "readiness" in operator_text_lower
            and "launch focus" in operator_text_lower
            and "browser evidence" in operator_text_lower
            and "tap fixture" in operator_text_lower
            and "recovery packet" in operator_text_lower
            and "final proof" in operator_text_lower
            and "provider packet" in operator_text_lower
            and "credential inputs" in operator_text_lower
            and "workspace smoke" in operator_text_lower
            and "handoff refresh scan" in operator_text_lower,
            operator_text[:500],
        )
        launch_focus_scope = str(launch_focus.get("scope") or "").strip()
        launch_focus_payload_card = launch_focus.get("card")
        launch_focus_payload_card = launch_focus_payload_card if isinstance(launch_focus_payload_card, dict) else {}
        launch_focus_value = str(launch_focus_payload_card.get("value") or "").strip().lower()
        launch_focus_card_visible = page.evaluate(
            """() => {
                const cards = Array.from(document.querySelectorAll('#operator-readiness .operator-card'));
                const normalize = value => String(value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const card = cards.find(item => normalize(item.querySelector('.label')?.innerText) === 'launch focus');
                if (!card) return {};
                return {
                    label: (card.querySelector('.label')?.innerText || '').trim(),
                    value: (card.querySelector('.operator-value')?.innerText || '').trim(),
                    detail: (card.querySelector('.operator-card-detail')?.innerText || '').trim(),
                    state: (card.querySelector('.operator-state')?.innerText || '').trim().toLowerCase(),
                };
            }"""
        )
        _record_check(
            checks,
            "operator_launch_focus_visible",
            bool(launch_focus_card_visible.get("label"))
            and launch_focus_scope in {"supabase_db_only", "launch_ready", "multiple_or_unknown"}
            and (
                launch_focus_scope != "supabase_db_only"
                or (
                    launch_focus_value == "db only"
                    and str(launch_focus_card_visible.get("value", "")).strip().lower() == "db only"
                    and "provider" in str(launch_focus_card_visible.get("detail", "")).lower()
                    and "scheduler" in str(launch_focus_card_visible.get("detail", "")).lower()
                    and "secret scan" in str(launch_focus_card_visible.get("detail", "")).lower()
                )
            ),
            {"payload": launch_focus, "card": launch_focus_card_visible},
        )
        final_proof_payload_card = next(
            (
                card
                for card in operator_payload_cards
                if isinstance(card, dict) and str(card.get("label", "")).strip().lower() == "final proof"
            ),
            None,
        )
        final_proof_rendered_card = page.evaluate(
            """() => {
                const cards = Array.from(document.querySelectorAll('#operator-readiness .operator-card'));
                const normalize = value => String(value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const card = cards.find(item => normalize(item.querySelector('.label')?.innerText) === 'final proof');
                if (!card) {
                    return {
                        labels: cards.map(item => (item.querySelector('.label')?.innerText || '').trim()).filter(Boolean),
                    };
                }
                return {
                    label: (card.querySelector('.label')?.innerText || '').trim(),
                    value: (card.querySelector('.operator-value')?.innerText || '').trim(),
                    detail: (card.querySelector('.operator-card-detail')?.innerText || '').trim(),
                    state: (card.querySelector('.operator-state')?.innerText || '').trim().toLowerCase(),
                };
            }"""
        )
        final_proof_expected_detail = (
            str(final_proof_payload_card.get("detail") or "").strip()
            if isinstance(final_proof_payload_card, dict)
            else ""
        )
        _record_check(
            checks,
            "operator_final_proof_card_visible",
            isinstance(final_proof_payload_card, dict)
            and str(final_proof_rendered_card.get("label") or "").strip().lower() == "final proof"
            and str(final_proof_rendered_card.get("value") or "").strip()
            == str(final_proof_payload_card.get("value") or "").strip()
            and str(final_proof_rendered_card.get("state") or "").strip().lower()
            == str(final_proof_payload_card.get("state") or "").strip().lower()
            and bool(re.search(r"\d+ required|missing", str(final_proof_rendered_card.get("value") or ""), re.I))
            and (
                not final_proof_expected_detail
                or final_proof_expected_detail in str(final_proof_rendered_card.get("detail") or "")
            )
            and (
                "post-credential recheck" in str(final_proof_rendered_card.get("detail") or "").lower()
                or "final proof bundle" in str(final_proof_rendered_card.get("detail") or "").lower()
            ),
            {
                "payload": final_proof_payload_card,
                "rendered": final_proof_rendered_card,
            },
        )
        operator_card_density = page.evaluate(
            """() => Array.from(document.querySelectorAll('#operator-readiness .operator-card')).map(card => {
                const label = (card.querySelector('.label')?.innerText || '').trim();
                const detail = (card.querySelector('.operator-card-detail')?.innerText || '').trim();
                const rect = card.getBoundingClientRect();
                return {
                    label,
                    detailLength: detail.length,
                    detail,
                    height: Math.round(rect.height),
                    hasLongRecoveryCommand: /getdaytrends_update_credentials\\.py|GETDAYTRENDS_NEW_|Transaction pooler URI|Next action:/i.test(detail),
                };
            })"""
        )
        recovery_card_density = [
            item
            for item in operator_card_density
            if str(item.get("label", "")).lower() in {"recovery packet", "provider packet"}
        ]
        credential_inputs_card = page.evaluate(
            """() => {
                const cards = Array.from(document.querySelectorAll('#operator-readiness .operator-card'));
                const normalize = value => String(value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const card = cards.find(item => normalize(item.querySelector('.label')?.innerText) === 'credential inputs');
                if (!card) {
                    return {
                        labels: cards.map(item => (item.querySelector('.label')?.innerText || '').trim()).filter(Boolean),
                    };
                }
                return {
                    label: (card.querySelector('.label')?.innerText || '').trim(),
                    value: (card.querySelector('.operator-value')?.innerText || '').trim(),
                    detail: (card.querySelector('.operator-card-detail')?.innerText || '').trim(),
                    state: (card.querySelector('.operator-state')?.innerText || '').trim(),
                };
            }"""
        )
        compact_packet_cards_ok = (
            bool(recovery_card_density)
            and all(int(item.get("detailLength") or 0) <= 80 for item in recovery_card_density)
            and not any(item.get("hasLongRecoveryCommand") for item in recovery_card_density)
        )
        plural_issue_label_ok = "1 issues" not in operator_text_lower
        _record_check(
            checks,
            "operator_readiness_cards_compact",
            compact_packet_cards_ok and plural_issue_label_ok,
            {
                "expected_mode": "operator_readiness_packet_cards_compact",
                "compact_packet_cards_ok": compact_packet_cards_ok,
                "plural_issue_label_ok": plural_issue_label_ok,
                "packet_card_count": len(recovery_card_density),
                "max_packet_detail_length": max(
                    [int(item.get("detailLength") or 0) for item in recovery_card_density] or [0]
                ),
                "packet_labels": [str(item.get("label", "")) for item in recovery_card_density],
            },
        )
        cli_fallback_payload_card = next(
            (
                card
                for card in operator_payload_cards
                if isinstance(card, dict) and str(card.get("label", "")).strip().lower() == "cli fallback"
            ),
            None,
        )
        cli_fallback_rendered_card = page.evaluate(
            """() => {
                const cards = Array.from(document.querySelectorAll('#operator-readiness .operator-card'));
                const normalize = value => String(value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const card = cards.find(item => normalize(item.querySelector('.label')?.innerText) === 'cli fallback');
                if (!card) {
                    return {
                        labels: cards.map(item => (item.querySelector('.label')?.innerText || '').trim()).filter(Boolean),
                    };
                }
                return {
                    label: (card.querySelector('.label')?.innerText || '').trim(),
                    value: (card.querySelector('.operator-value')?.innerText || '').trim(),
                    detail: (card.querySelector('.operator-card-detail')?.innerText || '').trim(),
                    state: (card.querySelector('.operator-state')?.innerText || '').trim().toLowerCase(),
                };
            }"""
        )
        cli_fallback_card_ok = cli_fallback_payload_card is None and not cli_fallback_rendered_card.get("label")
        if isinstance(cli_fallback_payload_card, dict):
            expected_detail = str(cli_fallback_payload_card.get("detail") or "").strip()
            cli_fallback_card_ok = (
                str(cli_fallback_rendered_card.get("label") or "").strip().lower() == "cli fallback"
                and str(cli_fallback_rendered_card.get("value") or "").strip()
                == str(cli_fallback_payload_card.get("value") or "").strip()
                and str(cli_fallback_rendered_card.get("state") or "").strip().lower()
                == str(cli_fallback_payload_card.get("state") or "").strip().lower()
                and (not expected_detail or expected_detail in str(cli_fallback_rendered_card.get("detail") or ""))
            )
        _record_check(
            checks,
            "operator_cli_fallback_card",
            cli_fallback_card_ok,
            {
                "payload": cli_fallback_payload_card,
                "rendered": cli_fallback_rendered_card,
            },
        )
        _record_check(
            checks,
            "operator_credential_inputs_card",
            credential_inputs_card.get("value") in {"none staged", "staged", "missing"}
            and str(credential_inputs_card.get("state", "")).strip().lower() in {"warn", "unknown"}
            and (
                credential_inputs_card.get("value") != "none staged"
                or "safe to skip strict rerun" in str(credential_inputs_card.get("detail", "")).lower()
            ),
            credential_inputs_card,
        )
        scheduler_age_card = page.evaluate(
            """() => {
                const cards = Array.from(document.querySelectorAll('#operator-readiness .operator-card'));
                const normalize = value => String(value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const card = cards.find(item => normalize(item.querySelector('.label')?.innerText) === 'scheduler age');
                if (!card) {
                    return {
                        labels: cards.map(item => (item.querySelector('.label')?.innerText || '').trim()).filter(Boolean),
                    };
                }
                return {
                    label: (card.querySelector('.label')?.innerText || '').trim(),
                    value: (card.querySelector('.operator-value')?.innerText || '').trim(),
                    detail: (card.querySelector('.operator-card-detail')?.innerText || '').trim(),
                    state: (card.querySelector('.operator-state')?.innerText || '').trim().toLowerCase(),
                };
            }"""
        )
        scheduler_age_match = re.search(r"(\d+(?:\.\d+)?)h", str(scheduler_age_card.get("value", "")))
        scheduler_age_hours = float(scheduler_age_match.group(1)) if scheduler_age_match else None
        scheduler_age_stale = scheduler_age_hours is not None and scheduler_age_hours > 24
        scheduler_age_near_stale = (
            scheduler_age_hours is not None and 21.6 <= scheduler_age_hours <= 24
        )
        scheduler_age_state = str(scheduler_age_card.get("state", "")).strip().lower()
        scheduler_age_guard_ok = bool(scheduler_age_card.get("label")) and (
            scheduler_age_state == "warn"
            if scheduler_age_near_stale or scheduler_age_stale
            else scheduler_age_state in {"pass", "warn", "unknown"}
        )
        if scheduler_age_near_stale:
            scheduler_age_guard_ok = scheduler_age_guard_ok and "refresh soon" in str(
                scheduler_age_card.get("detail", "")
            ).lower()
        if scheduler_age_stale:
            scheduler_age_guard_ok = scheduler_age_guard_ok and "refresh now" in str(
                scheduler_age_card.get("detail", "")
            ).lower()
        _record_check(
            checks,
            "operator_scheduler_age_warns_before_stale",
            scheduler_age_guard_ok,
            {
                **scheduler_age_card,
                "age_hours": scheduler_age_hours,
                "stale_threshold_hours": 24,
                "near_stale_threshold_hours": 21.6,
            },
        )
        _record_check(
            checks,
            "operator_blockers_rendered",
            not operator_gaps,
            {"issue_count": len(operator_issues), "gaps": operator_gaps, "text": operator_blockers_text[:420]},
        )
        operator_blocker_titles = page.evaluate(
            """() => Array.from(document.querySelectorAll('#operator-blockers .operator-item-title'))
                .map(item => (item.innerText || '').trim())
                .filter(Boolean)"""
        )
        expected_operator_title_fragments = {
            "cli_smoke_report": "CLI smoke report (cli_smoke_report)",
            "provider_auth_report": "Provider auth report (provider_auth_report)",
            "live_db_doctor": "Live DB doctor (live_db_doctor)",
            "scheduler_freshness": "Scheduler freshness (scheduler_freshness)",
            "readiness_report": "Readiness report (readiness_report)",
        }
        expected_operator_titles = [
            expected_operator_title_fragments.get(str(issue.get("name", "")).strip())
            for issue in operator_issues
        ]
        expected_operator_titles = [item for item in expected_operator_titles if item]
        _record_check(
            checks,
            "operator_blocker_titles_readable",
            all(
                any(expected in title for title in operator_blocker_titles)
                for expected in expected_operator_titles
            ),
            {
                "titles": operator_blocker_titles,
                "expected_fragments": expected_operator_titles,
            },
        )
        live_db_issue = next(
            (issue for issue in operator_issues if str(issue.get("name", "")) == "live_db_doctor"),
            None,
        )
        if live_db_issue:
            live_db_message = str(live_db_issue.get("message", ""))
            live_db_failure_type = str(live_db_issue.get("failure_type", "")).strip()
            live_db_diagnostics = live_db_issue.get("diagnostics")
            live_db_diagnostics = live_db_diagnostics if isinstance(live_db_diagnostics, list) else []
            live_db_diagnostic_text = "\n".join(str(item) for item in live_db_diagnostics)
            live_db_timeout_without_diagnostics = "timed out" in live_db_message.lower() and not live_db_diagnostics
            live_db_message_compact = (
                len(live_db_message) <= 220
                and "Diagnostics:" not in live_db_message
                and (
                    live_db_timeout_without_diagnostics
                    or (
                        len(live_db_diagnostics) >= 3
                        and "db.endpoint_tcp" in live_db_diagnostic_text
                        and "db.live_postgres" in live_db_diagnostic_text
                    )
                )
            )
        else:
            live_db_message = ""
            live_db_failure_type = ""
            live_db_diagnostics = []
            live_db_message_compact = True
        live_db_inline_diagnostics_removed = "Diagnostics:" not in live_db_message
        live_db_diagnostic_context_ok = (
            not live_db_issue
            or live_db_timeout_without_diagnostics
            or (
                len(live_db_diagnostics) >= 3
                and "db.endpoint_tcp" in live_db_diagnostic_text
                and "db.live_postgres" in live_db_diagnostic_text
            )
        )
        _record_check(
            checks,
            "operator_live_db_message_compact",
            live_db_message_compact,
            {
                "expected_mode": "operator_live_db_message_compact_with_separate_diagnostics",
                "live_db_status": "blocker_present" if live_db_issue else "no_live_db_blocker",
                "compact_message_ok": live_db_message_compact,
                "inline_diagnostics_removed_ok": live_db_inline_diagnostics_removed,
                "diagnostic_context_ok": live_db_diagnostic_context_ok,
                "message_length": len(live_db_message),
                "diagnostic_count": len(live_db_diagnostics),
            },
        )
        live_db_failure_type_visible = (
            not live_db_issue
            or (
                live_db_failure_type
                in {"timeout", "execution_error", "diagnostic_error", "nonzero_exit"}
                and f"live db failure type: {live_db_failure_type}".lower() in operator_blockers_text.lower()
            )
        )
        _record_check(
            checks,
            "operator_live_db_failure_type_visible",
            live_db_failure_type_visible,
            {
                "live_db_blocker_present": live_db_issue is not None,
                "failure_type": live_db_failure_type,
                "accepted_failure_types": ["timeout", "execution_error", "diagnostic_error", "nonzero_exit"],
            },
        )
        operator_action_descriptions = page.evaluate(
            """() => Array.from(document.querySelectorAll('#operator-blockers .operator-item')).flatMap(item => {
                const title = item.querySelector('.operator-item-title');
                const titleText = (title?.innerText || '').trim();
                return Array.from(item.querySelectorAll('.operator-action button')).map(button => {
                    const describedBy = (button.getAttribute('aria-describedby') || '').trim();
                    const ids = describedBy ? describedBy.split(/\\s+/).filter(Boolean) : [];
                    const descriptionTexts = ids.map(id => (document.getElementById(id)?.innerText || '').trim());
                    const labelledBy = (button.getAttribute('aria-labelledby') || '').trim();
                    const labelIds = labelledBy ? labelledBy.split(/\\s+/).filter(Boolean) : [];
                    const labelTexts = labelIds.map(id => (document.getElementById(id)?.innerText || '').trim()).filter(Boolean);
                    const computedName = (labelTexts.join(' ') || button.getAttribute('aria-label') || button.innerText || '').replace(/\\s+/g, ' ').trim();
                    return {
                        label: button.getAttribute('aria-label') || button.innerText || '',
                        text: (button.innerText || '').trim(),
                        describedBy,
                        labelledBy,
                        titleText,
                        descriptionTexts,
                        labelTexts,
                        computedName,
                        hasTitleDescription: titleText && descriptionTexts.includes(titleText),
                        hasTitleLabel: titleText && labelTexts.includes(titleText),
                    };
                });
            })"""
        )
        operator_action_names = [
            str(item.get("computedName", "")).strip()
            for item in operator_action_descriptions
            if str(item.get("computedName", "")).strip()
        ]
        operator_action_duplicate_names = sorted(
            {name for name in operator_action_names if operator_action_names.count(name) > 1}
        )
        _record_check(
            checks,
            "operator_action_buttons_described",
            (
                bool(operator_action_descriptions)
                and all(item.get("hasTitleDescription") for item in operator_action_descriptions)
            )
            if operator_issues
            else not operator_action_descriptions,
            {
                "issue_count": len(operator_issues),
                "buttons": operator_action_descriptions,
            },
        )
        _record_check(
            checks,
            "operator_action_button_unique_names",
            (
                bool(operator_action_descriptions)
                and all(item.get("hasTitleLabel") for item in operator_action_descriptions)
                and not operator_action_duplicate_names
            )
            if operator_issues
            else not operator_action_descriptions,
            {
                "issue_count": len(operator_issues),
                "buttons": operator_action_descriptions,
                "duplicate_names": operator_action_duplicate_names,
            },
        )
        recovery_row_action_groups = page.evaluate(
            """() => Array.from(document.querySelectorAll('#operator-blockers [data-recovery-row-actions="true"]')).map(group => {
                const action = group.closest('.operator-action');
                const title = action?.querySelector('.operator-action-title');
                const titleLabel = title?.querySelector('.operator-action-label');
                const titleNote = title?.querySelector('.operator-action-note');
                const buttons = Array.from(group.querySelectorAll('button')).map(button => {
                    const rect = button.getBoundingClientRect();
                    return {
                        text: (button.innerText || '').trim(),
                        ariaLabel: button.getAttribute('aria-label') || '',
                        type: button.getAttribute('type') || '',
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                    };
                });
                return {
                    role: group.getAttribute('role') || '',
                    label: group.getAttribute('aria-label') || '',
                    actionTitleText: (title?.innerText || '').replace(/\\s+/g, ' ').trim(),
                    actionTitleRawText: (title?.textContent || '').replace(/\\s+/g, ' ').trim(),
                    hasActionTitleClass: Boolean(title),
                    hasTitleLabel: Boolean(titleLabel),
                    hasReusedPacketNote: Boolean(titleNote),
                    hasConcatenatedReuseText: Boolean((title?.textContent || '').includes('Recovery packetSame packet as')),
                    buttonTexts: buttons.map(button => button.text),
                    buttonAriaLabels: buttons.map(button => button.ariaLabel),
                    buttonTypes: buttons.map(button => button.type),
                    buttonHeights: buttons.map(button => button.height),
                    minButtonHeight: buttons.length ? Math.min(...buttons.map(button => button.height)) : 0,
                    buttons,
                };
            })"""
        )
        expected_row_action_order = [
            "View recovery packet",
            "Copy scheduler pause",
            "Copy credential update",
            "Copy recovery bundle",
            "Copy recovery verification bundle",
            "Copy launch criteria",
            "Copy scheduler resume",
            "Copy packet path",
        ]
        recovery_row_action_gaps: list[str] = []
        if has_recovery_packets and not recovery_row_action_groups:
            recovery_row_action_gaps.append("missing recovery row action group")
        if not has_recovery_packets and recovery_row_action_groups:
            recovery_row_action_gaps.append("recovery row action group rendered without recovery packets")
        for group in recovery_row_action_groups:
            if group.get("role") != "group":
                recovery_row_action_gaps.append("missing row action group role")
            if group.get("label") != "Recovery row copy actions":
                recovery_row_action_gaps.append("missing row action group label")
            if group.get("hasReusedPacketNote") and group.get("hasConcatenatedReuseText"):
                recovery_row_action_gaps.append("reused packet label is visually concatenated")
            if group.get("hasReusedPacketNote") and "Recovery packet Same packet as" not in str(group.get("actionTitleRawText", "")):
                recovery_row_action_gaps.append("reused packet label missing readable spacing")
            if group.get("buttonTexts") != expected_row_action_order:
                recovery_row_action_gaps.append("row action order changed")
            if int(group.get("minButtonHeight") or 0) < 28:
                recovery_row_action_gaps.append("row action target height below 28px")
            if not all(button_type == "button" for button_type in group.get("buttonTypes", [])):
                recovery_row_action_gaps.append("row action button type missing")
        recovery_row_group_contract_ok = (
            all(
                group.get("role") == "group" and group.get("label") == "Recovery row copy actions"
                for group in recovery_row_action_groups
            )
            if has_recovery_packets
            else not recovery_row_action_groups
        )
        recovery_row_reused_spacing_ok = all(
            not group.get("hasReusedPacketNote")
            or (
                not group.get("hasConcatenatedReuseText")
                and "Recovery packet Same packet as" in str(group.get("actionTitleRawText", ""))
            )
            for group in recovery_row_action_groups
        )
        recovery_row_button_order_ok = all(
            group.get("buttonTexts") == expected_row_action_order for group in recovery_row_action_groups
        )
        recovery_row_button_types_ok = all(
            all(button_type == "button" for button_type in group.get("buttonTypes", []))
            for group in recovery_row_action_groups
        )
        recovery_row_min_button_height = min(
            [int(group.get("minButtonHeight") or 0) for group in recovery_row_action_groups] or [0]
        )
        recovery_row_target_size_ok = (
            recovery_row_min_button_height >= 28 if has_recovery_packets else not recovery_row_action_groups
        )
        _record_check(
            checks,
            "operator_recovery_row_action_group",
            (
                bool(recovery_row_action_groups)
                if has_recovery_packets
                else not recovery_row_action_groups
            )
            and not recovery_row_action_gaps,
            {
                "expected_mode": "operator_recovery_row_actions_accessible_compact",
                "recovery_packet_count": len(recovery_packet_paths),
                "group_count": len(recovery_row_action_groups),
                "group_contract_ok": recovery_row_group_contract_ok,
                "reused_packet_note_spacing_ok": recovery_row_reused_spacing_ok,
                "button_order_ok": recovery_row_button_order_ok,
                "button_types_ok": recovery_row_button_types_ok,
                "target_size_ok": recovery_row_target_size_ok,
                "min_button_height": recovery_row_min_button_height,
                "expected_order": expected_row_action_order,
                "gaps": recovery_row_action_gaps,
                "wcag_target_size_minimum_reference": W3C_WCAG_TARGET_SIZE_MINIMUM_URL,
            },
        )
        readiness_busy_ok, readiness_busy_detail = _probe_operator_preview_busy(
            page,
            button_selector="[aria-controls='operator-readiness-report-preview']",
            preview_selector=".operator-readiness-report-preview",
            url_fragment="/api/operator/readiness-report",
            loading_text="Loading readiness report",
            loaded_text="Readiness report:",
        )
        _record_check(
            checks,
            "operator_readiness_report_busy_state",
            readiness_busy_ok,
            readiness_busy_detail,
        )
        if has_recovery_packets:
            recovery_busy_ok, recovery_busy_detail = _probe_operator_preview_busy(
                page,
                button_selector="[aria-label='View recovery packet']",
                preview_selector="",
                url_fragment="/api/operator/recovery-packet",
                loading_text="Loading packet",
                loaded_text="Packet status:",
            )
        else:
            recovery_view_button_count = page.locator("[aria-label='View recovery packet']").count()
            recovery_busy_ok = recovery_view_button_count == 0
            recovery_busy_detail = {
                "expected_mode": "clean_no_recovery_packet",
                "button_count": recovery_view_button_count,
                "recovery_packet_count": 0,
            }
        _record_check(
            checks,
            "operator_recovery_packet_busy_state",
            recovery_busy_ok,
            recovery_busy_detail,
        )
        workspace_busy_ok, workspace_busy_detail = _probe_operator_preview_busy(
            page,
            button_selector="[aria-controls='operator-workspace-smoke-preview']",
            preview_selector=".operator-workspace-smoke-preview",
            url_fragment="/api/operator/workspace-smoke",
            loading_text="Loading workspace smoke",
            loaded_text="Workspace smoke:",
        )
        _record_check(
            checks,
            "operator_workspace_smoke_busy_state",
            workspace_busy_ok,
            workspace_busy_detail,
        )
        supabase_recovery_gaps = _operator_supabase_recovery_gaps(operator_blockers_text, operator_issues)
        _record_check(
            checks,
            "supabase_recovery_blocker_rendered",
            not supabase_recovery_gaps,
            {
                "live_db_blocker_present": any(
                    str(issue.get("name", "")) == "live_db_doctor" for issue in operator_issues
                ),
                "gaps": supabase_recovery_gaps,
                "text": operator_blockers_text[:900],
            },
        )
        provider_auth_issue = next(
            (issue for issue in operator_issues if str(issue.get("name", "")) == "provider_auth_report"),
            None,
        )
        provider_auth_expected_mode = "provider_blocker" if provider_auth_issue else "clean_no_blocker"
        provider_auth_blocker_present = provider_auth_issue is not None
        provider_auth_clean_no_blocker_ok = not provider_auth_blocker_present if not provider_auth_issue else None
        provider_auth_gaps = _operator_provider_auth_gaps(operator_blockers_text, operator_issues)
        _record_check(
            checks,
            "provider_auth_blocker_rendered",
            not provider_auth_gaps,
            {
                "provider_auth_expected_mode": provider_auth_expected_mode,
                "provider_auth_blocker_expected": True if provider_auth_issue else None,
                "provider_auth_blocker_present": provider_auth_blocker_present if provider_auth_issue else None,
                "provider_auth_clean_no_blocker_ok": provider_auth_clean_no_blocker_ok,
                "gaps": provider_auth_gaps,
                "text": operator_blockers_text[:900],
            },
        )
        recovery_reuse_gaps = _operator_recovery_packet_reuse_gaps(operator_blockers_text, operator_issues)
        _record_check(
            checks,
            "operator_reused_recovery_packet_label",
            not recovery_reuse_gaps,
            {
                "gaps": recovery_reuse_gaps,
                "text": operator_blockers_text[:900],
            },
        )
        remediation_issues = [issue for issue in operator_issues if str(issue.get("remediation", "")).strip()]
        copy_buttons = page.locator("[aria-label='Copy remediation action']")
        copy_button_count = copy_buttons.count()
        copy_detail: dict[str, Any] = {
            "copy_button_count": copy_button_count,
            "remediation_issue_count": len(remediation_issues),
        }
        copy_ok = copy_button_count >= len(remediation_issues)
        if copy_button_count:
            first_copy_button = copy_buttons.first
            initial_copy_button_text = first_copy_button.inner_text(timeout=timeout_ms).strip()
            action_text = first_copy_button.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_copy_button.click()
            copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy remediation action']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            button_text = first_copy_button.inner_text(timeout=timeout_ms)
            copy_detail.update(
                {
                    "first_action": action_text[:240],
                    "initial_button_text": initial_copy_button_text,
                    "button_text": button_text,
                    "copy_feedback_seen": copy_feedback_seen,
                    "clipboard_matches": bool(action_text and clipboard_text == action_text),
                }
            )
            copy_ok = (
                copy_ok
                and bool(action_text)
                and clipboard_text == action_text
                and initial_copy_button_text == "Copy remediation action"
            )
        _record_check(checks, "operator_remediation_copy", copy_ok, copy_detail)

        recovery_copy_buttons = page.locator("[aria-label='Copy recovery packet path']")
        recovery_copy_button_count = recovery_copy_buttons.count()
        recovery_copy_detail: dict[str, Any] = {
            "copy_button_count": recovery_copy_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        recovery_copy_ok = recovery_copy_button_count >= len(recovery_packet_paths)
        if recovery_copy_button_count:
            first_recovery_button = recovery_copy_buttons.first
            packet_text = first_recovery_button.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_recovery_button.click()
            recovery_copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy recovery packet path']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                recovery_copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            button_text = first_recovery_button.inner_text(timeout=timeout_ms)
            recovery_copy_detail.update(
                {
                    "first_packet": packet_text[:240],
                    "button_text": button_text,
                    "copy_feedback_seen": recovery_copy_feedback_seen,
                    "clipboard_matches": bool(packet_text and clipboard_text == packet_text),
                }
            )
            recovery_copy_ok = (
                recovery_copy_ok
                and bool(packet_text)
                and clipboard_text == packet_text
            )
        _record_check(checks, "operator_recovery_packet_copy", recovery_copy_ok, recovery_copy_detail)

        expected_recovery_bundle_fragments: list[dict[str, str]] = []
        recovery_bundle_packet_error = ""
        expected_recovery_bundle_source = ""
        recovery_bundle_packet_fields = (
            "next_required_action",
            "operator_focus",
            "recovery_summary",
            "evidence_freshness_summary",
            "scheduler_pause_command_bundle",
            "credential_update_command_bundle",
            "scheduler_resume_command_bundle",
        )
        for recovery_packet_path in dict.fromkeys(recovery_packet_paths):
            packet_path = Path(recovery_packet_path)
            if not packet_path.is_absolute():
                packet_path = PROJECT_ROOT / packet_path
            try:
                packet_payload = json.loads(packet_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                if not recovery_bundle_packet_error:
                    recovery_bundle_packet_error = f"{recovery_packet_path}: {exc}"
                continue
            if not isinstance(packet_payload, dict):
                if not recovery_bundle_packet_error:
                    recovery_bundle_packet_error = f"{recovery_packet_path}: recovery packet is not a JSON object"
                continue
            expected_recovery_bundle_fragments = [
                {
                    "field": field,
                    "value": str(packet_payload.get(field) or "").strip(),
                }
                for field in recovery_bundle_packet_fields
                if str(packet_payload.get(field) or "").strip()
            ]
            if expected_recovery_bundle_fragments:
                expected_recovery_bundle_source = recovery_packet_path
                recovery_bundle_packet_error = ""
                break
            if not recovery_bundle_packet_error:
                recovery_bundle_packet_error = f"{recovery_packet_path}: recovery bundle fields are empty"

        recovery_row_bundle_buttons = page.locator("[aria-label='Copy recovery bundle']")
        recovery_row_bundle_button_count = recovery_row_bundle_buttons.count()
        recovery_row_bundle_detail: dict[str, Any] = {
            "copy_button_count": recovery_row_bundle_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
            "expected_recovery_bundle_source": expected_recovery_bundle_source,
            "expected_recovery_bundle_fragment_count": len(expected_recovery_bundle_fragments),
            "recovery_bundle_packet_error": recovery_bundle_packet_error,
        }
        recovery_row_bundle_ok = recovery_row_bundle_button_count >= len(recovery_packet_paths)
        if recovery_row_bundle_button_count:
            first_recovery_row_bundle = recovery_row_bundle_buttons.first
            initial_recovery_row_bundle_text = first_recovery_row_bundle.inner_text(timeout=timeout_ms).strip()
            row_packet_text = first_recovery_row_bundle.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_recovery_row_bundle.click()
            row_bundle_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy recovery bundle']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                row_bundle_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            row_bundle_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://[^\s\"'<>]+", normalized_clipboard_text):
                row_bundle_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", normalized_clipboard_text):
                row_bundle_secret_gaps.append("clipboard contains raw OpenAI-style key")
            if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", normalized_clipboard_text):
                row_bundle_secret_gaps.append("clipboard contains raw Google API-style key")
            row_bundle_target_gaps = []
            if "workspace-smoke-getdaytrends-operator-recheck.json" not in normalized_clipboard_text:
                row_bundle_target_gaps.append("missing operator recheck workspace smoke target")
            if "workspace-smoke-getdaytrends-launch-final.json" in normalized_clipboard_text:
                row_bundle_target_gaps.append("uses launch-final workspace smoke target")
            missing_recovery_row_bundle_fragments = [
                fragment["field"]
                for fragment in expected_recovery_bundle_fragments
                if fragment["value"] not in normalized_clipboard_text
            ]
            button_text = first_recovery_row_bundle.inner_text(timeout=timeout_ms)
            recovery_row_bundle_detail.update(
                {
                    "first_packet": row_packet_text[:240],
                    "initial_button_text": initial_recovery_row_bundle_text,
                    "button_text": button_text,
                    "copy_feedback_seen": row_bundle_feedback_seen,
                    "clipboard_text": clipboard_text[:1600],
                    "secret_gaps": row_bundle_secret_gaps,
                    "target_gaps": row_bundle_target_gaps,
                    "missing_recovery_bundle_fragments": missing_recovery_row_bundle_fragments,
                }
            )
            recovery_row_bundle_ok = (
                recovery_row_bundle_ok
                and bool(expected_recovery_bundle_fragments)
                and not recovery_bundle_packet_error
                and not missing_recovery_row_bundle_fragments
                and bool(row_packet_text)
                and "# getdaytrends Supabase recovery bundle" in normalized_clipboard_text
                and "## Next required action" in normalized_clipboard_text
                and "Transaction pooler" in normalized_clipboard_text
                and "## Current blocker summary" in normalized_clipboard_text
                and "## Verification commands" in normalized_clipboard_text
                and "Set-Location -LiteralPath" in normalized_clipboard_text
                and "python main.py --doctor --require-live-db" in normalized_clipboard_text
                and "run_workspace_smoke.py --scope getdaytrends" in normalized_clipboard_text
                and not row_bundle_target_gaps
                and not row_bundle_secret_gaps
                and initial_recovery_row_bundle_text == "Copy recovery bundle"
            )
        _record_check(
            checks,
            "operator_recovery_bundle_row_copy",
            recovery_row_bundle_ok,
            recovery_row_bundle_detail,
        )

        expected_recovery_verify_commands: list[str] = []
        recovery_verify_packet_error = ""
        expected_recovery_verify_source = ""
        for recovery_packet_path in dict.fromkeys(recovery_packet_paths):
            packet_path = Path(recovery_packet_path)
            if not packet_path.is_absolute():
                packet_path = PROJECT_ROOT / packet_path
            try:
                packet_payload = json.loads(packet_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                if not recovery_verify_packet_error:
                    recovery_verify_packet_error = f"{recovery_packet_path}: {exc}"
                continue
            if not isinstance(packet_payload, dict):
                if not recovery_verify_packet_error:
                    recovery_verify_packet_error = f"{recovery_packet_path}: recovery packet is not a JSON object"
                continue
            recheck_sequence = packet_payload.get("post_credential_recheck_sequence")
            if not isinstance(recheck_sequence, list):
                if not recovery_verify_packet_error:
                    recovery_verify_packet_error = (
                        f"{recovery_packet_path}: post_credential_recheck_sequence missing or not a list"
                    )
                continue
            expected_recovery_verify_commands = [
                str(item.get("command") or "").strip()
                for item in recheck_sequence
                if isinstance(item, dict) and str(item.get("command") or "").strip()
            ]
            if expected_recovery_verify_commands:
                expected_recovery_verify_source = recovery_packet_path
                recovery_verify_packet_error = ""
                break
            if not recovery_verify_packet_error:
                recovery_verify_packet_error = (
                    f"{recovery_packet_path}: post_credential_recheck_sequence has no valid commands"
                )

        recovery_row_verify_buttons = page.locator("[aria-label='Copy recovery verification bundle']")
        recovery_row_verify_button_count = recovery_row_verify_buttons.count()
        recovery_row_verify_detail: dict[str, Any] = {
            "copy_button_count": recovery_row_verify_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
            "expected_recovery_verify_source": expected_recovery_verify_source,
            "expected_recovery_verify_command_count": len(expected_recovery_verify_commands),
            "recovery_verify_packet_error": recovery_verify_packet_error,
        }
        recovery_row_verify_ok = recovery_row_verify_button_count >= len(recovery_packet_paths)
        if recovery_row_verify_button_count:
            first_recovery_row_verify = recovery_row_verify_buttons.first
            initial_row_verify_button_text = first_recovery_row_verify.inner_text(timeout=timeout_ms).strip()
            row_verify_packet_text = first_recovery_row_verify.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_recovery_row_verify.click()
            row_verify_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy recovery verification bundle']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                row_verify_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_verify_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            row_verify_first_line = normalized_verify_text.splitlines()[0].strip() if normalized_verify_text else ""
            row_verify_starts_in_workdir = (
                row_verify_first_line.startswith("Set-Location -LiteralPath")
                and str(PROJECT_ROOT) in row_verify_first_line
            )
            row_verify_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://[^\s\"'<>]+", normalized_verify_text):
                row_verify_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", normalized_verify_text):
                row_verify_secret_gaps.append("clipboard contains raw OpenAI-style key")
            if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", normalized_verify_text):
                row_verify_secret_gaps.append("clipboard contains raw Google API-style key")
            row_verify_target_gaps = []
            if "workspace-smoke-getdaytrends-operator-recheck.json" not in normalized_verify_text:
                row_verify_target_gaps.append("missing operator recheck workspace smoke target")
            if "workspace-smoke-getdaytrends-launch-final.json" in normalized_verify_text:
                row_verify_target_gaps.append("uses launch-final workspace smoke target")
            missing_recovery_verify_commands = [
                command for command in expected_recovery_verify_commands if command not in normalized_verify_text
            ]
            button_text = first_recovery_row_verify.inner_text(timeout=timeout_ms)
            recovery_row_verify_detail.update(
                {
                    "first_packet": row_verify_packet_text[:240],
                    "initial_button_text": initial_row_verify_button_text,
                    "first_line": row_verify_first_line,
                    "button_text": button_text,
                    "copy_feedback_seen": row_verify_feedback_seen,
                    "starts_in_workdir": row_verify_starts_in_workdir,
                    "clipboard_text": clipboard_text[:1200],
                    "secret_gaps": row_verify_secret_gaps,
                    "target_gaps": row_verify_target_gaps,
                    "missing_recovery_verify_commands": missing_recovery_verify_commands,
                }
            )
            recovery_row_verify_ok = (
                recovery_row_verify_ok
                and bool(expected_recovery_verify_commands)
                and not recovery_verify_packet_error
                and not missing_recovery_verify_commands
                and bool(row_verify_packet_text)
                and row_verify_starts_in_workdir
                and "python main.py --doctor --require-live-db" in normalized_verify_text
                and "python scripts\\smoke_cli.py --include-dry-run" in normalized_verify_text
                and "--tap-source-fixture" in normalized_verify_text
                and "readiness_check.py" in normalized_verify_text
                and "run_workspace_smoke.py --scope getdaytrends" in normalized_verify_text
                and not row_verify_target_gaps
                and not row_verify_secret_gaps
                and initial_row_verify_button_text == "Copy recovery verification bundle"
            )
        _record_check(
            checks,
            "operator_recovery_verify_row_copy",
            recovery_row_verify_ok,
            recovery_row_verify_detail,
        )

        expected_launch_success_criteria: list[str] = []
        launch_success_criteria_packet_error = ""
        expected_launch_success_criteria_source = ""
        for recovery_packet_path in dict.fromkeys(recovery_packet_paths):
            packet_path = Path(recovery_packet_path)
            if not packet_path.is_absolute():
                packet_path = PROJECT_ROOT / packet_path
            try:
                packet_payload = json.loads(packet_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                if not launch_success_criteria_packet_error:
                    launch_success_criteria_packet_error = f"{recovery_packet_path}: {exc}"
                continue
            if not isinstance(packet_payload, dict):
                if not launch_success_criteria_packet_error:
                    launch_success_criteria_packet_error = (
                        f"{recovery_packet_path}: recovery packet is not a JSON object"
                    )
                continue
            launch_success_criteria = packet_payload.get("launch_success_criteria")
            if not isinstance(launch_success_criteria, list):
                if not launch_success_criteria_packet_error:
                    launch_success_criteria_packet_error = (
                        f"{recovery_packet_path}: launch_success_criteria missing or not a list"
                    )
                continue
            expected_launch_success_criteria = [
                str(criterion).strip()
                for criterion in launch_success_criteria
                if str(criterion).strip()
            ]
            if expected_launch_success_criteria:
                expected_launch_success_criteria_source = recovery_packet_path
                launch_success_criteria_packet_error = ""
                break
            if not launch_success_criteria_packet_error:
                launch_success_criteria_packet_error = (
                    f"{recovery_packet_path}: launch_success_criteria has no valid criteria"
                )

        recovery_row_success_buttons = page.locator("[aria-label='Copy launch success criteria']")
        recovery_row_success_button_count = recovery_row_success_buttons.count()
        recovery_row_success_detail: dict[str, Any] = {
            "copy_button_count": recovery_row_success_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
            "expected_launch_success_criteria_source": expected_launch_success_criteria_source,
            "expected_launch_success_criteria_count": len(expected_launch_success_criteria),
            "launch_success_criteria_packet_error": launch_success_criteria_packet_error,
        }
        recovery_row_success_ok = recovery_row_success_button_count >= len(recovery_packet_paths)
        if recovery_row_success_button_count:
            first_recovery_row_success = recovery_row_success_buttons.first
            initial_row_success_button_text = first_recovery_row_success.inner_text(timeout=timeout_ms).strip()
            row_success_packet_text = first_recovery_row_success.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_recovery_row_success.click()
            row_success_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy launch success criteria']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                row_success_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_success_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            row_success_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://[^\s\"'<>]+", normalized_success_text):
                row_success_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", normalized_success_text):
                row_success_secret_gaps.append("clipboard contains raw OpenAI-style key")
            if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", normalized_success_text):
                row_success_secret_gaps.append("clipboard contains raw Google API-style key")
            missing_launch_success_criteria = [
                criterion
                for criterion in expected_launch_success_criteria
                if criterion not in normalized_success_text
            ]
            observed_launch_success_criteria_count = len(re.findall(r"(?m)^\d+\.\s+", normalized_success_text))
            launch_success_criteria_count_matches = (
                observed_launch_success_criteria_count == len(expected_launch_success_criteria)
            )
            button_text = first_recovery_row_success.inner_text(timeout=timeout_ms)
            recovery_row_success_detail.update(
                {
                    "first_packet": row_success_packet_text[:240],
                    "initial_button_text": initial_row_success_button_text,
                    "button_text": button_text,
                    "copy_feedback_seen": row_success_feedback_seen,
                    "clipboard_text": clipboard_text[:1200],
                    "secret_gaps": row_success_secret_gaps,
                    "observed_launch_success_criteria_count": observed_launch_success_criteria_count,
                    "launch_success_criteria_count_matches": launch_success_criteria_count_matches,
                    "missing_launch_success_criteria": missing_launch_success_criteria,
                }
            )
            recovery_row_success_ok = (
                recovery_row_success_ok
                and bool(expected_launch_success_criteria)
                and not launch_success_criteria_packet_error
                and launch_success_criteria_count_matches
                and not missing_launch_success_criteria
                and bool(row_success_packet_text)
                and "Launch success criteria:" in normalized_success_text
                and "Live DB doctor reports OK" in normalized_success_text
                and "runtime_fallback_count 0" in normalized_success_text
                and "Strict readiness reports status pass" in normalized_success_text
                and "Canonical getdaytrends workspace smoke reports all configured checks PASS" in normalized_success_text
                and "##" not in normalized_success_text
                and not row_success_secret_gaps
                and initial_row_success_button_text == "Copy launch criteria"
            )
        _record_check(
            checks,
            "operator_recovery_success_row_copy",
            recovery_row_success_ok,
            recovery_row_success_detail,
        )

        scheduler_pause_row_buttons = page.locator("[aria-label='Copy scheduler pause commands from blocker row']")
        scheduler_pause_row_button_count = scheduler_pause_row_buttons.count()
        scheduler_pause_row_detail: dict[str, Any] = {
            "copy_button_count": scheduler_pause_row_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        scheduler_pause_row_ok = scheduler_pause_row_button_count >= len(recovery_packet_paths)
        if scheduler_pause_row_button_count:
            first_scheduler_pause_row = scheduler_pause_row_buttons.first
            initial_scheduler_pause_row_text = first_scheduler_pause_row.inner_text(timeout=timeout_ms).strip()
            pause_row_packet_text = first_scheduler_pause_row.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_scheduler_pause_row.click()
            pause_row_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy scheduler pause commands from blocker row']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                pause_row_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_pause_row_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            pause_row_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://[^\s\"'<>]+", normalized_pause_row_text):
                pause_row_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", normalized_pause_row_text):
                pause_row_secret_gaps.append("clipboard contains raw OpenAI-style key")
            if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", normalized_pause_row_text):
                pause_row_secret_gaps.append("clipboard contains raw Google API-style key")
            scheduler_pause_row_detail.update(
                {
                    "first_packet": pause_row_packet_text[:240],
                    "initial_button_text": initial_scheduler_pause_row_text,
                    "button_text": first_scheduler_pause_row.inner_text(timeout=timeout_ms),
                    "copy_feedback_seen": pause_row_feedback_seen,
                    "clipboard_text": clipboard_text[:1200],
                    "secret_gaps": pause_row_secret_gaps,
                }
            )
            scheduler_pause_row_ok = (
                scheduler_pause_row_ok
                and bool(pause_row_packet_text)
                and "Set-Location -LiteralPath" in normalized_pause_row_text
                and "automation\\getdaytrends" in normalized_pause_row_text
                and "data\\getdaytrends.lock" in normalized_pause_row_text
                and "Get-Process -Id" in normalized_pause_row_text
                and "GetDayTrends_CurrentUser" in normalized_pause_row_text
                and "GetDayTrends_NewTask" in normalized_pause_row_text
                and "schtasks /Query /TN" in normalized_pause_row_text
                and "schtasks /Change /TN $taskName /DISABLE" in normalized_pause_row_text
                and "postgresql://" not in normalized_pause_row_text
                and not pause_row_secret_gaps
                and initial_scheduler_pause_row_text == "Copy scheduler pause"
            )
        _record_check(
            checks,
            "operator_scheduler_pause_row_copy",
            scheduler_pause_row_ok,
            scheduler_pause_row_detail,
        )

        credential_update_row_buttons = page.locator("[aria-label='Copy credential update commands from blocker row']")
        credential_update_row_button_count = credential_update_row_buttons.count()
        credential_update_row_detail: dict[str, Any] = {
            "copy_button_count": credential_update_row_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        credential_update_row_ok = credential_update_row_button_count >= len(recovery_packet_paths)
        if credential_update_row_button_count:
            first_credential_update_row = credential_update_row_buttons.first
            initial_credential_update_row_text = first_credential_update_row.inner_text(timeout=timeout_ms).strip()
            credential_row_packet_text = first_credential_update_row.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_credential_update_row.click()
            credential_row_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy credential update commands from blocker row']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                credential_row_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_credential_row_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            credential_row_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", normalized_credential_row_text, re.IGNORECASE):
                credential_row_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", normalized_credential_row_text, re.IGNORECASE):
                credential_row_secret_gaps.append("clipboard contains raw tenant user")
            credential_update_row_detail.update(
                {
                    "first_packet": credential_row_packet_text[:240],
                    "initial_button_text": initial_credential_update_row_text,
                    "button_text": first_credential_update_row.inner_text(timeout=timeout_ms),
                    "copy_feedback_seen": credential_row_feedback_seen,
                    "clipboard_text": clipboard_text[:1200],
                    "secret_gaps": credential_row_secret_gaps,
                }
            )
            credential_update_row_ok = (
                credential_update_row_ok
                and bool(credential_row_packet_text)
                and "Set-Location -LiteralPath" in normalized_credential_row_text
                and "automation\\getdaytrends" in normalized_credential_row_text
                and "Fast path" in normalized_credential_row_text
                and "Get-Clipboard -Raw" in normalized_credential_row_text
                and "without interactive EOF" in normalized_credential_row_text
                and "Interactive fallback" in normalized_credential_row_text
                and "Transaction pooler DATABASE_URL" in normalized_credential_row_text
                and "send EOF" in normalized_credential_row_text
                and "Ctrl+Z, then Enter in PowerShell" in normalized_credential_row_text
                and "Pause scheduled/background getdaytrends clients" in normalized_credential_row_text
                and "circuit breaker" in normalized_credential_row_text
                and "wait at least 2 minutes" in normalized_credential_row_text
                and SAFE_DATABASE_UPDATE_FRAGMENTS[0] in normalized_credential_row_text
                and SAFE_DATABASE_UPDATE_FRAGMENTS[1] in normalized_credential_row_text
                and "postgresql://" not in normalized_credential_row_text
                and not credential_row_secret_gaps
                and initial_credential_update_row_text == "Copy credential update"
            )
        _record_check(
            checks,
            "operator_credential_update_row_copy",
            credential_update_row_ok,
            credential_update_row_detail,
        )

        scheduler_resume_row_buttons = page.locator("[aria-label='Copy scheduler resume commands from blocker row']")
        scheduler_resume_row_button_count = scheduler_resume_row_buttons.count()
        scheduler_resume_row_detail: dict[str, Any] = {
            "copy_button_count": scheduler_resume_row_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        scheduler_resume_row_ok = scheduler_resume_row_button_count >= len(recovery_packet_paths)
        if scheduler_resume_row_button_count:
            first_scheduler_resume_row = scheduler_resume_row_buttons.first
            initial_scheduler_resume_row_text = first_scheduler_resume_row.inner_text(timeout=timeout_ms).strip()
            resume_row_packet_text = first_scheduler_resume_row.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_scheduler_resume_row.click()
            resume_row_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy scheduler resume commands from blocker row']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                resume_row_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_resume_row_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            resume_row_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://[^\s\"'<>]+", normalized_resume_row_text):
                resume_row_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", normalized_resume_row_text):
                resume_row_secret_gaps.append("clipboard contains raw OpenAI-style key")
            if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", normalized_resume_row_text):
                resume_row_secret_gaps.append("clipboard contains raw Google API-style key")
            scheduler_resume_row_detail.update(
                {
                    "first_packet": resume_row_packet_text[:240],
                    "initial_button_text": initial_scheduler_resume_row_text,
                    "button_text": first_scheduler_resume_row.inner_text(timeout=timeout_ms),
                    "copy_feedback_seen": resume_row_feedback_seen,
                    "clipboard_text": clipboard_text[:1200],
                    "secret_gaps": resume_row_secret_gaps,
                }
            )
            scheduler_resume_row_ok = (
                scheduler_resume_row_ok
                and bool(resume_row_packet_text)
                and "Set-Location -LiteralPath" in normalized_resume_row_text
                and "automation\\getdaytrends" in normalized_resume_row_text
                and "GetDayTrends_CurrentUser" in normalized_resume_row_text
                and "GetDayTrends_NewTask" in normalized_resume_row_text
                and "schtasks /Query /TN" in normalized_resume_row_text
                and "schtasks /Change /TN $taskName /ENABLE" in normalized_resume_row_text
                and "live DB doctor" in normalized_resume_row_text
                and "workspace smoke pass" in normalized_resume_row_text
                and "postgresql://" not in normalized_resume_row_text
                and not resume_row_secret_gaps
                and initial_scheduler_resume_row_text == "Copy scheduler resume"
            )
        _record_check(
            checks,
            "operator_scheduler_resume_row_copy",
            scheduler_resume_row_ok,
            scheduler_resume_row_detail,
        )

        recovery_view_buttons = page.locator("[aria-label='View recovery packet']")
        recovery_view_button_count = recovery_view_buttons.count()
        recovery_view_detail: dict[str, Any] = {
            "view_button_count": recovery_view_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        recovery_view_ok = recovery_view_button_count >= len(recovery_packet_paths)
        if recovery_view_button_count:
            first_view_button = recovery_view_buttons.first
            initial_recovery_disclosure = first_view_button.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        height: Math.round(button.getBoundingClientRect().height),
                        controls,
                        artifact_path: button.getAttribute('data-artifact-path') || '',
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                    };
                }"""
            )
            recovery_view_detail["initial_disclosure"] = initial_recovery_disclosure
            first_view_button = page.locator(
                f"[aria-controls='{initial_recovery_disclosure.get('controls', '')}']"
            ).first
            first_view_button.click()
            try:
                page.wait_for_function(
                    """() => Array.from(document.querySelectorAll('.operator-view-btn')).some(
                        button => button.getAttribute('aria-expanded') === 'true'
                            && (document.getElementById(button.getAttribute('aria-controls') || '')?.innerText || '').includes('Packet status:')
                    )""",
                    timeout=timeout_ms,
                )
            except PlaywrightTimeoutError:
                pass
            preview_text = first_view_button.evaluate(
                "(button) => button.closest('.operator-action')?.querySelector('.operator-packet-preview')?.innerText || ''"
            )
            reference_links = first_view_button.evaluate(
                """button => Array.from(
                    button.closest('.operator-action')?.querySelectorAll('.operator-packet-preview .operator-reference-link') || []
                ).map(link => ({
                    text: (link.textContent || '').trim(),
                    href: link.href || '',
                    target: link.getAttribute('target') || '',
                    rel: link.getAttribute('rel') || '',
                }))"""
            )
            recovery_disclosure = first_view_button.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        height: Math.round(button.getBoundingClientRect().height),
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').slice(0, 500),
                    };
                }"""
            )
            first_view_button.click()
            page.wait_for_timeout(120)
            recovery_collapsed_disclosure = first_view_button.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        height: Math.round(button.getBoundingClientRect().height),
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').trim(),
                    };
                }"""
            )
            first_view_button.click()
            try:
                page.wait_for_function(
                    """() => Array.from(document.querySelectorAll('.operator-view-btn')).some(
                        button => button.getAttribute('aria-expanded') === 'true'
                            && (document.getElementById(button.getAttribute('aria-controls') || '')?.innerText || '').includes('Packet status:')
                    )""",
                    timeout=timeout_ms,
                )
            except PlaywrightTimeoutError:
                pass
            recovery_reopened_disclosure = first_view_button.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        height: Math.round(button.getBoundingClientRect().height),
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').slice(0, 500),
                    };
                }"""
            )
            recovery_view_detail["preview_text"] = preview_text[:500]
            recovery_view_detail["reference_links"] = reference_links
            recovery_view_detail["disclosure"] = recovery_disclosure
            recovery_view_detail["collapsed_disclosure"] = recovery_collapsed_disclosure
            recovery_view_detail["reopened_disclosure"] = recovery_reopened_disclosure
            recovery_action_group = page.evaluate(
                """() => {
                    const preview = document.querySelector('.operator-packet-preview:not([hidden])');
                    const group = preview?.querySelector('.operator-packet-action-group');
                    const buttons = Array.from(group?.querySelectorAll('button') || []).map(button => ({
                        text: (button.innerText || '').trim(),
                        ariaLabel: button.getAttribute('aria-label') || '',
                        className: button.className || '',
                        priority: button.getAttribute('data-copy-priority') || '',
                        title: button.getAttribute('title') || '',
                        height: Math.round(button.getBoundingClientRect().height),
                        type: button.getAttribute('type') || '',
                    }));
                    return {
                        exists: Boolean(group),
                        role: group?.getAttribute('role') || '',
                        label: group?.getAttribute('aria-label') || '',
                        buttonCount: buttons.length,
                        buttonTexts: buttons.map(button => button.text),
                        buttonAriaLabels: buttons.map(button => button.ariaLabel),
                        buttonClasses: buttons.map(button => button.className),
                        buttonPriorities: buttons.map(button => button.priority),
                        buttonTitles: buttons.map(button => button.title),
                        buttonHeights: buttons.map(button => button.height),
                        minButtonHeight: buttons.length
                            ? Math.min(...buttons.map(button => button.height))
                            : 0,
                        primaryButtonTexts: buttons
                            .filter(button => button.priority === 'primary')
                            .map(button => button.text),
                        primaryButtonClasses: buttons
                            .filter(button => button.priority === 'primary')
                            .map(button => button.className),
                        buttonTypes: buttons.map(button => button.type),
                    };
                }"""
            )
            recovery_view_detail["action_group"] = recovery_action_group
            recovery_preview_timeout = (
                "live_db_doctor_timeout" in preview_text
                or "Live DB doctor timed out" in preview_text
            )
            recovery_preview_failure_fragments = (
                [
                    "live_db_doctor_timeout",
                    "verify network reachability",
                    "current database password",
                    "reachable network path",
                ]
                if recovery_preview_timeout
                else [
                    "Project refs, DNS, and TCP already pass",
                    "Transaction pooler credentials",
                    "Doctor diagnostics:",
                ]
            )
            recovery_preview_required_fragments = [
                "Packet status:",
                "Generated:",
                "Readiness",
                "Next action:",
                "Operator focus:",
                *recovery_preview_failure_fragments,
                "Copy recovery next action",
                "Transaction pooler",
                "Issue types:",
                "Blocking checks:",
                "cli_smoke_report",
                "live_db_doctor",
                "Runtime fallbacks: 0",
                "Required env:",
                "DATABASE_URL",
                "SUPABASE_URL",
                "Connection facts:",
                "Supabase Transaction pooler",
                "Accepted Transaction pooler shapes",
                "aws-[region].pooler.supabase.com",
                "postgres.<project_ref>",
                "Pause scheduled/background getdaytrends clients",
                "Supavisor/shared pooler circuit breaker",
                "short lockout",
                "Recovery safety:",
                "Copy connection facts",
                "Copy credential update commands",
                "References:",
                "Supabase database connection guide",
                "Supabase Supavisor password rotation circuit-breaker guide",
                "wait at least 2 minutes",
                "Microsoft schtasks query reference",
                "Microsoft schtasks change reference",
                "Scheduler control:",
                SAFE_DATABASE_UPDATE_FRAGMENTS[0],
                SAFE_DATABASE_UPDATE_FRAGMENTS[1],
                "Verification cwd:",
                str(PROJECT_ROOT),
                "Launch success:",
                "runtime_fallback_count 0",
                "Canonical getdaytrends workspace smoke reports all configured checks PASS",
                "Post-credential recheck:",
                "live_db_doctor -> cli_smoke -> strict_readiness -> canonical_workspace_smoke",
                "Recheck evidence:",
                "logs\\smoke\\cli_smoke_latest.json",
                "logs\\readiness\\readiness_latest.json",
                "workspace-smoke-getdaytrends-operator-recheck.json",
                "Final proof:",
                "Final proof signals:",
                "status=pass, failed=0",
                "runtime_fallback_count=0",
                "Copy post-credential recheck",
                "Copy final proof bundle",
                "Checklist:",
                "Supabase dashboard Connect panel",
                "Verify:",
            ]
            recovery_view_detail["missing_preview_fragments"] = [
                item for item in recovery_preview_required_fragments if item not in preview_text
            ]
            recovery_view_detail["missing_preview_patterns"] = [
                label
                for label, pattern in [
                    ("Issue count", r"\bIssue count:\s*[1-9]\d*\b"),
                    ("Blocking check count", r"\bBlocking check count:\s*[1-9]\d*\b"),
                ]
                if not re.search(pattern, preview_text)
            ]
            recovery_view_detail["forbidden_preview_fragments"] = [
                item for item in ["provider_auth_report"] if item in preview_text
            ]
            recovery_view_ok = (
                recovery_view_ok
                and initial_recovery_disclosure.get("label") == "View recovery packet"
                and initial_recovery_disclosure.get("text") == "View recovery packet"
                and initial_recovery_disclosure.get("expanded") == "false"
                and int(initial_recovery_disclosure.get("height") or 0) >= 28
                and bool(initial_recovery_disclosure.get("controls"))
                and initial_recovery_disclosure.get("target_exists") is True
                and initial_recovery_disclosure.get("target_hidden") is True
                and recovery_disclosure.get("label") == "Hide recovery packet"
                and recovery_disclosure.get("text") == "Hide recovery packet"
                and recovery_disclosure.get("expanded") == "true"
                and int(recovery_disclosure.get("height") or 0) >= 28
                and recovery_disclosure.get("target_exists") is True
                and recovery_disclosure.get("target_hidden") is False
                and "Packet status:" in recovery_disclosure.get("target_text", "")
                and recovery_collapsed_disclosure.get("label") == "View recovery packet"
                and recovery_collapsed_disclosure.get("text") == "View recovery packet"
                and recovery_collapsed_disclosure.get("expanded") == "false"
                and int(recovery_collapsed_disclosure.get("height") or 0) >= 28
                and recovery_collapsed_disclosure.get("target_exists") is True
                and recovery_collapsed_disclosure.get("target_hidden") is True
                and recovery_collapsed_disclosure.get("target_text") == ""
                and recovery_reopened_disclosure.get("label") == "Hide recovery packet"
                and recovery_reopened_disclosure.get("text") == "Hide recovery packet"
                and recovery_reopened_disclosure.get("expanded") == "true"
                and int(recovery_reopened_disclosure.get("height") or 0) >= 28
                and recovery_reopened_disclosure.get("target_exists") is True
                and recovery_reopened_disclosure.get("target_hidden") is False
                and "Packet status:" in recovery_reopened_disclosure.get("target_text", "")
                and "Packet status:" in preview_text
                and "Generated:" in preview_text
                and "Readiness" in preview_text
                and "Next action:" in preview_text
                and "Operator focus:" in preview_text
                and not recovery_view_detail["missing_preview_fragments"]
                and not recovery_view_detail["missing_preview_patterns"]
                and not recovery_view_detail["forbidden_preview_fragments"]
                and "Copy recovery next action" in preview_text
                and "Transaction pooler" in preview_text
                and "Issue types:" in preview_text
                and re.search(r"\bIssue count:\s*[1-9]\d*\b", preview_text)
                and "Blocking checks:" in preview_text
                and re.search(r"\bBlocking check count:\s*[1-9]\d*\b", preview_text)
                and "cli_smoke_report" in preview_text
                and "live_db_doctor" in preview_text
                and "provider_auth_report" not in preview_text
                and "Runtime fallbacks: 0" in preview_text
                and "Required env:" in preview_text
                and "DATABASE_URL" in preview_text
                and "SUPABASE_URL" in preview_text
                and "Connection facts:" in preview_text
                and "Supabase Transaction pooler" in preview_text
                and "Accepted Transaction pooler shapes" in preview_text
                and "aws-[region].pooler.supabase.com" in preview_text
                and "postgres.<project_ref>" in preview_text
                and "Pause scheduled/background getdaytrends clients" in preview_text
                and "Supavisor/shared pooler circuit breaker" in preview_text
                and "short lockout" in preview_text
                and "Recovery safety:" in preview_text
                and "Copy connection facts" in preview_text
                and "Copy credential update commands" in preview_text
                and "References:" in preview_text
                and "Supabase database connection guide" in preview_text
                and "Supabase Supavisor password rotation circuit-breaker guide" in preview_text
                and "wait at least 2 minutes" in preview_text
                and "Microsoft schtasks query reference" in preview_text
                and "Microsoft schtasks change reference" in preview_text
                and "Scheduler control:" in preview_text
                and _reference_link_present(
                    reference_links,
                    "Supabase database connection guide",
                    SUPABASE_REFERENCE_URL,
                )
                and _reference_link_present(
                    reference_links,
                    "Supabase Supavisor password rotation circuit-breaker guide",
                    SUPABASE_CIRCUIT_BREAKER_REFERENCE_URL,
                )
                and _reference_link_present(
                    reference_links,
                    "Microsoft schtasks query reference",
                    MICROSOFT_SCHTASKS_QUERY_REFERENCE_URL,
                )
                and _reference_link_present(
                    reference_links,
                    "Microsoft schtasks change reference",
                    MICROSOFT_SCHTASKS_CHANGE_REFERENCE_URL,
                )
                and SAFE_DATABASE_UPDATE_FRAGMENTS[0] in preview_text
                and SAFE_DATABASE_UPDATE_FRAGMENTS[1] in preview_text
                and "Verification cwd:" in preview_text
                and str(PROJECT_ROOT) in preview_text
                and "Launch success:" in preview_text
                and "runtime_fallback_count 0" in preview_text
                and "Canonical getdaytrends workspace smoke reports all configured checks PASS" in preview_text
                and "Post-credential recheck:" in preview_text
                and "live_db_doctor -> cli_smoke -> strict_readiness -> canonical_workspace_smoke" in preview_text
                and "Recheck evidence:" in preview_text
                and "logs\\smoke\\cli_smoke_latest.json" in preview_text
                and "logs\\readiness\\readiness_latest.json" in preview_text
                and "workspace-smoke-getdaytrends-operator-recheck.json" in preview_text
                and "Final proof:" in preview_text
                and "Final proof signals:" in preview_text
                and "status=pass, failed=0" in preview_text
                and "runtime_fallback_count=0" in preview_text
                and "Copy post-credential recheck" in preview_text
                and "Copy final proof bundle" in preview_text
                and "Checklist:" in preview_text
                and "Supabase dashboard Connect panel" in preview_text
                and "Verify:" in preview_text
                and recovery_action_group.get("exists") is True
                and recovery_action_group.get("role") == "group"
                and recovery_action_group.get("label") == "Recovery packet copy actions"
                and int(recovery_action_group.get("buttonCount") or 0) >= 7
                and "Copy recovery next action" in recovery_action_group.get("buttonTexts", [])
                and "Copy connection facts" in recovery_action_group.get("buttonTexts", [])
                and "Copy scheduler pause commands" in recovery_action_group.get("buttonTexts", [])
                and "Copy credential update commands" in recovery_action_group.get("buttonTexts", [])
                and "Copy post-credential recheck" in recovery_action_group.get("buttonTexts", [])
                and "Copy final proof bundle" in recovery_action_group.get("buttonTexts", [])
                and "Copy recovery bundle" in recovery_action_group.get("buttonTexts", [])
                and "Copy recovery env template" in recovery_action_group.get("buttonTexts", [])
                and "Copy recovery checklist" in recovery_action_group.get("buttonTexts", [])
                and "Copy scheduler resume commands" in recovery_action_group.get("buttonTexts", [])
                and "Copy recovery verification commands" in recovery_action_group.get("buttonTexts", [])
                and int(recovery_action_group.get("minButtonHeight") or 0) >= 28
                and recovery_action_group.get("buttonPriorities", []).count("primary") == 1
                and recovery_action_group.get("primaryButtonTexts") == ["Copy recovery bundle"]
                and any(
                    "operator-copy-btn-primary" in class_name
                    for class_name in recovery_action_group.get("primaryButtonClasses", [])
                )
                and "Recommended recovery handoff" in recovery_action_group.get("buttonTitles", [])
                and all(button_type == "button" for button_type in recovery_action_group.get("buttonTypes", []))
            )
            recovery_missing_preview_fragments = recovery_view_detail["missing_preview_fragments"]
            recovery_missing_preview_patterns = recovery_view_detail["missing_preview_patterns"]
            recovery_forbidden_preview_fragments = recovery_view_detail["forbidden_preview_fragments"]
            recovery_reference_links_ok = (
                _reference_link_present(
                    reference_links,
                    "Supabase database connection guide",
                    SUPABASE_REFERENCE_URL,
                )
                and _reference_link_present(
                    reference_links,
                    "Supabase Supavisor password rotation circuit-breaker guide",
                    SUPABASE_CIRCUIT_BREAKER_REFERENCE_URL,
                )
                and _reference_link_present(
                    reference_links,
                    "Microsoft schtasks query reference",
                    MICROSOFT_SCHTASKS_QUERY_REFERENCE_URL,
                )
                and _reference_link_present(
                    reference_links,
                    "Microsoft schtasks change reference",
                    MICROSOFT_SCHTASKS_CHANGE_REFERENCE_URL,
                )
            )
            recovery_action_group_ok = (
                recovery_action_group.get("exists") is True
                and recovery_action_group.get("role") == "group"
                and recovery_action_group.get("label") == "Recovery packet copy actions"
                and int(recovery_action_group.get("buttonCount") or 0) >= 7
                and int(recovery_action_group.get("minButtonHeight") or 0) >= 28
                and recovery_action_group.get("buttonPriorities", []).count("primary") == 1
                and recovery_action_group.get("primaryButtonTexts") == ["Copy recovery bundle"]
                and all(button_type == "button" for button_type in recovery_action_group.get("buttonTypes", []))
            )
            recovery_view_detail = {
                "expected_mode": "operator_recovery_packet_disclosure_lifecycle",
                "view_button_count": recovery_view_button_count,
                "recovery_packet_count": len(recovery_packet_paths),
                "initial_collapsed_ok": (
                    initial_recovery_disclosure.get("label") == "View recovery packet"
                    and initial_recovery_disclosure.get("expanded") == "false"
                    and initial_recovery_disclosure.get("target_exists") is True
                    and initial_recovery_disclosure.get("target_hidden") is True
                ),
                "open_disclosure_visible_ok": (
                    recovery_disclosure.get("label") == "Hide recovery packet"
                    and recovery_disclosure.get("expanded") == "true"
                    and recovery_disclosure.get("target_exists") is True
                    and recovery_disclosure.get("target_hidden") is False
                    and "Packet status:" in recovery_disclosure.get("target_text", "")
                ),
                "collapsed_disclosure_hidden_ok": (
                    recovery_collapsed_disclosure.get("label") == "View recovery packet"
                    and recovery_collapsed_disclosure.get("expanded") == "false"
                    and recovery_collapsed_disclosure.get("target_exists") is True
                    and recovery_collapsed_disclosure.get("target_hidden") is True
                    and recovery_collapsed_disclosure.get("target_text") == ""
                ),
                "reopened_disclosure_visible_ok": (
                    recovery_reopened_disclosure.get("label") == "Hide recovery packet"
                    and recovery_reopened_disclosure.get("expanded") == "true"
                    and recovery_reopened_disclosure.get("target_exists") is True
                    and recovery_reopened_disclosure.get("target_hidden") is False
                    and "Packet status:" in recovery_reopened_disclosure.get("target_text", "")
                ),
                "preview_content_ok": (
                    "Packet status:" in preview_text
                    and not recovery_missing_preview_fragments
                    and not recovery_missing_preview_patterns
                    and not recovery_forbidden_preview_fragments
                ),
                "reference_links_ok": recovery_reference_links_ok,
                "reference_link_count": len(reference_links),
                "action_group_ok": recovery_action_group_ok,
                "action_button_count": int(recovery_action_group.get("buttonCount") or 0),
                "min_action_button_height": int(recovery_action_group.get("minButtonHeight") or 0),
                "missing_preview_fragments": recovery_missing_preview_fragments,
                "missing_preview_patterns": recovery_missing_preview_patterns,
                "forbidden_preview_fragments": recovery_forbidden_preview_fragments,
            }
        _record_check(checks, "operator_recovery_packet_view", recovery_view_ok, recovery_view_detail)

        next_action_copy_buttons = page.locator("[aria-label='Copy recovery next action']")
        next_action_copy_button_count = next_action_copy_buttons.count()
        next_action_copy_detail: dict[str, Any] = {
            "copy_button_count": next_action_copy_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        next_action_copy_ok = next_action_copy_button_count >= 1 if recovery_packet_paths else next_action_copy_button_count == 0
        if next_action_copy_button_count:
            first_next_action_copy = next_action_copy_buttons.first
            initial_next_action_copy_text = first_next_action_copy.inner_text(timeout=timeout_ms).strip()
            next_action_text = first_next_action_copy.evaluate("(button) => button.dataset.copyText || ''")
            expected_next_action_clipboard = next_action_text.replace("\\n", "\n")
            first_next_action_copy.click()
            next_action_copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy recovery next action']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                next_action_copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            button_text = first_next_action_copy.inner_text(timeout=timeout_ms)
            next_action_gaps = _supabase_recovery_next_action_gaps(expected_next_action_clipboard)
            next_action_copy_detail.update(
                {
                    "next_action": expected_next_action_clipboard[:700],
                    "initial_button_text": initial_next_action_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": next_action_copy_feedback_seen,
                    "clipboard_text": clipboard_text[:700],
                    "clipboard_matches": bool(
                        expected_next_action_clipboard and normalized_clipboard_text == expected_next_action_clipboard
                    ),
                    "next_action_gaps": next_action_gaps,
                }
            )
            next_action_copy_ok = (
                next_action_copy_ok
                and bool(expected_next_action_clipboard)
                and not next_action_gaps
                and normalized_clipboard_text == expected_next_action_clipboard
                and initial_next_action_copy_text == "Copy recovery next action"
            )
        _record_check(checks, "operator_recovery_next_action_copy", next_action_copy_ok, next_action_copy_detail)

        bundle_copy_buttons = page.locator("[aria-label='Copy complete recovery bundle']")
        bundle_copy_button_count = bundle_copy_buttons.count()
        bundle_copy_detail: dict[str, Any] = {
            "copy_button_count": bundle_copy_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
            "expected_recovery_bundle_source": expected_recovery_bundle_source,
            "expected_recovery_bundle_fragment_count": len(expected_recovery_bundle_fragments),
            "recovery_bundle_packet_error": recovery_bundle_packet_error,
        }
        bundle_copy_ok = bundle_copy_button_count >= 1 if recovery_packet_paths else bundle_copy_button_count == 0
        if bundle_copy_button_count:
            first_bundle_copy = bundle_copy_buttons.first
            initial_bundle_copy_text = first_bundle_copy.inner_text(timeout=timeout_ms).strip()
            bundle_text = first_bundle_copy.evaluate("(button) => button.dataset.copyText || ''")
            expected_bundle_clipboard = bundle_text.replace("\\n", "\n")
            first_bundle_copy.click()
            bundle_copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy complete recovery bundle']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                bundle_copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            button_text = first_bundle_copy.inner_text(timeout=timeout_ms)
            page.wait_for_timeout(1700)
            rapid_initial_text = first_bundle_copy.inner_text(timeout=timeout_ms).strip()
            first_bundle_copy.click()
            page.wait_for_timeout(350)
            rapid_after_first_click = first_bundle_copy.inner_text(timeout=timeout_ms).strip()
            first_bundle_copy.click()
            page.wait_for_timeout(350)
            rapid_after_second_click = first_bundle_copy.inner_text(timeout=timeout_ms).strip()
            page.wait_for_timeout(1900)
            rapid_final_text = first_bundle_copy.inner_text(timeout=timeout_ms).strip()
            rapid_button_state = first_bundle_copy.evaluate(
                """button => ({
                    copyResult: button.dataset.copyResult || '',
                    originalText: button.dataset.copyOriginalText || '',
                    priority: button.getAttribute('data-copy-priority') || '',
                    className: button.className || '',
                    ariaLabel: button.getAttribute('aria-label') || '',
                })"""
            )
            primary_denied_feedback_seen = False
            primary_denied_state: dict[str, Any] = {}
            primary_denied_reset_state: dict[str, Any] = {}
            primary_denied_escape_state: dict[str, Any] = {}
            first_bundle_copy.evaluate(
                """button => {
                    hideManualCopy({ restoreFocus: false });
                    button.innerText = 'Copy recovery bundle';
                    delete button.dataset.copyResult;
                    window.__gdtPrimaryBundleDeniedOriginals = {
                        clipboardDescriptor: Object.getOwnPropertyDescriptor(Navigator.prototype, 'clipboard'),
                        execCommand: document.execCommand,
                    };
                    window.__gdtPrimaryBundleDeniedExecCommandCalled = false;
                    Object.defineProperty(Navigator.prototype, 'clipboard', {
                        configurable: true,
                        get() {
                            return {
                                writeText: async () => {
                                    throw new DOMException('Write permission denied.', 'NotAllowedError');
                                },
                                readText: async () => 'unchanged clipboard',
                            };
                        },
                    });
                    document.execCommand = () => {
                        window.__gdtPrimaryBundleDeniedExecCommandCalled = true;
                        return true;
                    };
                    button.focus();
                }"""
            )
            try:
                first_bundle_copy.click()
                try:
                    page.wait_for_function(
                        """() => document.querySelector("[aria-label='Copy complete recovery bundle']")?.dataset.copyResult === 'failed'
                            && document.getElementById('manual-copy-panel')?.classList.contains('show')
                            && document.getElementById('manual-copy-panel')?.hidden === false
                            && (document.getElementById('manual-copy-text')?.value || '').trim().length > 0
                            && (document.getElementById('toast')?.textContent || '').includes('Copy failed')""",
                        timeout=timeout_ms,
                    )
                    primary_denied_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                primary_denied_state = page.evaluate(
                    """() => {
                        const button = document.querySelector("[aria-label='Copy complete recovery bundle']");
                        const panel = document.getElementById('manual-copy-panel');
                        const textarea = document.getElementById('manual-copy-text');
                        const toast = document.getElementById('toast');
                        return {
                            buttonText: (button?.innerText || '').trim(),
                            originalText: button?.dataset.copyOriginalText || '',
                            copyResult: button?.dataset.copyResult || '',
                            priority: button?.getAttribute('data-copy-priority') || '',
                            className: button?.className || '',
                            manualVisible: panel?.classList.contains('show') || false,
                            manualHidden: panel?.hidden ?? null,
                            manualText: textarea?.value || '',
                            activeId: document.activeElement?.id || '',
                            activeLabel: document.activeElement?.getAttribute('aria-label') || '',
                            toastText: toast?.textContent || '',
                            toastType: toast?.dataset.lastToastType || '',
                            toastRole: toast?.dataset.lastToastRole || '',
                            toastLive: toast?.dataset.lastToastLive || '',
                            execCommandCalled: Boolean(window.__gdtPrimaryBundleDeniedExecCommandCalled),
                        };
                    }"""
                )
                page.wait_for_timeout(1700)
                primary_denied_reset_state = page.evaluate(
                    """() => {
                        const button = document.querySelector("[aria-label='Copy complete recovery bundle']");
                        const panel = document.getElementById('manual-copy-panel');
                        const textarea = document.getElementById('manual-copy-text');
                        return {
                            buttonText: (button?.innerText || '').trim(),
                            originalText: button?.dataset.copyOriginalText || '',
                            copyResult: button?.dataset.copyResult || '',
                            manualVisible: panel?.classList.contains('show') || false,
                            manualHidden: panel?.hidden ?? null,
                            manualTextLength: (textarea?.value || '').trim().length,
                            activeId: document.activeElement?.id || '',
                            activeLabel: document.activeElement?.getAttribute('aria-label') || '',
                        };
                    }"""
                )
                page.keyboard.press("Escape")
                try:
                    page.wait_for_function(
                        """() => !document.getElementById('manual-copy-panel')?.classList.contains('show')
                            && document.getElementById('manual-copy-panel')?.hidden === true
                            && (document.getElementById('manual-copy-text')?.value || '') === ''
                            && document.activeElement === document.querySelector("[aria-label='Copy complete recovery bundle']")""",
                        timeout=timeout_ms,
                    )
                except PlaywrightTimeoutError:
                    pass
                primary_denied_escape_state = page.evaluate(
                    """() => {
                        const button = document.querySelector("[aria-label='Copy complete recovery bundle']");
                        const panel = document.getElementById('manual-copy-panel');
                        const textarea = document.getElementById('manual-copy-text');
                        return {
                            buttonText: (button?.innerText || '').trim(),
                            manualVisible: panel?.classList.contains('show') || false,
                            manualHidden: panel?.hidden ?? null,
                            manualTextLength: (textarea?.value || '').trim().length,
                            activeLabel: document.activeElement?.getAttribute('aria-label') || '',
                        };
                    }"""
                )
            finally:
                page.evaluate(
                    """() => {
                        const originals = window.__gdtPrimaryBundleDeniedOriginals || {};
                        if (originals.clipboardDescriptor) {
                            Object.defineProperty(Navigator.prototype, 'clipboard', originals.clipboardDescriptor);
                        } else {
                            delete Navigator.prototype.clipboard;
                        }
                        if (originals.execCommand) {
                            document.execCommand = originals.execCommand;
                        }
                        delete window.__gdtPrimaryBundleDeniedOriginals;
                        delete window.__gdtPrimaryBundleDeniedExecCommandCalled;
                        hideManualCopy({ restoreFocus: false });
                    }"""
                )
            primary_denied_manual_text = str(primary_denied_state.get("manualText", ""))
            primary_denied_ok = (
                primary_denied_feedback_seen
                and primary_denied_state.get("buttonText") == "Failed"
                and primary_denied_state.get("originalText") == "Copy recovery bundle"
                and primary_denied_state.get("copyResult") == "failed"
                and primary_denied_state.get("priority") == "primary"
                and "operator-copy-btn-primary" in primary_denied_state.get("className", "")
                and primary_denied_state.get("manualVisible") is True
                and primary_denied_state.get("manualHidden") is False
                and primary_denied_state.get("activeId") == "manual-copy-text"
                and primary_denied_state.get("toastType") == "error"
                and primary_denied_state.get("toastRole") == "alert"
                and primary_denied_state.get("toastLive") == "assertive"
                and "Copy failed" in primary_denied_state.get("toastText", "")
                and primary_denied_state.get("execCommandCalled") is False
                and primary_denied_manual_text.replace("\r\n", "\n").replace("\r", "\n") == expected_bundle_clipboard
                and primary_denied_reset_state.get("buttonText") == "Copy recovery bundle"
                and primary_denied_reset_state.get("copyResult") == "failed"
                and primary_denied_reset_state.get("manualVisible") is True
                and primary_denied_reset_state.get("manualHidden") is False
                and int(primary_denied_reset_state.get("manualTextLength") or 0) > 0
                and primary_denied_escape_state.get("buttonText") == "Copy recovery bundle"
                and primary_denied_escape_state.get("manualVisible") is False
                and primary_denied_escape_state.get("manualHidden") is True
                and primary_denied_escape_state.get("manualTextLength") == 0
                and primary_denied_escape_state.get("activeLabel") == "Copy complete recovery bundle"
            )
            primary_denied_detail = {
                "expected_mode": "primary_bundle_async_clipboard_denied_manual_copy",
                "feedback_seen": primary_denied_feedback_seen,
                "button_failed": primary_denied_state.get("buttonText") == "Failed",
                "copy_result_failed": primary_denied_state.get("copyResult") == "failed",
                "primary_priority_preserved": primary_denied_state.get("priority") == "primary",
                "manual_panel_open_ok": primary_denied_state.get("manualVisible") is True
                and primary_denied_state.get("manualHidden") is False,
                "manual_focus_ok": primary_denied_state.get("activeId") == "manual-copy-text",
                "toast_accessible_error_ok": primary_denied_state.get("toastType") == "error"
                and primary_denied_state.get("toastRole") == "alert"
                and primary_denied_state.get("toastLive") == "assertive"
                and "Copy failed" in primary_denied_state.get("toastText", ""),
                "no_exec_command_fallback_ok": primary_denied_state.get("execCommandCalled") is False,
                "manual_text_matches": primary_denied_manual_text.replace("\r\n", "\n").replace("\r", "\n")
                == expected_bundle_clipboard,
                "reset_kept_manual_panel_open_ok": primary_denied_reset_state.get("manualVisible") is True
                and primary_denied_reset_state.get("manualHidden") is False
                and int(primary_denied_reset_state.get("manualTextLength") or 0) > 0,
                "escape_closed_manual_panel_ok": primary_denied_escape_state.get("manualVisible") is False
                and primary_denied_escape_state.get("manualHidden") is True
                and primary_denied_escape_state.get("manualTextLength") == 0,
                "escape_focus_returned_ok": primary_denied_escape_state.get("activeLabel")
                == "Copy complete recovery bundle",
                "manual_text_preview": primary_denied_manual_text[:1600],
            }
            missing_recovery_bundle_fragments = [
                fragment["field"]
                for fragment in expected_recovery_bundle_fragments
                if fragment["value"] not in expected_bundle_clipboard
            ]
            bundle_copy_detail.update(
                {
                    "bundle": expected_bundle_clipboard[:1600],
                    "initial_button_text": initial_bundle_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": bundle_copy_feedback_seen,
                    "clipboard_text": clipboard_text[:1600],
                    "clipboard_matches": bool(
                        expected_bundle_clipboard and normalized_clipboard_text == expected_bundle_clipboard
                    ),
                    "rapid_initial_text": rapid_initial_text,
                    "rapid_after_first_click": rapid_after_first_click,
                    "rapid_after_second_click": rapid_after_second_click,
                    "rapid_final_text": rapid_final_text,
                    "rapid_button_state": rapid_button_state,
                    "primary_denied_feedback_seen": primary_denied_feedback_seen,
                    "primary_denied_detail": primary_denied_detail,
                    "primary_denied_ok": primary_denied_ok,
                    "missing_recovery_bundle_fragments": missing_recovery_bundle_fragments,
                }
            )
            supabase_bundle_timeout = "live_db_doctor_timeout" in expected_bundle_clipboard
            supabase_bundle_failure_specific_ok = (
                "live_db_doctor_timeout" in expected_bundle_clipboard
                and "live_postgres_probe_failed" in expected_bundle_clipboard
                and "Live DB doctor timed out" in expected_bundle_clipboard
                and "verify network reachability" in expected_bundle_clipboard
                and "current database password" in expected_bundle_clipboard
            ) if supabase_bundle_timeout else (
                "Project refs, DNS, and TCP already pass" in expected_bundle_clipboard
                and "Transaction pooler credentials" in expected_bundle_clipboard
                and "pooler_tenant_user_not_found" in expected_bundle_clipboard
                and "Doctor diagnostics:" in expected_bundle_clipboard
                and "db.endpoint_tcp" in expected_bundle_clipboard
                and "db.live_postgres" in expected_bundle_clipboard
            )
            bundle_copy_ok = (
                bundle_copy_ok
                and bool(expected_recovery_bundle_fragments)
                and not recovery_bundle_packet_error
                and not missing_recovery_bundle_fragments
                and "# getdaytrends Supabase recovery bundle" in expected_bundle_clipboard
                and "## Next required action" in expected_bundle_clipboard
                and "## Operator focus" in expected_bundle_clipboard
                and supabase_bundle_failure_specific_ok
                and "Transaction pooler" in expected_bundle_clipboard
                and "## Current blocker summary" in expected_bundle_clipboard
                and "Issue types:" in expected_bundle_clipboard
                and "## Evidence freshness" in expected_bundle_clipboard
                and "Packet generated:" in expected_bundle_clipboard
                and "Readiness generated:" in expected_bundle_clipboard
                and "Readiness report:" in expected_bundle_clipboard
                and "## Launch success criteria" in expected_bundle_clipboard
                and "runtime_fallback_count 0" in expected_bundle_clipboard
                and "Strict readiness reports status pass" in expected_bundle_clipboard
                and "Canonical getdaytrends workspace smoke reports all configured checks PASS" in expected_bundle_clipboard
                and "## Env template" in expected_bundle_clipboard
                and "SUPABASE_URL=https://<project_ref>.supabase.co" in expected_bundle_clipboard
                and "DATABASE_URL=<transaction_pooler_uri_from_same_project>" in expected_bundle_clipboard
                and "## Connection mode facts" in expected_bundle_clipboard
                and "Expected DATABASE_URL mode: Supabase Transaction pooler." in expected_bundle_clipboard
                and "Accepted Transaction pooler shapes" in expected_bundle_clipboard
                and "aws-[region].pooler.supabase.com:6543/postgres" in expected_bundle_clipboard
                and "db.<project_ref>.supabase.co:6543/postgres" in expected_bundle_clipboard
                and "Expected port: 6543." in expected_bundle_clipboard
                and "Expected database: postgres." in expected_bundle_clipboard
                and "Pause scheduled/background getdaytrends clients" in expected_bundle_clipboard
                and "Supavisor/shared pooler circuit breaker" in expected_bundle_clipboard
                and "short lockout" in expected_bundle_clipboard
                and "## Scheduler pause commands" in expected_bundle_clipboard
                and "data\\getdaytrends.lock" in expected_bundle_clipboard
                and "Get-Process -Id" in expected_bundle_clipboard
                and "GetDayTrends_CurrentUser" in expected_bundle_clipboard
                and "schtasks /Change /TN $taskName /DISABLE" in expected_bundle_clipboard
                and "## Credential update commands" in expected_bundle_clipboard
                and "getdaytrends_update_credentials.py --input-status" in expected_bundle_clipboard
                and "Fast path" in expected_bundle_clipboard
                and "Get-Clipboard -Raw" in expected_bundle_clipboard
                and "without interactive EOF" in expected_bundle_clipboard
                and "Interactive fallback" in expected_bundle_clipboard
                and "Transaction pooler DATABASE_URL" in expected_bundle_clipboard
                and "send EOF" in expected_bundle_clipboard
                and "Ctrl+Z, then Enter in PowerShell" in expected_bundle_clipboard
                and "circuit breaker" in expected_bundle_clipboard
                and "wait at least 2 minutes" in expected_bundle_clipboard
                and SAFE_DATABASE_UPDATE_FRAGMENTS[0] in expected_bundle_clipboard
                and SAFE_DATABASE_UPDATE_FRAGMENTS[1] in expected_bundle_clipboard
                and "## Recovery checklist" in expected_bundle_clipboard
                and "Supabase dashboard Connect panel" in expected_bundle_clipboard
                and "Copy and run the scheduler pause commands" in expected_bundle_clipboard
                and "## Scheduler resume commands" in expected_bundle_clipboard
                and "schtasks /Change /TN $taskName /ENABLE" in expected_bundle_clipboard
                and "## References" in expected_bundle_clipboard
                and "Supabase database connection guide" in expected_bundle_clipboard
                and SUPABASE_REFERENCE_URL in expected_bundle_clipboard
                and "Supabase Supavisor password rotation circuit-breaker guide" in expected_bundle_clipboard
                and SUPABASE_CIRCUIT_BREAKER_REFERENCE_URL in expected_bundle_clipboard
                and "Microsoft schtasks query reference" in expected_bundle_clipboard
                and MICROSOFT_SCHTASKS_QUERY_REFERENCE_URL in expected_bundle_clipboard
                and "Microsoft schtasks change reference" in expected_bundle_clipboard
                and MICROSOFT_SCHTASKS_CHANGE_REFERENCE_URL in expected_bundle_clipboard
                and "## Verification commands" in expected_bundle_clipboard
                and "Set-Location -LiteralPath" in expected_bundle_clipboard
                and "python main.py --doctor --require-live-db" in expected_bundle_clipboard
                and "workspace-smoke-getdaytrends-operator-recheck.json" in expected_bundle_clipboard
                and "workspace-smoke-getdaytrends-launch-final.json" not in expected_bundle_clipboard
                and "postgresql://" not in expected_bundle_clipboard
                and normalized_clipboard_text == expected_bundle_clipboard
                and initial_bundle_copy_text == "Copy recovery bundle"
                and rapid_initial_text == "Copy recovery bundle"
                and rapid_after_first_click == "Copied"
                and rapid_after_second_click == "Copied"
                and rapid_final_text == "Copy recovery bundle"
                and rapid_button_state.get("copyResult") == "copied"
                and rapid_button_state.get("originalText") == "Copy recovery bundle"
                and rapid_button_state.get("priority") == "primary"
                and "operator-copy-btn-primary" in rapid_button_state.get("className", "")
                and primary_denied_ok
            )
        _record_check(checks, "operator_recovery_bundle_copy", bundle_copy_ok, bundle_copy_detail)

        connection_copy_buttons = page.locator("[aria-label='Copy connection mode facts']")
        connection_copy_button_count = connection_copy_buttons.count()
        connection_copy_detail: dict[str, Any] = {
            "copy_button_count": connection_copy_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        connection_copy_ok = connection_copy_button_count >= 1 if recovery_packet_paths else connection_copy_button_count == 0
        if connection_copy_button_count:
            first_connection_copy = connection_copy_buttons.first
            initial_connection_copy_text = first_connection_copy.inner_text(timeout=timeout_ms).strip()
            connection_text = first_connection_copy.evaluate("(button) => button.dataset.copyText || ''")
            expected_connection_clipboard = connection_text.replace("\\n", "\n")
            first_connection_copy.click()
            connection_copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy connection mode facts']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                connection_copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            button_text = first_connection_copy.inner_text(timeout=timeout_ms)
            connection_copy_detail.update(
                {
                    "connection_facts": expected_connection_clipboard,
                    "initial_button_text": initial_connection_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": connection_copy_feedback_seen,
                    "clipboard_text": clipboard_text,
                    "clipboard_matches": bool(
                        expected_connection_clipboard and normalized_clipboard_text == expected_connection_clipboard
                    ),
                }
            )
            connection_copy_ok = (
                connection_copy_ok
                and "Expected DATABASE_URL mode: Supabase Transaction pooler." in expected_connection_clipboard
                and "Accepted Transaction pooler shapes" in expected_connection_clipboard
                and "aws-[region].pooler.supabase.com:6543/postgres" in expected_connection_clipboard
                and "db.<project_ref>.supabase.co:6543/postgres" in expected_connection_clipboard
                and "Expected port: 6543." in expected_connection_clipboard
                and "Expected database: postgres." in expected_connection_clipboard
                and "pause scheduled/background getdaytrends clients" in expected_connection_clipboard
                and "Supavisor/shared pooler circuit breaker" in expected_connection_clipboard
                and "wait for the short lockout" in expected_connection_clipboard
                and "postgresql://" not in expected_connection_clipboard
                and normalized_clipboard_text == expected_connection_clipboard
                and initial_connection_copy_text == "Copy connection facts"
            )
        _record_check(checks, "operator_connection_mode_facts_copy", connection_copy_ok, connection_copy_detail)

        scheduler_pause_buttons = page.locator("[aria-label='Copy scheduler pause commands']")
        scheduler_pause_button_count = scheduler_pause_buttons.count()
        scheduler_pause_detail: dict[str, Any] = {
            "copy_button_count": scheduler_pause_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        scheduler_pause_ok = (
            scheduler_pause_button_count >= 1 if recovery_packet_paths else scheduler_pause_button_count == 0
        )
        if scheduler_pause_button_count:
            first_scheduler_pause = scheduler_pause_buttons.first
            initial_scheduler_pause_text = first_scheduler_pause.inner_text(timeout=timeout_ms).strip()
            scheduler_pause_text = first_scheduler_pause.evaluate("(button) => button.dataset.copyText || ''")
            expected_scheduler_pause_clipboard = scheduler_pause_text.replace("\\n", "\n")
            first_scheduler_pause.click()
            scheduler_pause_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy scheduler pause commands']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                scheduler_pause_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            button_text = first_scheduler_pause.inner_text(timeout=timeout_ms)
            scheduler_pause_detail.update(
                {
                    "commands": expected_scheduler_pause_clipboard,
                    "initial_button_text": initial_scheduler_pause_text,
                    "button_text": button_text,
                    "copy_feedback_seen": scheduler_pause_feedback_seen,
                    "clipboard_text": clipboard_text,
                    "clipboard_matches": bool(
                        expected_scheduler_pause_clipboard
                        and normalized_clipboard_text == expected_scheduler_pause_clipboard
                    ),
                }
            )
            scheduler_pause_ok = (
                scheduler_pause_ok
                and "Set-Location -LiteralPath" in expected_scheduler_pause_clipboard
                and "automation\\getdaytrends" in expected_scheduler_pause_clipboard
                and "data\\getdaytrends.lock" in expected_scheduler_pause_clipboard
                and "Get-Process -Id" in expected_scheduler_pause_clipboard
                and "GetDayTrends_CurrentUser" in expected_scheduler_pause_clipboard
                and "GetDayTrends_NewTask" in expected_scheduler_pause_clipboard
                and "schtasks /Query /TN" in expected_scheduler_pause_clipboard
                and "schtasks /Change /TN $taskName /DISABLE" in expected_scheduler_pause_clipboard
                and "postgresql://" not in expected_scheduler_pause_clipboard
                and normalized_clipboard_text == expected_scheduler_pause_clipboard
                and initial_scheduler_pause_text == "Copy scheduler pause commands"
            )
        _record_check(checks, "operator_scheduler_pause_commands_copy", scheduler_pause_ok, scheduler_pause_detail)

        credential_update_buttons = page.locator("[aria-label='Copy credential update commands']")
        credential_update_button_count = credential_update_buttons.count()
        credential_update_detail: dict[str, Any] = {
            "copy_button_count": credential_update_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        credential_update_ok = (
            credential_update_button_count >= 1 if recovery_packet_paths else credential_update_button_count == 0
        )
        if credential_update_button_count:
            first_credential_update = credential_update_buttons.first
            initial_credential_update_text = first_credential_update.inner_text(timeout=timeout_ms).strip()
            credential_update_text = first_credential_update.evaluate("(button) => button.dataset.copyText || ''")
            expected_credential_update_clipboard = credential_update_text.replace("\\n", "\n")
            first_credential_update.click()
            credential_update_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy credential update commands']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                credential_update_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            credential_update_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", normalized_clipboard_text, re.IGNORECASE):
                credential_update_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", normalized_clipboard_text, re.IGNORECASE):
                credential_update_secret_gaps.append("clipboard contains raw tenant user")
            button_text = first_credential_update.inner_text(timeout=timeout_ms)
            credential_update_detail.update(
                {
                    "commands": expected_credential_update_clipboard,
                    "initial_button_text": initial_credential_update_text,
                    "button_text": button_text,
                    "copy_feedback_seen": credential_update_feedback_seen,
                    "clipboard_text": clipboard_text,
                    "clipboard_matches": bool(
                        expected_credential_update_clipboard
                        and normalized_clipboard_text == expected_credential_update_clipboard
                    ),
                    "secret_gaps": credential_update_secret_gaps,
                }
            )
            credential_update_ok = (
                credential_update_ok
                and "Set-Location -LiteralPath" in expected_credential_update_clipboard
                and "automation\\getdaytrends" in expected_credential_update_clipboard
                and "Fast path" in expected_credential_update_clipboard
                and "Get-Clipboard -Raw" in expected_credential_update_clipboard
                and "without interactive EOF" in expected_credential_update_clipboard
                and "Interactive fallback" in expected_credential_update_clipboard
                and "Transaction pooler DATABASE_URL" in expected_credential_update_clipboard
                and "send EOF" in expected_credential_update_clipboard
                and "Ctrl+Z, then Enter in PowerShell" in expected_credential_update_clipboard
                and "Pause scheduled/background getdaytrends clients" in expected_credential_update_clipboard
                and "circuit breaker" in expected_credential_update_clipboard
                and "wait at least 2 minutes" in expected_credential_update_clipboard
                and SAFE_DATABASE_UPDATE_FRAGMENTS[0] in expected_credential_update_clipboard
                and SAFE_DATABASE_UPDATE_FRAGMENTS[1] in expected_credential_update_clipboard
                and "postgresql://" not in expected_credential_update_clipboard
                and not credential_update_secret_gaps
                and normalized_clipboard_text == expected_credential_update_clipboard
                and initial_credential_update_text == "Copy credential update commands"
            )
        _record_check(
            checks,
            "operator_credential_update_commands_copy",
            credential_update_ok,
            credential_update_detail,
        )

        expected_post_credential_recheck_steps: list[dict[str, str]] = []
        post_credential_recheck_packet_error = ""
        expected_post_credential_recheck_source = ""
        for recovery_packet_path in dict.fromkeys(recovery_packet_paths):
            packet_path = Path(recovery_packet_path)
            if not packet_path.is_absolute():
                packet_path = PROJECT_ROOT / packet_path
            try:
                packet_payload = json.loads(packet_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                if not post_credential_recheck_packet_error:
                    post_credential_recheck_packet_error = f"{recovery_packet_path}: {exc}"
                continue
            if not isinstance(packet_payload, dict):
                if not post_credential_recheck_packet_error:
                    post_credential_recheck_packet_error = (
                        f"{recovery_packet_path}: recovery packet is not a JSON object"
                    )
                continue
            recheck_sequence = packet_payload.get("post_credential_recheck_sequence")
            if not isinstance(recheck_sequence, list):
                if not post_credential_recheck_packet_error:
                    post_credential_recheck_packet_error = (
                        f"{recovery_packet_path}: post_credential_recheck_sequence missing or not a list"
                    )
                continue
            for item in recheck_sequence:
                if not isinstance(item, dict):
                    continue
                step = str(item.get("step") or "").strip()
                command = str(item.get("command") or "").strip()
                success_criterion = str(item.get("success_criterion") or "").strip()
                if step and command and success_criterion:
                    expected_post_credential_recheck_steps.append(
                        {
                            "step": step,
                            "command": command,
                            "success_criterion": success_criterion,
                        }
                    )
            if expected_post_credential_recheck_steps:
                expected_post_credential_recheck_source = recovery_packet_path
                post_credential_recheck_packet_error = ""
                break
            if not post_credential_recheck_packet_error:
                post_credential_recheck_packet_error = (
                    f"{recovery_packet_path}: post_credential_recheck_sequence has no valid steps"
                )

        post_credential_recheck_buttons = page.locator("[aria-label='Copy post-credential recheck sequence']")
        post_credential_recheck_button_count = post_credential_recheck_buttons.count()
        post_credential_recheck_detail: dict[str, Any] = {
            "copy_button_count": post_credential_recheck_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
            "expected_post_credential_recheck_source": expected_post_credential_recheck_source,
            "expected_post_credential_recheck_step_count": len(expected_post_credential_recheck_steps),
            "post_credential_recheck_packet_error": post_credential_recheck_packet_error,
        }
        post_credential_recheck_ok = (
            post_credential_recheck_button_count >= 1
            if recovery_packet_paths
            else post_credential_recheck_button_count == 0
        )
        if post_credential_recheck_button_count:
            first_post_credential_recheck = post_credential_recheck_buttons.first
            initial_post_credential_recheck_text = first_post_credential_recheck.inner_text(timeout=timeout_ms).strip()
            post_credential_recheck_text = first_post_credential_recheck.evaluate(
                "(button) => button.dataset.copyText || ''"
            )
            expected_post_credential_recheck_clipboard = post_credential_recheck_text.replace("\\n", "\n")
            first_post_credential_recheck.click()
            post_credential_recheck_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy post-credential recheck sequence']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                post_credential_recheck_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            button_text = first_post_credential_recheck.inner_text(timeout=timeout_ms)
            post_credential_recheck_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", normalized_clipboard_text, re.IGNORECASE):
                post_credential_recheck_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", normalized_clipboard_text):
                post_credential_recheck_secret_gaps.append("clipboard contains raw OpenAI-style key")
            if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", normalized_clipboard_text):
                post_credential_recheck_secret_gaps.append("clipboard contains raw Google API-style key")
            missing_post_credential_recheck_steps = [
                item
                for item in expected_post_credential_recheck_steps
                if item["step"] not in expected_post_credential_recheck_clipboard
                or item["command"] not in expected_post_credential_recheck_clipboard
                or item["success_criterion"] not in expected_post_credential_recheck_clipboard
            ]
            post_credential_recheck_sequence_section = expected_post_credential_recheck_clipboard.split(
                "Post-credential evidence artifacts:",
                1,
            )[0]
            observed_post_credential_recheck_step_count = len(
                re.findall(r"(?m)^\d+\.\s+", post_credential_recheck_sequence_section)
            )
            post_credential_recheck_step_count_matches = (
                observed_post_credential_recheck_step_count == len(expected_post_credential_recheck_steps)
            )
            post_credential_recheck_detail.update(
                {
                    "recheck_text": expected_post_credential_recheck_clipboard[:1600],
                    "initial_button_text": initial_post_credential_recheck_text,
                    "button_text": button_text,
                    "copy_feedback_seen": post_credential_recheck_feedback_seen,
                    "clipboard_text": clipboard_text[:1600],
                    "clipboard_matches": bool(
                        expected_post_credential_recheck_clipboard
                        and normalized_clipboard_text == expected_post_credential_recheck_clipboard
                    ),
                    "secret_gaps": post_credential_recheck_secret_gaps,
                    "observed_post_credential_recheck_step_count": observed_post_credential_recheck_step_count,
                    "post_credential_recheck_step_count_matches": post_credential_recheck_step_count_matches,
                    "missing_post_credential_recheck_steps": missing_post_credential_recheck_steps,
                }
            )
            post_credential_recheck_ok = (
                post_credential_recheck_ok
                and bool(expected_post_credential_recheck_steps)
                and not post_credential_recheck_packet_error
                and post_credential_recheck_step_count_matches
                and not missing_post_credential_recheck_steps
                and "Post-credential recheck sequence:" in expected_post_credential_recheck_clipboard
                and "1. live_db_doctor | python main.py --doctor --require-live-db" in expected_post_credential_recheck_clipboard
                and "2. cli_smoke | python scripts\\smoke_cli.py --include-dry-run" in expected_post_credential_recheck_clipboard
                and "3. strict_readiness | python scripts\\readiness_check.py" in expected_post_credential_recheck_clipboard
                and "--fail-on-runtime-fallback --require-live-db" in expected_post_credential_recheck_clipboard
                and "4. canonical_workspace_smoke | python ..\\..\\ops\\scripts\\run_workspace_smoke.py --scope getdaytrends" in expected_post_credential_recheck_clipboard
                and "workspace-smoke-getdaytrends-operator-recheck.json" in expected_post_credential_recheck_clipboard
                and "Live DB doctor reports OK" in expected_post_credential_recheck_clipboard
                and "runtime_fallback_count 0" in expected_post_credential_recheck_clipboard
                and "Strict readiness reports status pass" in expected_post_credential_recheck_clipboard
                and "Canonical getdaytrends workspace smoke reports all configured checks PASS" in expected_post_credential_recheck_clipboard
                and "Post-credential evidence artifacts:" in expected_post_credential_recheck_clipboard
                and "operator console output" in expected_post_credential_recheck_clipboard
                and "logs\\smoke\\cli_smoke_latest.json" in expected_post_credential_recheck_clipboard
                and "logs\\readiness\\readiness_latest.json" in expected_post_credential_recheck_clipboard
                and "status=pass and failed=0" in expected_post_credential_recheck_clipboard
                and "all configured getdaytrends checks pass" in expected_post_credential_recheck_clipboard
                and "postgresql://" not in expected_post_credential_recheck_clipboard
                and not post_credential_recheck_secret_gaps
                and normalized_clipboard_text == expected_post_credential_recheck_clipboard
                and initial_post_credential_recheck_text == "Copy post-credential recheck"
            )
        _record_check(
            checks,
            "operator_post_credential_recheck_copy",
            post_credential_recheck_ok,
            post_credential_recheck_detail,
        )

        expected_final_proof_items: list[dict[str, str]] = []
        final_proof_packet_error = ""
        expected_final_proof_source = ""
        for recovery_packet_path in dict.fromkeys(recovery_packet_paths):
            packet_path = Path(recovery_packet_path)
            if not packet_path.is_absolute():
                packet_path = PROJECT_ROOT / packet_path
            try:
                packet_payload = json.loads(packet_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                if not final_proof_packet_error:
                    final_proof_packet_error = f"{recovery_packet_path}: {exc}"
                continue
            if not isinstance(packet_payload, dict):
                if not final_proof_packet_error:
                    final_proof_packet_error = f"{recovery_packet_path}: recovery packet is not a JSON object"
                continue
            proof_bundle = packet_payload.get("operator_final_proof_bundle")
            if not isinstance(proof_bundle, list):
                if not final_proof_packet_error:
                    final_proof_packet_error = (
                        f"{recovery_packet_path}: operator_final_proof_bundle missing or not a list"
                    )
                continue
            for item in proof_bundle:
                if not isinstance(item, dict):
                    continue
                artifact = str(item.get("artifact") or "").strip()
                success_signal = str(item.get("success_signal") or "").strip()
                if artifact and success_signal:
                    expected_final_proof_items.append(
                        {
                            "artifact": artifact,
                            "success_signal": success_signal,
                        }
                    )
            if expected_final_proof_items:
                expected_final_proof_source = recovery_packet_path
                final_proof_packet_error = ""
                break
            if not final_proof_packet_error:
                final_proof_packet_error = f"{recovery_packet_path}: operator_final_proof_bundle has no valid items"

        final_proof_buttons = page.locator("[aria-label='Copy operator final proof bundle']")
        final_proof_button_count = final_proof_buttons.count()
        final_proof_detail: dict[str, Any] = {
            "copy_button_count": final_proof_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
            "expected_final_proof_source": expected_final_proof_source,
            "expected_final_proof_item_count": len(expected_final_proof_items),
            "final_proof_packet_error": final_proof_packet_error,
        }
        final_proof_ok = final_proof_button_count >= 1 if recovery_packet_paths else final_proof_button_count == 0
        if final_proof_button_count:
            first_final_proof = final_proof_buttons.first
            initial_final_proof_text = first_final_proof.inner_text(timeout=timeout_ms).strip()
            final_proof_text = first_final_proof.evaluate("(button) => button.dataset.copyText || ''")
            expected_final_proof_clipboard = final_proof_text.replace("\\n", "\n")
            first_final_proof.click()
            final_proof_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy operator final proof bundle']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                final_proof_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            button_text = first_final_proof.inner_text(timeout=timeout_ms)
            final_proof_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", normalized_clipboard_text, re.IGNORECASE):
                final_proof_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", normalized_clipboard_text):
                final_proof_secret_gaps.append("clipboard contains raw OpenAI-style key")
            if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", normalized_clipboard_text):
                final_proof_secret_gaps.append("clipboard contains raw Google API-style key")
            missing_final_proof_items = [
                item
                for item in expected_final_proof_items
                if item["artifact"] not in expected_final_proof_clipboard
                or item["success_signal"] not in expected_final_proof_clipboard
            ]
            observed_final_proof_item_count = len(
                re.findall(r"(?m)^\d+\.\s+", expected_final_proof_clipboard)
            )
            final_proof_item_count_matches = observed_final_proof_item_count == len(expected_final_proof_items)
            final_proof_detail.update(
                {
                    "final_proof": expected_final_proof_clipboard[:1600],
                    "initial_button_text": initial_final_proof_text,
                    "button_text": button_text,
                    "copy_feedback_seen": final_proof_feedback_seen,
                    "clipboard_text": clipboard_text[:1600],
                    "clipboard_matches": bool(
                        expected_final_proof_clipboard
                        and normalized_clipboard_text == expected_final_proof_clipboard
                    ),
                    "secret_gaps": final_proof_secret_gaps,
                    "observed_final_proof_item_count": observed_final_proof_item_count,
                    "final_proof_item_count_matches": final_proof_item_count_matches,
                    "missing_final_proof_items": missing_final_proof_items,
                }
            )
            final_proof_ok = (
                final_proof_ok
                and bool(expected_final_proof_items)
                and not final_proof_packet_error
                and final_proof_item_count_matches
                and not missing_final_proof_items
                and "Operator final proof bundle:" in expected_final_proof_clipboard
                and "1. logs\\readiness\\readiness_latest.json" in expected_final_proof_clipboard
                and "status=pass, failed=0, and cli_smoke_report/live_db_doctor both OK" in expected_final_proof_clipboard
                and "2. logs\\smoke\\cli_smoke_latest.json" in expected_final_proof_clipboard
                and "runtime_fallback_count=0 and provider_auth_failure_count=0" in expected_final_proof_clipboard
                and "3. logs\\smoke\\dashboard_browser_latest.json" in expected_final_proof_clipboard
                and "dashboard browser smoke reports pass" in expected_final_proof_clipboard
                and "4. logs\\smoke\\dashboard_browser_tap_source_evidence.json" in expected_final_proof_clipboard
                and "TAP fixture browser smoke reports all required TAP checks pass" in expected_final_proof_clipboard
                and "5. logs\\hygiene\\text_hygiene_latest.json" in expected_final_proof_clipboard
                and "status=pass with findings=0 and read_errors=0" in expected_final_proof_clipboard
                and "6. ..\\..\\var\\getdaytrends-launch-secret-scan-final-post-credential.json" in expected_final_proof_clipboard
                and "status=valid, findings=0, missing=0, and current artifacts included" in expected_final_proof_clipboard
                and "7. ..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json" in expected_final_proof_clipboard
                and "all configured getdaytrends workspace smoke checks pass" in expected_final_proof_clipboard
                and "postgresql://" not in expected_final_proof_clipboard
                and not final_proof_secret_gaps
                and normalized_clipboard_text == expected_final_proof_clipboard
                and initial_final_proof_text == "Copy final proof bundle"
            )
        _record_check(checks, "operator_final_proof_bundle_copy", final_proof_ok, final_proof_detail)

        env_copy_buttons = page.locator("[aria-label='Copy recovery env template']")
        env_copy_button_count = env_copy_buttons.count()
        env_copy_detail: dict[str, Any] = {
            "copy_button_count": env_copy_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        env_copy_ok = env_copy_button_count >= 1 if recovery_packet_paths else env_copy_button_count == 0
        if env_copy_button_count:
            first_env_copy = env_copy_buttons.first
            initial_env_copy_text = first_env_copy.inner_text(timeout=timeout_ms).strip()
            env_text = first_env_copy.evaluate("(button) => button.dataset.copyText || ''")
            expected_env_clipboard = env_text.replace("\\n", "\n")
            first_env_copy.click()
            env_copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy recovery env template']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                env_copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            button_text = first_env_copy.inner_text(timeout=timeout_ms)
            env_copy_detail.update(
                {
                    "env_template": expected_env_clipboard[:1200],
                    "initial_button_text": initial_env_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": env_copy_feedback_seen,
                    "clipboard_text": clipboard_text[:1200],
                    "clipboard_matches": bool(expected_env_clipboard and normalized_clipboard_text == expected_env_clipboard),
                }
            )
            env_copy_ok = (
                env_copy_ok
                and "SUPABASE_URL=https://<project_ref>.supabase.co" in expected_env_clipboard
                and "DATABASE_URL=<transaction_pooler_uri_from_same_project>" in expected_env_clipboard
                and "Transaction pooler URI" in expected_env_clipboard
                and "port 6543" in expected_env_clipboard
                and "postgresql://" not in expected_env_clipboard
                and normalized_clipboard_text == expected_env_clipboard
                and initial_env_copy_text == "Copy recovery env template"
            )
        _record_check(checks, "operator_recovery_env_template_copy", env_copy_ok, env_copy_detail)

        checklist_copy_buttons = page.locator("[aria-label='Copy recovery checklist']")
        checklist_copy_button_count = checklist_copy_buttons.count()
        checklist_copy_detail: dict[str, Any] = {
            "copy_button_count": checklist_copy_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        checklist_copy_ok = checklist_copy_button_count >= 1 if recovery_packet_paths else checklist_copy_button_count == 0
        if checklist_copy_button_count:
            first_checklist_copy = checklist_copy_buttons.first
            initial_checklist_copy_text = first_checklist_copy.inner_text(timeout=timeout_ms).strip()
            checklist_text = first_checklist_copy.evaluate("(button) => button.dataset.copyText || ''")
            expected_checklist_clipboard = checklist_text.replace("\\n", "\n")
            first_checklist_copy.click()
            checklist_copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy recovery checklist']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                checklist_copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            button_text = first_checklist_copy.inner_text(timeout=timeout_ms)
            checklist_copy_detail.update(
                {
                    "checklist": expected_checklist_clipboard[:1200],
                    "initial_button_text": initial_checklist_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": checklist_copy_feedback_seen,
                    "clipboard_text": clipboard_text[:1200],
                    "clipboard_matches": bool(
                        expected_checklist_clipboard and normalized_clipboard_text == expected_checklist_clipboard
                    ),
                }
            )
            checklist_copy_ok = (
                checklist_copy_ok
                and "Required env:" in expected_checklist_clipboard
                and "DATABASE_URL" in expected_checklist_clipboard
                and "SUPABASE_URL" in expected_checklist_clipboard
                and "Supabase dashboard Connect panel" in expected_checklist_clipboard
                and "Transaction pooler" in expected_checklist_clipboard
                and "Pause scheduled/background getdaytrends clients" in expected_checklist_clipboard
                and "circuit breaker" in expected_checklist_clipboard
                and "wait at least 2 minutes" in expected_checklist_clipboard
                and SAFE_DATABASE_UPDATE_FRAGMENTS[0] in expected_checklist_clipboard
                and SAFE_DATABASE_UPDATE_FRAGMENTS[1] in expected_checklist_clipboard
                and "python main.py --doctor --require-live-db" in expected_checklist_clipboard
                and normalized_clipboard_text == expected_checklist_clipboard
                and initial_checklist_copy_text == "Copy recovery checklist"
            )
        _record_check(checks, "operator_recovery_checklist_copy", checklist_copy_ok, checklist_copy_detail)

        scheduler_resume_buttons = page.locator("[aria-label='Copy scheduler resume commands']")
        scheduler_resume_button_count = scheduler_resume_buttons.count()
        scheduler_resume_detail: dict[str, Any] = {
            "copy_button_count": scheduler_resume_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
        }
        scheduler_resume_ok = (
            scheduler_resume_button_count >= 1 if recovery_packet_paths else scheduler_resume_button_count == 0
        )
        if scheduler_resume_button_count:
            first_scheduler_resume = scheduler_resume_buttons.first
            initial_scheduler_resume_text = first_scheduler_resume.inner_text(timeout=timeout_ms).strip()
            scheduler_resume_text = first_scheduler_resume.evaluate("(button) => button.dataset.copyText || ''")
            expected_scheduler_resume_clipboard = scheduler_resume_text.replace("\\n", "\n")
            first_scheduler_resume.click()
            scheduler_resume_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy scheduler resume commands']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                scheduler_resume_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            button_text = first_scheduler_resume.inner_text(timeout=timeout_ms)
            scheduler_resume_detail.update(
                {
                    "commands": expected_scheduler_resume_clipboard,
                    "initial_button_text": initial_scheduler_resume_text,
                    "button_text": button_text,
                    "copy_feedback_seen": scheduler_resume_feedback_seen,
                    "clipboard_text": clipboard_text,
                    "clipboard_matches": bool(
                        expected_scheduler_resume_clipboard
                        and normalized_clipboard_text == expected_scheduler_resume_clipboard
                    ),
                }
            )
            scheduler_resume_ok = (
                scheduler_resume_ok
                and "Set-Location -LiteralPath" in expected_scheduler_resume_clipboard
                and "automation\\getdaytrends" in expected_scheduler_resume_clipboard
                and "GetDayTrends_CurrentUser" in expected_scheduler_resume_clipboard
                and "GetDayTrends_NewTask" in expected_scheduler_resume_clipboard
                and "schtasks /Query /TN" in expected_scheduler_resume_clipboard
                and "schtasks /Change /TN $taskName /ENABLE" in expected_scheduler_resume_clipboard
                and "live DB doctor" in expected_scheduler_resume_clipboard
                and "workspace smoke pass" in expected_scheduler_resume_clipboard
                and "postgresql://" not in expected_scheduler_resume_clipboard
                and normalized_clipboard_text == expected_scheduler_resume_clipboard
                and initial_scheduler_resume_text == "Copy scheduler resume commands"
            )
        _record_check(checks, "operator_scheduler_resume_commands_copy", scheduler_resume_ok, scheduler_resume_detail)

        verify_copy_buttons = page.locator("[aria-label='Copy recovery verification commands']")
        verify_copy_button_count = verify_copy_buttons.count()
        verify_copy_detail: dict[str, Any] = {
            "copy_button_count": verify_copy_button_count,
            "recovery_packet_count": len(recovery_packet_paths),
            "expected_recovery_verify_source": expected_recovery_verify_source,
            "expected_recovery_verify_command_count": len(expected_recovery_verify_commands),
            "recovery_verify_packet_error": recovery_verify_packet_error,
        }
        verify_copy_ok = verify_copy_button_count >= 1 if recovery_packet_paths else verify_copy_button_count == 0
        if verify_copy_button_count:
            first_verify_copy = verify_copy_buttons.first
            initial_verify_copy_text = first_verify_copy.inner_text(timeout=timeout_ms).strip()
            verify_text = first_verify_copy.evaluate("(button) => button.dataset.copyText || ''")
            expected_verify_clipboard = verify_text.replace("\\n", "\n")
            first_verify_copy.click()
            verify_copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy recovery verification commands']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                verify_copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            normalized_clipboard_text = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
            button_text = first_verify_copy.inner_text(timeout=timeout_ms)
            verify_first_line = normalized_clipboard_text.splitlines()[0].strip() if normalized_clipboard_text else ""
            verify_starts_in_workdir = (
                verify_first_line.startswith("Set-Location -LiteralPath")
                and str(PROJECT_ROOT) in verify_first_line
            )
            recovery_preview_text = first_verify_copy.evaluate(
                "(button) => button.closest('.operator-action')?.querySelector('.operator-packet-preview')?.innerText || ''"
            )
            missing_recovery_verify_commands = [
                command for command in expected_recovery_verify_commands if command not in expected_verify_clipboard
            ]
            verify_copy_detail.update(
                {
                    "commands": expected_verify_clipboard[:1200],
                    "initial_button_text": initial_verify_copy_text,
                    "first_line": verify_first_line,
                    "button_text": button_text,
                    "copy_feedback_seen": verify_copy_feedback_seen,
                    "clipboard_text": clipboard_text[:1200],
                    "clipboard_matches": bool(expected_verify_clipboard and normalized_clipboard_text == expected_verify_clipboard),
                    "starts_in_workdir": verify_starts_in_workdir,
                    "preview_has_verification_cwd": "Verification cwd:" in recovery_preview_text,
                    "missing_recovery_verify_commands": missing_recovery_verify_commands,
                }
            )
            verify_copy_ok = (
                verify_copy_ok
                and bool(expected_recovery_verify_commands)
                and not recovery_verify_packet_error
                and not missing_recovery_verify_commands
                and "Set-Location -LiteralPath" in expected_verify_clipboard
                and verify_starts_in_workdir
                and "Verification cwd:" in recovery_preview_text
                and str(PROJECT_ROOT) in recovery_preview_text
                and "python main.py --doctor --require-live-db" in expected_verify_clipboard
                and "--tap-source-fixture" in expected_verify_clipboard
                and "readiness_check.py" in expected_verify_clipboard
                and "--fail-on-runtime-fallback --require-live-db" in expected_verify_clipboard
                and "run_workspace_smoke.py --scope getdaytrends" in expected_verify_clipboard
                and "workspace-smoke-getdaytrends-operator-recheck.json" in expected_verify_clipboard
                and "workspace-smoke-getdaytrends-launch-final.json" not in expected_verify_clipboard
                and normalized_clipboard_text == expected_verify_clipboard
                and initial_verify_copy_text == "Copy recovery verification commands"
            )
        _record_check(checks, "operator_recovery_verify_copy", verify_copy_ok, verify_copy_detail)

        provider_issue = next((issue for issue in operator_issues if str(issue.get("name", "")) == "provider_auth_report"), None)
        provider_packet_path = str(provider_issue.get("recovery_packet", "")).strip() if provider_issue else ""
        provider_action_index = -1
        if provider_packet_path:
            provider_action_index = int(
                page.evaluate(
                    """(path) => Array.from(document.querySelectorAll('#operator-blockers .operator-action')).findIndex(
                        action => (action.querySelector('code')?.innerText || '').trim() === path
                    )""",
                    provider_packet_path,
                )
            )
        provider_recovery_expected_mode = "provider_packet_required" if provider_issue else "clean_no_provider_packet"
        provider_clean_no_packet_ok = provider_issue is None and not provider_packet_path

        provider_base_detail: dict[str, Any] = {
            "provider_auth_recovery_expected_mode": provider_recovery_expected_mode,
            "provider_auth_report_present": True if provider_issue else None,
            "provider_clean_no_packet_ok": provider_clean_no_packet_ok if not provider_issue else None,
            "provider_packet_required": True if provider_issue else None,
            "provider_packet_missing": bool(provider_issue and not provider_packet_path) if provider_issue else None,
            "provider_packet_path": provider_packet_path,
            "provider_action_found": provider_action_index >= 0 if provider_packet_path else None,
        }
        if not provider_issue:
            _record_check(checks, "operator_provider_recovery_packet_view", True, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_bundle_row_copy", True, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_verify_row_copy", True, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_success_row_copy", True, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_next_action_copy", True, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_bundle_copy", True, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_env_template_copy", True, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_checklist_copy", True, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_verify_copy", True, provider_base_detail)
        elif not provider_packet_path or provider_action_index < 0:
            _record_check(checks, "operator_provider_recovery_packet_view", False, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_bundle_row_copy", False, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_verify_row_copy", False, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_success_row_copy", False, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_next_action_copy", False, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_bundle_copy", False, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_env_template_copy", False, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_checklist_copy", False, provider_base_detail)
            _record_check(checks, "operator_provider_recovery_verify_copy", False, provider_base_detail)
        else:
            provider_action = page.locator("#operator-blockers .operator-action").nth(provider_action_index)
            provider_row_bundle_buttons = provider_action.locator("[aria-label='Copy recovery bundle']")
            provider_row_bundle_button_count = provider_row_bundle_buttons.count()
            provider_row_bundle_detail: dict[str, Any] = {
                **provider_base_detail,
                "button_count": provider_row_bundle_button_count,
            }
            provider_row_bundle_text = ""
            if provider_row_bundle_button_count:
                provider_row_bundle_button = provider_row_bundle_buttons.first
                provider_row_bundle_initial_text = provider_row_bundle_button.inner_text(timeout=timeout_ms).strip()
                provider_row_bundle_button.click()
                provider_row_bundle_feedback_seen = False
                try:
                    page.wait_for_function(
                        """(path) => {
                            const action = Array.from(document.querySelectorAll('#operator-blockers .operator-action')).find(
                                item => (item.querySelector('code')?.innerText || '').trim() === path
                            );
                            return (action?.querySelector("[aria-label='Copy recovery bundle']")?.innerText || '').trim() === 'Copied';
                        }""",
                        arg=provider_packet_path,
                        timeout=timeout_ms,
                    )
                    provider_row_bundle_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                provider_row_bundle_clipboard = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                provider_row_bundle_text = provider_row_bundle_clipboard.replace("\r\n", "\n").replace("\r", "\n")
                provider_row_bundle_gaps = _provider_recovery_bundle_gaps(provider_row_bundle_text)
                provider_row_bundle_detail.update(
                    {
                        "initial_button_text": provider_row_bundle_initial_text,
                        "button_text": provider_row_bundle_button.inner_text(timeout=timeout_ms),
                        "copy_feedback_seen": provider_row_bundle_feedback_seen,
                        "clipboard_text": provider_row_bundle_clipboard[:1600],
                        "bundle_gaps": provider_row_bundle_gaps,
                    }
                )
            else:
                provider_row_bundle_gaps = ["missing provider row recovery bundle copy button"]
            _record_check(
                checks,
                "operator_provider_recovery_bundle_row_copy",
                bool(provider_row_bundle_text)
                and not provider_row_bundle_gaps
                and "Set-Location -LiteralPath" in provider_row_bundle_text
                and "python scripts\\smoke_cli.py --include-dry-run" in provider_row_bundle_text
                and "run_workspace_smoke.py --scope getdaytrends" in provider_row_bundle_text
                and provider_row_bundle_detail.get("initial_button_text") == "Copy recovery bundle",
                provider_row_bundle_detail,
            )

            provider_row_verify_buttons = provider_action.locator("[aria-label='Copy recovery verification bundle']")
            provider_row_verify_button_count = provider_row_verify_buttons.count()
            provider_row_verify_detail: dict[str, Any] = {
                **provider_base_detail,
                "button_count": provider_row_verify_button_count,
            }
            provider_row_verify_text = ""
            if provider_row_verify_button_count:
                provider_row_verify_button = provider_row_verify_buttons.first
                initial_provider_row_verify_button_text = provider_row_verify_button.inner_text(
                    timeout=timeout_ms
                ).strip()
                provider_row_verify_button.click()
                provider_row_verify_feedback_seen = False
                try:
                    page.wait_for_function(
                        """(path) => {
                            const action = Array.from(document.querySelectorAll('#operator-blockers .operator-action')).find(
                                item => (item.querySelector('code')?.innerText || '').trim() === path
                            );
                            return (action?.querySelector("[aria-label='Copy recovery verification bundle']")?.innerText || '').trim() === 'Copied';
                        }""",
                        arg=provider_packet_path,
                        timeout=timeout_ms,
                    )
                    provider_row_verify_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                provider_row_verify_clipboard = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                provider_row_verify_text = provider_row_verify_clipboard.replace("\r\n", "\n").replace("\r", "\n")
                provider_row_verify_gaps = _provider_recovery_verify_gaps(provider_row_verify_text)
                provider_row_verify_first_line = (
                    provider_row_verify_text.splitlines()[0].strip() if provider_row_verify_text else ""
                )
                provider_row_verify_starts_in_workdir = (
                    provider_row_verify_first_line.startswith("Set-Location -LiteralPath")
                    and str(PROJECT_ROOT) in provider_row_verify_first_line
                )
                provider_row_verify_detail.update(
                    {
                        "initial_button_text": initial_provider_row_verify_button_text,
                        "button_text": provider_row_verify_button.inner_text(timeout=timeout_ms),
                        "copy_feedback_seen": provider_row_verify_feedback_seen,
                        "clipboard_text": provider_row_verify_clipboard[:1200],
                        "first_line": provider_row_verify_first_line,
                        "starts_in_workdir": provider_row_verify_starts_in_workdir,
                        "verify_gaps": provider_row_verify_gaps,
                    }
                )
            else:
                provider_row_verify_gaps = ["missing provider row recovery verification copy button"]
                provider_row_verify_starts_in_workdir = False
            _record_check(
                checks,
                "operator_provider_recovery_verify_row_copy",
                bool(provider_row_verify_text)
                and not provider_row_verify_gaps
                and provider_row_verify_starts_in_workdir
                and provider_row_verify_detail.get("initial_button_text") == "Copy recovery verification bundle",
                provider_row_verify_detail,
            )

            provider_row_success_buttons = provider_action.locator("[aria-label='Copy launch success criteria']")
            provider_row_success_button_count = provider_row_success_buttons.count()
            provider_row_success_detail: dict[str, Any] = {
                **provider_base_detail,
                "button_count": provider_row_success_button_count,
            }
            provider_row_success_text = ""
            if provider_row_success_button_count:
                provider_row_success_button = provider_row_success_buttons.first
                initial_provider_row_success_button_text = provider_row_success_button.inner_text(
                    timeout=timeout_ms
                ).strip()
                provider_row_success_button.click()
                provider_row_success_feedback_seen = False
                try:
                    page.wait_for_function(
                        """(path) => {
                            const action = Array.from(document.querySelectorAll('#operator-blockers .operator-action')).find(
                                item => (item.querySelector('code')?.innerText || '').trim() === path
                            );
                            return (action?.querySelector("[aria-label='Copy launch success criteria']")?.innerText || '').trim() === 'Copied';
                        }""",
                        arg=provider_packet_path,
                        timeout=timeout_ms,
                    )
                    provider_row_success_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                provider_row_success_clipboard = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                provider_row_success_text = provider_row_success_clipboard.replace("\r\n", "\n").replace("\r", "\n")
                provider_row_success_gaps = _fragment_gaps(
                    provider_row_success_text,
                    (
                        "Launch success criteria:",
                        "provider_auth_failure_count 0",
                        "without leaked-key, invalid-key, permission-denied, or authentication failure output",
                        "Strict readiness reports status pass",
                        "Canonical getdaytrends workspace smoke reports all configured checks PASS",
                    ),
                    "provider success",
                )
                if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b|\bAIza[0-9A-Za-z_-]{16,}\b", provider_row_success_text):
                    provider_row_success_gaps.append("provider success criteria contains secret-shaped key")
                provider_row_success_detail.update(
                    {
                        "initial_button_text": initial_provider_row_success_button_text,
                        "button_text": provider_row_success_button.inner_text(timeout=timeout_ms),
                        "copy_feedback_seen": provider_row_success_feedback_seen,
                        "clipboard_text": provider_row_success_clipboard[:1200],
                        "success_gaps": provider_row_success_gaps,
                    }
                )
            else:
                provider_row_success_gaps = ["missing provider row recovery success criteria copy button"]
            _record_check(
                checks,
                "operator_provider_recovery_success_row_copy",
                bool(provider_row_success_text)
                and not provider_row_success_gaps
                and "##" not in provider_row_success_text
                and provider_row_success_detail.get("initial_button_text") == "Copy launch criteria",
                provider_row_success_detail,
            )

            provider_view_state = provider_action.evaluate(
                """action => {
                    const button = action.querySelector("[aria-label='View recovery packet']");
                    const preview = action.querySelector('.operator-packet-preview');
                    if (!button) return { button_found: false };
                    button.scrollIntoView({ block: 'center', inline: 'nearest' });
                    const before = {
                        button_found: true,
                        text: (button.innerText || '').trim(),
                        label: button.getAttribute('aria-label') || '',
                        expanded: button.getAttribute('aria-expanded') || '',
                        busy: button.getAttribute('aria-busy') || '',
                        preview_busy: preview?.getAttribute('aria-busy') || '',
                    };
                    button.click();
                    return before;
                }"""
            )
            try:
                page.wait_for_function(
                    """(path) => {
                        const action = Array.from(document.querySelectorAll('#operator-blockers .operator-action')).find(
                            item => (item.querySelector('code')?.innerText || '').trim() === path
                        );
                        return (action?.querySelector('.operator-packet-preview')?.innerText || '').includes('Packet status:');
                    }""",
                    arg=provider_packet_path,
                    timeout=timeout_ms,
                )
            except PlaywrightTimeoutError:
                pass
            provider_preview_text = provider_action.locator(".operator-packet-preview").first.inner_text(timeout=timeout_ms)
            provider_reference_links = provider_action.evaluate(
                """action => Array.from(action.querySelectorAll('.operator-packet-preview .operator-reference-link')).map(link => ({
                    text: (link.textContent || '').trim(),
                    href: link.href || '',
                    target: link.getAttribute('target') || '',
                    rel: link.getAttribute('rel') || '',
                }))"""
            )
            provider_preview_gaps = _provider_recovery_preview_gaps(provider_preview_text)
            provider_view_detail = {
                **provider_base_detail,
                "view_state": provider_view_state,
                "preview_text": provider_preview_text[:900],
                "reference_links": provider_reference_links,
                "preview_gaps": provider_preview_gaps,
            }
            _record_check(
                checks,
                "operator_provider_recovery_packet_view",
                not provider_preview_gaps
                and _reference_link_present(
                    provider_reference_links,
                    "OpenAI API key production guidance",
                    OPENAI_REFERENCE_URL,
                )
                and _reference_link_present(
                    provider_reference_links,
                    "Google AI Gemini API key guide",
                    GOOGLE_AI_REFERENCE_URL,
                ),
                provider_view_detail,
            )

            def _copy_provider_packet_control(label: str) -> tuple[str, str, dict[str, Any]]:
                detail: dict[str, Any] = {
                    **provider_base_detail,
                    "button_label": label,
                }
                buttons = provider_action.locator(f"[aria-label='{label}']")
                button_count = buttons.count()
                detail["button_count"] = button_count
                if button_count == 0:
                    return "", "", detail
                button = buttons.first
                expected_visible_text = {
                    "Copy recovery next action": "Copy recovery next action",
                    "Copy complete recovery bundle": "Copy recovery bundle",
                    "Copy recovery env template": "Copy recovery env template",
                    "Copy recovery checklist": "Copy recovery checklist",
                    "Copy recovery verification commands": "Copy recovery verification commands",
                }.get(label, label)
                initial_button_text = button.inner_text(timeout=timeout_ms).strip()
                expected_text = button.evaluate("(button) => button.dataset.copyText || ''").replace("\\n", "\n")
                button.click()
                copy_feedback_seen = False
                try:
                    page.wait_for_function(
                        """({path, label}) => {
                            const action = Array.from(document.querySelectorAll('#operator-blockers .operator-action')).find(
                                item => (item.querySelector('code')?.innerText || '').trim() === path
                            );
                            return (action?.querySelector(`[aria-label="${label}"]`)?.innerText || '').trim() === 'Copied';
                        }""",
                        arg={"path": provider_packet_path, "label": label},
                        timeout=timeout_ms,
                    )
                    copy_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                clipboard_text = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                normalized_clipboard = clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
                detail.update(
                    {
                        "initial_button_text": initial_button_text,
                        "expected_visible_text": expected_visible_text,
                        "button_text": button.inner_text(timeout=timeout_ms),
                        "copy_feedback_seen": copy_feedback_seen,
                        "clipboard_matches": bool(expected_text and normalized_clipboard == expected_text),
                        "clipboard_text": clipboard_text[:1200],
                    }
                )
                return expected_text, normalized_clipboard, detail

            provider_next_action_text, provider_next_action_clipboard, provider_next_action_detail = (
                _copy_provider_packet_control("Copy recovery next action")
            )
            provider_next_action_gaps = _provider_recovery_next_action_gaps(provider_next_action_text)
            provider_next_action_detail.update(
                {
                    "next_action": provider_next_action_text[:700],
                    "next_action_gaps": provider_next_action_gaps,
                }
            )
            _record_check(
                checks,
                "operator_provider_recovery_next_action_copy",
                bool(provider_next_action_text)
                and not provider_next_action_gaps
                and provider_next_action_clipboard == provider_next_action_text
                and provider_next_action_detail.get("initial_button_text") == "Copy recovery next action",
                provider_next_action_detail,
            )

            provider_bundle_text, provider_bundle_clipboard, provider_bundle_detail = _copy_provider_packet_control(
                "Copy complete recovery bundle"
            )
            provider_bundle_gaps = _provider_recovery_bundle_gaps(provider_bundle_text)
            provider_bundle_detail.update(
                {
                    "bundle": provider_bundle_text[:1600],
                    "bundle_gaps": provider_bundle_gaps,
                }
            )
            _record_check(
                checks,
                "operator_provider_recovery_bundle_copy",
                bool(provider_bundle_text)
                and not provider_bundle_gaps
                and provider_bundle_clipboard == provider_bundle_text
                and provider_bundle_detail.get("initial_button_text") == "Copy recovery bundle",
                provider_bundle_detail,
            )

            provider_env_text, provider_env_clipboard, provider_env_detail = _copy_provider_packet_control(
                "Copy recovery env template"
            )
            provider_env_gaps = _provider_recovery_env_gaps(provider_env_text)
            provider_env_detail.update(
                {
                    "env_template": provider_env_text[:1200],
                    "env_gaps": provider_env_gaps,
                }
            )
            _record_check(
                checks,
                "operator_provider_recovery_env_template_copy",
                bool(provider_env_text)
                and not provider_env_gaps
                and provider_env_clipboard == provider_env_text
                and provider_env_detail.get("initial_button_text") == "Copy recovery env template",
                provider_env_detail,
            )

            provider_checklist_text, provider_checklist_clipboard, provider_checklist_detail = (
                _copy_provider_packet_control("Copy recovery checklist")
            )
            provider_checklist_gaps = _provider_recovery_checklist_gaps(provider_checklist_text)
            provider_checklist_detail.update(
                {
                    "checklist": provider_checklist_text[:1200],
                    "checklist_gaps": provider_checklist_gaps,
                }
            )
            _record_check(
                checks,
                "operator_provider_recovery_checklist_copy",
                bool(provider_checklist_text)
                and not provider_checklist_gaps
                and provider_checklist_clipboard == provider_checklist_text
                and provider_checklist_detail.get("initial_button_text") == "Copy recovery checklist",
                provider_checklist_detail,
            )

            provider_verify_text, provider_verify_clipboard, provider_verify_detail = _copy_provider_packet_control(
                "Copy recovery verification commands"
            )
            provider_verify_gaps = _provider_recovery_verify_gaps(provider_verify_text)
            provider_verify_first_line = provider_verify_clipboard.splitlines()[0].strip() if provider_verify_clipboard else ""
            provider_verify_starts_in_workdir = (
                provider_verify_first_line.startswith("Set-Location -LiteralPath")
                and str(PROJECT_ROOT) in provider_verify_first_line
            )
            provider_verify_detail.update(
                {
                    "commands": provider_verify_text[:1200],
                    "first_line": provider_verify_first_line,
                    "starts_in_workdir": provider_verify_starts_in_workdir,
                    "preview_has_verification_cwd": "Verification cwd:" in provider_preview_text,
                    "verify_gaps": provider_verify_gaps,
                }
            )
            _record_check(
                checks,
                "operator_provider_recovery_verify_copy",
                bool(provider_verify_text)
                and not provider_verify_gaps
                and provider_verify_starts_in_workdir
                and "Verification cwd:" in provider_preview_text
                and str(PROJECT_ROOT) in provider_preview_text
                and provider_verify_clipboard == provider_verify_text
                and provider_verify_detail.get("initial_button_text") == "Copy recovery verification commands",
                provider_verify_detail,
            )

        cards = operator_payload.get("cards") if isinstance(operator_payload.get("cards"), list) else []
        workspace_smoke_card = next(
            (
                card
                for card in cards
                if isinstance(card, dict) and str(card.get("label", "")).strip().lower() == "workspace smoke"
            ),
            {},
        )
        workspace_smoke_state = str(workspace_smoke_card.get("state", "")).strip().lower()
        workspace_smoke_failed = workspace_smoke_state == "fail"
        workspace_smoke_action_required = workspace_smoke_state == "warn"
        workspace_smoke_needs_rerun = workspace_smoke_failed or workspace_smoke_action_required
        workspace_smoke_expected_conclusion = "failure" if workspace_smoke_failed else "action_required"
        artifacts = operator_payload.get("artifacts") if isinstance(operator_payload.get("artifacts"), dict) else {}
        artifact_actions = (
            operator_payload.get("artifact_actions")
            if isinstance(operator_payload.get("artifact_actions"), list)
            else []
        )
        artifact_action_keys = {
            str(action.get("key", "")).strip()
            for action in artifact_actions
            if isinstance(action, dict) and str(action.get("key", "")).strip()
        }
        artifact_dom_keys = page.locator("#operator-artifacts [data-artifact-key]").evaluate_all(
            """nodes => nodes.map(node => node.getAttribute('data-artifact-key') || '').filter(Boolean)"""
        )
        artifact_note_dom = page.locator("#operator-artifacts .operator-action-note").evaluate_all(
            """nodes => nodes.map(node => (node.innerText || '').trim()).filter(Boolean)"""
        )

        def _artifact_action(key: str) -> dict[str, Any]:
            for action in artifact_actions:
                if isinstance(action, dict) and str(action.get("key", "")).strip() == key:
                    return action
            return {}

        def _artifact_note_labels(action: dict[str, Any]) -> list[str]:
            notes = action.get("notes")
            if not isinstance(notes, list):
                return []
            return [
                str(note.get("label", "")).strip()
                for note in notes
                if isinstance(note, dict) and str(note.get("label", "")).strip()
            ]

        def _artifact_note_states(action: dict[str, Any]) -> list[str]:
            notes = action.get("notes")
            if not isinstance(notes, list):
                return []
            return [
                str(note.get("state", "")).strip().lower()
                for note in notes
                if isinstance(note, dict) and str(note.get("state", "")).strip()
            ]

        def _artifact_action_view(action: dict[str, Any]) -> dict[str, Any]:
            view = action.get("view")
            return view if isinstance(view, dict) else {}

        def _json_object_from_path(path_value: str, label: str) -> tuple[dict[str, Any], str]:
            if not path_value:
                return {}, f"{label} path missing"
            try:
                payload = json.loads(Path(path_value).read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                return {}, str(exc)
            if not isinstance(payload, dict):
                return {}, f"{label} is not a JSON object"
            return payload, ""

        def _credential_status_expected_note_labels(path_value: str) -> tuple[list[str], str]:
            if not path_value:
                return [], ""
            try:
                payload = json.loads(Path(path_value).read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                return [], str(exc)
            if not isinstance(payload, dict):
                return [], "credential input status JSON is not an object"
            launch_blocker = payload.get("launch_blocker_summary")
            if not isinstance(launch_blocker, dict):
                return [], ""
            labels: list[str] = []
            if launch_blocker.get("readiness_scheduler_artifact_stale") is True:
                labels.append("readiness scheduler artifact stale")
            if launch_blocker.get("latest_scheduler_artifact_evidence_complete") is True:
                labels.append("latest scheduler evidence complete")
            return labels, ""

        readiness_report_path = str(artifacts.get("readiness", "")).strip()
        readiness_report_json_payload, readiness_report_json_error = _json_object_from_path(
            readiness_report_path,
            "readiness report",
        )
        readiness_report_json_required_fields = ("status", "generated_at", "summary", "checks")
        readiness_report_json_missing_fields = [
            key for key in readiness_report_json_required_fields if key not in readiness_report_json_payload
        ]
        readiness_report_json_summary = readiness_report_json_payload.get("summary")
        readiness_report_json_summary_ok = isinstance(readiness_report_json_summary, dict)
        readiness_report_json_checks = readiness_report_json_payload.get("checks")
        readiness_report_json_checks_ok = isinstance(readiness_report_json_checks, list) and bool(
            readiness_report_json_checks
        )
        readiness_report_json_ok = (
            bool(readiness_report_path)
            and not readiness_report_json_error
            and not readiness_report_json_missing_fields
            and readiness_report_json_summary_ok
            and readiness_report_json_checks_ok
        )
        readiness_refresh_command = str(artifacts.get("readiness_refresh_command", "")).strip()
        dashboard_browser_path = str(artifacts.get("browser", "")).strip()
        dashboard_browser_screenshot_path = str(artifacts.get("browser_screenshot", "")).strip()
        tap_fixture_browser_path = str(artifacts.get("tap_fixture_browser", "")).strip()
        tap_fixture_screenshot_path = str(artifacts.get("tap_fixture_browser_screenshot", "")).strip()
        tap_fixture_refresh_command = str(artifacts.get("tap_fixture_browser_refresh_command", "")).strip()
        scheduler_artifact_path = str(artifacts.get("scheduler", "")).strip()
        scheduler_artifact_json_payload, scheduler_artifact_json_error = _json_object_from_path(
            scheduler_artifact_path,
            "scheduler artifact",
        )
        scheduler_artifact_json_required_fields = ("status", "exit_code", "duration_seconds")
        scheduler_artifact_json_missing_fields = [
            key for key in scheduler_artifact_json_required_fields if key not in scheduler_artifact_json_payload
        ]
        scheduler_artifact_json_has_detail_log = bool(
            str(scheduler_artifact_json_payload.get("detail_log", "")).strip()
        )
        scheduler_artifact_json_has_summary_log = any(
            str(scheduler_artifact_json_payload.get(key, "")).strip()
            for key in ("summary_log", "summary_fallback_log")
        )
        scheduler_artifact_json_ok = (
            bool(scheduler_artifact_path)
            and not scheduler_artifact_json_error
            and not scheduler_artifact_json_missing_fields
            and scheduler_artifact_json_has_detail_log
            and scheduler_artifact_json_has_summary_log
        )
        provider_packet_artifact_path = str(artifacts.get("provider_auth_recovery_packet", "")).strip()
        provider_packet_json_payload, provider_packet_json_error = _json_object_from_path(
            provider_packet_artifact_path,
            "provider recovery packet",
        )
        provider_packet_json_required_fields = (
            "status",
            "next_required_action",
            "recovery_summary",
            "env_template",
            "recovery_checklist",
            "launch_success_criteria",
            "verification_commands",
            "verification_command_bundle",
        )
        provider_packet_json_missing_fields = [
            key for key in provider_packet_json_required_fields if key not in provider_packet_json_payload
        ]
        provider_packet_launch_success_criteria = provider_packet_json_payload.get("launch_success_criteria")
        provider_packet_launch_success_criteria_ok = isinstance(provider_packet_launch_success_criteria, list) and bool(
            provider_packet_launch_success_criteria
        )
        provider_packet_expected_launch_success_criteria = [
            str(criterion).strip()
            for criterion in (
                provider_packet_launch_success_criteria if isinstance(provider_packet_launch_success_criteria, list) else []
            )
            if str(criterion).strip()
        ]
        provider_packet_recovery_checklist = provider_packet_json_payload.get("recovery_checklist")
        provider_packet_recovery_checklist_ok = isinstance(provider_packet_recovery_checklist, list) and bool(
            provider_packet_recovery_checklist
        )
        provider_packet_expected_recovery_checklist = [
            str(item).strip()
            for item in (provider_packet_recovery_checklist if isinstance(provider_packet_recovery_checklist, list) else [])
            if str(item).strip()
        ]
        provider_packet_verification_commands = provider_packet_json_payload.get("verification_commands")
        provider_packet_verification_commands_ok = isinstance(provider_packet_verification_commands, list) and bool(
            provider_packet_verification_commands
        )
        provider_packet_expected_verification_commands = [
            str(command).strip()
            for command in (
                provider_packet_verification_commands if isinstance(provider_packet_verification_commands, list) else []
            )
            if str(command).strip()
        ]
        provider_packet_json_ok = (
            not provider_packet_artifact_path
            or (
                not provider_packet_json_error
                and not provider_packet_json_missing_fields
                and provider_packet_launch_success_criteria_ok
                and provider_packet_recovery_checklist_ok
                and provider_packet_verification_commands_ok
                and bool(str(provider_packet_json_payload.get("env_template") or "").strip())
                and bool(str(provider_packet_json_payload.get("verification_command_bundle") or "").strip())
            )
        )
        credential_input_status_path = str(artifacts.get("credential_input_status", "")).strip()
        credential_input_status_json_path = str(artifacts.get("credential_input_status_json", "")).strip()
        credential_status_expected_note_labels, credential_status_note_error = (
            _credential_status_expected_note_labels(credential_input_status_json_path)
        )
        credential_status_json_required = bool(credential_input_status_path)
        credential_status_json_ok = (
            not credential_status_json_required
            or (bool(credential_input_status_json_path) and not credential_status_note_error)
        )
        workspace_smoke_path = str(artifacts.get("workspace_smoke", "")).strip()
        workspace_smoke_json_payload, workspace_smoke_json_error = _json_object_from_path(
            workspace_smoke_path,
            "workspace smoke",
        )
        workspace_smoke_json_required_fields = ("status", "generated_at", "summary", "results")
        workspace_smoke_json_missing_fields = [
            key for key in workspace_smoke_json_required_fields if key not in workspace_smoke_json_payload
        ]
        workspace_smoke_json_summary = workspace_smoke_json_payload.get("summary")
        workspace_smoke_json_summary_counts_ok = isinstance(workspace_smoke_json_summary, dict) and all(
            isinstance(workspace_smoke_json_summary.get(key), int) for key in ("total", "passed", "failed")
        )
        workspace_smoke_json_results = workspace_smoke_json_payload.get("results")
        workspace_smoke_json_results_ok = isinstance(workspace_smoke_json_results, list) and bool(
            workspace_smoke_json_results
        )
        workspace_smoke_json_status_complete = workspace_smoke_json_payload.get("status") == "complete"
        workspace_smoke_json_summary_text = (
            f"{workspace_smoke_json_summary.get('passed')}/{workspace_smoke_json_summary.get('total')} passed, "
            f"{workspace_smoke_json_summary.get('failed')} failed"
            if isinstance(workspace_smoke_json_summary, dict) and workspace_smoke_json_summary_counts_ok
            else ""
        )
        workspace_smoke_json_ok = (
            bool(workspace_smoke_path)
            and not workspace_smoke_json_error
            and not workspace_smoke_json_missing_fields
            and workspace_smoke_json_status_complete
            and workspace_smoke_json_summary_counts_ok
            and workspace_smoke_json_results_ok
        )
        launch_secret_scan_path = str(artifacts.get("launch_secret_scan", "")).strip()
        handoff_refresh_path = str(artifacts.get("handoff_refresh", "")).strip()
        launch_secret_scan_refresh_command = str(
            artifacts.get("launch_secret_scan_refresh_command", "")
        ).strip()
        expected_artifact_action_keys = {
            "readiness_report",
            "readiness_refresh",
            "launch_secret_scan_refresh",
            "provider_auth_recovery_packet",
            "dashboard_browser_report",
            "dashboard_browser_screenshot",
            "tap_fixture_report",
            "tap_fixture_screenshot",
            "tap_fixture_refresh",
            "scheduler_artifact",
            "workspace_smoke",
        }
        if credential_input_status_path:
            expected_artifact_action_keys.add("credential_input_status")
        if launch_secret_scan_path:
            expected_artifact_action_keys.add("launch_secret_scan")
        if handoff_refresh_path:
            expected_artifact_action_keys.add("handoff_refresh")
        readiness_action = _artifact_action("readiness_report")
        launch_secret_scan_action = _artifact_action("launch_secret_scan")
        launch_secret_scan_refresh_action = _artifact_action("launch_secret_scan_refresh")
        handoff_refresh_action = _artifact_action("handoff_refresh")
        credential_input_status_action = _artifact_action("credential_input_status")
        provider_packet_artifact_action = _artifact_action("provider_auth_recovery_packet")
        dashboard_browser_action = _artifact_action("dashboard_browser_report")
        dashboard_browser_screenshot_action = _artifact_action("dashboard_browser_screenshot")
        tap_fixture_action = _artifact_action("tap_fixture_report")
        tap_fixture_screenshot_action = _artifact_action("tap_fixture_screenshot")
        scheduler_artifact_action = _artifact_action("scheduler_artifact")
        workspace_smoke_action = _artifact_action("workspace_smoke")
        freshness_note_actions = {
            "readiness_report": readiness_action,
            "provider_auth_recovery_packet": provider_packet_artifact_action,
            "dashboard_browser_report": dashboard_browser_action,
            "dashboard_browser_screenshot": dashboard_browser_screenshot_action,
            "tap_fixture_report": tap_fixture_action,
            "tap_fixture_screenshot": tap_fixture_screenshot_action,
            "scheduler_artifact": scheduler_artifact_action,
            "workspace_smoke": workspace_smoke_action,
        }
        if launch_secret_scan_path:
            freshness_note_actions["launch_secret_scan"] = launch_secret_scan_action
        if handoff_refresh_path:
            freshness_note_actions["handoff_refresh"] = handoff_refresh_action
        if credential_input_status_path:
            freshness_note_actions["credential_input_status"] = credential_input_status_action
        artifact_note_labels_by_key = {
            key: _artifact_note_labels(action) for key, action in freshness_note_actions.items()
        }
        artifact_note_states_by_key = {
            key: _artifact_note_states(action) for key, action in freshness_note_actions.items()
        }
        artifact_static_note_labels_by_key = {
            key: [label for label in labels if " old" not in label]
            for key, labels in artifact_note_labels_by_key.items()
        }
        artifact_dom_age_note_count = sum(1 for label in artifact_note_dom if " old" in label)
        artifact_freshness_note_ok = (
            all(labels and any(" old" in label for label in labels) for labels in artifact_note_labels_by_key.values())
            and all(
                states and all(state in {"fresh", "stale"} for state in states)
                for states in artifact_note_states_by_key.values()
            )
            and len(artifact_note_dom) >= len(freshness_note_actions)
            and artifact_dom_age_note_count >= len(freshness_note_actions)
            and all(
                any(label in artifact_note_dom for label in labels)
                for labels in artifact_static_note_labels_by_key.values()
                if labels
            )
        )
        readiness_action_view = _artifact_action_view(readiness_action)
        launch_secret_scan_view = _artifact_action_view(launch_secret_scan_action)
        provider_packet_artifact_view = _artifact_action_view(provider_packet_artifact_action)
        dashboard_browser_screenshot_view = _artifact_action_view(dashboard_browser_screenshot_action)
        tap_fixture_screenshot_view = _artifact_action_view(tap_fixture_screenshot_action)
        workspace_smoke_view = _artifact_action_view(workspace_smoke_action)
        workspace_smoke_uses_launch_final = (
            "workspace-smoke-getdaytrends-launch-final.json" in workspace_smoke_path
        )
        artifact_action_manifest_detail = {
            "api_keys": sorted(artifact_action_keys),
            "dom_keys": artifact_dom_keys,
            "expected_keys": sorted(expected_artifact_action_keys),
            "workspace_smoke_uses_launch_final": workspace_smoke_uses_launch_final,
            "readiness_action": readiness_action,
            "readiness_report_json_error": readiness_report_json_error,
            "readiness_report_json_missing_fields": readiness_report_json_missing_fields,
            "readiness_report_json_ok": readiness_report_json_ok,
            "readiness_report_json_status": str(readiness_report_json_payload.get("status", "")),
            "readiness_report_json_generated_at": str(readiness_report_json_payload.get("generated_at", "")),
            "readiness_report_json_summary": readiness_report_json_summary
            if isinstance(readiness_report_json_summary, dict)
            else {},
            "readiness_report_json_check_count": len(readiness_report_json_checks)
            if isinstance(readiness_report_json_checks, list)
            else 0,
            "launch_secret_scan_action": launch_secret_scan_action,
            "launch_secret_scan_view": launch_secret_scan_view,
            "launch_secret_scan_refresh_action": launch_secret_scan_refresh_action,
            "handoff_refresh_action": handoff_refresh_action,
            "credential_input_status_action": credential_input_status_action,
            "provider_packet_artifact_action": provider_packet_artifact_action,
            "dashboard_browser_action": dashboard_browser_action,
            "dashboard_browser_screenshot_action": dashboard_browser_screenshot_action,
            "tap_fixture_action": tap_fixture_action,
            "tap_fixture_screenshot_action": tap_fixture_screenshot_action,
            "scheduler_artifact_action": scheduler_artifact_action,
            "scheduler_artifact_json_error": scheduler_artifact_json_error,
            "scheduler_artifact_json_missing_fields": scheduler_artifact_json_missing_fields,
            "scheduler_artifact_json_ok": scheduler_artifact_json_ok,
            "scheduler_artifact_json_status": str(scheduler_artifact_json_payload.get("status", "")),
            "scheduler_artifact_json_exit_code": scheduler_artifact_json_payload.get("exit_code"),
            "scheduler_artifact_json_duration_seconds": scheduler_artifact_json_payload.get("duration_seconds"),
            "scheduler_artifact_json_has_detail_log": scheduler_artifact_json_has_detail_log,
            "scheduler_artifact_json_has_summary_log": scheduler_artifact_json_has_summary_log,
            "workspace_smoke_action": workspace_smoke_action,
            "workspace_smoke_json_error": workspace_smoke_json_error,
            "workspace_smoke_json_missing_fields": workspace_smoke_json_missing_fields,
            "workspace_smoke_json_ok": workspace_smoke_json_ok,
            "workspace_smoke_json_status": str(workspace_smoke_json_payload.get("status", "")),
            "workspace_smoke_json_generated_at": str(workspace_smoke_json_payload.get("generated_at", "")),
            "workspace_smoke_json_summary_text": workspace_smoke_json_summary_text,
            "workspace_smoke_json_result_count": len(workspace_smoke_json_results)
            if isinstance(workspace_smoke_json_results, list)
            else 0,
            "credential_input_status_json_path": credential_input_status_json_path,
            "credential_status_json_required": credential_status_json_required,
            "credential_status_json_ok": credential_status_json_ok,
            "credential_status_expected_note_labels": credential_status_expected_note_labels,
            "credential_status_note_error": credential_status_note_error,
            "artifact_note_dom": artifact_note_dom,
            "artifact_note_labels_by_key": artifact_note_labels_by_key,
            "artifact_note_states_by_key": artifact_note_states_by_key,
            "artifact_static_note_labels_by_key": artifact_static_note_labels_by_key,
            "artifact_dom_age_note_count": artifact_dom_age_note_count,
        }
        artifact_action_manifest_ok = (
            expected_artifact_action_keys.issubset(artifact_action_keys)
            and expected_artifact_action_keys.issubset({str(key).strip() for key in artifact_dom_keys})
            and artifact_freshness_note_ok
            and readiness_action.get("value") == readiness_report_path
            and readiness_action.get("copy_label") == "Copy readiness report path"
            and readiness_action_view.get("kind") == "readiness_report"
            and readiness_action_view.get("controls") == "operator-readiness-report-preview"
            and readiness_report_json_ok
            and (not launch_secret_scan_path or launch_secret_scan_action.get("value") == launch_secret_scan_path)
            and (
                not launch_secret_scan_path
                or launch_secret_scan_action.get("copy_label") == "Copy launch secret scan path"
            )
            and (not launch_secret_scan_path or launch_secret_scan_view.get("kind") == "launch_secret_scan")
            and (
                not launch_secret_scan_path
                or launch_secret_scan_view.get("label") == "View launch secret scan"
            )
            and (
                not launch_secret_scan_path
                or launch_secret_scan_view.get("view_text") == "View scan"
            )
            and (
                not launch_secret_scan_path
                or launch_secret_scan_view.get("hide_text") == "Hide scan"
            )
            and (
                not launch_secret_scan_path
                or launch_secret_scan_view.get("controls") == "operator-launch-secret-scan-preview"
            )
            and launch_secret_scan_refresh_action.get("value") == launch_secret_scan_refresh_command
            and launch_secret_scan_refresh_action.get("copy_label") == "Copy launch secret scan refresh command"
            and (not handoff_refresh_path or handoff_refresh_action.get("value") == handoff_refresh_path)
            and (
                not handoff_refresh_path
                or handoff_refresh_action.get("copy_label") == "Copy handoff refresh bundle path"
            )
            and (not credential_input_status_path or credential_input_status_action.get("value") == credential_input_status_path)
            and credential_status_json_ok
            and (
                not credential_input_status_path
                or credential_input_status_action.get("copy_label") == "Copy credential input status path"
            )
            and provider_packet_artifact_action.get("value") == provider_packet_artifact_path
            and provider_packet_artifact_action.get("copy_label") == "Copy provider recovery packet path"
            and provider_packet_artifact_view.get("kind") == "recovery_packet"
            and provider_packet_artifact_view.get("label") == "View provider recovery packet"
            and provider_packet_artifact_view.get("view_text") == "View provider packet"
            and provider_packet_artifact_view.get("hide_text") == "Hide provider packet"
            and provider_packet_artifact_view.get("controls") == "operator-provider-recovery-packet-preview"
            and dashboard_browser_action.get("value") == dashboard_browser_path
            and dashboard_browser_action.get("copy_label") == "Copy dashboard browser report path"
            and dashboard_browser_screenshot_action.get("value") == dashboard_browser_screenshot_path
            and dashboard_browser_screenshot_action.get("copy_label") == "Copy dashboard browser screenshot path"
            and dashboard_browser_screenshot_view.get("kind") == "artifact_image"
            and dashboard_browser_screenshot_view.get("controls") == "operator-dashboard-browser-screenshot-preview"
            and dashboard_browser_screenshot_view.get("image_path") == dashboard_browser_screenshot_path
            and dashboard_browser_screenshot_view.get("image_alt") == "Dashboard browser smoke screenshot"
            and tap_fixture_screenshot_action.get("value") == tap_fixture_screenshot_path
            and tap_fixture_screenshot_action.get("copy_label") == "Copy TAP fixture screenshot path"
            and tap_fixture_screenshot_view.get("kind") == "artifact_image"
            and tap_fixture_screenshot_view.get("controls") == "operator-tap-fixture-screenshot-preview"
            and tap_fixture_screenshot_view.get("image_path") == tap_fixture_screenshot_path
            and tap_fixture_screenshot_view.get("image_alt") == "TAP fixture browser smoke screenshot"
            and scheduler_artifact_action.get("value") == scheduler_artifact_path
            and scheduler_artifact_action.get("copy_label") == "Copy scheduler artifact path"
            and scheduler_artifact_json_ok
            and workspace_smoke_action.get("value") == workspace_smoke_path
            and workspace_smoke_action.get("copy_label") == "Copy workspace smoke path"
            and workspace_smoke_uses_launch_final
            and workspace_smoke_json_ok
            and workspace_smoke_view.get("kind") == "workspace_smoke"
            and workspace_smoke_view.get("controls") == "operator-workspace-smoke-preview"
        )
        _record_check(
            checks,
            "operator_artifact_action_manifest",
            artifact_action_manifest_ok,
            artifact_action_manifest_detail,
        )
        scheduler_artifact_dom_notes = page.locator(
            "#operator-artifacts [data-artifact-key='scheduler_artifact'] .operator-action-note"
        ).evaluate_all("""nodes => nodes.map(node => (node.innerText || '').trim()).filter(Boolean)""")
        scheduler_artifact_static_notes = artifact_static_note_labels_by_key.get("scheduler_artifact", [])
        scheduler_artifact_diagnostic_labels = [
            label for label in scheduler_artifact_static_notes if " old" not in label
        ]
        scheduler_artifact_summary_labels = {
            "primary summary log present",
            "fallback summary log present",
            "summary log missing",
        }
        scheduler_artifact_detail_containment_labels = {
            "detail log contained",
            "detail log outside scheduler dir",
        }
        scheduler_artifact_summary_containment_labels = {
            "primary summary log contained",
            "primary summary log outside scheduler dir",
            "fallback summary log contained",
            "fallback summary log outside scheduler dir",
        }
        scheduler_artifact_has_detail_log = "detail log present" in scheduler_artifact_diagnostic_labels
        scheduler_artifact_has_summary_log = any(
            label in {"primary summary log present", "fallback summary log present"}
            for label in scheduler_artifact_diagnostic_labels
        )
        scheduler_artifact_detail_containment_ok = (
            not scheduler_artifact_has_detail_log
            or any(label in scheduler_artifact_detail_containment_labels for label in scheduler_artifact_diagnostic_labels)
        )
        scheduler_artifact_summary_containment_ok = (
            not scheduler_artifact_has_summary_log
            or any(label in scheduler_artifact_summary_containment_labels for label in scheduler_artifact_diagnostic_labels)
        )
        scheduler_age_detail = str(scheduler_age_card.get("detail", "")).strip().lower()
        scheduler_age_detail_exit_match = re.search(r"\bexit\s+-?\d+\b", scheduler_age_detail)
        scheduler_age_detail_duration_match = re.search(r"\b\d+(?:\.\d+)?s\b", scheduler_age_detail)
        scheduler_age_detail_has_log_containment = (
            "contained" in scheduler_age_detail or "outside scheduler dir" in scheduler_age_detail
        )
        scheduler_age_detail_has_run_diagnostics = (
            bool(scheduler_age_detail_exit_match)
            and bool(scheduler_age_detail_duration_match)
            and "detail log" in scheduler_age_detail
            and "summary log" in scheduler_age_detail
            and scheduler_age_detail_has_log_containment
        )
        if scheduler_age_hours is not None and scheduler_age_hours < 21.6:
            scheduler_age_detail_expected_mode = "run_diagnostics"
        elif scheduler_age_stale:
            scheduler_age_detail_expected_mode = "stale_refresh_hint"
        elif scheduler_age_near_stale:
            scheduler_age_detail_expected_mode = "near_stale_refresh_hint"
        else:
            scheduler_age_detail_expected_mode = "detail_present"
        scheduler_age_detail_refresh_hint_ok = (
            "refresh now" in scheduler_age_detail
            if scheduler_age_detail_expected_mode == "stale_refresh_hint"
            else "refresh soon" in scheduler_age_detail
            if scheduler_age_detail_expected_mode == "near_stale_refresh_hint"
            else False
        )
        scheduler_age_detail_ok = (
            scheduler_age_detail_has_run_diagnostics
            if scheduler_age_detail_expected_mode == "run_diagnostics"
            else scheduler_age_detail_refresh_hint_ok
            if scheduler_age_detail_expected_mode
            in {
                "stale_refresh_hint",
                "near_stale_refresh_hint",
            }
            else bool(scheduler_age_card.get("detail"))
        )
        scheduler_artifact_diagnostics_ok = (
            bool(scheduler_artifact_path)
            and any(label.startswith("status: ") for label in scheduler_artifact_diagnostic_labels)
            and any(label.startswith("exit code: ") for label in scheduler_artifact_diagnostic_labels)
            and any(label.startswith("duration: ") and label.endswith("s") for label in scheduler_artifact_diagnostic_labels)
            and any(label in {"detail log present", "detail log missing"} for label in scheduler_artifact_diagnostic_labels)
            and any(label in scheduler_artifact_summary_labels for label in scheduler_artifact_diagnostic_labels)
            and scheduler_artifact_detail_containment_ok
            and scheduler_artifact_summary_containment_ok
            and scheduler_artifact_json_ok
            and all(label in scheduler_artifact_dom_notes for label in scheduler_artifact_diagnostic_labels)
            and scheduler_age_detail_ok
        )
        _record_check(
            checks,
            "operator_scheduler_artifact_diagnostics",
            scheduler_artifact_diagnostics_ok,
            {
                "scheduler_artifact_path_present": bool(scheduler_artifact_path),
                "scheduler_artifact_json_ok": scheduler_artifact_json_ok,
                "scheduler_artifact_json_error": scheduler_artifact_json_error,
                "scheduler_artifact_json_missing_fields": scheduler_artifact_json_missing_fields,
                "scheduler_artifact_json_has_detail_log": scheduler_artifact_json_has_detail_log,
                "scheduler_artifact_json_has_summary_log": scheduler_artifact_json_has_summary_log,
                "api_notes": scheduler_artifact_diagnostic_labels,
                "dom_notes": scheduler_artifact_dom_notes,
                "scheduler_age_card": scheduler_age_card,
                "scheduler_age_detail_expected_mode": scheduler_age_detail_expected_mode,
                "scheduler_age_detail_ok": scheduler_age_detail_ok,
                "scheduler_age_detail_has_run_diagnostics": scheduler_age_detail_has_run_diagnostics
                if scheduler_age_detail_expected_mode == "run_diagnostics"
                else None,
                "scheduler_age_detail_has_log_containment": scheduler_age_detail_has_log_containment
                if scheduler_age_detail_expected_mode == "run_diagnostics"
                else None,
                "scheduler_age_detail_refresh_hint_ok": scheduler_age_detail_refresh_hint_ok
                if scheduler_age_detail_expected_mode
                in {
                    "stale_refresh_hint",
                    "near_stale_refresh_hint",
                }
                else None,
                "scheduler_age_detail_exit": scheduler_age_detail_exit_match.group(0)
                if scheduler_age_detail_exit_match
                else "",
                "scheduler_age_detail_duration": scheduler_age_detail_duration_match.group(0)
                if scheduler_age_detail_duration_match
                else "",
                "accepted_summary_labels": sorted(scheduler_artifact_summary_labels),
                "accepted_detail_containment_labels": sorted(scheduler_artifact_detail_containment_labels),
                "accepted_summary_containment_labels": sorted(scheduler_artifact_summary_containment_labels),
                "detail_containment_ok": scheduler_artifact_detail_containment_ok,
                "summary_containment_ok": scheduler_artifact_summary_containment_ok,
            },
        )

        expected_artifact_action_groups: dict[str, dict[str, Any]] = {}
        if readiness_report_path:
            expected_artifact_action_groups["readiness_report"] = {
                "label": "Readiness report artifact actions",
                "button_texts": ["View report", "Copy path"],
                "button_labels": ["View readiness report", "Copy readiness report path"],
            }
        if readiness_refresh_command:
            expected_artifact_action_groups["readiness_refresh"] = {
                "label": "Readiness refresh artifact actions",
                "button_texts": ["Copy command"],
                "button_labels": ["Copy readiness refresh command"],
            }
        if launch_secret_scan_path:
            expected_artifact_action_groups["launch_secret_scan"] = {
                "label": "Launch secret scan artifact actions",
                "button_texts": ["View scan", "Copy path"],
                "button_labels": ["View launch secret scan", "Copy launch secret scan path"],
            }
        if launch_secret_scan_refresh_command:
            expected_artifact_action_groups["launch_secret_scan_refresh"] = {
                "label": "Launch secret scan refresh artifact actions",
                "button_texts": ["Copy command"],
                "button_labels": ["Copy launch secret scan refresh command"],
            }
        if handoff_refresh_path:
            expected_artifact_action_groups["handoff_refresh"] = {
                "label": "Handoff refresh bundle artifact actions",
                "button_texts": ["Copy path"],
                "button_labels": ["Copy handoff refresh bundle path"],
            }
        if credential_input_status_path:
            expected_artifact_action_groups["credential_input_status"] = {
                "label": "Credential input status artifact actions",
                "button_texts": ["Copy path"],
                "button_labels": ["Copy credential input status path"],
            }
        if provider_packet_artifact_path:
            expected_artifact_action_groups["provider_auth_recovery_packet"] = {
                "label": "Provider recovery packet artifact actions",
                "button_texts": ["View provider packet", "Copy path"],
                "button_labels": ["View provider recovery packet", "Copy provider recovery packet path"],
            }
        if dashboard_browser_path:
            expected_artifact_action_groups["dashboard_browser_report"] = {
                "label": "Dashboard browser report artifact actions",
                "button_texts": ["Copy path"],
                "button_labels": ["Copy dashboard browser report path"],
            }
        if dashboard_browser_screenshot_path:
            expected_artifact_action_groups["dashboard_browser_screenshot"] = {
                "label": "Dashboard browser screenshot artifact actions",
                "button_texts": ["View screenshot", "Copy path"],
                "button_labels": ["View dashboard browser screenshot", "Copy dashboard browser screenshot path"],
            }
        if tap_fixture_browser_path:
            expected_artifact_action_groups["tap_fixture_report"] = {
                "label": "TAP fixture report artifact actions",
                "button_texts": ["Copy path"],
                "button_labels": ["Copy TAP fixture report path"],
            }
        if tap_fixture_screenshot_path:
            expected_artifact_action_groups["tap_fixture_screenshot"] = {
                "label": "TAP fixture screenshot artifact actions",
                "button_texts": ["View screenshot", "Copy path"],
                "button_labels": ["View TAP fixture screenshot", "Copy TAP fixture screenshot path"],
            }
        if tap_fixture_refresh_command:
            expected_artifact_action_groups["tap_fixture_refresh"] = {
                "label": "TAP fixture refresh artifact actions",
                "button_texts": ["Copy command"],
                "button_labels": ["Copy TAP fixture refresh command"],
            }
        if scheduler_artifact_path:
            expected_artifact_action_groups["scheduler_artifact"] = {
                "label": "Scheduler artifact artifact actions",
                "button_texts": ["Copy path"],
                "button_labels": ["Copy scheduler artifact path"],
            }
        if workspace_smoke_path:
            expected_artifact_action_groups["workspace_smoke"] = {
                "label": "Workspace smoke artifact actions",
                "button_texts": ["View workspace", "Copy path"],
                "button_labels": ["View workspace smoke", "Copy workspace smoke path"],
            }
        artifact_action_group_dom = page.locator(
            "#operator-artifacts [data-artifact-action-group='true']"
        ).evaluate_all(
            """groups => groups.map(group => {
                const action = group.closest('.operator-action');
                const head = action?.querySelector('.operator-action-head');
                const headRect = head?.getBoundingClientRect();
                const groupRect = group.getBoundingClientRect();
                const buttons = Array.from(group.querySelectorAll('button')).map(button => {
                    const rect = button.getBoundingClientRect();
                    return {
                        text: (button.innerText || '').trim(),
                        ariaLabel: button.getAttribute('aria-label') || '',
                        type: button.getAttribute('type') || '',
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                    };
                });
                return {
                    key: action?.getAttribute('data-artifact-key') || '',
                    role: group.getAttribute('role') || '',
                    label: group.getAttribute('aria-label') || '',
                    buttonTexts: buttons.map(button => button.text),
                    buttonLabels: buttons.map(button => button.ariaLabel),
                    buttonTypes: buttons.map(button => button.type),
                    minButtonHeight: buttons.length ? Math.min(...buttons.map(button => button.height)) : 0,
                    rightAligned: headRect ? Math.abs(Math.round(headRect.right - groupRect.right)) <= 4 : false,
                    buttons,
                };
            })"""
        )
        artifact_action_group_by_key = {
            str(group.get("key") or ""): group
            for group in artifact_action_group_dom
            if isinstance(group, dict) and str(group.get("key") or "")
        }
        artifact_action_group_gaps: list[str] = []
        expected_artifact_group_keys = set(expected_artifact_action_groups)
        observed_artifact_group_keys = set(artifact_action_group_by_key)
        missing_artifact_group_keys = sorted(expected_artifact_group_keys - observed_artifact_group_keys)
        unexpected_artifact_group_keys = sorted(observed_artifact_group_keys - expected_artifact_group_keys)
        if missing_artifact_group_keys:
            artifact_action_group_gaps.append("missing artifact action groups")
        if unexpected_artifact_group_keys:
            artifact_action_group_gaps.append("unexpected artifact action groups")
        for key, expected_group in expected_artifact_action_groups.items():
            group = artifact_action_group_by_key.get(key, {})
            if group.get("role") != "group":
                artifact_action_group_gaps.append(f"{key}: missing group role")
            if group.get("label") != expected_group["label"]:
                artifact_action_group_gaps.append(f"{key}: group label changed")
            if group.get("buttonTexts") != expected_group["button_texts"]:
                artifact_action_group_gaps.append(f"{key}: button order changed")
            if group.get("buttonLabels") != expected_group["button_labels"]:
                artifact_action_group_gaps.append(f"{key}: button aria labels changed")
            if int(group.get("minButtonHeight") or 0) < 28:
                artifact_action_group_gaps.append(f"{key}: target height below 28px")
            if group.get("rightAligned") is not True:
                artifact_action_group_gaps.append(f"{key}: action group not right aligned")
            if not all(button_type == "button" for button_type in group.get("buttonTypes", [])):
                artifact_action_group_gaps.append(f"{key}: button type missing")
        _record_check(
            checks,
            "operator_artifact_action_groups",
            bool(expected_artifact_action_groups) and not artifact_action_group_gaps,
            {
                "expected": expected_artifact_action_groups,
                "groups": artifact_action_group_dom,
                "missing_keys": missing_artifact_group_keys,
                "unexpected_keys": unexpected_artifact_group_keys,
                "gaps": artifact_action_group_gaps,
                "wcag_target_size_minimum_reference": W3C_WCAG_TARGET_SIZE_MINIMUM_URL,
                "focus_order_reference": W3C_WCAG_FOCUS_ORDER_URL,
            },
        )

        launch_secret_scan_buttons = page.locator("[aria-label='Copy launch secret scan path']")
        launch_secret_scan_button_count = launch_secret_scan_buttons.count()
        launch_secret_scan_detail: dict[str, Any] = {
            "copy_button_count": launch_secret_scan_button_count,
            "launch_secret_scan_path_present": bool(launch_secret_scan_path),
        }
        launch_secret_scan_copy_ok = (
            launch_secret_scan_button_count >= 1 if launch_secret_scan_path else launch_secret_scan_button_count == 0
        )
        if launch_secret_scan_button_count:
            launch_secret_scan_button = launch_secret_scan_buttons.first
            initial_launch_secret_scan_copy_text = launch_secret_scan_button.inner_text(timeout=timeout_ms).strip()
            launch_secret_scan_text = launch_secret_scan_button.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            launch_secret_scan_button.click()
            launch_secret_scan_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy launch secret scan path']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                launch_secret_scan_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            launch_secret_scan_clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            note_labels = _artifact_note_labels(launch_secret_scan_action)
            launch_secret_scan_detail.update(
                {
                    "launch_secret_scan_path": launch_secret_scan_text[:240],
                    "initial_button_text": initial_launch_secret_scan_copy_text,
                    "button_text": launch_secret_scan_button.inner_text(timeout=timeout_ms),
                    "copy_feedback_seen": launch_secret_scan_feedback_seen,
                    "clipboard_matches": bool(
                        launch_secret_scan_text and launch_secret_scan_clipboard_text == launch_secret_scan_text
                    ),
                    "note_labels": note_labels,
                }
            )
            launch_secret_scan_copy_ok = (
                launch_secret_scan_copy_ok
                and bool(launch_secret_scan_text)
                and launch_secret_scan_text == launch_secret_scan_path
                and "getdaytrends-launch-secret-scan" in launch_secret_scan_text
                and launch_secret_scan_clipboard_text == launch_secret_scan_text
                and initial_launch_secret_scan_copy_text == "Copy path"
                and "current artifacts included" in note_labels
            )
        _record_check(
            checks,
            "operator_launch_secret_scan_artifact_copy",
            launch_secret_scan_copy_ok,
            launch_secret_scan_detail,
        )

        launch_secret_scan_view_buttons = page.locator("[aria-controls='operator-launch-secret-scan-preview']")
        launch_secret_scan_view_button_count = launch_secret_scan_view_buttons.count()
        launch_secret_scan_view_detail: dict[str, Any] = {
            "view_button_count": launch_secret_scan_view_button_count,
            "launch_secret_scan_path_present": bool(launch_secret_scan_path),
        }
        launch_secret_scan_view_ok = (
            launch_secret_scan_view_button_count >= 1
            if launch_secret_scan_path
            else launch_secret_scan_view_button_count == 0
        )
        if launch_secret_scan_view_button_count:
            launch_secret_scan_view_button = launch_secret_scan_view_buttons.first
            initial_launch_secret_scan_disclosure = launch_secret_scan_view_button.evaluate(
                """button => {
                    const target = document.getElementById(button.getAttribute('aria-controls'));
                    return {
                        label: button.getAttribute('aria-label'),
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded'),
                        controls: button.getAttribute('aria-controls'),
                        artifact_path: button.dataset.artifactPath || '',
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                    };
                }"""
            )
            launch_secret_scan_keyboard_open_feedback_seen = False
            launch_secret_scan_keyboard_collapse_feedback_seen = False
            launch_secret_scan_keyboard_open_disclosure: dict[str, Any] = {}
            launch_secret_scan_keyboard_collapsed_disclosure: dict[str, Any] = {}
            launch_secret_scan_keyboard_secret_gaps: list[str] = []
            launch_secret_scan_keyboard_gaps: list[str] = []
            launch_secret_scan_view_button.focus()
            page.keyboard.press("Enter")
            try:
                page.wait_for_function(
                    """() => {
                        const button = document.querySelector("[aria-controls='operator-launch-secret-scan-preview']");
                        const target = document.getElementById('operator-launch-secret-scan-preview');
                        return button?.getAttribute('aria-expanded') === 'true'
                            && target
                            && target.hidden === false
                            && (target.innerText || '').includes('Launch secret scan:');
                    }""",
                    timeout=timeout_ms,
                )
                launch_secret_scan_keyboard_open_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            launch_secret_scan_keyboard_open_disclosure = launch_secret_scan_view_button.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        artifact_path: button.dataset.artifactPath || '',
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || ''),
                    };
                }"""
            )
            launch_secret_scan_keyboard_preview_text = str(
                launch_secret_scan_keyboard_open_disclosure.get("target_text") or ""
            )
            launch_secret_scan_keyboard_secret_gaps = _copy_payload_secret_gaps(
                launch_secret_scan_keyboard_preview_text,
                "launch secret scan keyboard preview",
            )
            launch_secret_scan_view_button.focus()
            page.keyboard.press("Space")
            try:
                page.wait_for_function(
                    """() => {
                        const button = document.querySelector("[aria-controls='operator-launch-secret-scan-preview']");
                        const target = document.getElementById('operator-launch-secret-scan-preview');
                        return button?.getAttribute('aria-expanded') === 'false'
                            && target
                            && target.hidden === true
                            && (target.innerText || '').trim() === '';
                    }""",
                    timeout=timeout_ms,
                )
                launch_secret_scan_keyboard_collapse_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            launch_secret_scan_keyboard_collapsed_disclosure = launch_secret_scan_view_button.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        artifact_path: button.dataset.artifactPath || '',
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').trim(),
                    };
                }"""
            )
            if not launch_secret_scan_keyboard_open_feedback_seen:
                launch_secret_scan_keyboard_gaps.append(
                    "launch secret scan disclosure Enter activation did not expand"
                )
            if launch_secret_scan_keyboard_open_disclosure.get("label") != "Hide launch secret scan":
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard open label changed")
            if launch_secret_scan_keyboard_open_disclosure.get("text") != "Hide scan":
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard open text changed")
            if launch_secret_scan_keyboard_open_disclosure.get("expanded") != "true":
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard open aria-expanded mismatch")
            if launch_secret_scan_keyboard_open_disclosure.get("artifact_path") != launch_secret_scan_path:
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard open artifact path mismatch")
            if launch_secret_scan_keyboard_open_disclosure.get("target_exists") is not True:
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard preview missing")
            if launch_secret_scan_keyboard_open_disclosure.get("target_hidden") is not False:
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard preview stayed hidden")
            if "Launch secret scan:" not in launch_secret_scan_keyboard_preview_text:
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard preview missing heading")
            if "Current artifacts: included" not in launch_secret_scan_keyboard_preview_text:
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard preview missing current artifacts")
            if "Current artifact sample:" not in launch_secret_scan_keyboard_preview_text:
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard preview missing artifact sample")
            if not launch_secret_scan_keyboard_collapse_feedback_seen:
                launch_secret_scan_keyboard_gaps.append(
                    "launch secret scan disclosure Space activation did not collapse"
                )
            if launch_secret_scan_keyboard_collapsed_disclosure.get("label") != "View launch secret scan":
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard collapsed label changed")
            if launch_secret_scan_keyboard_collapsed_disclosure.get("text") != "View scan":
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard collapsed text changed")
            if launch_secret_scan_keyboard_collapsed_disclosure.get("expanded") != "false":
                launch_secret_scan_keyboard_gaps.append(
                    "launch secret scan keyboard collapsed aria-expanded mismatch"
                )
            if launch_secret_scan_keyboard_collapsed_disclosure.get("artifact_path") != launch_secret_scan_path:
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard collapsed artifact path mismatch")
            if launch_secret_scan_keyboard_collapsed_disclosure.get("target_exists") is not True:
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard collapsed preview missing")
            if launch_secret_scan_keyboard_collapsed_disclosure.get("target_hidden") is not True:
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard collapse did not hide preview")
            if launch_secret_scan_keyboard_collapsed_disclosure.get("target_text") != "":
                launch_secret_scan_keyboard_gaps.append("launch secret scan keyboard collapse left preview text")
            launch_secret_scan_keyboard_gaps.extend(launch_secret_scan_keyboard_secret_gaps)
            if launch_secret_scan_view_button.get_attribute("aria-expanded") == "true":
                launch_secret_scan_view_button.click()
                page.wait_for_timeout(120)
            launch_secret_scan_view_button.click()
            launch_secret_scan_preview_loaded = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector('.operator-launch-secret-scan-preview')?.innerText || '').includes('Launch secret scan:')",
                    timeout=timeout_ms,
                )
                launch_secret_scan_preview_loaded = True
            except PlaywrightTimeoutError:
                pass
            launch_secret_scan_preview = page.locator(".operator-launch-secret-scan-preview").first
            launch_secret_scan_preview_text = launch_secret_scan_preview.inner_text(timeout=timeout_ms)
            launch_secret_scan_provenance = launch_secret_scan_preview.evaluate(
                """preview => {
                    const generated = preview.querySelector('time');
                    const spans = Array.from(preview.querySelectorAll('span'));
                    const artifactLine = spans.find(
                        span => (span.innerText || '').startsWith('Artifact:')
                    );
                    const currentArtifactLine = spans.find(
                        span => (span.innerText || '').startsWith('Current artifact sample:')
                    );
                    return {
                        hidden: preview.hidden,
                        text: (preview.innerText || '').trim(),
                        generatedText: generated ? generated.textContent : '',
                        generatedDateTime: generated ? generated.getAttribute('datetime') : '',
                        artifactText: artifactLine ? artifactLine.innerText : '',
                        currentArtifactText: currentArtifactLine ? currentArtifactLine.innerText : '',
                        copySummaryButtonCount: preview.querySelectorAll("[aria-label='Copy launch secret scan summary']").length,
                        copyRefreshButtonCount: preview.querySelectorAll("[aria-label='Copy launch secret scan preview refresh command']").length,
                    };
                }"""
            )
            launch_secret_scan_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", launch_secret_scan_preview_text, re.IGNORECASE):
                launch_secret_scan_secret_gaps.append("preview contains raw postgres URL")
            if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", launch_secret_scan_preview_text, re.IGNORECASE):
                launch_secret_scan_secret_gaps.append("preview contains raw tenant user")
            if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", launch_secret_scan_preview_text):
                launch_secret_scan_secret_gaps.append("preview contains raw OpenAI-style key")
            if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", launch_secret_scan_preview_text):
                launch_secret_scan_secret_gaps.append("preview contains raw Google API-style key")
            launch_secret_scan_summary_buttons = page.locator(
                "#operator-launch-secret-scan-preview [aria-label='Copy launch secret scan summary']"
            )
            launch_secret_scan_summary_copy_ok = launch_secret_scan_summary_buttons.count() >= 1
            if launch_secret_scan_summary_buttons.count():
                summary_button = launch_secret_scan_summary_buttons.first
                summary_text = summary_button.evaluate(
                    "(button) => String(button.dataset.copyText || '').replace(/\\\\n/g, '\\n').trim()"
                )
                summary_payload_secret_gaps = []
                if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", summary_text, re.IGNORECASE):
                    summary_payload_secret_gaps.append("summary payload contains raw postgres URL")
                if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", summary_text, re.IGNORECASE):
                    summary_payload_secret_gaps.append("summary payload contains raw tenant user")
                if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", summary_text):
                    summary_payload_secret_gaps.append("summary payload contains raw OpenAI-style key")
                if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", summary_text):
                    summary_payload_secret_gaps.append("summary payload contains raw Google API-style key")
                summary_button.click()
                summary_feedback_seen = False
                try:
                    page.wait_for_function(
                        "() => (document.querySelector(\"#operator-launch-secret-scan-preview [aria-label='Copy launch secret scan summary']\")?.innerText || '').trim() === 'Copied'",
                        timeout=timeout_ms,
                    )
                    summary_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                summary_clipboard = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                summary_clipboard_normalized = summary_clipboard.replace("\r\n", "\n").replace("\r", "\n").strip()
                summary_clipboard_matches = bool(summary_text and summary_clipboard_normalized == summary_text)
                summary_payload_safe = (
                    bool(summary_text)
                    and "Launch secret scan:" in summary_text
                    and "Current artifacts: included" in summary_text
                    and "Current artifact sample:" in summary_text
                    and "dashboard_browser" in summary_text
                    and "workspace-smoke-getdaytrends" in summary_text
                    and "Summary:" in summary_text
                    and "getdaytrends-launch-secret-scan-final-" in summary_text
                    and not summary_payload_secret_gaps
                )
                summary_copy_gaps: list[str] = []
                if not summary_payload_safe:
                    summary_copy_gaps.append("launch secret scan summary payload unsafe")
                if not summary_feedback_seen:
                    summary_copy_gaps.append("launch secret scan summary copy feedback missing")
                if not summary_clipboard_matches:
                    summary_copy_gaps.append("launch secret scan summary clipboard mismatch")
                summary_copy_gaps.extend(summary_payload_secret_gaps)
                launch_secret_scan_summary_copy_ok = (
                    summary_payload_safe
                    and summary_feedback_seen
                    and summary_clipboard_matches
                    and not summary_copy_gaps
                )
                launch_secret_scan_view_detail["summary_copy"] = {
                    "clipboard_matches": summary_clipboard_matches,
                    "clipboard_preview": summary_clipboard_normalized[:280],
                    "feedback_seen": summary_feedback_seen,
                    "gaps": summary_copy_gaps,
                    "payload_safe": summary_payload_safe,
                    "secret_gaps": summary_payload_secret_gaps,
                    "summary_preview": summary_text[:280],
                }
            launch_secret_scan_view_detail.update(
                {
                    "initial_disclosure": initial_launch_secret_scan_disclosure,
                    "preview_loaded": launch_secret_scan_preview_loaded,
                    "preview_text": launch_secret_scan_preview_text[:500],
                    "provenance": launch_secret_scan_provenance,
                    "secret_gaps": launch_secret_scan_secret_gaps,
                    "keyboard_open_feedback_seen": launch_secret_scan_keyboard_open_feedback_seen,
                    "keyboard_collapse_feedback_seen": launch_secret_scan_keyboard_collapse_feedback_seen,
                    "keyboard_open_disclosure": {
                        **launch_secret_scan_keyboard_open_disclosure,
                        "target_text": launch_secret_scan_keyboard_preview_text[:500],
                    },
                    "keyboard_collapsed_disclosure": launch_secret_scan_keyboard_collapsed_disclosure,
                    "keyboard_secret_gaps": launch_secret_scan_keyboard_secret_gaps,
                    "keyboard_gaps": launch_secret_scan_keyboard_gaps,
                    "summary_copy_ok": launch_secret_scan_summary_copy_ok,
                }
            )
            launch_secret_scan_view_ok = (
                launch_secret_scan_view_ok
                and initial_launch_secret_scan_disclosure.get("label") == "View launch secret scan"
                and initial_launch_secret_scan_disclosure.get("text") == "View scan"
                and initial_launch_secret_scan_disclosure.get("expanded") == "false"
                and initial_launch_secret_scan_disclosure.get("controls") == "operator-launch-secret-scan-preview"
                and initial_launch_secret_scan_disclosure.get("artifact_path") == launch_secret_scan_path
                and initial_launch_secret_scan_disclosure.get("target_exists") is True
                and initial_launch_secret_scan_disclosure.get("target_hidden") is True
                and launch_secret_scan_preview_loaded
                and launch_secret_scan_provenance.get("hidden") is False
                and "Launch secret scan: valid" in launch_secret_scan_preview_text
                and "Current artifacts: included" in launch_secret_scan_preview_text
                and "Current artifact sample:" in launch_secret_scan_preview_text
                and bool(re.search(r"Summary:\s+\d+ scanned, 0 findings, 0 missing", launch_secret_scan_preview_text))
                and launch_secret_scan_path in launch_secret_scan_provenance.get("artifactText", "")
                and "dashboard_browser" in launch_secret_scan_provenance.get("currentArtifactText", "")
                and "workspace-smoke-getdaytrends" in launch_secret_scan_provenance.get("currentArtifactText", "")
                and launch_secret_scan_provenance.get("generatedDateTime")
                == launch_secret_scan_provenance.get("generatedText")
                and launch_secret_scan_provenance.get("copySummaryButtonCount") >= 1
                and launch_secret_scan_provenance.get("copyRefreshButtonCount") >= 1
                and not launch_secret_scan_secret_gaps
                and launch_secret_scan_summary_copy_ok
                and not launch_secret_scan_keyboard_gaps
            )
            launch_secret_scan_initial_collapsed_ok = (
                initial_launch_secret_scan_disclosure.get("label") == "View launch secret scan"
                and initial_launch_secret_scan_disclosure.get("text") == "View scan"
                and initial_launch_secret_scan_disclosure.get("expanded") == "false"
                and initial_launch_secret_scan_disclosure.get("controls") == "operator-launch-secret-scan-preview"
                and initial_launch_secret_scan_disclosure.get("artifact_path") == launch_secret_scan_path
                and initial_launch_secret_scan_disclosure.get("target_exists") is True
                and initial_launch_secret_scan_disclosure.get("target_hidden") is True
            )
            launch_secret_scan_keyboard_open_visible_ok = (
                launch_secret_scan_keyboard_open_feedback_seen
                and launch_secret_scan_keyboard_open_disclosure.get("label") == "Hide launch secret scan"
                and launch_secret_scan_keyboard_open_disclosure.get("text") == "Hide scan"
                and launch_secret_scan_keyboard_open_disclosure.get("expanded") == "true"
                and launch_secret_scan_keyboard_open_disclosure.get("artifact_path") == launch_secret_scan_path
                and launch_secret_scan_keyboard_open_disclosure.get("target_exists") is True
                and launch_secret_scan_keyboard_open_disclosure.get("target_hidden") is False
                and "Launch secret scan:" in launch_secret_scan_keyboard_preview_text
                and "Current artifacts: included" in launch_secret_scan_keyboard_preview_text
                and "Current artifact sample:" in launch_secret_scan_keyboard_preview_text
            )
            launch_secret_scan_keyboard_collapsed_hidden_ok = (
                launch_secret_scan_keyboard_collapse_feedback_seen
                and launch_secret_scan_keyboard_collapsed_disclosure.get("label") == "View launch secret scan"
                and launch_secret_scan_keyboard_collapsed_disclosure.get("text") == "View scan"
                and launch_secret_scan_keyboard_collapsed_disclosure.get("expanded") == "false"
                and launch_secret_scan_keyboard_collapsed_disclosure.get("artifact_path") == launch_secret_scan_path
                and launch_secret_scan_keyboard_collapsed_disclosure.get("target_exists") is True
                and launch_secret_scan_keyboard_collapsed_disclosure.get("target_hidden") is True
                and launch_secret_scan_keyboard_collapsed_disclosure.get("target_text") == ""
            )
            launch_secret_scan_preview_content_ok = (
                launch_secret_scan_preview_loaded
                and "Launch secret scan: valid" in launch_secret_scan_preview_text
                and "Current artifacts: included" in launch_secret_scan_preview_text
                and "Current artifact sample:" in launch_secret_scan_preview_text
                and bool(re.search(r"Summary:\s+\d+ scanned, 0 findings, 0 missing", launch_secret_scan_preview_text))
                and not launch_secret_scan_secret_gaps
            )
            launch_secret_scan_provenance_ok = (
                launch_secret_scan_provenance.get("hidden") is False
                and launch_secret_scan_path in launch_secret_scan_provenance.get("artifactText", "")
                and "dashboard_browser" in launch_secret_scan_provenance.get("currentArtifactText", "")
                and "workspace-smoke-getdaytrends" in launch_secret_scan_provenance.get("currentArtifactText", "")
                and launch_secret_scan_provenance.get("generatedDateTime")
                == launch_secret_scan_provenance.get("generatedText")
            )
            launch_secret_scan_summary_copy_detail = launch_secret_scan_view_detail.get("summary_copy", {})
            launch_secret_scan_view_detail = {
                "expected_mode": "operator_launch_secret_scan_artifact_disclosure_lifecycle",
                "view_button_count": launch_secret_scan_view_button_count,
                "launch_secret_scan_path_present": bool(launch_secret_scan_path),
                "initial_collapsed_ok": launch_secret_scan_initial_collapsed_ok,
                "keyboard_open_visible_ok": launch_secret_scan_keyboard_open_visible_ok,
                "keyboard_collapsed_hidden_ok": launch_secret_scan_keyboard_collapsed_hidden_ok,
                "preview_content_ok": launch_secret_scan_preview_content_ok,
                "provenance_ok": launch_secret_scan_provenance_ok,
                "summary_copy_ok": launch_secret_scan_summary_copy_ok,
                "summary_copy_payload_safe": launch_secret_scan_summary_copy_detail.get("payload_safe"),
                "summary_copy_feedback_seen": launch_secret_scan_summary_copy_detail.get("feedback_seen"),
                "summary_copy_clipboard_matches": launch_secret_scan_summary_copy_detail.get("clipboard_matches"),
                "copy_summary_button_count": launch_secret_scan_provenance.get("copySummaryButtonCount"),
                "copy_refresh_button_count": launch_secret_scan_provenance.get("copyRefreshButtonCount"),
                "secret_gaps": launch_secret_scan_secret_gaps,
                "keyboard_secret_gaps": launch_secret_scan_keyboard_secret_gaps,
                "keyboard_gaps": launch_secret_scan_keyboard_gaps,
                "summary_copy_gaps": launch_secret_scan_summary_copy_detail.get("gaps", []),
                "summary_copy_secret_gaps": launch_secret_scan_summary_copy_detail.get("secret_gaps", []),
            }
        _record_check(
            checks,
            "operator_launch_secret_scan_artifact_view",
            launch_secret_scan_view_ok,
            launch_secret_scan_view_detail,
        )

        launch_secret_scan_refresh_buttons = page.locator(
            "[aria-label='Copy launch secret scan refresh command']"
        )
        launch_secret_scan_refresh_button_count = launch_secret_scan_refresh_buttons.count()
        launch_secret_scan_refresh_detail: dict[str, Any] = {
            "copy_button_count": launch_secret_scan_refresh_button_count,
            "launch_secret_scan_refresh_command_present": bool(launch_secret_scan_refresh_command),
        }
        launch_secret_scan_refresh_ok = (
            launch_secret_scan_refresh_button_count >= 1
            if launch_secret_scan_refresh_command
            else launch_secret_scan_refresh_button_count == 0
        )
        if launch_secret_scan_refresh_button_count:
            launch_secret_scan_refresh_button = launch_secret_scan_refresh_buttons.first
            initial_launch_secret_scan_refresh_copy_text = launch_secret_scan_refresh_button.inner_text(
                timeout=timeout_ms
            ).strip()
            launch_secret_scan_refresh_text = launch_secret_scan_refresh_button.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            launch_secret_scan_refresh_button.click()
            launch_secret_scan_refresh_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy launch secret scan refresh command']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                launch_secret_scan_refresh_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            launch_secret_scan_refresh_clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            launch_secret_scan_refresh_detail.update(
                {
                    "launch_secret_scan_refresh_command": launch_secret_scan_refresh_text[:280],
                    "initial_button_text": initial_launch_secret_scan_refresh_copy_text,
                    "button_text": launch_secret_scan_refresh_button.inner_text(timeout=timeout_ms),
                    "copy_feedback_seen": launch_secret_scan_refresh_feedback_seen,
                    "clipboard_matches": bool(
                        launch_secret_scan_refresh_text
                        and launch_secret_scan_refresh_clipboard_text == launch_secret_scan_refresh_text
                    ),
                }
            )
            launch_secret_scan_refresh_ok = (
                launch_secret_scan_refresh_ok
                and bool(launch_secret_scan_refresh_text)
                and launch_secret_scan_refresh_text == launch_secret_scan_refresh_command
                and "getdaytrends_launch_secret_scan.py" in launch_secret_scan_refresh_text
                and "--include-current-artifacts" in launch_secret_scan_refresh_text
                and "--json-out" in launch_secret_scan_refresh_text
                and "getdaytrends-launch-secret-scan-final-" in launch_secret_scan_refresh_text
                and launch_secret_scan_refresh_clipboard_text == launch_secret_scan_refresh_text
                and initial_launch_secret_scan_refresh_copy_text == "Copy command"
            )
        _record_check(
            checks,
            "operator_launch_secret_scan_refresh_copy",
            launch_secret_scan_refresh_ok,
            launch_secret_scan_refresh_detail,
        )

        credential_status_buttons = page.locator("[aria-label='Copy credential input status path']")
        credential_status_button_count = credential_status_buttons.count()
        credential_status_detail: dict[str, Any] = {
            "copy_button_count": credential_status_button_count,
            "credential_input_status_path_present": bool(credential_input_status_path),
        }
        credential_status_ok = (
            credential_status_button_count >= 1 if credential_input_status_path else credential_status_button_count == 0
        )
        if credential_status_button_count:
            credential_status_button = credential_status_buttons.first
            initial_credential_status_copy_text = credential_status_button.inner_text(timeout=timeout_ms).strip()
            credential_status_text = credential_status_button.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            credential_status_dom_note_labels = page.locator(
                "#operator-artifacts [data-artifact-key='credential_input_status'] .operator-action-note"
            ).evaluate_all("""nodes => nodes.map(node => (node.innerText || '').trim()).filter(Boolean)""")
            credential_status_button.click()
            credential_status_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy credential input status path']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                credential_status_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            credential_status_clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            note_labels = _artifact_note_labels(credential_input_status_action)
            credential_status_detail.update(
                {
                    "credential_input_status_path": credential_status_text[:240],
                    "initial_button_text": initial_credential_status_copy_text,
                    "button_text": credential_status_button.inner_text(timeout=timeout_ms),
                    "copy_feedback_seen": credential_status_feedback_seen,
                    "clipboard_matches": bool(
                        credential_status_text and credential_status_clipboard_text == credential_status_text
                    ),
                    "note_labels": note_labels,
                    "dom_note_labels": credential_status_dom_note_labels,
                    "expected_note_labels": credential_status_expected_note_labels,
                    "expected_note_error": credential_status_note_error,
                    "json_path": credential_input_status_json_path,
                    "json_required": credential_status_json_required,
                    "json_ok": credential_status_json_ok,
                }
            )
            credential_status_ok = (
                credential_status_ok
                and bool(credential_status_text)
                and credential_status_text == credential_input_status_path
                and "GETDAYTRENDS_CREDENTIAL_INPUT_STATUS" in credential_status_text
                and credential_status_clipboard_text == credential_status_text
                and initial_credential_status_copy_text == "Copy path"
                and any(label in {"credential inputs: none staged", "credential inputs: staged"} for label in note_labels)
                and credential_status_json_ok
                and all(label in note_labels for label in credential_status_expected_note_labels)
                and all(label in credential_status_dom_note_labels for label in credential_status_expected_note_labels)
            )
        _record_check(
            checks,
            "operator_credential_input_status_artifact_copy",
            credential_status_ok,
            credential_status_detail,
        )

        readiness_report_buttons = page.locator("[aria-label='Copy readiness report path']")
        readiness_report_button_count = readiness_report_buttons.count()
        readiness_report_detail: dict[str, Any] = {
            "copy_button_count": readiness_report_button_count,
            "readiness_report_path_present": bool(readiness_report_path),
            "readiness_report_json_ok": readiness_report_json_ok,
            "readiness_report_json_error": readiness_report_json_error,
            "readiness_report_json_missing_fields": readiness_report_json_missing_fields,
        }
        readiness_report_ok = (
            readiness_report_button_count >= 1 if readiness_report_path else readiness_report_button_count == 0
        )
        if readiness_report_button_count:
            first_readiness_report_copy = readiness_report_buttons.first
            initial_readiness_report_copy_text = first_readiness_report_copy.inner_text(timeout=timeout_ms).strip()
            readiness_report_text = first_readiness_report_copy.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_readiness_report_copy.click()
            readiness_report_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy readiness report path']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                readiness_report_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            button_text = first_readiness_report_copy.inner_text(timeout=timeout_ms)
            readiness_report_detail.update(
                {
                    "readiness_report_path": readiness_report_text[:240],
                    "initial_button_text": initial_readiness_report_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": readiness_report_feedback_seen,
                    "clipboard_matches": bool(readiness_report_text and clipboard_text == readiness_report_text),
                    "readiness_report_json_ok": readiness_report_json_ok,
                }
            )
            readiness_report_ok = (
                readiness_report_ok
                and bool(readiness_report_text)
                and readiness_report_text == readiness_report_path
                and "readiness_latest.json" in readiness_report_text
                and clipboard_text == readiness_report_text
                and initial_readiness_report_copy_text == "Copy path"
                and readiness_report_json_ok
            )
        _record_check(checks, "operator_readiness_report_copy", readiness_report_ok, readiness_report_detail)

        readiness_report_view_buttons = page.locator("[aria-label='View readiness report']")
        readiness_report_view_button_count = readiness_report_view_buttons.count()
        operator_summary = operator_payload.get("summary") if isinstance(operator_payload.get("summary"), dict) else {}
        readiness_report_failed = int(operator_summary.get("failed") or 0) > 0
        readiness_report_json_summary_matches_operator = (
            readiness_report_json_summary_ok
            and all(
                int(operator_summary.get(key) or 0) == int(readiness_report_json_summary.get(key) or 0)
                for key in ("total", "passed", "failed")
            )
        )
        readiness_report_view_detail: dict[str, Any] = {
            "view_button_count": readiness_report_view_button_count,
            "readiness_report_path_present": bool(readiness_report_path),
            "readiness_report_failed": readiness_report_failed,
            "readiness_report_json_ok": readiness_report_json_ok,
            "readiness_report_json_error": readiness_report_json_error,
            "readiness_report_json_missing_fields": readiness_report_json_missing_fields,
            "readiness_report_json_status": str(readiness_report_json_payload.get("status", "")),
            "readiness_report_json_generated_at": str(readiness_report_json_payload.get("generated_at", "")),
            "readiness_report_json_check_count": len(readiness_report_json_checks)
            if isinstance(readiness_report_json_checks, list)
            else 0,
            "readiness_report_json_summary_matches_operator": readiness_report_json_summary_matches_operator,
        }
        readiness_report_view_ok = (
            readiness_report_view_button_count >= 1 if readiness_report_path else readiness_report_view_button_count == 0
        )
        readiness_action_bundle_copy_detail: dict[str, Any] = {
            "readiness_report_path_present": bool(readiness_report_path),
            "readiness_report_failed": readiness_report_failed,
        }
        readiness_action_bundle_copy_ok = not (readiness_report_path and readiness_report_failed)
        operator_failed_checks = operator_payload.get("blockers")
        if not isinstance(operator_failed_checks, list):
            operator_failed_checks = []

        def _operator_display_check_line(item: Any) -> str:
            if not isinstance(item, dict):
                return ""
            raw_name = str(item.get("name") or "unknown check").strip() or "unknown check"
            display_name = str(item.get("display_name") or "").strip()
            label = f"{display_name} ({raw_name})" if display_name and display_name != raw_name else raw_name
            level = str(item.get("level") or "").strip()
            return f"Check: {label}{f' ({level})' if level else ''}"

        expected_action_check_lines = [
            line for line in (_operator_display_check_line(item) for item in operator_failed_checks) if line
        ]
        expected_recovery_packets = sorted(
            {
                str(item.get("recovery_packet") or "").strip()
                for item in operator_failed_checks
                if isinstance(item, dict) and str(item.get("recovery_packet") or "").strip()
            }
        )
        readiness_failure_comparison_copy_detail: dict[str, Any] = {
            "readiness_report_path_present": bool(readiness_report_path),
            "readiness_report_failed": readiness_report_failed,
        }
        readiness_failure_comparison_copy_ok = not (readiness_report_path and readiness_report_failed)
        readiness_verification_bundle_copy_detail: dict[str, Any] = {
            "readiness_report_path_present": bool(readiness_report_path),
        }
        readiness_verification_bundle_copy_ok = not bool(readiness_report_path)
        if readiness_report_view_button_count:
            first_readiness_report_view = readiness_report_view_buttons.first
            initial_readiness_report_disclosure = first_readiness_report_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        artifact_path: button.getAttribute('data-artifact-path') || '',
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                    };
                }"""
            )
            readiness_report_view_detail["initial_disclosure"] = initial_readiness_report_disclosure
            first_readiness_report_view = page.locator("[aria-controls='operator-readiness-report-preview']").first
            readiness_report_disclosure_keyboard_open_feedback_seen = False
            readiness_report_disclosure_keyboard_collapse_feedback_seen = False
            readiness_report_disclosure_keyboard_open: dict[str, Any] = {}
            readiness_report_disclosure_keyboard_collapsed: dict[str, Any] = {}
            readiness_report_disclosure_keyboard_secret_gaps: list[str] = []
            readiness_report_disclosure_keyboard_gaps: list[str] = []
            first_readiness_report_view.focus()
            page.keyboard.press("Enter")
            try:
                page.wait_for_function(
                    """() => {
                        const button = document.querySelector("[aria-controls='operator-readiness-report-preview']");
                        const target = document.getElementById('operator-readiness-report-preview');
                        return button?.getAttribute('aria-expanded') === 'true'
                            && target
                            && target.hidden === false
                            && (target.innerText || '').includes('Readiness report:');
                    }""",
                    timeout=timeout_ms,
                )
                readiness_report_disclosure_keyboard_open_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            readiness_report_disclosure_keyboard_open = first_readiness_report_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || ''),
                    };
                }"""
            )
            readiness_report_keyboard_preview_text = str(
                readiness_report_disclosure_keyboard_open.get("target_text") or ""
            )
            readiness_report_disclosure_keyboard_secret_gaps = _copy_payload_secret_gaps(
                readiness_report_keyboard_preview_text,
                "readiness report keyboard preview",
            )
            first_readiness_report_view.focus()
            page.keyboard.press("Space")
            try:
                page.wait_for_function(
                    """() => {
                        const button = document.querySelector("[aria-controls='operator-readiness-report-preview']");
                        const target = document.getElementById('operator-readiness-report-preview');
                        return button?.getAttribute('aria-expanded') === 'false'
                            && target
                            && target.hidden === true
                            && (target.innerText || '').trim() === '';
                    }""",
                    timeout=timeout_ms,
                )
                readiness_report_disclosure_keyboard_collapse_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            readiness_report_disclosure_keyboard_collapsed = first_readiness_report_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').trim(),
                    };
                }"""
            )
            if not readiness_report_disclosure_keyboard_open_feedback_seen:
                readiness_report_disclosure_keyboard_gaps.append(
                    "readiness report disclosure Enter activation did not expand"
                )
            if readiness_report_disclosure_keyboard_open.get("label") != "Hide readiness report":
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard open label changed")
            if readiness_report_disclosure_keyboard_open.get("text") != "Hide report":
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard open text changed")
            if readiness_report_disclosure_keyboard_open.get("expanded") != "true":
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard open aria-expanded mismatch")
            if readiness_report_disclosure_keyboard_open.get("target_exists") is not True:
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard preview missing")
            if readiness_report_disclosure_keyboard_open.get("target_hidden") is not False:
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard preview stayed hidden")
            if "Readiness report:" not in readiness_report_keyboard_preview_text:
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard preview missing heading")
            if readiness_report_failed and "Failed checks:" not in readiness_report_keyboard_preview_text:
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard preview missing failed checks")
            if not readiness_report_disclosure_keyboard_collapse_feedback_seen:
                readiness_report_disclosure_keyboard_gaps.append(
                    "readiness report disclosure Space activation did not collapse"
                )
            if readiness_report_disclosure_keyboard_collapsed.get("label") != "View readiness report":
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard collapsed label changed")
            if readiness_report_disclosure_keyboard_collapsed.get("text") != "View report":
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard collapsed text changed")
            if readiness_report_disclosure_keyboard_collapsed.get("expanded") != "false":
                readiness_report_disclosure_keyboard_gaps.append(
                    "readiness report keyboard collapsed aria-expanded mismatch"
                )
            if readiness_report_disclosure_keyboard_collapsed.get("target_exists") is not True:
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard collapsed preview missing")
            if readiness_report_disclosure_keyboard_collapsed.get("target_hidden") is not True:
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard collapse did not hide preview")
            if readiness_report_disclosure_keyboard_collapsed.get("target_text") != "":
                readiness_report_disclosure_keyboard_gaps.append("readiness report keyboard collapse left preview text")
            readiness_report_disclosure_keyboard_gaps.extend(readiness_report_disclosure_keyboard_secret_gaps)
            if first_readiness_report_view.get_attribute("aria-expanded") == "true":
                first_readiness_report_view.click()
                page.wait_for_timeout(120)
            first_readiness_report_view.click()
            try:
                page.wait_for_function(
                    "() => (document.querySelector('.operator-readiness-report-preview')?.innerText || '').includes('Readiness report:')",
                    timeout=timeout_ms,
                )
            except PlaywrightTimeoutError:
                pass
            readiness_report_preview = page.locator(".operator-readiness-report-preview").first
            readiness_report_preview_text = readiness_report_preview.inner_text(timeout=timeout_ms)
            readiness_report_provenance = readiness_report_preview.evaluate(
                """preview => {
                    const generated = preview.querySelector('time');
                    const spans = Array.from(preview.querySelectorAll('span'));
                    const artifactLine = spans.find(item => (item.innerText || '').startsWith('Artifact:'));
                    const summaryLine = spans.find(item => (item.innerText || '').startsWith('Summary:'));
                    const failedLine = spans.find(item => (item.innerText || '').startsWith('Failed checks:'));
                    const verificationCwdLine = spans.find(item => (item.innerText || '').startsWith('Verification cwd:'));
                    const blockerLine = spans.find(item => (item.innerText || '').startsWith('Blocker:'));
                    const actionLine = spans.find(item => (item.innerText || '').startsWith('Action:'));
                    const diagnosticsLine = spans.find(item => (item.innerText || '').startsWith('Diagnostics:'));
                    const actionGroup = preview.querySelector('.operator-packet-action-group[aria-label="Readiness report copy actions"]');
                    const actionButtons = Array.from(actionGroup?.querySelectorAll('button') || []).map(button => {
                        const rect = button.getBoundingClientRect();
                        return {
                            text: (button.innerText || '').trim(),
                            ariaLabel: button.getAttribute('aria-label') || '',
                            type: button.getAttribute('type') || '',
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                        };
                    });
                    return {
                        generatedText: (generated?.innerText || '').trim(),
                        generatedDateTime: generated?.getAttribute('datetime') || '',
                        artifactText: (artifactLine?.innerText || '').trim(),
                        summaryText: (summaryLine?.innerText || '').trim(),
                        failedText: (failedLine?.innerText || '').trim(),
                        verificationCwdText: (verificationCwdLine?.innerText || '').trim(),
                        blockerText: (blockerLine?.innerText || '').trim(),
                        actionText: (actionLine?.querySelector('code')?.innerText || '').trim(),
                        diagnosticsText: (diagnosticsLine?.querySelector('samp')?.innerText || '').trim(),
                        codeCount: preview.querySelectorAll('code').length,
                        sampleOutputCount: preview.querySelectorAll('samp').length,
                        actionGroup: {
                            role: actionGroup?.getAttribute('role') || '',
                            label: actionGroup?.getAttribute('aria-label') || '',
                            buttonTexts: actionButtons.map(button => button.text),
                            buttonLabels: actionButtons.map(button => button.ariaLabel),
                            buttonTypes: actionButtons.map(button => button.type),
                            minButtonHeight: actionButtons.length ? Math.min(...actionButtons.map(button => button.height)) : 0,
                            buttons: actionButtons,
                        },
                    };
                }"""
            )
            expected_readiness_preview_button_texts = []
            expected_readiness_preview_button_labels = []
            if readiness_report_failed:
                expected_readiness_preview_button_texts.extend(
                    ["Copy readiness actions", "Copy failure comparison"]
                )
                expected_readiness_preview_button_labels.extend(
                    ["Copy readiness action bundle", "Copy readiness failure comparison"]
                )
            if readiness_report_path:
                expected_readiness_preview_button_texts.append("Copy readiness verification bundle")
                expected_readiness_preview_button_labels.append("Copy readiness verification bundle")
            readiness_preview_action_group = readiness_report_provenance.get("actionGroup", {})
            readiness_preview_action_group_ok = (
                isinstance(readiness_preview_action_group, dict)
                and readiness_preview_action_group.get("role") == "group"
                and readiness_preview_action_group.get("label") == "Readiness report copy actions"
                and readiness_preview_action_group.get("buttonTexts") == expected_readiness_preview_button_texts
                and readiness_preview_action_group.get("buttonLabels") == expected_readiness_preview_button_labels
                and int(readiness_preview_action_group.get("minButtonHeight") or 0) >= 28
                and all(
                    button_type == "button"
                    for button_type in readiness_preview_action_group.get("buttonTypes", [])
                )
            )
            readiness_report_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", readiness_report_preview_text, re.IGNORECASE):
                readiness_report_secret_gaps.append("preview contains raw postgres URL")
            if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", readiness_report_preview_text, re.IGNORECASE):
                readiness_report_secret_gaps.append("preview contains raw tenant user")
            if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", readiness_report_preview_text):
                readiness_report_secret_gaps.append("preview contains raw OpenAI-style key")
            if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", readiness_report_preview_text):
                readiness_report_secret_gaps.append("preview contains raw Google API-style key")
            readiness_action_bundle_buttons = page.locator("[aria-label='Copy readiness action bundle']")
            readiness_action_bundle_button_count = readiness_action_bundle_buttons.count()
            readiness_action_bundle_copy_detail["copy_button_count"] = readiness_action_bundle_button_count
            readiness_action_bundle_copy_ok = (
                readiness_action_bundle_button_count >= 1
                if readiness_report_failed
                else readiness_action_bundle_button_count == 0
            )
            if readiness_action_bundle_button_count:
                readiness_action_bundle_button = readiness_action_bundle_buttons.first
                initial_readiness_action_bundle_text = readiness_action_bundle_button.inner_text(
                    timeout=timeout_ms
                ).strip()
                readiness_action_bundle_text = readiness_action_bundle_button.evaluate(
                    "(button) => String(button.dataset.copyText || '').trim()"
                )
                readiness_action_bundle_expected = readiness_action_bundle_text.replace("\\n", "\n")
                readiness_action_bundle_button.click()
                readiness_action_bundle_feedback_seen = False
                try:
                    page.wait_for_function(
                        "() => (document.querySelector(\"[aria-label='Copy readiness action bundle']\")?.innerText || '').trim() === 'Copied'",
                        timeout=timeout_ms,
                    )
                    readiness_action_bundle_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                clipboard_text = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                clipboard_normalized = clipboard_text.replace("\r\n", "\n").replace("\r", "\n").strip()
                action_bundle_secret_gaps = []
                if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", clipboard_normalized, re.IGNORECASE):
                    action_bundle_secret_gaps.append("clipboard contains raw postgres URL")
                if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", clipboard_normalized, re.IGNORECASE):
                    action_bundle_secret_gaps.append("clipboard contains raw tenant user")
                if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", clipboard_normalized):
                    action_bundle_secret_gaps.append("clipboard contains raw OpenAI-style key")
                if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", clipboard_normalized):
                    action_bundle_secret_gaps.append("clipboard contains raw Google API-style key")
                missing_action_check_lines = [
                    line for line in expected_action_check_lines if line not in clipboard_normalized
                ]
                button_text = readiness_action_bundle_button.inner_text(timeout=timeout_ms)
                readiness_action_bundle_copy_detail.update(
                    {
                        "bundle_preview": readiness_action_bundle_text[:500],
                        "initial_button_text": initial_readiness_action_bundle_text,
                        "button_text": button_text,
                        "copy_feedback_seen": readiness_action_bundle_feedback_seen,
                        "clipboard_matches": bool(
                            readiness_action_bundle_expected
                            and clipboard_normalized == readiness_action_bundle_expected
                        ),
                        "secret_gaps": action_bundle_secret_gaps,
                        "expected_check_lines": expected_action_check_lines,
                        "missing_check_lines": missing_action_check_lines,
                    }
                )
                readiness_action_bundle_copy_ok = (
                    readiness_action_bundle_copy_ok
                    and bool(readiness_action_bundle_expected)
                    and clipboard_normalized == readiness_action_bundle_expected
                    and "Readiness report:" in clipboard_normalized
                    and "Failed checks:" in clipboard_normalized
                    and "Compare packet:" in clipboard_normalized
                    and "Action:" in clipboard_normalized
                    and readiness_report_path in clipboard_normalized
                    and not action_bundle_secret_gaps
                    and not missing_action_check_lines
                    and initial_readiness_action_bundle_text == "Copy readiness actions"
                )
            readiness_failure_comparison_buttons = page.locator(
                "[aria-label='Copy readiness failure comparison']"
            )
            readiness_failure_comparison_button_count = readiness_failure_comparison_buttons.count()
            readiness_failure_comparison_copy_detail["copy_button_count"] = (
                readiness_failure_comparison_button_count
            )
            readiness_failure_comparison_copy_ok = (
                readiness_failure_comparison_button_count >= 1
                if readiness_report_failed
                else readiness_failure_comparison_button_count == 0
            )
            if readiness_failure_comparison_button_count:
                readiness_failure_comparison_button = readiness_failure_comparison_buttons.first
                initial_failure_comparison_text = readiness_failure_comparison_button.inner_text(
                    timeout=timeout_ms
                ).strip()
                failure_comparison_text = readiness_failure_comparison_button.evaluate(
                    "(button) => String(button.dataset.copyText || '').trim()"
                )
                failure_comparison_expected = failure_comparison_text.replace("\\n", "\n")
                readiness_failure_comparison_button.click()
                failure_comparison_feedback_seen = False
                try:
                    page.wait_for_function(
                        "() => (document.querySelector(\"[aria-label='Copy readiness failure comparison']\")?.innerText || '').trim() === 'Copied'",
                        timeout=timeout_ms,
                    )
                    failure_comparison_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                failure_comparison_copy_result = readiness_failure_comparison_button.evaluate(
                    "(button) => String(button.dataset.copyResult || '')"
                )
                failure_comparison_clipboard_error = ""
                try:
                    failure_comparison_clipboard_text = page.evaluate(
                        """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                    )
                except Exception as exc:
                    failure_comparison_clipboard_text = ""
                    failure_comparison_clipboard_error = str(exc)
                failure_comparison_clipboard_normalized = (
                    failure_comparison_clipboard_text.replace("\r\n", "\n").replace("\r", "\n").strip()
                )
                failure_comparison_observed = (
                    failure_comparison_clipboard_normalized
                    if failure_comparison_clipboard_normalized
                    else failure_comparison_expected
                    if failure_comparison_copy_result == "copied"
                    else ""
                )
                failure_comparison_secret_gaps = []
                if re.search(
                    r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+",
                    failure_comparison_observed,
                    re.IGNORECASE,
                ):
                    failure_comparison_secret_gaps.append("clipboard contains raw postgres URL")
                if re.search(
                    r"\btenant/user\s+(?!\*\*\*)[^\s),;]+",
                    failure_comparison_observed,
                    re.IGNORECASE,
                ):
                    failure_comparison_secret_gaps.append("clipboard contains raw tenant user")
                if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", failure_comparison_observed):
                    failure_comparison_secret_gaps.append("clipboard contains raw OpenAI-style key")
                if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", failure_comparison_observed):
                    failure_comparison_secret_gaps.append("clipboard contains raw Google API-style key")
                missing_comparison_check_lines = [
                    line for line in expected_action_check_lines if line not in failure_comparison_observed
                ]
                missing_recovery_packets = [
                    path for path in expected_recovery_packets if path not in failure_comparison_observed
                ]
                failure_comparison_button_text = readiness_failure_comparison_button.inner_text(
                    timeout=timeout_ms
                )
                readiness_failure_comparison_copy_detail.update(
                    {
                        "bundle_preview": failure_comparison_text[:500],
                        "initial_button_text": initial_failure_comparison_text,
                        "button_text": failure_comparison_button_text,
                        "copy_feedback_seen": failure_comparison_feedback_seen,
                        "copy_result": failure_comparison_copy_result,
                        "clipboard_error": failure_comparison_clipboard_error,
                        "clipboard_matches": bool(
                            failure_comparison_expected
                            and failure_comparison_observed == failure_comparison_expected
                        ),
                        "secret_gaps": failure_comparison_secret_gaps,
                        "expected_check_lines": expected_action_check_lines,
                        "missing_check_lines": missing_comparison_check_lines,
                        "expected_recovery_packets": expected_recovery_packets,
                        "missing_recovery_packets": missing_recovery_packets,
                    }
                )
                readiness_failure_comparison_copy_ok = (
                    readiness_failure_comparison_copy_ok
                    and bool(failure_comparison_expected)
                    and failure_comparison_observed == failure_comparison_expected
                    and failure_comparison_copy_result == "copied"
                    and "Readiness failure comparison:" in failure_comparison_observed
                    and "Compare packet:" in failure_comparison_observed
                    and "Supabase recovery packet" in failure_comparison_observed
                    and readiness_report_path in failure_comparison_observed
                    and not failure_comparison_secret_gaps
                    and not missing_comparison_check_lines
                    and not missing_recovery_packets
                    and initial_failure_comparison_text == "Copy failure comparison"
                )
            readiness_verification_bundle_buttons = page.locator(
                "[aria-label='Copy readiness verification bundle']"
            )
            readiness_verification_bundle_button_count = readiness_verification_bundle_buttons.count()
            readiness_verification_bundle_copy_detail["copy_button_count"] = (
                readiness_verification_bundle_button_count
            )
            readiness_verification_bundle_copy_ok = (
                readiness_verification_bundle_button_count >= 1
                if readiness_report_path
                else readiness_verification_bundle_button_count == 0
            )
            if readiness_verification_bundle_button_count:
                readiness_verification_bundle_button = readiness_verification_bundle_buttons.first
                initial_readiness_verification_bundle_text = readiness_verification_bundle_button.inner_text(
                    timeout=timeout_ms
                ).strip()
                readiness_verification_bundle_text = readiness_verification_bundle_button.evaluate(
                    "(button) => String(button.dataset.copyText || '').trim()"
                )
                readiness_verification_bundle_expected = (
                    readiness_verification_bundle_text.replace("\\n", "\n")
                    .replace("\r\n", "\n")
                    .replace("\r", "\n")
                    .strip()
                )
                readiness_verification_bundle_button.click()
                readiness_verification_bundle_feedback_seen = False
                try:
                    page.wait_for_function(
                        "() => (document.querySelector(\"[aria-label='Copy readiness verification bundle']\")?.innerText || '').trim() === 'Copied'",
                        timeout=timeout_ms,
                    )
                    readiness_verification_bundle_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                verification_clipboard_text = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                verification_clipboard_normalized = (
                    verification_clipboard_text.replace("\r\n", "\n").replace("\r", "\n").strip()
                )
                verification_bundle_secret_gaps = []
                if re.search(
                    r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+",
                    verification_clipboard_normalized,
                    re.IGNORECASE,
                ):
                    verification_bundle_secret_gaps.append("clipboard contains raw postgres URL")
                if re.search(
                    r"\btenant/user\s+(?!\*\*\*)[^\s),;]+",
                    verification_clipboard_normalized,
                    re.IGNORECASE,
                ):
                    verification_bundle_secret_gaps.append("clipboard contains raw tenant user")
                if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", verification_clipboard_normalized):
                    verification_bundle_secret_gaps.append("clipboard contains raw OpenAI-style key")
                if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", verification_clipboard_normalized):
                    verification_bundle_secret_gaps.append("clipboard contains raw Google API-style key")
                verification_required_fragments = [
                    "Set-Location -LiteralPath",
                    str(PROJECT_ROOT),
                    "smoke_cli.py --include-dry-run",
                    "browser_smoke.py --timeout 45",
                    "--tap-source-fixture",
                    "check_text_hygiene.py",
                    "getdaytrends_launch_secret_scan.py",
                    "--include-current-artifacts",
                    "getdaytrends-launch-secret-scan-final-",
                    "readiness_check.py",
                    "--fail-on-runtime-fallback",
                    "--require-live-db",
                    "run_workspace_smoke.py --scope getdaytrends",
                    "workspace-smoke-getdaytrends-post-credential.json",
                ]
                verification_missing_fragments = [
                    item
                    for item in verification_required_fragments
                    if item not in verification_clipboard_normalized
                ]
                verification_first_line = verification_clipboard_normalized.splitlines()[0].strip()
                verification_starts_in_workdir = verification_first_line.startswith("Set-Location -LiteralPath")
                readiness_verification_bundle_copy_detail.update(
                    {
                        "bundle_preview": readiness_verification_bundle_text[:500],
                        "initial_button_text": initial_readiness_verification_bundle_text,
                        "first_line": verification_first_line,
                        "copy_feedback_seen": readiness_verification_bundle_feedback_seen,
                        "clipboard_matches": bool(
                            readiness_verification_bundle_expected
                            and verification_clipboard_normalized == readiness_verification_bundle_expected
                        ),
                        "starts_in_workdir": verification_starts_in_workdir,
                        "missing_fragments": verification_missing_fragments,
                        "secret_gaps": verification_bundle_secret_gaps,
                    }
                )
                readiness_verification_bundle_copy_ok = (
                    readiness_verification_bundle_copy_ok
                    and bool(readiness_verification_bundle_expected)
                    and verification_clipboard_normalized == readiness_verification_bundle_expected
                    and verification_starts_in_workdir
                    and not verification_missing_fragments
                    and "workspace-smoke-getdaytrends-launch-final.json" not in verification_clipboard_normalized
                    and not verification_bundle_secret_gaps
                    and initial_readiness_verification_bundle_text == "Copy readiness verification bundle"
                )
            first_readiness_report_view = page.locator("[aria-controls='operator-readiness-report-preview']").first
            readiness_report_disclosure = first_readiness_report_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').slice(0, 500),
                    };
                }"""
            )
            first_readiness_report_view.click()
            page.wait_for_timeout(120)
            readiness_report_collapsed_disclosure = first_readiness_report_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').trim(),
                    };
                }"""
            )
            readiness_report_view_detail["preview_text"] = readiness_report_preview_text[:500]
            readiness_report_view_detail["provenance"] = readiness_report_provenance
            readiness_report_view_detail["action_group"] = readiness_preview_action_group
            readiness_report_view_detail["expected_action_group_texts"] = expected_readiness_preview_button_texts
            readiness_report_view_detail["secret_gaps"] = readiness_report_secret_gaps
            readiness_report_view_detail["keyboard_open_feedback_seen"] = (
                readiness_report_disclosure_keyboard_open_feedback_seen
            )
            readiness_report_view_detail["keyboard_collapse_feedback_seen"] = (
                readiness_report_disclosure_keyboard_collapse_feedback_seen
            )
            readiness_report_view_detail["keyboard_open_disclosure"] = {
                **readiness_report_disclosure_keyboard_open,
                "target_text": readiness_report_keyboard_preview_text[:500],
            }
            readiness_report_view_detail["keyboard_collapsed_disclosure"] = (
                readiness_report_disclosure_keyboard_collapsed
            )
            readiness_report_view_detail["keyboard_secret_gaps"] = readiness_report_disclosure_keyboard_secret_gaps
            readiness_report_view_detail["keyboard_gaps"] = readiness_report_disclosure_keyboard_gaps
            readiness_report_view_detail["disclosure"] = readiness_report_disclosure
            readiness_report_view_detail["collapsed_disclosure"] = readiness_report_collapsed_disclosure
            readiness_report_failed_detail_ok = (
                not readiness_report_failed
                or (
                    "Failed checks:" in readiness_report_preview_text
                    and "Blocker:" in readiness_report_preview_text
                    and bool(readiness_report_provenance.get("blockerText"))
                    and not readiness_report_secret_gaps
                )
            )
            readiness_report_view_ok = (
                readiness_report_view_ok
                and initial_readiness_report_disclosure.get("label") == "View readiness report"
                and initial_readiness_report_disclosure.get("text") == "View report"
                and initial_readiness_report_disclosure.get("expanded") == "false"
                and initial_readiness_report_disclosure.get("controls") == "operator-readiness-report-preview"
                and initial_readiness_report_disclosure.get("target_exists") is True
                and initial_readiness_report_disclosure.get("target_hidden") is True
                and readiness_report_disclosure.get("label") == "Hide readiness report"
                and readiness_report_disclosure.get("text") == "Hide report"
                and readiness_report_disclosure.get("expanded") == "true"
                and readiness_report_disclosure.get("target_exists") is True
                and readiness_report_disclosure.get("target_hidden") is False
                and "Readiness report:" in readiness_report_disclosure.get("target_text", "")
                and readiness_report_collapsed_disclosure.get("label") == "View readiness report"
                and readiness_report_collapsed_disclosure.get("text") == "View report"
                and readiness_report_collapsed_disclosure.get("expanded") == "false"
                and readiness_report_collapsed_disclosure.get("target_exists") is True
                and readiness_report_collapsed_disclosure.get("target_hidden") is True
                and readiness_report_collapsed_disclosure.get("target_text") == ""
                and "Readiness report:" in readiness_report_preview_text
                and "Generated:" in readiness_report_preview_text
                and "Artifact:" in readiness_report_preview_text
                and "Summary:" in readiness_report_preview_text
                and "Verification cwd:" in readiness_report_preview_text
                and readiness_report_path in readiness_report_provenance.get("artifactText", "")
                and str(PROJECT_ROOT) in readiness_report_provenance.get("verificationCwdText", "")
                and bool(readiness_report_provenance.get("generatedText"))
                and readiness_report_provenance.get("generatedDateTime")
                == readiness_report_provenance.get("generatedText")
                and readiness_report_json_ok
                and readiness_report_json_summary_matches_operator
                and str(readiness_report_json_payload.get("generated_at", ""))
                == readiness_report_provenance.get("generatedDateTime")
                and readiness_preview_action_group_ok
                and readiness_report_failed_detail_ok
                and not readiness_report_disclosure_keyboard_gaps
            )
            readiness_report_view_detail = {
                "expected_mode": "operator_readiness_report_disclosure_lifecycle",
                "view_button_count": readiness_report_view_button_count,
                "readiness_report_path_present": bool(readiness_report_path),
                "readiness_report_failed": readiness_report_failed,
                "readiness_report_json_ok": readiness_report_json_ok,
                "readiness_report_json_status": readiness_report_json_payload.get("status", ""),
                "readiness_report_json_check_count": len(readiness_report_json_payload.get("checks", []))
                if isinstance(readiness_report_json_payload.get("checks"), list)
                else 0,
                "readiness_report_json_summary_matches_operator": readiness_report_json_summary_matches_operator,
                "initial_collapsed_ok": (
                    initial_readiness_report_disclosure.get("label") == "View readiness report"
                    and initial_readiness_report_disclosure.get("expanded") == "false"
                    and initial_readiness_report_disclosure.get("controls") == "operator-readiness-report-preview"
                    and initial_readiness_report_disclosure.get("target_exists") is True
                    and initial_readiness_report_disclosure.get("target_hidden") is True
                ),
                "keyboard_open_visible_ok": (
                    readiness_report_disclosure_keyboard_open_feedback_seen
                    and readiness_report_disclosure_keyboard_open.get("label") == "Hide readiness report"
                    and readiness_report_disclosure_keyboard_open.get("expanded") == "true"
                    and readiness_report_disclosure_keyboard_open.get("target_exists") is True
                    and readiness_report_disclosure_keyboard_open.get("target_hidden") is False
                    and "Readiness report:" in readiness_report_keyboard_preview_text
                ),
                "keyboard_collapsed_hidden_ok": (
                    readiness_report_disclosure_keyboard_collapse_feedback_seen
                    and readiness_report_disclosure_keyboard_collapsed.get("label") == "View readiness report"
                    and readiness_report_disclosure_keyboard_collapsed.get("expanded") == "false"
                    and readiness_report_disclosure_keyboard_collapsed.get("target_exists") is True
                    and readiness_report_disclosure_keyboard_collapsed.get("target_hidden") is True
                    and readiness_report_disclosure_keyboard_collapsed.get("target_text") == ""
                ),
                "click_open_visible_ok": (
                    readiness_report_disclosure.get("label") == "Hide readiness report"
                    and readiness_report_disclosure.get("expanded") == "true"
                    and readiness_report_disclosure.get("target_exists") is True
                    and readiness_report_disclosure.get("target_hidden") is False
                    and "Readiness report:" in readiness_report_disclosure.get("target_text", "")
                ),
                "click_collapsed_hidden_ok": (
                    readiness_report_collapsed_disclosure.get("label") == "View readiness report"
                    and readiness_report_collapsed_disclosure.get("expanded") == "false"
                    and readiness_report_collapsed_disclosure.get("target_exists") is True
                    and readiness_report_collapsed_disclosure.get("target_hidden") is True
                    and readiness_report_collapsed_disclosure.get("target_text") == ""
                ),
                "preview_content_ok": (
                    "Readiness report:" in readiness_report_preview_text
                    and "Generated:" in readiness_report_preview_text
                    and "Artifact:" in readiness_report_preview_text
                    and "Summary:" in readiness_report_preview_text
                    and "Verification cwd:" in readiness_report_preview_text
                    and readiness_report_failed_detail_ok
                    and not readiness_report_secret_gaps
                ),
                "action_group_ok": readiness_preview_action_group_ok,
                "action_button_count": len(readiness_preview_action_group.get("buttonTexts", []))
                if isinstance(readiness_preview_action_group, dict)
                else 0,
                "min_action_button_height": int(readiness_preview_action_group.get("minButtonHeight") or 0)
                if isinstance(readiness_preview_action_group, dict)
                else 0,
                "expected_action_group_texts": expected_readiness_preview_button_texts,
                "readiness_report_json_missing_fields": readiness_report_json_missing_fields,
                "secret_gaps": readiness_report_secret_gaps,
                "keyboard_secret_gaps": readiness_report_disclosure_keyboard_secret_gaps,
                "keyboard_gaps": readiness_report_disclosure_keyboard_gaps,
            }
        _record_check(checks, "operator_readiness_report_view", readiness_report_view_ok, readiness_report_view_detail)

        provider_packet_copy_buttons = page.locator("[aria-label='Copy provider recovery packet path']")
        provider_packet_copy_button_count = provider_packet_copy_buttons.count()
        provider_packet_copy_detail: dict[str, Any] = {
            "copy_button_count": provider_packet_copy_button_count,
            "provider_packet_path_present": bool(provider_packet_artifact_path),
            "provider_packet_json_ok": provider_packet_json_ok,
            "provider_packet_json_error": provider_packet_json_error,
            "provider_packet_json_missing_fields": provider_packet_json_missing_fields,
            "provider_packet_launch_success_criteria_count": len(provider_packet_expected_launch_success_criteria),
        }
        provider_packet_copy_ok = (
            provider_packet_copy_button_count >= 1
            if provider_packet_artifact_path
            else provider_packet_copy_button_count == 0
        )
        if provider_packet_copy_button_count:
            first_provider_packet_copy = provider_packet_copy_buttons.first
            initial_provider_packet_copy_text = first_provider_packet_copy.inner_text(timeout=timeout_ms).strip()
            provider_packet_copy_text = first_provider_packet_copy.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_provider_packet_copy.click()
            provider_packet_copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy provider recovery packet path']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                provider_packet_copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            button_text = first_provider_packet_copy.inner_text(timeout=timeout_ms)
            provider_packet_copy_detail.update(
                {
                    "provider_packet_path": provider_packet_copy_text[:240],
                    "initial_button_text": initial_provider_packet_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": provider_packet_copy_feedback_seen,
                    "clipboard_matches": bool(
                        provider_packet_copy_text and clipboard_text == provider_packet_copy_text
                    ),
                }
            )
            provider_packet_copy_ok = (
                provider_packet_copy_ok
                and provider_packet_json_ok
                and bool(provider_packet_copy_text)
                and provider_packet_copy_text == provider_packet_artifact_path
                and "provider_auth_recovery_packet_latest.json" in provider_packet_copy_text
                and clipboard_text == provider_packet_copy_text
                and initial_provider_packet_copy_text == "Copy path"
            )
        _record_check(
            checks,
            "operator_provider_recovery_packet_artifact_copy",
            provider_packet_copy_ok,
            provider_packet_copy_detail,
        )

        provider_packet_view_buttons = page.locator("[aria-controls='operator-provider-recovery-packet-preview']")
        provider_packet_view_button_count = provider_packet_view_buttons.count()
        provider_packet_view_detail: dict[str, Any] = {
            "view_button_count": provider_packet_view_button_count,
            "provider_packet_path_present": bool(provider_packet_artifact_path),
        }
        provider_packet_view_ok = (
            provider_packet_view_button_count >= 1
            if provider_packet_artifact_path
            else provider_packet_view_button_count == 0
        )
        if provider_packet_view_button_count:
            first_provider_packet_view = provider_packet_view_buttons.first
            initial_provider_packet_disclosure = first_provider_packet_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                    };
                }"""
            )
            provider_packet_view_detail["initial_disclosure"] = initial_provider_packet_disclosure
            provider_packet_disclosure_keyboard_open_feedback_seen = False
            provider_packet_disclosure_keyboard_collapse_feedback_seen = False
            provider_packet_disclosure_keyboard_open: dict[str, Any] = {}
            provider_packet_disclosure_keyboard_collapsed: dict[str, Any] = {}
            provider_packet_disclosure_keyboard_secret_gaps: list[str] = []
            provider_packet_disclosure_keyboard_gaps: list[str] = []
            provider_packet_keyboard_expected_status = str(provider_packet_json_payload.get("status") or "").strip()
            first_provider_packet_view.focus()
            page.keyboard.press("Enter")
            try:
                page.wait_for_function(
                    """() => {
                        const button = document.querySelector("[aria-controls='operator-provider-recovery-packet-preview']");
                        const target = document.getElementById('operator-provider-recovery-packet-preview');
                        return button?.getAttribute('aria-expanded') === 'true'
                            && target
                            && target.hidden === false
                            && (target.innerText || '').includes('Packet status:');
                    }""",
                    timeout=timeout_ms,
                )
                provider_packet_disclosure_keyboard_open_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            provider_packet_disclosure_keyboard_open = first_provider_packet_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || ''),
                    };
                }"""
            )
            provider_packet_keyboard_preview_text = str(
                provider_packet_disclosure_keyboard_open.get("target_text") or ""
            )
            provider_packet_disclosure_keyboard_secret_gaps = _copy_payload_secret_gaps(
                provider_packet_keyboard_preview_text,
                "provider packet keyboard preview",
            )
            first_provider_packet_view.focus()
            page.keyboard.press("Space")
            try:
                page.wait_for_function(
                    """() => {
                        const button = document.querySelector("[aria-controls='operator-provider-recovery-packet-preview']");
                        const target = document.getElementById('operator-provider-recovery-packet-preview');
                        return button?.getAttribute('aria-expanded') === 'false'
                            && target
                            && target.hidden === true
                            && (target.innerText || '').trim() === '';
                    }""",
                    timeout=timeout_ms,
                )
                provider_packet_disclosure_keyboard_collapse_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            provider_packet_disclosure_keyboard_collapsed = first_provider_packet_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').trim(),
                    };
                }"""
            )
            if not provider_packet_disclosure_keyboard_open_feedback_seen:
                provider_packet_disclosure_keyboard_gaps.append(
                    "provider packet disclosure Enter activation did not expand"
                )
            if provider_packet_disclosure_keyboard_open.get("label") != "Hide provider recovery packet":
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard open label changed")
            if provider_packet_disclosure_keyboard_open.get("text") != "Hide provider packet":
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard open text changed")
            if provider_packet_disclosure_keyboard_open.get("expanded") != "true":
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard open aria-expanded mismatch")
            if provider_packet_disclosure_keyboard_open.get("target_exists") is not True:
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard preview missing")
            if provider_packet_disclosure_keyboard_open.get("target_hidden") is not False:
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard preview stayed hidden")
            if "Packet status:" not in provider_packet_keyboard_preview_text:
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard preview missing status")
            if provider_packet_keyboard_expected_status and (
                f"Packet status: {provider_packet_keyboard_expected_status}" not in provider_packet_keyboard_preview_text
            ):
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard preview missing expected status")
            if not provider_packet_disclosure_keyboard_collapse_feedback_seen:
                provider_packet_disclosure_keyboard_gaps.append(
                    "provider packet disclosure Space activation did not collapse"
                )
            if provider_packet_disclosure_keyboard_collapsed.get("label") != "View provider recovery packet":
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard collapsed label changed")
            if provider_packet_disclosure_keyboard_collapsed.get("text") != "View provider packet":
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard collapsed text changed")
            if provider_packet_disclosure_keyboard_collapsed.get("expanded") != "false":
                provider_packet_disclosure_keyboard_gaps.append(
                    "provider packet keyboard collapsed aria-expanded mismatch"
                )
            if provider_packet_disclosure_keyboard_collapsed.get("target_exists") is not True:
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard collapsed preview missing")
            if provider_packet_disclosure_keyboard_collapsed.get("target_hidden") is not True:
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard collapse did not hide preview")
            if provider_packet_disclosure_keyboard_collapsed.get("target_text") != "":
                provider_packet_disclosure_keyboard_gaps.append("provider packet keyboard collapse left preview text")
            provider_packet_disclosure_keyboard_gaps.extend(provider_packet_disclosure_keyboard_secret_gaps)
            if first_provider_packet_view.get_attribute("aria-expanded") == "true":
                first_provider_packet_view.click()
                page.wait_for_timeout(120)
            first_provider_packet_view.click()
            try:
                page.wait_for_function(
                    "() => (document.getElementById('operator-provider-recovery-packet-preview')?.innerText || '').includes('Packet status:')",
                    timeout=timeout_ms,
                )
            except PlaywrightTimeoutError:
                pass
            provider_packet_preview = page.locator("#operator-provider-recovery-packet-preview").first
            provider_packet_preview_text = provider_packet_preview.inner_text(timeout=timeout_ms)
            provider_packet_is_clear = "Packet status: clear" in provider_packet_preview_text
            provider_packet_is_blocked = "Packet status: blocked" in provider_packet_preview_text
            provider_packet_preview_gaps = (
                _provider_recovery_preview_gaps(provider_packet_preview_text) if provider_packet_is_blocked else []
            )
            provider_packet_expected_status = str(provider_packet_json_payload.get("status") or "").strip()
            provider_packet_expected_next_action = str(
                provider_packet_json_payload.get("next_required_action") or ""
            ).strip()
            provider_packet_expected_recovery_summary = str(
                provider_packet_json_payload.get("recovery_summary") or ""
            ).strip()
            provider_packet_expected_evidence_freshness = str(
                provider_packet_json_payload.get("evidence_freshness_summary") or ""
            ).strip()
            provider_packet_expected_verification_bundle = str(
                provider_packet_json_payload.get("verification_command_bundle") or ""
            ).strip()
            provider_packet_expected_auth_failure_count = provider_packet_json_payload.get(
                "provider_auth_failure_count"
            )
            provider_packet_preview_missing_fragments = [
                fragment
                for fragment in (
                    f"Packet status: {provider_packet_expected_status}",
                    provider_packet_expected_next_action,
                    *provider_packet_expected_launch_success_criteria,
                )
                if fragment and fragment not in provider_packet_preview_text
            ]
            if isinstance(provider_packet_expected_auth_failure_count, int):
                expected_failure_fragment = f"Provider auth failures: {provider_packet_expected_auth_failure_count}"
                if expected_failure_fragment not in provider_packet_preview_text:
                    provider_packet_preview_missing_fragments.append(expected_failure_fragment)
            provider_packet_disclosure = first_provider_packet_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').trim(),
                    };
                }"""
            )
            provider_packet_bundle_buttons = page.locator(
                "#operator-provider-recovery-packet-preview [aria-label='Copy complete recovery bundle']"
            )
            provider_packet_bundle_button_count = provider_packet_bundle_buttons.count()
            provider_packet_denied_feedback_seen = False
            provider_packet_denied_state: dict[str, Any] = {}
            provider_packet_denied_reset_state: dict[str, Any] = {}
            provider_packet_denied_escape_state: dict[str, Any] = {}
            provider_packet_bundle_text = ""
            provider_packet_bundle_gaps: list[str] = []
            if provider_packet_bundle_button_count:
                provider_packet_bundle_button = provider_packet_bundle_buttons.first
                provider_packet_bundle_text = provider_packet_bundle_button.evaluate(
                    "(button) => String(button.dataset.copyText || '').replace(/\\\\n/g, '\\n')"
                )
                provider_packet_bundle_gaps = _provider_recovery_bundle_gaps(provider_packet_bundle_text)
                provider_packet_bundle_missing_fragments = [
                    fragment
                    for fragment in (
                        provider_packet_expected_next_action,
                        provider_packet_expected_recovery_summary,
                        provider_packet_expected_evidence_freshness,
                        provider_packet_expected_verification_bundle,
                        *provider_packet_expected_launch_success_criteria,
                    )
                    if fragment and fragment not in provider_packet_bundle_text
                ]
                provider_packet_bundle_button.evaluate(
                    """button => {
                        hideManualCopy({ restoreFocus: false });
                        button.innerText = 'Copy recovery bundle';
                        delete button.dataset.copyResult;
                        window.__gdtProviderPacketDeniedOriginals = {
                            clipboardDescriptor: Object.getOwnPropertyDescriptor(Navigator.prototype, 'clipboard'),
                            execCommand: document.execCommand,
                        };
                        window.__gdtProviderPacketDeniedExecCommandCalled = false;
                        Object.defineProperty(Navigator.prototype, 'clipboard', {
                            configurable: true,
                            get() {
                                return {
                                    writeText: async () => {
                                        throw new DOMException('Write permission denied.', 'NotAllowedError');
                                    },
                                    readText: async () => 'unchanged clipboard',
                                };
                            },
                        });
                        document.execCommand = () => {
                            window.__gdtProviderPacketDeniedExecCommandCalled = true;
                            return true;
                        };
                        button.focus();
                    }"""
                )
                try:
                    provider_packet_bundle_button.click()
                    try:
                        page.wait_for_function(
                            """() => document.querySelector("#operator-provider-recovery-packet-preview [aria-label='Copy complete recovery bundle']")?.dataset.copyResult === 'failed'
                                && document.getElementById('manual-copy-panel')?.classList.contains('show')
                                && document.getElementById('manual-copy-panel')?.hidden === false
                                && (document.getElementById('manual-copy-text')?.value || '').trim().length > 0
                                && (document.getElementById('toast')?.textContent || '').includes('Copy failed')""",
                            timeout=timeout_ms,
                        )
                        provider_packet_denied_feedback_seen = True
                    except PlaywrightTimeoutError:
                        pass
                    provider_packet_denied_state = page.evaluate(
                        """() => {
                            const button = document.querySelector("#operator-provider-recovery-packet-preview [aria-label='Copy complete recovery bundle']");
                            const panel = document.getElementById('manual-copy-panel');
                            const textarea = document.getElementById('manual-copy-text');
                            const toast = document.getElementById('toast');
                            return {
                                buttonText: (button?.innerText || '').trim(),
                                originalText: button?.dataset.copyOriginalText || '',
                                copyResult: button?.dataset.copyResult || '',
                                priority: button?.getAttribute('data-copy-priority') || '',
                                className: button?.className || '',
                                manualVisible: panel?.classList.contains('show') || false,
                                manualHidden: panel?.hidden ?? null,
                                manualText: textarea?.value || '',
                                activeId: document.activeElement?.id || '',
                                activeLabel: document.activeElement?.getAttribute('aria-label') || '',
                                toastText: toast?.textContent || '',
                                toastType: toast?.dataset.lastToastType || '',
                                toastRole: toast?.dataset.lastToastRole || '',
                                toastLive: toast?.dataset.lastToastLive || '',
                                execCommandCalled: Boolean(window.__gdtProviderPacketDeniedExecCommandCalled),
                            };
                        }"""
                    )
                    page.wait_for_timeout(1700)
                    provider_packet_denied_reset_state = page.evaluate(
                        """() => {
                            const button = document.querySelector("#operator-provider-recovery-packet-preview [aria-label='Copy complete recovery bundle']");
                            const panel = document.getElementById('manual-copy-panel');
                            const textarea = document.getElementById('manual-copy-text');
                            return {
                                buttonText: (button?.innerText || '').trim(),
                                originalText: button?.dataset.copyOriginalText || '',
                                copyResult: button?.dataset.copyResult || '',
                                manualVisible: panel?.classList.contains('show') || false,
                                manualHidden: panel?.hidden ?? null,
                                manualTextLength: (textarea?.value || '').trim().length,
                                activeId: document.activeElement?.id || '',
                                activeLabel: document.activeElement?.getAttribute('aria-label') || '',
                            };
                        }"""
                    )
                    page.keyboard.press("Escape")
                    try:
                        page.wait_for_function(
                            """() => !document.getElementById('manual-copy-panel')?.classList.contains('show')
                                && document.getElementById('manual-copy-panel')?.hidden === true
                                && (document.getElementById('manual-copy-text')?.value || '') === ''
                                && document.activeElement === document.querySelector("#operator-provider-recovery-packet-preview [aria-label='Copy complete recovery bundle']")""",
                            timeout=timeout_ms,
                        )
                    except PlaywrightTimeoutError:
                        pass
                    provider_packet_denied_escape_state = page.evaluate(
                        """() => {
                            const button = document.querySelector("#operator-provider-recovery-packet-preview [aria-label='Copy complete recovery bundle']");
                            const panel = document.getElementById('manual-copy-panel');
                            const textarea = document.getElementById('manual-copy-text');
                            return {
                                buttonText: (button?.innerText || '').trim(),
                                manualVisible: panel?.classList.contains('show') || false,
                                manualHidden: panel?.hidden ?? null,
                                manualTextLength: (textarea?.value || '').trim().length,
                                activeLabel: document.activeElement?.getAttribute('aria-label') || '',
                            };
                        }"""
                    )
                finally:
                    page.evaluate(
                        """() => {
                            const originals = window.__gdtProviderPacketDeniedOriginals || {};
                            if (originals.clipboardDescriptor) {
                                Object.defineProperty(Navigator.prototype, 'clipboard', originals.clipboardDescriptor);
                            } else {
                                delete Navigator.prototype.clipboard;
                            }
                            if (originals.execCommand) {
                                document.execCommand = originals.execCommand;
                            }
                            delete window.__gdtProviderPacketDeniedOriginals;
                            delete window.__gdtProviderPacketDeniedExecCommandCalled;
                            hideManualCopy({ restoreFocus: false });
                        }"""
                    )
            else:
                provider_packet_bundle_missing_fragments = ["missing provider packet recovery bundle copy button"]
            provider_packet_denied_manual_text = str(provider_packet_denied_state.get("manualText", ""))
            provider_packet_denied_ok = (
                provider_packet_denied_feedback_seen
                and provider_packet_denied_state.get("buttonText") == "Failed"
                and provider_packet_denied_state.get("originalText") == "Copy recovery bundle"
                and provider_packet_denied_state.get("copyResult") == "failed"
                and provider_packet_denied_state.get("priority") == "primary"
                and "operator-copy-btn-primary" in provider_packet_denied_state.get("className", "")
                and provider_packet_denied_state.get("manualVisible") is True
                and provider_packet_denied_state.get("manualHidden") is False
                and provider_packet_denied_state.get("activeId") == "manual-copy-text"
                and provider_packet_denied_state.get("toastType") == "error"
                and provider_packet_denied_state.get("toastRole") == "alert"
                and provider_packet_denied_state.get("toastLive") == "assertive"
                and "Copy failed" in provider_packet_denied_state.get("toastText", "")
                and provider_packet_denied_state.get("execCommandCalled") is False
                and provider_packet_denied_manual_text.replace("\r\n", "\n").replace("\r", "\n")
                == provider_packet_bundle_text
                and provider_packet_denied_reset_state.get("buttonText") == "Copy recovery bundle"
                and provider_packet_denied_reset_state.get("copyResult") == "failed"
                and provider_packet_denied_reset_state.get("manualVisible") is True
                and provider_packet_denied_reset_state.get("manualHidden") is False
                and int(provider_packet_denied_reset_state.get("manualTextLength") or 0) > 0
                and provider_packet_denied_escape_state.get("buttonText") == "Copy recovery bundle"
                and provider_packet_denied_escape_state.get("manualVisible") is False
                and provider_packet_denied_escape_state.get("manualHidden") is True
                and provider_packet_denied_escape_state.get("manualTextLength") == 0
                and provider_packet_denied_escape_state.get("activeLabel") == "Copy complete recovery bundle"
            )
            provider_packet_denied_detail = {
                "expected_mode": "provider_packet_async_clipboard_denied_manual_copy",
                "feedback_seen": provider_packet_denied_feedback_seen,
                "button_failed": provider_packet_denied_state.get("buttonText") == "Failed",
                "copy_result_failed": provider_packet_denied_state.get("copyResult") == "failed",
                "primary_priority_preserved": provider_packet_denied_state.get("priority") == "primary",
                "manual_panel_open_ok": provider_packet_denied_state.get("manualVisible") is True
                and provider_packet_denied_state.get("manualHidden") is False,
                "manual_focus_ok": provider_packet_denied_state.get("activeId") == "manual-copy-text",
                "toast_accessible_error_ok": provider_packet_denied_state.get("toastType") == "error"
                and provider_packet_denied_state.get("toastRole") == "alert"
                and provider_packet_denied_state.get("toastLive") == "assertive"
                and "Copy failed" in provider_packet_denied_state.get("toastText", ""),
                "no_exec_command_fallback_ok": provider_packet_denied_state.get("execCommandCalled") is False,
                "manual_text_matches": provider_packet_denied_manual_text.replace("\r\n", "\n").replace("\r", "\n")
                == provider_packet_bundle_text,
                "reset_kept_manual_panel_open_ok": provider_packet_denied_reset_state.get("manualVisible") is True
                and provider_packet_denied_reset_state.get("manualHidden") is False
                and int(provider_packet_denied_reset_state.get("manualTextLength") or 0) > 0,
                "escape_closed_manual_panel_ok": provider_packet_denied_escape_state.get("manualVisible") is False
                and provider_packet_denied_escape_state.get("manualHidden") is True
                and provider_packet_denied_escape_state.get("manualTextLength") == 0,
                "escape_focus_returned_ok": provider_packet_denied_escape_state.get("activeLabel")
                == "Copy complete recovery bundle",
                "manual_text_preview": provider_packet_denied_manual_text[:1200],
            }
            provider_packet_expected_env_template = str(
                provider_packet_json_payload.get("env_template") or ""
            ).strip()
            provider_packet_expected_verification_bundle = str(
                provider_packet_json_payload.get("verification_command_bundle") or ""
            ).strip()
            provider_packet_copy_control_gaps: list[str] = []

            def _provider_packet_preview_copy_text(label: str) -> str:
                buttons = provider_packet_preview.locator(f"[aria-label='{label}']")
                if buttons.count() == 0:
                    provider_packet_copy_control_gaps.append(f"missing provider packet copy control: {label}")
                    return ""
                return buttons.first.evaluate("(button) => String(button.dataset.copyText || '').replace(/\\\\n/g, '\\n')")

            provider_packet_next_action_text = _provider_packet_preview_copy_text("Copy recovery next action")
            provider_packet_env_text = _provider_packet_preview_copy_text("Copy recovery env template")
            provider_packet_checklist_text = _provider_packet_preview_copy_text("Copy recovery checklist")
            provider_packet_verify_text = _provider_packet_preview_copy_text("Copy recovery verification commands")
            provider_packet_next_action_matches_json = (
                bool(provider_packet_expected_next_action)
                and provider_packet_next_action_text == provider_packet_expected_next_action
            )
            provider_packet_env_matches_json = (
                bool(provider_packet_expected_env_template)
                and provider_packet_env_text == provider_packet_expected_env_template
            )
            provider_packet_checklist_missing_items = [
                item for item in provider_packet_expected_recovery_checklist if item not in provider_packet_checklist_text
            ]
            provider_packet_verify_missing_commands = [
                command
                for command in provider_packet_expected_verification_commands
                if command not in provider_packet_verify_text
            ]
            provider_packet_verify_matches_bundle = (
                bool(provider_packet_expected_verification_bundle)
                and provider_packet_verify_text == provider_packet_expected_verification_bundle
            )
            provider_packet_preview_secret_gaps = _copy_payload_secret_gaps(
                provider_packet_preview_text,
                "provider packet preview",
            )
            provider_packet_copy_secret_gaps = []
            for provider_packet_copy_label, provider_packet_copy_text in (
                ("next action copy", provider_packet_next_action_text),
                ("bundle copy", provider_packet_bundle_text),
                ("env template copy", provider_packet_env_text),
                ("checklist copy", provider_packet_checklist_text),
                ("verification commands copy", provider_packet_verify_text),
            ):
                provider_packet_copy_secret_gaps.extend(
                    _copy_payload_secret_gaps(
                        provider_packet_copy_text,
                        f"provider packet {provider_packet_copy_label}",
                    )
                )
            provider_packet_view_detail.update(
                {
                    "preview_text": provider_packet_preview_text[:700],
                    "preview_gaps": provider_packet_preview_gaps,
                    "preview_secret_gaps": provider_packet_preview_secret_gaps,
                    "provider_packet_json_ok": provider_packet_json_ok,
                    "provider_packet_json_error": provider_packet_json_error,
                    "provider_packet_json_missing_fields": provider_packet_json_missing_fields,
                    "provider_packet_preview_missing_fragments": provider_packet_preview_missing_fragments,
                    "disclosure": provider_packet_disclosure,
                    "keyboard_open_feedback_seen": provider_packet_disclosure_keyboard_open_feedback_seen,
                    "keyboard_collapse_feedback_seen": provider_packet_disclosure_keyboard_collapse_feedback_seen,
                    "keyboard_open_disclosure": {
                        **provider_packet_disclosure_keyboard_open,
                        "target_text": provider_packet_keyboard_preview_text[:700],
                    },
                    "keyboard_collapsed_disclosure": provider_packet_disclosure_keyboard_collapsed,
                    "keyboard_secret_gaps": provider_packet_disclosure_keyboard_secret_gaps,
                    "keyboard_gaps": provider_packet_disclosure_keyboard_gaps,
                    "bundle_button_count": provider_packet_bundle_button_count,
                    "bundle_gaps": provider_packet_bundle_gaps,
                    "provider_packet_bundle_missing_fragments": provider_packet_bundle_missing_fragments,
                    "provider_packet_launch_success_criteria_count": len(
                        provider_packet_expected_launch_success_criteria
                    ),
                    "provider_packet_recovery_checklist_count": len(provider_packet_expected_recovery_checklist),
                    "provider_packet_verification_command_count": len(provider_packet_expected_verification_commands),
                    "provider_packet_copy_control_gaps": provider_packet_copy_control_gaps,
                    "provider_packet_next_action_matches_json": provider_packet_next_action_matches_json,
                    "provider_packet_env_matches_json": provider_packet_env_matches_json,
                    "provider_packet_checklist_missing_items": provider_packet_checklist_missing_items,
                    "provider_packet_verify_missing_commands": provider_packet_verify_missing_commands,
                    "provider_packet_verify_matches_bundle": provider_packet_verify_matches_bundle,
                    "provider_packet_copy_secret_gaps": provider_packet_copy_secret_gaps,
                    "provider_packet_denied_feedback_seen": provider_packet_denied_feedback_seen,
                    "provider_packet_denied_detail": provider_packet_denied_detail,
                    "provider_packet_denied_ok": provider_packet_denied_ok,
                }
            )
            provider_packet_view_ok = (
                provider_packet_view_ok
                and provider_packet_json_ok
                and initial_provider_packet_disclosure.get("label") == "View provider recovery packet"
                and initial_provider_packet_disclosure.get("text") == "View provider packet"
                and initial_provider_packet_disclosure.get("expanded") == "false"
                and initial_provider_packet_disclosure.get("controls") == "operator-provider-recovery-packet-preview"
                and initial_provider_packet_disclosure.get("target_exists") is True
                and initial_provider_packet_disclosure.get("target_hidden") is True
                and provider_packet_disclosure.get("label") == "Hide provider recovery packet"
                and provider_packet_disclosure.get("text") == "Hide provider packet"
                and provider_packet_disclosure.get("expanded") == "true"
                and provider_packet_disclosure.get("target_exists") is True
                and provider_packet_disclosure.get("target_hidden") is False
                and (provider_packet_is_clear or provider_packet_is_blocked)
                and (
                    ("Provider auth failures: 0" in provider_packet_preview_text)
                    if provider_packet_is_clear
                    else bool(re.search(r"Provider auth failures:\s*[1-9]\d*", provider_packet_preview_text))
                )
                and not provider_packet_preview_gaps
                and "Copy recovery bundle" in provider_packet_preview_text
                and "Copy recovery verification commands" in provider_packet_preview_text
                and bool(provider_packet_bundle_text)
                and not provider_packet_bundle_gaps
                and not provider_packet_preview_missing_fragments
                and not provider_packet_bundle_missing_fragments
                and not provider_packet_preview_secret_gaps
                and not provider_packet_copy_control_gaps
                and provider_packet_next_action_matches_json
                and provider_packet_env_matches_json
                and not provider_packet_checklist_missing_items
                and provider_packet_verify_matches_bundle
                and not provider_packet_verify_missing_commands
                and not provider_packet_copy_secret_gaps
                and provider_packet_denied_ok
                and not provider_packet_disclosure_keyboard_gaps
            )
            provider_packet_initial_collapsed_ok = (
                initial_provider_packet_disclosure.get("label") == "View provider recovery packet"
                and initial_provider_packet_disclosure.get("text") == "View provider packet"
                and initial_provider_packet_disclosure.get("expanded") == "false"
                and initial_provider_packet_disclosure.get("controls") == "operator-provider-recovery-packet-preview"
                and initial_provider_packet_disclosure.get("target_exists") is True
                and initial_provider_packet_disclosure.get("target_hidden") is True
            )
            provider_packet_keyboard_open_visible_ok = (
                provider_packet_disclosure_keyboard_open_feedback_seen
                and provider_packet_disclosure_keyboard_open.get("label") == "Hide provider recovery packet"
                and provider_packet_disclosure_keyboard_open.get("text") == "Hide provider packet"
                and provider_packet_disclosure_keyboard_open.get("expanded") == "true"
                and provider_packet_disclosure_keyboard_open.get("target_exists") is True
                and provider_packet_disclosure_keyboard_open.get("target_hidden") is False
                and "Packet status:" in provider_packet_keyboard_preview_text
                and (
                    not provider_packet_keyboard_expected_status
                    or f"Packet status: {provider_packet_keyboard_expected_status}"
                    in provider_packet_keyboard_preview_text
                )
            )
            provider_packet_keyboard_collapsed_hidden_ok = (
                provider_packet_disclosure_keyboard_collapse_feedback_seen
                and provider_packet_disclosure_keyboard_collapsed.get("label") == "View provider recovery packet"
                and provider_packet_disclosure_keyboard_collapsed.get("text") == "View provider packet"
                and provider_packet_disclosure_keyboard_collapsed.get("expanded") == "false"
                and provider_packet_disclosure_keyboard_collapsed.get("target_exists") is True
                and provider_packet_disclosure_keyboard_collapsed.get("target_hidden") is True
                and provider_packet_disclosure_keyboard_collapsed.get("target_text") == ""
            )
            provider_packet_click_open_visible_ok = (
                provider_packet_disclosure.get("label") == "Hide provider recovery packet"
                and provider_packet_disclosure.get("text") == "Hide provider packet"
                and provider_packet_disclosure.get("expanded") == "true"
                and provider_packet_disclosure.get("target_exists") is True
                and provider_packet_disclosure.get("target_hidden") is False
                and "Packet status:" in provider_packet_disclosure.get("target_text", "")
            )
            provider_packet_preview_content_ok = (
                (provider_packet_is_clear or provider_packet_is_blocked)
                and (
                    ("Provider auth failures: 0" in provider_packet_preview_text)
                    if provider_packet_is_clear
                    else bool(re.search(r"Provider auth failures:\s*[1-9]\d*", provider_packet_preview_text))
                )
                and "Copy recovery bundle" in provider_packet_preview_text
                and "Copy recovery verification commands" in provider_packet_preview_text
                and not provider_packet_preview_gaps
                and not provider_packet_preview_missing_fragments
                and not provider_packet_preview_secret_gaps
            )
            provider_packet_bundle_ok = (
                provider_packet_bundle_button_count >= 1
                and bool(provider_packet_bundle_text)
                and not provider_packet_bundle_gaps
                and not provider_packet_bundle_missing_fragments
            )
            provider_packet_copy_controls_ok = (
                not provider_packet_copy_control_gaps
                and provider_packet_next_action_matches_json
                and provider_packet_env_matches_json
                and not provider_packet_checklist_missing_items
                and provider_packet_verify_matches_bundle
                and not provider_packet_verify_missing_commands
                and not provider_packet_copy_secret_gaps
            )
            provider_packet_view_detail = {
                "expected_mode": "operator_provider_recovery_packet_artifact_disclosure_lifecycle",
                "view_button_count": provider_packet_view_button_count,
                "provider_packet_path_present": bool(provider_packet_artifact_path),
                "provider_packet_json_ok": provider_packet_json_ok,
                "provider_packet_json_error": provider_packet_json_error,
                "provider_packet_json_missing_fields": provider_packet_json_missing_fields,
                "provider_packet_status": provider_packet_expected_status,
                "provider_packet_auth_failure_count": provider_packet_expected_auth_failure_count,
                "provider_packet_status_mode": "clear" if provider_packet_is_clear else "blocked",
                "initial_collapsed_ok": provider_packet_initial_collapsed_ok,
                "keyboard_open_visible_ok": provider_packet_keyboard_open_visible_ok,
                "keyboard_collapsed_hidden_ok": provider_packet_keyboard_collapsed_hidden_ok,
                "click_open_visible_ok": provider_packet_click_open_visible_ok,
                "preview_content_ok": provider_packet_preview_content_ok,
                "bundle_ok": provider_packet_bundle_ok,
                "copy_controls_ok": provider_packet_copy_controls_ok,
                "provider_packet_denied_ok": provider_packet_denied_ok,
                "provider_packet_denied_expected_mode": provider_packet_denied_detail.get("expected_mode"),
                "provider_packet_denied_manual_panel_open_ok": provider_packet_denied_detail.get(
                    "manual_panel_open_ok"
                ),
                "provider_packet_denied_escape_closed_manual_panel_ok": provider_packet_denied_detail.get(
                    "escape_closed_manual_panel_ok"
                ),
                "provider_packet_denied_no_exec_command_fallback_ok": provider_packet_denied_detail.get(
                    "no_exec_command_fallback_ok"
                ),
                "bundle_button_count": provider_packet_bundle_button_count,
                "provider_packet_launch_success_criteria_count": len(
                    provider_packet_expected_launch_success_criteria
                ),
                "provider_packet_recovery_checklist_count": len(provider_packet_expected_recovery_checklist),
                "provider_packet_verification_command_count": len(provider_packet_expected_verification_commands),
                "preview_gaps": provider_packet_preview_gaps,
                "preview_secret_gaps": provider_packet_preview_secret_gaps,
                "provider_packet_preview_missing_fragments": provider_packet_preview_missing_fragments,
                "bundle_gaps": provider_packet_bundle_gaps,
                "provider_packet_bundle_missing_fragments": provider_packet_bundle_missing_fragments,
                "provider_packet_copy_control_gaps": provider_packet_copy_control_gaps,
                "provider_packet_checklist_missing_items": provider_packet_checklist_missing_items,
                "provider_packet_verify_missing_commands": provider_packet_verify_missing_commands,
                "provider_packet_copy_secret_gaps": provider_packet_copy_secret_gaps,
                "keyboard_secret_gaps": provider_packet_disclosure_keyboard_secret_gaps,
                "keyboard_gaps": provider_packet_disclosure_keyboard_gaps,
            }
        _record_check(
            checks,
            "operator_provider_recovery_packet_artifact_view",
            provider_packet_view_ok,
            provider_packet_view_detail,
        )
        _record_check(
            checks,
            "operator_readiness_action_bundle_copy",
            readiness_action_bundle_copy_ok,
            readiness_action_bundle_copy_detail,
        )
        _record_check(
            checks,
            "operator_readiness_failure_comparison_copy",
            readiness_failure_comparison_copy_ok,
            readiness_failure_comparison_copy_detail,
        )
        _record_check(
            checks,
            "operator_readiness_verification_bundle_copy",
            readiness_verification_bundle_copy_ok,
            readiness_verification_bundle_copy_detail,
        )

        readiness_refresh_command = str(artifacts.get("readiness_refresh_command", "")).strip()
        readiness_refresh_buttons = page.locator("[aria-label='Copy readiness refresh command']")
        readiness_refresh_button_count = readiness_refresh_buttons.count()
        readiness_refresh_detail: dict[str, Any] = {
            "copy_button_count": readiness_refresh_button_count,
            "readiness_refresh_command_present": bool(readiness_refresh_command),
        }
        readiness_refresh_ok = (
            readiness_refresh_button_count >= 1 if readiness_refresh_command else readiness_refresh_button_count == 0
        )
        if readiness_refresh_button_count:
            first_readiness_refresh_copy = readiness_refresh_buttons.first
            initial_readiness_refresh_copy_text = first_readiness_refresh_copy.inner_text(timeout=timeout_ms).strip()
            readiness_refresh_text = first_readiness_refresh_copy.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_readiness_refresh_copy.click()
            readiness_refresh_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy readiness refresh command']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                readiness_refresh_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            button_text = first_readiness_refresh_copy.inner_text(timeout=timeout_ms)
            readiness_refresh_detail.update(
                {
                    "readiness_refresh_command": readiness_refresh_text[:240],
                    "initial_button_text": initial_readiness_refresh_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": readiness_refresh_feedback_seen,
                    "clipboard_matches": bool(readiness_refresh_text and clipboard_text == readiness_refresh_text),
                }
            )
            readiness_refresh_ok = (
                readiness_refresh_ok
                and bool(readiness_refresh_text)
                and readiness_refresh_text == readiness_refresh_command
                and "readiness_check.py" in readiness_refresh_text
                and "--max-browser-smoke-age-hours 24" in readiness_refresh_text
                and "--fail-on-runtime-fallback" in readiness_refresh_text
                and "--require-live-db" in readiness_refresh_text
                and clipboard_text == readiness_refresh_text
                and initial_readiness_refresh_copy_text == "Copy command"
            )
        _record_check(checks, "operator_readiness_refresh_copy", readiness_refresh_ok, readiness_refresh_detail)

        dashboard_browser_copy_buttons = page.locator("[aria-label='Copy dashboard browser report path']")
        dashboard_browser_copy_button_count = dashboard_browser_copy_buttons.count()
        dashboard_browser_copy_detail: dict[str, Any] = {
            "copy_button_count": dashboard_browser_copy_button_count,
            "dashboard_browser_path_present": bool(dashboard_browser_path),
        }
        dashboard_browser_copy_ok = (
            dashboard_browser_copy_button_count >= 1
            if dashboard_browser_path
            else dashboard_browser_copy_button_count == 0
        )
        if dashboard_browser_copy_button_count:
            first_dashboard_browser_copy = dashboard_browser_copy_buttons.first
            initial_dashboard_browser_copy_text = first_dashboard_browser_copy.inner_text(timeout=timeout_ms).strip()
            dashboard_browser_text = first_dashboard_browser_copy.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_dashboard_browser_copy.click()
            dashboard_browser_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy dashboard browser report path']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                dashboard_browser_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            button_text = first_dashboard_browser_copy.inner_text(timeout=timeout_ms)
            dashboard_browser_copy_detail.update(
                {
                    "dashboard_browser_path": dashboard_browser_text[:240],
                    "initial_button_text": initial_dashboard_browser_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": dashboard_browser_feedback_seen,
                    "clipboard_matches": bool(dashboard_browser_text and clipboard_text == dashboard_browser_text),
                }
            )
            dashboard_browser_copy_ok = (
                dashboard_browser_copy_ok
                and bool(dashboard_browser_text)
                and dashboard_browser_text == dashboard_browser_path
                and Path(dashboard_browser_text).name.startswith("dashboard_browser")
                and not Path(dashboard_browser_text).name.startswith("dashboard_browser_tap_source")
                and dashboard_browser_text.endswith(".json")
                and clipboard_text == dashboard_browser_text
                and initial_dashboard_browser_copy_text == "Copy path"
            )
        _record_check(
            checks,
            "operator_dashboard_browser_report_copy",
            dashboard_browser_copy_ok,
            dashboard_browser_copy_detail,
        )

        dashboard_browser_screenshot_view_buttons = page.locator(
            "[aria-controls='operator-dashboard-browser-screenshot-preview']"
        )
        dashboard_browser_screenshot_copy_buttons = page.locator(
            "[aria-label='Copy dashboard browser screenshot path']"
        )
        dashboard_browser_screenshot_view_count = dashboard_browser_screenshot_view_buttons.count()
        dashboard_browser_screenshot_copy_count = dashboard_browser_screenshot_copy_buttons.count()
        dashboard_browser_screenshot_detail: dict[str, Any] = {
            "view_button_count": dashboard_browser_screenshot_view_count,
            "copy_button_count": dashboard_browser_screenshot_copy_count,
            "dashboard_browser_screenshot_path_present": bool(dashboard_browser_screenshot_path),
        }
        dashboard_browser_screenshot_ok = (
            dashboard_browser_screenshot_view_count >= 1 and dashboard_browser_screenshot_copy_count >= 1
            if dashboard_browser_screenshot_path
            else dashboard_browser_screenshot_view_count == 0 and dashboard_browser_screenshot_copy_count == 0
        )
        if dashboard_browser_screenshot_view_count:
            first_dashboard_screenshot_view = dashboard_browser_screenshot_view_buttons.first
            first_dashboard_screenshot_view.click()
            dashboard_screenshot_image_loaded = False
            try:
                page.wait_for_function(
                    """() => {
                        const img = document.querySelector('#operator-dashboard-browser-screenshot-preview img.operator-artifact-image-preview');
                        return Boolean(img && img.complete && img.naturalWidth > 0 && img.naturalHeight > 0);
                    }""",
                    timeout=timeout_ms,
                )
                dashboard_screenshot_image_loaded = True
            except PlaywrightTimeoutError:
                pass
            dashboard_screenshot_preview_state = page.locator(
                "#operator-dashboard-browser-screenshot-preview"
            ).evaluate(
                """preview => {
                    const img = preview.querySelector('img.operator-artifact-image-preview');
                    const error = preview.querySelector('.operator-image-error');
                    return {
                        hidden: preview.hidden,
                        pathText: (preview.querySelector('span')?.innerText || '').trim(),
                        imageSrc: img?.getAttribute('src') || '',
                        imageAlt: img?.getAttribute('alt') || '',
                        naturalWidth: img?.naturalWidth || 0,
                        naturalHeight: img?.naturalHeight || 0,
                        errorVisible: error ? !error.hidden : null,
                        errorText: error?.textContent || '',
                    };
                }"""
            )
            dashboard_screenshot_clipboard_text = ""
            dashboard_screenshot_copy_feedback_seen = False
            if dashboard_browser_screenshot_copy_count:
                first_dashboard_screenshot_copy = dashboard_browser_screenshot_copy_buttons.first
                initial_dashboard_screenshot_copy_text = first_dashboard_screenshot_copy.inner_text(
                    timeout=timeout_ms
                ).strip()
                dashboard_screenshot_copy_text = first_dashboard_screenshot_copy.evaluate(
                    "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
                )
                first_dashboard_screenshot_copy.click()
                try:
                    page.wait_for_function(
                        "() => (document.querySelector(\"[aria-label='Copy dashboard browser screenshot path']\")?.innerText || '').trim() === 'Copied'",
                        timeout=timeout_ms,
                    )
                    dashboard_screenshot_copy_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                dashboard_screenshot_clipboard_text = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                dashboard_browser_screenshot_detail["copy_text"] = dashboard_screenshot_copy_text[:240]
                dashboard_browser_screenshot_detail["initial_copy_button_text"] = (
                    initial_dashboard_screenshot_copy_text
                )
            first_dashboard_screenshot_view.click()
            collapsed_dashboard_screenshot_disclosure = first_dashboard_screenshot_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        target_hidden: Boolean(target?.hidden),
                    };
                }"""
            )
            dashboard_browser_screenshot_detail.update(
                {
                    "preview_state": dashboard_screenshot_preview_state,
                    "collapsed_disclosure": collapsed_dashboard_screenshot_disclosure,
                    "image_loaded": dashboard_screenshot_image_loaded,
                    "copy_feedback_seen": dashboard_screenshot_copy_feedback_seen,
                    "clipboard_matches": bool(
                        dashboard_browser_screenshot_path
                        and dashboard_screenshot_clipboard_text == dashboard_browser_screenshot_path
                    ),
                }
            )
            dashboard_browser_screenshot_ok = (
                dashboard_browser_screenshot_ok
                and dashboard_screenshot_image_loaded
                and dashboard_screenshot_preview_state.get("hidden") is False
                and dashboard_browser_screenshot_path in dashboard_screenshot_preview_state.get("pathText", "")
                and "/api/operator/artifact-image?path=" in dashboard_screenshot_preview_state.get("imageSrc", "")
                and dashboard_screenshot_preview_state.get("imageAlt") == "Dashboard browser smoke screenshot"
                and int(dashboard_screenshot_preview_state.get("naturalWidth") or 0) > 0
                and int(dashboard_screenshot_preview_state.get("naturalHeight") or 0) > 0
                and dashboard_screenshot_preview_state.get("errorVisible") is False
                and dashboard_screenshot_preview_state.get("errorText") == ""
                and Path(dashboard_browser_screenshot_path).name.startswith("dashboard_browser")
                and not Path(dashboard_browser_screenshot_path).name.startswith("dashboard_browser_tap_source")
                and dashboard_browser_screenshot_path.endswith(".png")
                and dashboard_screenshot_clipboard_text == dashboard_browser_screenshot_path
                and dashboard_screenshot_copy_feedback_seen
                and dashboard_browser_screenshot_detail.get("initial_copy_button_text") == "Copy path"
                and collapsed_dashboard_screenshot_disclosure.get("label") == "View dashboard browser screenshot"
                and collapsed_dashboard_screenshot_disclosure.get("text") == "View screenshot"
                and collapsed_dashboard_screenshot_disclosure.get("expanded") == "false"
                and collapsed_dashboard_screenshot_disclosure.get("target_hidden") is True
            )
            dashboard_browser_screenshot_detail = {
                "expected_mode": "operator_dashboard_browser_screenshot_preview_loaded",
                "view_button_count": dashboard_browser_screenshot_view_count,
                "copy_button_count": dashboard_browser_screenshot_copy_count,
                "dashboard_browser_screenshot_path_present": bool(dashboard_browser_screenshot_path),
                "image_loaded": dashboard_screenshot_image_loaded,
                "preview_visible_ok": (
                    dashboard_screenshot_image_loaded
                    and dashboard_screenshot_preview_state.get("hidden") is False
                    and dashboard_browser_screenshot_path in dashboard_screenshot_preview_state.get("pathText", "")
                    and "/api/operator/artifact-image?path="
                    in dashboard_screenshot_preview_state.get("imageSrc", "")
                ),
                "image_alt_ok": dashboard_screenshot_preview_state.get("imageAlt")
                == "Dashboard browser smoke screenshot",
                "image_dimensions_ok": int(dashboard_screenshot_preview_state.get("naturalWidth") or 0) > 0
                and int(dashboard_screenshot_preview_state.get("naturalHeight") or 0) > 0,
                "natural_width": int(dashboard_screenshot_preview_state.get("naturalWidth") or 0),
                "natural_height": int(dashboard_screenshot_preview_state.get("naturalHeight") or 0),
                "error_absent_ok": dashboard_screenshot_preview_state.get("errorVisible") is False
                and dashboard_screenshot_preview_state.get("errorText") == "",
                "path_name_ok": Path(dashboard_browser_screenshot_path).name.startswith("dashboard_browser")
                and not Path(dashboard_browser_screenshot_path).name.startswith("dashboard_browser_tap_source")
                and dashboard_browser_screenshot_path.endswith(".png"),
                "copy_feedback_seen": dashboard_screenshot_copy_feedback_seen,
                "clipboard_matches": bool(
                    dashboard_browser_screenshot_path
                    and dashboard_screenshot_clipboard_text == dashboard_browser_screenshot_path
                ),
                "initial_copy_button_ok": dashboard_browser_screenshot_detail.get("initial_copy_button_text")
                == "Copy path",
                "collapsed_hidden_ok": (
                    collapsed_dashboard_screenshot_disclosure.get("label") == "View dashboard browser screenshot"
                    and collapsed_dashboard_screenshot_disclosure.get("text") == "View screenshot"
                    and collapsed_dashboard_screenshot_disclosure.get("expanded") == "false"
                    and collapsed_dashboard_screenshot_disclosure.get("target_hidden") is True
                ),
            }
        _record_check(
            checks,
            "operator_dashboard_browser_screenshot_view",
            dashboard_browser_screenshot_ok,
            dashboard_browser_screenshot_detail,
        )

        tap_fixture_browser_path = str(artifacts.get("tap_fixture_browser", "")).strip()
        tap_fixture_copy_buttons = page.locator("[aria-label='Copy TAP fixture report path']")
        tap_fixture_copy_button_count = tap_fixture_copy_buttons.count()
        tap_fixture_copy_detail: dict[str, Any] = {
            "copy_button_count": tap_fixture_copy_button_count,
            "tap_fixture_browser_path_present": bool(tap_fixture_browser_path),
        }
        tap_fixture_copy_ok = (
            tap_fixture_copy_button_count >= 1 if tap_fixture_browser_path else tap_fixture_copy_button_count == 0
        )
        if tap_fixture_copy_button_count:
            first_tap_fixture_copy = tap_fixture_copy_buttons.first
            initial_tap_fixture_copy_text = first_tap_fixture_copy.inner_text(timeout=timeout_ms).strip()
            tap_fixture_text = first_tap_fixture_copy.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_tap_fixture_copy.click()
            tap_fixture_copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy TAP fixture report path']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                tap_fixture_copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            button_text = first_tap_fixture_copy.inner_text(timeout=timeout_ms)
            tap_fixture_copy_detail.update(
                {
                    "tap_fixture_browser_path": tap_fixture_text[:240],
                    "initial_button_text": initial_tap_fixture_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": tap_fixture_copy_feedback_seen,
                    "clipboard_matches": bool(tap_fixture_text and clipboard_text == tap_fixture_text),
                }
            )
            tap_fixture_copy_ok = (
                tap_fixture_copy_ok
                and bool(tap_fixture_text)
                and tap_fixture_text == tap_fixture_browser_path
                and tap_fixture_text.endswith("dashboard_browser_tap_source_evidence.json")
                and "tap_fixture_browser_latest" not in tap_fixture_text
                and clipboard_text == tap_fixture_text
                and initial_tap_fixture_copy_text == "Copy path"
            )
        _record_check(checks, "operator_tap_fixture_report_copy", tap_fixture_copy_ok, tap_fixture_copy_detail)

        scheduler_artifact_buttons = page.locator("[aria-label='Copy scheduler artifact path']")
        scheduler_artifact_button_count = scheduler_artifact_buttons.count()
        scheduler_artifact_detail: dict[str, Any] = {
            "copy_button_count": scheduler_artifact_button_count,
            "scheduler_artifact_path_present": bool(scheduler_artifact_path),
        }
        scheduler_artifact_ok = (
            scheduler_artifact_button_count >= 1 if scheduler_artifact_path else scheduler_artifact_button_count == 0
        )
        if scheduler_artifact_button_count:
            first_scheduler_artifact_copy = scheduler_artifact_buttons.first
            initial_scheduler_artifact_copy_text = first_scheduler_artifact_copy.inner_text(timeout=timeout_ms).strip()
            scheduler_artifact_text = first_scheduler_artifact_copy.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_scheduler_artifact_copy.click()
            scheduler_artifact_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy scheduler artifact path']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                scheduler_artifact_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            button_text = first_scheduler_artifact_copy.inner_text(timeout=timeout_ms)
            scheduler_artifact_detail.update(
                {
                    "scheduler_artifact_path": scheduler_artifact_text[:240],
                    "initial_button_text": initial_scheduler_artifact_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": scheduler_artifact_feedback_seen,
                    "clipboard_matches": bool(scheduler_artifact_text and clipboard_text == scheduler_artifact_text),
                    "scheduler_artifact_json_ok": scheduler_artifact_json_ok,
                    "scheduler_artifact_json_error": scheduler_artifact_json_error,
                    "scheduler_artifact_json_missing_fields": scheduler_artifact_json_missing_fields,
                }
            )
            scheduler_artifact_ok = (
                scheduler_artifact_ok
                and bool(scheduler_artifact_text)
                and scheduler_artifact_text == scheduler_artifact_path
                and "\\logs\\scheduler\\" in scheduler_artifact_text
                and clipboard_text == scheduler_artifact_text
                and initial_scheduler_artifact_copy_text == "Copy path"
                and scheduler_artifact_json_ok
            )
        _record_check(
            checks,
            "operator_scheduler_artifact_copy",
            scheduler_artifact_ok,
            scheduler_artifact_detail,
        )

        tap_fixture_refresh_command = str(artifacts.get("tap_fixture_browser_refresh_command", "")).strip()
        tap_fixture_refresh_buttons = page.locator("[aria-label='Copy TAP fixture refresh command']")
        tap_fixture_refresh_button_count = tap_fixture_refresh_buttons.count()
        tap_fixture_refresh_detail: dict[str, Any] = {
            "copy_button_count": tap_fixture_refresh_button_count,
            "tap_fixture_refresh_command_present": bool(tap_fixture_refresh_command),
        }
        tap_fixture_refresh_ok = (
            tap_fixture_refresh_button_count >= 1
            if tap_fixture_refresh_command
            else tap_fixture_refresh_button_count == 0
        )
        if tap_fixture_refresh_button_count:
            first_tap_fixture_refresh_copy = tap_fixture_refresh_buttons.first
            initial_tap_fixture_refresh_copy_text = first_tap_fixture_refresh_copy.inner_text(
                timeout=timeout_ms
            ).strip()
            tap_fixture_refresh_text = first_tap_fixture_refresh_copy.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_tap_fixture_refresh_copy.click()
            tap_fixture_refresh_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy TAP fixture refresh command']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                tap_fixture_refresh_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            button_text = first_tap_fixture_refresh_copy.inner_text(timeout=timeout_ms)
            tap_fixture_refresh_detail.update(
                {
                    "tap_fixture_refresh_command": tap_fixture_refresh_text[:240],
                    "initial_button_text": initial_tap_fixture_refresh_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": tap_fixture_refresh_feedback_seen,
                    "clipboard_matches": bool(tap_fixture_refresh_text and clipboard_text == tap_fixture_refresh_text),
                }
            )
            tap_fixture_refresh_ok = (
                tap_fixture_refresh_ok
                and bool(tap_fixture_refresh_text)
                and tap_fixture_refresh_text == tap_fixture_refresh_command
                and "browser_smoke.py --tap-source-fixture --timeout 45" in tap_fixture_refresh_text
                and "tap_fixture_browser_latest" not in tap_fixture_refresh_text
                and clipboard_text == tap_fixture_refresh_text
                and initial_tap_fixture_refresh_copy_text == "Copy command"
            )
        _record_check(
            checks,
            "operator_tap_fixture_refresh_copy",
            tap_fixture_refresh_ok,
            tap_fixture_refresh_detail,
        )

        tap_fixture_screenshot_view_buttons = page.locator("[aria-controls='operator-tap-fixture-screenshot-preview']")
        tap_fixture_screenshot_copy_buttons = page.locator("[aria-label='Copy TAP fixture screenshot path']")
        tap_fixture_screenshot_view_count = tap_fixture_screenshot_view_buttons.count()
        tap_fixture_screenshot_copy_count = tap_fixture_screenshot_copy_buttons.count()
        tap_fixture_screenshot_detail: dict[str, Any] = {
            "view_button_count": tap_fixture_screenshot_view_count,
            "copy_button_count": tap_fixture_screenshot_copy_count,
            "tap_fixture_screenshot_path_present": bool(tap_fixture_screenshot_path),
        }
        tap_fixture_screenshot_ok = (
            tap_fixture_screenshot_view_count >= 1 and tap_fixture_screenshot_copy_count >= 1
            if tap_fixture_screenshot_path
            else tap_fixture_screenshot_view_count == 0 and tap_fixture_screenshot_copy_count == 0
        )
        if tap_fixture_screenshot_view_count:
            first_screenshot_view = tap_fixture_screenshot_view_buttons.first
            initial_screenshot_disclosure = first_screenshot_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                    };
                }"""
            )
            first_screenshot_view.click()
            screenshot_image_loaded = False
            try:
                page.wait_for_function(
                    """() => {
                        const img = document.querySelector('#operator-tap-fixture-screenshot-preview img.operator-artifact-image-preview');
                        return Boolean(img && img.complete && img.naturalWidth > 0 && img.naturalHeight > 0);
                    }""",
                    timeout=timeout_ms,
                )
                screenshot_image_loaded = True
            except PlaywrightTimeoutError:
                pass
            screenshot_preview_state = page.locator("#operator-tap-fixture-screenshot-preview").evaluate(
                """preview => {
                    const img = preview.querySelector('img.operator-artifact-image-preview');
                    const pathLine = Array.from(preview.querySelectorAll('span')).find(
                        item => (item.innerText || '').startsWith('Screenshot:')
                    );
                    return {
                        hidden: preview.hidden,
                        text: (preview.innerText || '').trim(),
                        pathText: (pathLine?.innerText || '').trim(),
                        imageSrc: img?.getAttribute('src') || '',
                        imageAlt: img?.getAttribute('alt') || '',
                        imageWidth: img?.getAttribute('width') || '',
                        imageHeight: img?.getAttribute('height') || '',
                        imageComplete: Boolean(img?.complete),
                        naturalWidth: img?.naturalWidth || 0,
                        naturalHeight: img?.naturalHeight || 0,
                        errorVisible: preview.querySelector('.operator-image-error')?.hidden === false,
                        errorText: (preview.querySelector('.operator-image-error')?.textContent || '').trim(),
                        unavailableTextPresent: (preview.innerText || '').includes('Screenshot unavailable'),
                    };
                }"""
            )
            screenshot_clipboard_text = ""
            screenshot_copy_feedback_seen = False
            if tap_fixture_screenshot_copy_count:
                first_screenshot_copy = tap_fixture_screenshot_copy_buttons.first
                initial_screenshot_copy_text = first_screenshot_copy.inner_text(timeout=timeout_ms).strip()
                screenshot_copy_text = first_screenshot_copy.evaluate(
                    "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
                )
                first_screenshot_copy.click()
                try:
                    page.wait_for_function(
                        "() => (document.querySelector(\"[aria-label='Copy TAP fixture screenshot path']\")?.innerText || '').trim() === 'Copied'",
                        timeout=timeout_ms,
                    )
                    screenshot_copy_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                screenshot_clipboard_text = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                tap_fixture_screenshot_detail["copy_text"] = screenshot_copy_text[:240]
                tap_fixture_screenshot_detail["initial_copy_button_text"] = initial_screenshot_copy_text
            first_screenshot_view.click()
            collapsed_screenshot_disclosure = first_screenshot_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        target_hidden: Boolean(target?.hidden),
                    };
                }"""
            )
            tap_fixture_screenshot_detail.update(
                {
                    "initial_disclosure": initial_screenshot_disclosure,
                    "preview_state": screenshot_preview_state,
                    "collapsed_disclosure": collapsed_screenshot_disclosure,
                    "image_loaded": screenshot_image_loaded,
                    "copy_feedback_seen": screenshot_copy_feedback_seen,
                    "clipboard_matches": bool(
                        tap_fixture_screenshot_path and screenshot_clipboard_text == tap_fixture_screenshot_path
                    ),
                }
            )
            tap_fixture_screenshot_ok = (
                tap_fixture_screenshot_ok
                and initial_screenshot_disclosure.get("label") == "View TAP fixture screenshot"
                and initial_screenshot_disclosure.get("text") == "View screenshot"
                and initial_screenshot_disclosure.get("expanded") == "false"
                and initial_screenshot_disclosure.get("controls") == "operator-tap-fixture-screenshot-preview"
                and initial_screenshot_disclosure.get("target_exists") is True
                and initial_screenshot_disclosure.get("target_hidden") is True
                and screenshot_image_loaded
                and screenshot_preview_state.get("hidden") is False
                and tap_fixture_screenshot_path in screenshot_preview_state.get("pathText", "")
                and "/api/operator/artifact-image?path=" in screenshot_preview_state.get("imageSrc", "")
                and screenshot_preview_state.get("imageAlt") == "TAP fixture browser smoke screenshot"
                and screenshot_preview_state.get("imageWidth") == "960"
                and screenshot_preview_state.get("imageHeight") == "540"
                and int(screenshot_preview_state.get("naturalWidth") or 0) > 0
                and int(screenshot_preview_state.get("naturalHeight") or 0) > 0
                and screenshot_preview_state.get("errorVisible") is False
                and screenshot_preview_state.get("errorText") == ""
                and screenshot_preview_state.get("unavailableTextPresent") is False
                and tap_fixture_screenshot_path.endswith("dashboard_browser_tap_source_evidence.png")
                and "tap_fixture_browser_latest" not in tap_fixture_screenshot_path
                and screenshot_clipboard_text == tap_fixture_screenshot_path
                and screenshot_copy_feedback_seen
                and tap_fixture_screenshot_detail.get("initial_copy_button_text") == "Copy path"
                and collapsed_screenshot_disclosure.get("label") == "View TAP fixture screenshot"
                and collapsed_screenshot_disclosure.get("text") == "View screenshot"
                and collapsed_screenshot_disclosure.get("expanded") == "false"
                and collapsed_screenshot_disclosure.get("target_hidden") is True
            )
            tap_fixture_screenshot_detail = {
                "expected_mode": "operator_tap_fixture_screenshot_preview_loaded",
                "view_button_count": tap_fixture_screenshot_view_count,
                "copy_button_count": tap_fixture_screenshot_copy_count,
                "tap_fixture_screenshot_path_present": bool(tap_fixture_screenshot_path),
                "initial_collapsed_ok": (
                    initial_screenshot_disclosure.get("label") == "View TAP fixture screenshot"
                    and initial_screenshot_disclosure.get("text") == "View screenshot"
                    and initial_screenshot_disclosure.get("expanded") == "false"
                    and initial_screenshot_disclosure.get("controls") == "operator-tap-fixture-screenshot-preview"
                    and initial_screenshot_disclosure.get("target_exists") is True
                    and initial_screenshot_disclosure.get("target_hidden") is True
                ),
                "image_loaded": screenshot_image_loaded,
                "preview_visible_ok": (
                    screenshot_image_loaded
                    and screenshot_preview_state.get("hidden") is False
                    and tap_fixture_screenshot_path in screenshot_preview_state.get("pathText", "")
                    and "/api/operator/artifact-image?path=" in screenshot_preview_state.get("imageSrc", "")
                ),
                "image_alt_ok": screenshot_preview_state.get("imageAlt") == "TAP fixture browser smoke screenshot",
                "image_dimensions_ok": int(screenshot_preview_state.get("naturalWidth") or 0) > 0
                and int(screenshot_preview_state.get("naturalHeight") or 0) > 0,
                "image_size_attributes_ok": screenshot_preview_state.get("imageWidth") == "960"
                and screenshot_preview_state.get("imageHeight") == "540",
                "natural_width": int(screenshot_preview_state.get("naturalWidth") or 0),
                "natural_height": int(screenshot_preview_state.get("naturalHeight") or 0),
                "error_absent_ok": screenshot_preview_state.get("errorVisible") is False
                and screenshot_preview_state.get("errorText") == "",
                "unavailable_absent_ok": screenshot_preview_state.get("unavailableTextPresent") is False,
                "path_name_ok": tap_fixture_screenshot_path.endswith("dashboard_browser_tap_source_evidence.png")
                and "tap_fixture_browser_latest" not in tap_fixture_screenshot_path,
                "copy_feedback_seen": screenshot_copy_feedback_seen,
                "clipboard_matches": bool(
                    tap_fixture_screenshot_path and screenshot_clipboard_text == tap_fixture_screenshot_path
                ),
                "initial_copy_button_ok": tap_fixture_screenshot_detail.get("initial_copy_button_text")
                == "Copy path",
                "collapsed_hidden_ok": (
                    collapsed_screenshot_disclosure.get("label") == "View TAP fixture screenshot"
                    and collapsed_screenshot_disclosure.get("text") == "View screenshot"
                    and collapsed_screenshot_disclosure.get("expanded") == "false"
                    and collapsed_screenshot_disclosure.get("target_hidden") is True
                ),
            }
        _record_check(
            checks,
            "operator_tap_fixture_screenshot_view",
            tap_fixture_screenshot_ok,
            tap_fixture_screenshot_detail,
        )

        workspace_copy_buttons = page.locator("[aria-label='Copy workspace smoke path']")
        workspace_copy_button_count = workspace_copy_buttons.count()
        workspace_copy_detail: dict[str, Any] = {
            "copy_button_count": workspace_copy_button_count,
            "workspace_smoke_path_present": bool(workspace_smoke_path),
            "workspace_smoke_json_ok": workspace_smoke_json_ok,
            "workspace_smoke_json_error": workspace_smoke_json_error,
            "workspace_smoke_json_missing_fields": workspace_smoke_json_missing_fields,
        }
        workspace_copy_ok = workspace_copy_button_count >= 1 if workspace_smoke_path else workspace_copy_button_count == 0
        if workspace_copy_button_count:
            first_workspace_copy = workspace_copy_buttons.first
            initial_workspace_copy_text = first_workspace_copy.inner_text(timeout=timeout_ms).strip()
            workspace_text = first_workspace_copy.evaluate(
                "(button) => (button.closest('.operator-action')?.querySelector('code')?.innerText || '').trim()"
            )
            first_workspace_copy.click()
            workspace_copy_feedback_seen = False
            try:
                page.wait_for_function(
                    "() => (document.querySelector(\"[aria-label='Copy workspace smoke path']\")?.innerText || '').trim() === 'Copied'",
                    timeout=timeout_ms,
                )
                workspace_copy_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            workspace_keyboard_feedback_seen = False
            workspace_keyboard_clipboard_text = ""
            workspace_keyboard_clipboard_matches = False
            workspace_keyboard_secret_gaps: list[str] = []
            first_workspace_copy.evaluate(
                """button => {
                    delete button.dataset.copyResult;
                    button.innerText = button.dataset.copyOriginalText || 'Copy path';
                }"""
            )
            first_workspace_copy.focus()
            page.keyboard.press("Enter")
            try:
                page.wait_for_function(
                    f"""async () => {{
                        const button = document.querySelector("[aria-label='Copy workspace smoke path']");
                        const clipboardText = navigator.clipboard?.readText ? await navigator.clipboard.readText() : '';
                        return button?.dataset.copyResult === 'copied'
                            && clipboardText.trim() === {json.dumps(workspace_text)};
                    }}""",
                    timeout=timeout_ms,
                )
                workspace_keyboard_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            workspace_keyboard_clipboard_text = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            workspace_keyboard_clipboard_matches = bool(
                workspace_text and workspace_keyboard_clipboard_text.strip() == workspace_text
            )
            workspace_keyboard_secret_gaps = _copy_payload_secret_gaps(
                workspace_keyboard_clipboard_text,
                "workspace smoke path keyboard clipboard",
            )
            workspace_copy_gaps: list[str] = []
            if not workspace_copy_feedback_seen:
                workspace_copy_gaps.append("workspace smoke path click activation did not report copied")
            if clipboard_text != workspace_text:
                workspace_copy_gaps.append("workspace smoke path click clipboard mismatch")
            if not workspace_keyboard_feedback_seen:
                workspace_copy_gaps.append("workspace smoke path Enter activation did not report copied")
            if not workspace_keyboard_clipboard_matches:
                workspace_copy_gaps.append("workspace smoke path keyboard clipboard mismatch")
            workspace_copy_gaps.extend(workspace_keyboard_secret_gaps)
            button_text = first_workspace_copy.inner_text(timeout=timeout_ms)
            workspace_copy_detail.update(
                {
                    "workspace_smoke_path": workspace_text[:240],
                    "initial_button_text": initial_workspace_copy_text,
                    "button_text": button_text,
                    "copy_feedback_seen": workspace_copy_feedback_seen,
                    "clipboard_matches": bool(workspace_text and clipboard_text == workspace_text),
                    "workspace_keyboard_feedback_seen": workspace_keyboard_feedback_seen,
                    "workspace_keyboard_clipboard_matches": workspace_keyboard_clipboard_matches,
                    "workspace_keyboard_clipboard": workspace_keyboard_clipboard_text[:240],
                    "workspace_keyboard_secret_gaps": workspace_keyboard_secret_gaps,
                    "workspace_smoke_json_ok": workspace_smoke_json_ok,
                    "gaps": workspace_copy_gaps,
                }
            )
            workspace_copy_ok = (
                workspace_copy_ok
                and bool(workspace_text)
                and clipboard_text == workspace_text
                and initial_workspace_copy_text == "Copy path"
                and workspace_smoke_json_ok
                and workspace_keyboard_feedback_seen
                and workspace_keyboard_clipboard_matches
                and not workspace_keyboard_secret_gaps
                and not workspace_copy_gaps
            )
        _record_check(checks, "operator_workspace_smoke_copy", workspace_copy_ok, workspace_copy_detail)

        workspace_view_buttons = page.locator("[aria-label='View workspace smoke']")
        workspace_view_button_count = workspace_view_buttons.count()
        workspace_view_detail: dict[str, Any] = {
            "view_button_count": workspace_view_button_count,
            "workspace_smoke_path_present": bool(workspace_smoke_path),
            "workspace_smoke_json_ok": workspace_smoke_json_ok,
            "workspace_smoke_json_error": workspace_smoke_json_error,
            "workspace_smoke_json_missing_fields": workspace_smoke_json_missing_fields,
            "workspace_smoke_json_status": str(workspace_smoke_json_payload.get("status", "")),
            "workspace_smoke_json_generated_at": str(workspace_smoke_json_payload.get("generated_at", "")),
            "workspace_smoke_json_summary_text": workspace_smoke_json_summary_text,
            "workspace_smoke_json_result_count": len(workspace_smoke_json_results)
            if isinstance(workspace_smoke_json_results, list)
            else 0,
        }
        workspace_view_ok = workspace_view_button_count >= 1 if workspace_smoke_path else workspace_view_button_count == 0
        workspace_failed_rerun_copy_ok = not workspace_smoke_needs_rerun
        workspace_smoke_rerun_expected_mode = (
            "failed_rerun"
            if workspace_smoke_failed
            else "action_required_rerun"
            if workspace_smoke_action_required
            else "no_rerun_expected"
        )
        workspace_failed_rerun_copy_detail: dict[str, Any] = {
            "workspace_smoke_rerun_expected_mode": workspace_smoke_rerun_expected_mode,
            "workspace_smoke_expected_conclusion": workspace_smoke_expected_conclusion
            if workspace_smoke_needs_rerun
            else None,
            "workspace_smoke_failed_ok": True if workspace_smoke_failed else None,
            "workspace_smoke_action_required_ok": True if workspace_smoke_action_required else None,
            "workspace_smoke_no_rerun_ok": True if not workspace_smoke_needs_rerun else None,
            "workspace_smoke_rerun_required": True if workspace_smoke_needs_rerun else None,
            "workspace_smoke_path_present": bool(workspace_smoke_path),
        }
        if workspace_view_button_count:
            first_workspace_view = workspace_view_buttons.first
            initial_workspace_disclosure = first_workspace_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        artifact_path: button.getAttribute('data-artifact-path') || '',
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                    };
                }"""
            )
            workspace_view_detail["initial_disclosure"] = initial_workspace_disclosure
            first_workspace_view = page.locator("[aria-controls='operator-workspace-smoke-preview']").first
            workspace_keyboard_open_feedback_seen = False
            workspace_keyboard_collapse_feedback_seen = False
            workspace_keyboard_open_disclosure: dict[str, Any] = {}
            workspace_keyboard_collapsed_disclosure: dict[str, Any] = {}
            workspace_keyboard_secret_gaps: list[str] = []
            workspace_keyboard_gaps: list[str] = []
            first_workspace_view.focus()
            page.keyboard.press("Enter")
            try:
                page.wait_for_function(
                    """() => {
                        const button = document.querySelector("[aria-controls='operator-workspace-smoke-preview']");
                        const target = document.getElementById('operator-workspace-smoke-preview');
                        return button?.getAttribute('aria-expanded') === 'true'
                            && target
                            && target.hidden === false
                            && (target.innerText || '').includes('Workspace smoke:');
                    }""",
                    timeout=timeout_ms,
                )
                workspace_keyboard_open_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            workspace_keyboard_open_disclosure = first_workspace_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || ''),
                    };
                }"""
            )
            workspace_keyboard_preview_text = str(workspace_keyboard_open_disclosure.get("target_text") or "")
            workspace_keyboard_secret_gaps = _copy_payload_secret_gaps(
                workspace_keyboard_preview_text,
                "workspace smoke keyboard preview",
            )
            first_workspace_view.focus()
            page.keyboard.press("Space")
            try:
                page.wait_for_function(
                    """() => {
                        const button = document.querySelector("[aria-controls='operator-workspace-smoke-preview']");
                        const target = document.getElementById('operator-workspace-smoke-preview');
                        return button?.getAttribute('aria-expanded') === 'false'
                            && target
                            && target.hidden === true
                            && (target.innerText || '').trim() === '';
                    }""",
                    timeout=timeout_ms,
                )
                workspace_keyboard_collapse_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            workspace_keyboard_collapsed_disclosure = first_workspace_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').trim(),
                    };
                }"""
            )
            if not workspace_keyboard_open_feedback_seen:
                workspace_keyboard_gaps.append("workspace smoke disclosure Enter activation did not expand")
            if workspace_keyboard_open_disclosure.get("label") != "Hide workspace smoke":
                workspace_keyboard_gaps.append("workspace smoke keyboard open label changed")
            if workspace_keyboard_open_disclosure.get("text") != "Hide workspace":
                workspace_keyboard_gaps.append("workspace smoke keyboard open text changed")
            if workspace_keyboard_open_disclosure.get("expanded") != "true":
                workspace_keyboard_gaps.append("workspace smoke keyboard open aria-expanded mismatch")
            if workspace_keyboard_open_disclosure.get("target_exists") is not True:
                workspace_keyboard_gaps.append("workspace smoke keyboard preview missing")
            if workspace_keyboard_open_disclosure.get("target_hidden") is not False:
                workspace_keyboard_gaps.append("workspace smoke keyboard preview stayed hidden")
            if "Workspace smoke:" not in workspace_keyboard_preview_text:
                workspace_keyboard_gaps.append("workspace smoke keyboard preview missing heading")
            if workspace_smoke_needs_rerun and f"Workspace smoke: {workspace_smoke_expected_conclusion}" not in (
                workspace_keyboard_preview_text
            ):
                workspace_keyboard_gaps.append("workspace smoke keyboard preview missing expected conclusion")
            if not workspace_keyboard_collapse_feedback_seen:
                workspace_keyboard_gaps.append("workspace smoke disclosure Space activation did not collapse")
            if workspace_keyboard_collapsed_disclosure.get("label") != "View workspace smoke":
                workspace_keyboard_gaps.append("workspace smoke keyboard collapsed label changed")
            if workspace_keyboard_collapsed_disclosure.get("text") != "View workspace":
                workspace_keyboard_gaps.append("workspace smoke keyboard collapsed text changed")
            if workspace_keyboard_collapsed_disclosure.get("expanded") != "false":
                workspace_keyboard_gaps.append("workspace smoke keyboard collapsed aria-expanded mismatch")
            if workspace_keyboard_collapsed_disclosure.get("target_exists") is not True:
                workspace_keyboard_gaps.append("workspace smoke keyboard collapsed preview missing")
            if workspace_keyboard_collapsed_disclosure.get("target_hidden") is not True:
                workspace_keyboard_gaps.append("workspace smoke keyboard collapse did not hide preview")
            if workspace_keyboard_collapsed_disclosure.get("target_text") != "":
                workspace_keyboard_gaps.append("workspace smoke keyboard collapse left preview text")
            workspace_keyboard_gaps.extend(workspace_keyboard_secret_gaps)
            if first_workspace_view.get_attribute("aria-expanded") == "true":
                first_workspace_view.click()
                page.wait_for_timeout(120)
            first_workspace_view.click()
            try:
                page.wait_for_function(
                    "() => (document.querySelector('.operator-workspace-smoke-preview')?.innerText || '').includes('Workspace smoke:')",
                    timeout=timeout_ms,
                )
            except PlaywrightTimeoutError:
                pass
            workspace_preview_text = page.locator(".operator-workspace-smoke-preview").first.inner_text(timeout=timeout_ms)
            workspace_provenance = page.locator(".operator-workspace-smoke-preview").first.evaluate(
                """preview => {
                    const generated = preview.querySelector('time');
                    const artifactLine = Array.from(preview.querySelectorAll('span')).find(
                        item => (item.innerText || '').startsWith('Artifact:')
                    );
                    const statusLine = Array.from(preview.querySelectorAll('span')).find(
                        item => (item.innerText || '').startsWith('Run status:')
                    );
                    return {
                        generatedText: (generated?.innerText || '').trim(),
                        generatedDateTime: generated?.getAttribute('datetime') || '',
                        artifactText: (artifactLine?.innerText || '').trim(),
                        runStatusText: (statusLine?.innerText || '').trim(),
                        spanCount: preview.querySelectorAll('span').length,
                    };
                }"""
            )
            workspace_failure_detail = page.locator(".operator-workspace-smoke-preview").first.evaluate(
                """preview => {
                    const spans = Array.from(preview.querySelectorAll('span'));
                    const findLine = prefix => spans.find(item => (item.innerText || '').startsWith(prefix));
                    const commandLine = findLine('Command:');
                    const outputLine = findLine('Output:');
                    return {
                        detailText: (findLine('Detail:')?.innerText || '').trim(),
                        commandText: (commandLine?.querySelector('code')?.innerText || '').trim(),
                        outputText: (outputLine?.querySelector('samp')?.innerText || '').trim(),
                        codeCount: preview.querySelectorAll('code').length,
                        sampleOutputCount: preview.querySelectorAll('samp').length,
                    };
                }"""
            )
            workspace_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", workspace_preview_text, re.IGNORECASE):
                workspace_secret_gaps.append("preview contains raw postgres URL")
            if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", workspace_preview_text, re.IGNORECASE):
                workspace_secret_gaps.append("preview contains raw tenant user")
            if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", workspace_preview_text):
                workspace_secret_gaps.append("preview contains raw OpenAI-style key")
            if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", workspace_preview_text):
                workspace_secret_gaps.append("preview contains raw Google API-style key")
            failed_rerun_buttons = page.locator("[aria-label='Copy failed workspace smoke command']")
            failed_rerun_button_count = failed_rerun_buttons.count()
            workspace_failed_rerun_copy_detail["copy_button_count"] = failed_rerun_button_count
            workspace_failed_rerun_copy_ok = (
                failed_rerun_button_count >= 1 if workspace_smoke_needs_rerun else failed_rerun_button_count == 0
            )
            if failed_rerun_button_count:
                failed_rerun_button = failed_rerun_buttons.first
                initial_failed_rerun_text = failed_rerun_button.inner_text(timeout=timeout_ms).strip()
                failed_rerun_text = failed_rerun_button.evaluate("(button) => button.dataset.copyText || ''")
                expected_failed_rerun_clipboard = failed_rerun_text.replace("\\n", "\n")
                failed_rerun_button.click()
                failed_rerun_feedback_seen = False
                try:
                    page.wait_for_function(
                        "() => (document.querySelector(\"[aria-label='Copy failed workspace smoke command']\")?.innerText || '').trim() === 'Copied'",
                        timeout=timeout_ms,
                    )
                    failed_rerun_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                failed_rerun_clipboard_text = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                failed_rerun_clipboard_normalized = failed_rerun_clipboard_text.replace("\r\n", "\n").replace("\r", "\n")
                failed_rerun_secret_gaps = []
                if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", expected_failed_rerun_clipboard, re.IGNORECASE):
                    failed_rerun_secret_gaps.append("clipboard contains raw postgres URL")
                if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", expected_failed_rerun_clipboard, re.IGNORECASE):
                    failed_rerun_secret_gaps.append("clipboard contains raw tenant user")
                if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", expected_failed_rerun_clipboard):
                    failed_rerun_secret_gaps.append("clipboard contains raw OpenAI-style key")
                if re.search(r"\bAIza[0-9A-Za-z_-]{16,}\b", expected_failed_rerun_clipboard):
                    failed_rerun_secret_gaps.append("clipboard contains raw Google API-style key")
                failed_rerun_keyboard_feedback_seen = False
                failed_rerun_keyboard_clipboard_text = ""
                failed_rerun_keyboard_clipboard_matches = False
                failed_rerun_keyboard_secret_gaps: list[str] = []
                failed_rerun_button.evaluate(
                    """button => {
                        delete button.dataset.copyResult;
                        button.innerText = button.dataset.copyOriginalText || 'Copy failed command';
                    }"""
                )
                failed_rerun_button.focus()
                page.keyboard.press("Enter")
                try:
                    page.wait_for_function(
                        """() => document.querySelector("[aria-label='Copy failed workspace smoke command']")?.dataset.copyResult === 'copied'""",
                        timeout=timeout_ms,
                    )
                    failed_rerun_keyboard_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                failed_rerun_keyboard_clipboard_text = page.evaluate(
                    """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                )
                failed_rerun_keyboard_clipboard_normalized = failed_rerun_keyboard_clipboard_text.replace(
                    "\r\n", "\n"
                ).replace("\r", "\n")
                failed_rerun_keyboard_clipboard_matches = bool(
                    expected_failed_rerun_clipboard
                    and failed_rerun_keyboard_clipboard_normalized == expected_failed_rerun_clipboard
                )
                failed_rerun_keyboard_secret_gaps = _copy_payload_secret_gaps(
                    failed_rerun_keyboard_clipboard_normalized,
                    "workspace failed rerun keyboard clipboard",
                )
                failed_rerun_copy_gaps: list[str] = []
                if not failed_rerun_feedback_seen:
                    failed_rerun_copy_gaps.append("workspace failed rerun click activation did not report copied")
                if failed_rerun_clipboard_normalized != expected_failed_rerun_clipboard:
                    failed_rerun_copy_gaps.append("workspace failed rerun click clipboard mismatch")
                if not failed_rerun_keyboard_feedback_seen:
                    failed_rerun_copy_gaps.append("workspace failed rerun Enter activation did not report copied")
                if not failed_rerun_keyboard_clipboard_matches:
                    failed_rerun_copy_gaps.append("workspace failed rerun keyboard clipboard mismatch")
                failed_rerun_copy_gaps.extend(failed_rerun_secret_gaps)
                failed_rerun_copy_gaps.extend(failed_rerun_keyboard_secret_gaps)
                failed_rerun_button_text = failed_rerun_button.inner_text(timeout=timeout_ms)
                workspace_failed_rerun_copy_detail.update(
                    {
                        "bundle_preview": expected_failed_rerun_clipboard[:700],
                        "initial_button_text": initial_failed_rerun_text,
                        "button_text": failed_rerun_button_text,
                        "copy_feedback_seen": failed_rerun_feedback_seen,
                        "clipboard_matches": bool(
                            expected_failed_rerun_clipboard
                            and failed_rerun_clipboard_normalized == expected_failed_rerun_clipboard
                        ),
                        "secret_gaps": failed_rerun_secret_gaps,
                        "failed_rerun_keyboard_feedback_seen": failed_rerun_keyboard_feedback_seen,
                        "failed_rerun_keyboard_clipboard_matches": failed_rerun_keyboard_clipboard_matches,
                        "failed_rerun_keyboard_clipboard": failed_rerun_keyboard_clipboard_normalized[:700],
                        "failed_rerun_keyboard_secret_gaps": failed_rerun_keyboard_secret_gaps,
                        "gaps": failed_rerun_copy_gaps,
                    }
                )
                workspace_failed_rerun_copy_ok = (
                    workspace_failed_rerun_copy_ok
                    and expected_failed_rerun_clipboard.startswith("Workspace smoke failed rerun:")
                    and "Set-Location -LiteralPath" in expected_failed_rerun_clipboard
                    and "# Failed check: getdaytrends launch readiness gate" in expected_failed_rerun_clipboard
                    and "readiness_check.py" in expected_failed_rerun_clipboard
                    and "--require-live-db" in expected_failed_rerun_clipboard
                    and ("python.exe" in expected_failed_rerun_clipboard or "uv run" in expected_failed_rerun_clipboard)
                    and failed_rerun_clipboard_normalized == expected_failed_rerun_clipboard
                    and not failed_rerun_secret_gaps
                    and initial_failed_rerun_text == "Copy failed command"
                    and failed_rerun_feedback_seen
                    and failed_rerun_keyboard_feedback_seen
                    and failed_rerun_keyboard_clipboard_matches
                    and not failed_rerun_keyboard_secret_gaps
                    and not failed_rerun_copy_gaps
                )
            workspace_failure_detail_ok = (
                not workspace_smoke_failed
                or (
                    "Failed checks:" in workspace_preview_text
                    and workspace_failure_detail.get("detailText", "").startswith("Detail:")
                    and bool(workspace_failure_detail.get("commandText"))
                    and bool(workspace_failure_detail.get("outputText"))
                    and int(workspace_failure_detail.get("codeCount") or 0) >= 1
                    and int(workspace_failure_detail.get("sampleOutputCount") or 0) >= 1
                    and (
                        "getdaytrends launch readiness gate" not in workspace_preview_text
                        or "readiness_check.py" in workspace_failure_detail.get("commandText", "")
                    )
                    and not workspace_secret_gaps
                )
            )
            workspace_disclosure = first_workspace_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').slice(0, 500),
                    };
                }"""
            )
            first_workspace_view.click()
            page.wait_for_timeout(120)
            workspace_collapsed_disclosure = first_workspace_view.evaluate(
                """button => {
                    const controls = button.getAttribute('aria-controls') || '';
                    const target = controls ? document.getElementById(controls) : null;
                    return {
                        label: button.getAttribute('aria-label') || '',
                        text: (button.innerText || '').trim(),
                        expanded: button.getAttribute('aria-expanded') || '',
                        controls,
                        target_exists: Boolean(target),
                        target_hidden: Boolean(target?.hidden),
                        target_text: (target?.innerText || '').trim(),
                    };
                }"""
            )
            workspace_view_detail["preview_text"] = workspace_preview_text[:500]
            workspace_view_detail["provenance"] = workspace_provenance
            workspace_view_detail["failure_detail"] = workspace_failure_detail
            workspace_view_detail["failed_rerun_copy"] = workspace_failed_rerun_copy_detail
            workspace_view_detail["secret_gaps"] = workspace_secret_gaps
            workspace_view_detail["keyboard_open_feedback_seen"] = workspace_keyboard_open_feedback_seen
            workspace_view_detail["keyboard_collapse_feedback_seen"] = workspace_keyboard_collapse_feedback_seen
            workspace_view_detail["keyboard_open_disclosure"] = {
                **workspace_keyboard_open_disclosure,
                "target_text": workspace_keyboard_preview_text[:500],
            }
            workspace_view_detail["keyboard_collapsed_disclosure"] = workspace_keyboard_collapsed_disclosure
            workspace_view_detail["keyboard_secret_gaps"] = workspace_keyboard_secret_gaps
            workspace_view_detail["keyboard_gaps"] = workspace_keyboard_gaps
            workspace_view_detail["disclosure"] = workspace_disclosure
            workspace_view_detail["collapsed_disclosure"] = workspace_collapsed_disclosure
            workspace_view_ok = (
                workspace_view_ok
                and initial_workspace_disclosure.get("label") == "View workspace smoke"
                and initial_workspace_disclosure.get("text") == "View workspace"
                and initial_workspace_disclosure.get("expanded") == "false"
                and initial_workspace_disclosure.get("controls") == "operator-workspace-smoke-preview"
                and initial_workspace_disclosure.get("artifact_path") == workspace_smoke_path
                and initial_workspace_disclosure.get("target_exists") is True
                and initial_workspace_disclosure.get("target_hidden") is True
                and workspace_disclosure.get("label") == "Hide workspace smoke"
                and workspace_disclosure.get("text") == "Hide workspace"
                and workspace_disclosure.get("expanded") == "true"
                and workspace_disclosure.get("target_exists") is True
                and workspace_disclosure.get("target_hidden") is False
                and "Workspace smoke:" in workspace_disclosure.get("target_text", "")
                and (
                    not workspace_smoke_needs_rerun
                    or f"Workspace smoke: {workspace_smoke_expected_conclusion}"
                    in workspace_disclosure.get("target_text", "")
                )
                and workspace_collapsed_disclosure.get("label") == "View workspace smoke"
                and workspace_collapsed_disclosure.get("text") == "View workspace"
                and workspace_collapsed_disclosure.get("expanded") == "false"
                and workspace_collapsed_disclosure.get("target_exists") is True
                and workspace_collapsed_disclosure.get("target_hidden") is True
                and workspace_collapsed_disclosure.get("target_text") == ""
                and "Workspace smoke:" in workspace_preview_text
                and (
                    not workspace_smoke_needs_rerun
                    or f"Workspace smoke: {workspace_smoke_expected_conclusion}" in workspace_preview_text
                )
                and (not workspace_smoke_needs_rerun or "Run status: complete" in workspace_preview_text)
                and "Generated:" in workspace_preview_text
                and "Artifact:" in workspace_preview_text
                and "Summary:" in workspace_preview_text
                and workspace_smoke_json_ok
                and bool(workspace_provenance.get("generatedText"))
                and workspace_provenance.get("generatedDateTime") == workspace_provenance.get("generatedText")
                and str(workspace_smoke_json_payload.get("generated_at", ""))
                == workspace_provenance.get("generatedDateTime")
                and workspace_smoke_path in workspace_provenance.get("artifactText", "")
                and workspace_smoke_json_summary_text in workspace_preview_text
                and (
                    not workspace_smoke_needs_rerun
                    or workspace_provenance.get("runStatusText") == "Run status: complete"
                )
                and (not workspace_smoke_needs_rerun or "Failed checks:" in workspace_preview_text)
                and workspace_failure_detail_ok
                and not workspace_keyboard_gaps
            )
            workspace_initial_collapsed_ok = (
                initial_workspace_disclosure.get("label") == "View workspace smoke"
                and initial_workspace_disclosure.get("text") == "View workspace"
                and initial_workspace_disclosure.get("expanded") == "false"
                and initial_workspace_disclosure.get("controls") == "operator-workspace-smoke-preview"
                and initial_workspace_disclosure.get("artifact_path") == workspace_smoke_path
                and initial_workspace_disclosure.get("target_exists") is True
                and initial_workspace_disclosure.get("target_hidden") is True
            )
            workspace_keyboard_open_visible_ok = (
                workspace_keyboard_open_feedback_seen
                and workspace_keyboard_open_disclosure.get("label") == "Hide workspace smoke"
                and workspace_keyboard_open_disclosure.get("text") == "Hide workspace"
                and workspace_keyboard_open_disclosure.get("expanded") == "true"
                and workspace_keyboard_open_disclosure.get("target_exists") is True
                and workspace_keyboard_open_disclosure.get("target_hidden") is False
                and "Workspace smoke:" in workspace_keyboard_preview_text
                and (
                    not workspace_smoke_needs_rerun
                    or f"Workspace smoke: {workspace_smoke_expected_conclusion}" in workspace_keyboard_preview_text
                )
            )
            workspace_keyboard_collapsed_hidden_ok = (
                workspace_keyboard_collapse_feedback_seen
                and workspace_keyboard_collapsed_disclosure.get("label") == "View workspace smoke"
                and workspace_keyboard_collapsed_disclosure.get("text") == "View workspace"
                and workspace_keyboard_collapsed_disclosure.get("expanded") == "false"
                and workspace_keyboard_collapsed_disclosure.get("target_exists") is True
                and workspace_keyboard_collapsed_disclosure.get("target_hidden") is True
                and workspace_keyboard_collapsed_disclosure.get("target_text") == ""
            )
            workspace_click_open_visible_ok = (
                workspace_disclosure.get("label") == "Hide workspace smoke"
                and workspace_disclosure.get("text") == "Hide workspace"
                and workspace_disclosure.get("expanded") == "true"
                and workspace_disclosure.get("target_exists") is True
                and workspace_disclosure.get("target_hidden") is False
                and "Workspace smoke:" in workspace_disclosure.get("target_text", "")
                and (
                    not workspace_smoke_needs_rerun
                    or f"Workspace smoke: {workspace_smoke_expected_conclusion}"
                    in workspace_disclosure.get("target_text", "")
                )
            )
            workspace_click_collapsed_hidden_ok = (
                workspace_collapsed_disclosure.get("label") == "View workspace smoke"
                and workspace_collapsed_disclosure.get("text") == "View workspace"
                and workspace_collapsed_disclosure.get("expanded") == "false"
                and workspace_collapsed_disclosure.get("target_exists") is True
                and workspace_collapsed_disclosure.get("target_hidden") is True
                and workspace_collapsed_disclosure.get("target_text") == ""
            )
            workspace_preview_content_ok = (
                "Workspace smoke:" in workspace_preview_text
                and (
                    not workspace_smoke_needs_rerun
                    or f"Workspace smoke: {workspace_smoke_expected_conclusion}" in workspace_preview_text
                )
                and (not workspace_smoke_needs_rerun or "Run status: complete" in workspace_preview_text)
                and "Generated:" in workspace_preview_text
                and "Artifact:" in workspace_preview_text
                and "Summary:" in workspace_preview_text
                and workspace_smoke_json_summary_text in workspace_preview_text
            )
            workspace_provenance_ok = (
                bool(workspace_provenance.get("generatedText"))
                and workspace_provenance.get("generatedDateTime") == workspace_provenance.get("generatedText")
                and str(workspace_smoke_json_payload.get("generated_at", ""))
                == workspace_provenance.get("generatedDateTime")
                and workspace_smoke_path in workspace_provenance.get("artifactText", "")
                and (
                    not workspace_smoke_needs_rerun
                    or workspace_provenance.get("runStatusText") == "Run status: complete"
                )
            )
            workspace_view_detail = {
                "expected_mode": "operator_workspace_smoke_disclosure_lifecycle",
                "view_button_count": workspace_view_button_count,
                "workspace_smoke_path_present": bool(workspace_smoke_path),
                "workspace_smoke_rerun_expected_mode": workspace_smoke_rerun_expected_mode,
                "workspace_smoke_expected_conclusion": workspace_smoke_expected_conclusion
                if workspace_smoke_needs_rerun
                else None,
                "workspace_smoke_json_ok": workspace_smoke_json_ok,
                "workspace_smoke_json_status": str(workspace_smoke_json_payload.get("status", "")),
                "workspace_smoke_json_result_count": len(workspace_smoke_json_results)
                if isinstance(workspace_smoke_json_results, list)
                else 0,
                "workspace_smoke_json_summary_text": workspace_smoke_json_summary_text,
                "workspace_smoke_json_missing_fields": workspace_smoke_json_missing_fields,
                "initial_collapsed_ok": workspace_initial_collapsed_ok,
                "keyboard_open_visible_ok": workspace_keyboard_open_visible_ok,
                "keyboard_collapsed_hidden_ok": workspace_keyboard_collapsed_hidden_ok,
                "click_open_visible_ok": workspace_click_open_visible_ok,
                "click_collapsed_hidden_ok": workspace_click_collapsed_hidden_ok,
                "preview_content_ok": workspace_preview_content_ok,
                "provenance_ok": workspace_provenance_ok,
                "failure_detail_ok": workspace_failure_detail_ok,
                "failed_rerun_copy_ok": workspace_failed_rerun_copy_ok,
                "failed_rerun_copy_button_count": workspace_failed_rerun_copy_detail.get("copy_button_count", 0),
                "failed_rerun_keyboard_feedback_seen": workspace_failed_rerun_copy_detail.get(
                    "failed_rerun_keyboard_feedback_seen"
                ),
                "failed_rerun_keyboard_clipboard_matches": workspace_failed_rerun_copy_detail.get(
                    "failed_rerun_keyboard_clipboard_matches"
                ),
                "secret_gaps": workspace_secret_gaps,
                "keyboard_secret_gaps": workspace_keyboard_secret_gaps,
                "keyboard_gaps": workspace_keyboard_gaps,
                "failed_rerun_secret_gaps": workspace_failed_rerun_copy_detail.get("secret_gaps", []),
                "failed_rerun_keyboard_secret_gaps": workspace_failed_rerun_copy_detail.get(
                    "failed_rerun_keyboard_secret_gaps",
                    [],
                ),
                "failed_rerun_gaps": workspace_failed_rerun_copy_detail.get("gaps", []),
            }
        _record_check(checks, "operator_workspace_smoke_view", workspace_view_ok, workspace_view_detail)
        _record_check(
            checks,
            "operator_workspace_smoke_failed_rerun_copy",
            workspace_failed_rerun_copy_ok,
            workspace_failed_rerun_copy_detail,
        )

        artifact_keyboard_detail: dict[str, Any] = {
            "artifact_key": "readiness_report",
            "expected_order": ["View report", "Copy path"],
            "focus_order_reference": W3C_WCAG_FOCUS_ORDER_URL,
            "target_size_reference": W3C_WCAG_TARGET_SIZE_MINIMUM_URL,
        }
        artifact_keyboard_ok = False
        artifact_keyboard_gaps: list[str] = []
        artifact_keyboard_group = page.locator(
            "#operator-artifacts [data-artifact-key='readiness_report'] [data-artifact-action-group='true']"
        )
        artifact_keyboard_group_count = artifact_keyboard_group.count()
        artifact_keyboard_detail["group_count"] = artifact_keyboard_group_count
        if readiness_report_path and artifact_keyboard_group_count:
            page.evaluate(
                """() => {
                    const group = document.querySelector('#operator-artifacts [data-artifact-key="readiness_report"] [data-artifact-action-group="true"]');
                    if (!group) return;
                    Array.from(group.querySelectorAll('button')).forEach(button => {
                        delete button.dataset.copyResult;
                        if (button.dataset.copyOriginalText) button.innerText = button.dataset.copyOriginalText;
                        if (button.getAttribute('aria-expanded') === 'true') button.click();
                    });
                }"""
            )
            page.wait_for_timeout(150)
            artifact_keyboard_buttons = artifact_keyboard_group.locator("button")
            artifact_keyboard_button_count = artifact_keyboard_buttons.count()
            artifact_keyboard_detail["button_count"] = artifact_keyboard_button_count
            artifact_keyboard_buttons.nth(0).focus()
            artifact_focused_sequence: list[dict[str, Any]] = []
            for _ in artifact_keyboard_detail["expected_order"]:
                focused_state = page.evaluate(
                    """() => {
                        const active = document.activeElement;
                        const rect = active?.getBoundingClientRect?.();
                        const group = active?.closest?.('[data-artifact-action-group="true"]');
                        const action = active?.closest?.('.operator-action');
                        return {
                            text: (active?.innerText || '').trim(),
                            ariaLabel: active?.getAttribute?.('aria-label') || '',
                            type: active?.getAttribute?.('type') || '',
                            inArtifactActionGroup: Boolean(group),
                            groupRole: group?.getAttribute('role') || '',
                            groupLabel: group?.getAttribute('aria-label') || '',
                            artifactKey: action?.getAttribute('data-artifact-key') || '',
                            height: rect ? Math.round(rect.height) : 0,
                        };
                    }"""
                )
                artifact_focused_sequence.append(focused_state)
                page.keyboard.press("Tab")
                page.wait_for_timeout(35)
            readiness_keyboard_copy = page.locator(
                "#operator-artifacts [data-artifact-key='readiness_report'] [aria-label='Copy readiness report path']"
            ).first
            readiness_keyboard_copy.evaluate(
                """button => {
                    delete button.dataset.copyResult;
                    if (button.dataset.copyOriginalText) button.innerText = button.dataset.copyOriginalText;
                }"""
            )
            readiness_keyboard_copy.focus()
            page.keyboard.press("Enter")
            readiness_keyboard_feedback_seen = False
            try:
                page.wait_for_function(
                    f"""async () => {{
                        const button = document.querySelector('#operator-artifacts [data-artifact-key="readiness_report"] [aria-label="Copy readiness report path"]');
                        const clipboardText = navigator.clipboard?.readText ? await navigator.clipboard.readText() : '';
                        return button?.dataset.copyResult === 'copied'
                            && clipboardText.trim() === {json.dumps(readiness_report_path)};
                    }}""",
                    timeout=timeout_ms,
                )
                readiness_keyboard_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            readiness_keyboard_clipboard = page.evaluate(
                """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
            )
            provider_packet_keyboard_feedback_seen = False
            provider_packet_keyboard_clipboard = ""
            provider_packet_keyboard_secret_gaps: list[str] = []
            provider_packet_keyboard_clipboard_matches = not provider_packet_artifact_path
            launch_secret_scan_refresh_keyboard_feedback_seen = False
            launch_secret_scan_refresh_keyboard_clipboard = ""
            launch_secret_scan_refresh_keyboard_secret_gaps: list[str] = []
            launch_secret_scan_refresh_keyboard_clipboard_matches = not launch_secret_scan_refresh_command
            tap_fixture_refresh_keyboard_feedback_seen = False
            tap_fixture_refresh_keyboard_clipboard = ""
            tap_fixture_refresh_keyboard_secret_gaps: list[str] = []
            tap_fixture_refresh_keyboard_clipboard_matches = not tap_fixture_refresh_command
            if provider_packet_artifact_path:
                provider_packet_keyboard_copy = page.locator(
                    "#operator-artifacts [data-artifact-key='provider_auth_recovery_packet'] "
                    "[aria-label='Copy provider recovery packet path']"
                ).first
                provider_packet_keyboard_button_count = provider_packet_keyboard_copy.count()
                if provider_packet_keyboard_button_count:
                    provider_packet_keyboard_copy.evaluate(
                        """button => {
                            delete button.dataset.copyResult;
                            if (button.dataset.copyOriginalText) button.innerText = button.dataset.copyOriginalText;
                        }"""
                    )
                    provider_packet_keyboard_copy.focus()
                    page.keyboard.press("Space")
                    try:
                        page.wait_for_function(
                            f"""async () => {{
                                const button = document.querySelector('#operator-artifacts [data-artifact-key="provider_auth_recovery_packet"] [aria-label="Copy provider recovery packet path"]');
                                const clipboardText = navigator.clipboard?.readText ? await navigator.clipboard.readText() : '';
                                return button?.dataset.copyResult === 'copied'
                                    && clipboardText.trim() === {json.dumps(provider_packet_artifact_path)};
                            }}""",
                            timeout=timeout_ms,
                        )
                        provider_packet_keyboard_feedback_seen = True
                    except PlaywrightTimeoutError:
                        pass
                    provider_packet_keyboard_clipboard = page.evaluate(
                        """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                    )
                    provider_packet_keyboard_clipboard_matches = (
                        provider_packet_keyboard_clipboard.strip() == provider_packet_artifact_path
                    )
                    provider_packet_keyboard_secret_gaps = _copy_payload_secret_gaps(
                        provider_packet_keyboard_clipboard,
                        "provider packet artifact keyboard clipboard",
                    )
                else:
                    artifact_keyboard_gaps.append("provider packet keyboard copy button missing")
            if launch_secret_scan_refresh_command:
                launch_secret_scan_refresh_keyboard_copy = page.locator(
                    "#operator-artifacts [data-artifact-key='launch_secret_scan_refresh'] "
                    "[aria-label='Copy launch secret scan refresh command']"
                ).first
                launch_secret_scan_refresh_keyboard_button_count = launch_secret_scan_refresh_keyboard_copy.count()
                if launch_secret_scan_refresh_keyboard_button_count:
                    launch_secret_scan_refresh_keyboard_copy.evaluate(
                        """button => {
                            delete button.dataset.copyResult;
                            if (button.dataset.copyOriginalText) button.innerText = button.dataset.copyOriginalText;
                        }"""
                    )
                    launch_secret_scan_refresh_keyboard_copy.focus()
                    page.keyboard.press("Enter")
                    try:
                        page.wait_for_function(
                            f"""async () => {{
                                const button = document.querySelector('#operator-artifacts [data-artifact-key="launch_secret_scan_refresh"] [aria-label="Copy launch secret scan refresh command"]');
                                const clipboardText = navigator.clipboard?.readText ? await navigator.clipboard.readText() : '';
                                return button?.dataset.copyResult === 'copied'
                                    && clipboardText.trim() === {json.dumps(launch_secret_scan_refresh_command)};
                            }}""",
                            timeout=timeout_ms,
                        )
                        launch_secret_scan_refresh_keyboard_feedback_seen = True
                    except PlaywrightTimeoutError:
                        pass
                    launch_secret_scan_refresh_keyboard_clipboard = page.evaluate(
                        """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                    )
                    launch_secret_scan_refresh_keyboard_clipboard_matches = (
                        launch_secret_scan_refresh_keyboard_clipboard.strip() == launch_secret_scan_refresh_command
                    )
                    launch_secret_scan_refresh_keyboard_secret_gaps = _copy_payload_secret_gaps(
                        launch_secret_scan_refresh_keyboard_clipboard,
                        "launch secret scan refresh keyboard clipboard",
                    )
                else:
                    artifact_keyboard_gaps.append("launch secret scan refresh keyboard copy button missing")
            if tap_fixture_refresh_command:
                tap_fixture_refresh_keyboard_copy = page.locator(
                    "#operator-artifacts [data-artifact-key='tap_fixture_refresh'] "
                    "[aria-label='Copy TAP fixture refresh command']"
                ).first
                tap_fixture_refresh_keyboard_button_count = tap_fixture_refresh_keyboard_copy.count()
                if tap_fixture_refresh_keyboard_button_count:
                    tap_fixture_refresh_keyboard_copy.evaluate(
                        """button => {
                            delete button.dataset.copyResult;
                            if (button.dataset.copyOriginalText) button.innerText = button.dataset.copyOriginalText;
                        }"""
                    )
                    tap_fixture_refresh_keyboard_copy.focus()
                    page.keyboard.press("Enter")
                    try:
                        page.wait_for_function(
                            f"""async () => {{
                                const button = document.querySelector('#operator-artifacts [data-artifact-key="tap_fixture_refresh"] [aria-label="Copy TAP fixture refresh command"]');
                                const clipboardText = navigator.clipboard?.readText ? await navigator.clipboard.readText() : '';
                                return button?.dataset.copyResult === 'copied'
                                    && clipboardText.trim() === {json.dumps(tap_fixture_refresh_command)};
                            }}""",
                            timeout=timeout_ms,
                        )
                        tap_fixture_refresh_keyboard_feedback_seen = True
                    except PlaywrightTimeoutError:
                        pass
                    tap_fixture_refresh_keyboard_clipboard = page.evaluate(
                        """async () => navigator.clipboard?.readText ? await navigator.clipboard.readText() : ''"""
                    )
                    tap_fixture_refresh_keyboard_clipboard_matches = (
                        tap_fixture_refresh_keyboard_clipboard.strip() == tap_fixture_refresh_command
                    )
                    tap_fixture_refresh_keyboard_secret_gaps = _copy_payload_secret_gaps(
                        tap_fixture_refresh_keyboard_clipboard,
                        "TAP fixture refresh keyboard clipboard",
                    )
                else:
                    artifact_keyboard_gaps.append("TAP fixture refresh keyboard copy button missing")
            artifact_focused_texts = [str(item.get("text") or "") for item in artifact_focused_sequence]
            artifact_keyboard_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", readiness_keyboard_clipboard, re.IGNORECASE):
                artifact_keyboard_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", readiness_keyboard_clipboard, re.IGNORECASE):
                artifact_keyboard_secret_gaps.append("clipboard contains raw tenant user")
            if artifact_focused_texts != artifact_keyboard_detail["expected_order"]:
                artifact_keyboard_gaps.append("artifact keyboard focus order changed")
            if not all(item.get("inArtifactActionGroup") for item in artifact_focused_sequence):
                artifact_keyboard_gaps.append("focus left artifact action group")
            if not all(item.get("artifactKey") == "readiness_report" for item in artifact_focused_sequence):
                artifact_keyboard_gaps.append("focus left readiness artifact row")
            if not all(item.get("groupRole") == "group" for item in artifact_focused_sequence):
                artifact_keyboard_gaps.append("artifact group role missing during focus")
            if not all(item.get("groupLabel") == "Readiness report artifact actions" for item in artifact_focused_sequence):
                artifact_keyboard_gaps.append("artifact group label changed during focus")
            if any(int(item.get("height") or 0) < 28 for item in artifact_focused_sequence):
                artifact_keyboard_gaps.append("focused artifact action target height below 28px")
            if not all(str(item.get("type") or "") == "button" for item in artifact_focused_sequence):
                artifact_keyboard_gaps.append("focused artifact action button type missing")
            if not readiness_keyboard_feedback_seen:
                artifact_keyboard_gaps.append("readiness report Enter activation did not report copied")
            if readiness_keyboard_clipboard.strip() != readiness_report_path:
                artifact_keyboard_gaps.append("readiness report keyboard clipboard mismatch")
            if provider_packet_artifact_path and not provider_packet_keyboard_feedback_seen:
                artifact_keyboard_gaps.append("provider packet Space activation did not report copied")
            if not provider_packet_keyboard_clipboard_matches:
                artifact_keyboard_gaps.append("provider packet keyboard clipboard mismatch")
            if launch_secret_scan_refresh_command and not launch_secret_scan_refresh_keyboard_feedback_seen:
                artifact_keyboard_gaps.append("launch secret scan refresh Enter activation did not report copied")
            if not launch_secret_scan_refresh_keyboard_clipboard_matches:
                artifact_keyboard_gaps.append("launch secret scan refresh keyboard clipboard mismatch")
            if tap_fixture_refresh_command and not tap_fixture_refresh_keyboard_feedback_seen:
                artifact_keyboard_gaps.append("TAP fixture refresh Enter activation did not report copied")
            if not tap_fixture_refresh_keyboard_clipboard_matches:
                artifact_keyboard_gaps.append("TAP fixture refresh keyboard clipboard mismatch")
            artifact_keyboard_gaps.extend(artifact_keyboard_secret_gaps)
            artifact_keyboard_gaps.extend(provider_packet_keyboard_secret_gaps)
            artifact_keyboard_gaps.extend(launch_secret_scan_refresh_keyboard_secret_gaps)
            artifact_keyboard_gaps.extend(tap_fixture_refresh_keyboard_secret_gaps)
            artifact_keyboard_detail.update(
                {
                    "focused_sequence": artifact_focused_sequence,
                    "focused_texts": artifact_focused_texts,
                    "readiness_keyboard_feedback_seen": readiness_keyboard_feedback_seen,
                    "clipboard_text": readiness_keyboard_clipboard[:400],
                    "secret_gaps": artifact_keyboard_secret_gaps,
                    "provider_packet_keyboard_feedback_seen": provider_packet_keyboard_feedback_seen,
                    "provider_packet_keyboard_clipboard_matches": provider_packet_keyboard_clipboard_matches,
                    "provider_packet_keyboard_clipboard": provider_packet_keyboard_clipboard[:400],
                    "provider_packet_keyboard_secret_gaps": provider_packet_keyboard_secret_gaps,
                    "launch_secret_scan_refresh_keyboard_feedback_seen": (
                        launch_secret_scan_refresh_keyboard_feedback_seen
                    ),
                    "launch_secret_scan_refresh_keyboard_clipboard_matches": (
                        launch_secret_scan_refresh_keyboard_clipboard_matches
                    ),
                    "launch_secret_scan_refresh_keyboard_clipboard": (
                        launch_secret_scan_refresh_keyboard_clipboard[:600]
                    ),
                    "launch_secret_scan_refresh_keyboard_secret_gaps": (
                        launch_secret_scan_refresh_keyboard_secret_gaps
                    ),
                    "tap_fixture_refresh_keyboard_feedback_seen": tap_fixture_refresh_keyboard_feedback_seen,
                    "tap_fixture_refresh_keyboard_clipboard_matches": tap_fixture_refresh_keyboard_clipboard_matches,
                    "tap_fixture_refresh_keyboard_clipboard": tap_fixture_refresh_keyboard_clipboard[:600],
                    "tap_fixture_refresh_keyboard_secret_gaps": tap_fixture_refresh_keyboard_secret_gaps,
                    "gaps": artifact_keyboard_gaps,
                }
            )
            artifact_keyboard_ok = not artifact_keyboard_gaps
        else:
            if not readiness_report_path:
                artifact_keyboard_gaps.append("readiness report path missing")
            if not artifact_keyboard_group_count:
                artifact_keyboard_gaps.append("readiness artifact action group missing")
            artifact_keyboard_detail["gaps"] = artifact_keyboard_gaps
        _record_check(
            checks,
            "operator_artifact_action_group_keyboard_activation",
            artifact_keyboard_ok,
            artifact_keyboard_detail,
        )

        copy_failure_buttons = page.locator("[aria-label='Copy remediation action']")
        copy_failure_button_count = copy_failure_buttons.count()
        copy_failure_detail: dict[str, Any] = {"copy_button_count": copy_failure_button_count}
        copy_failure_ok = True
        if copy_failure_button_count:
            manual_dialog_initial_state = page.evaluate(
                """() => {
                    const panel = document.getElementById('manual-copy-panel');
                    return {
                        hidden: panel?.hidden ?? null,
                        ariaHidden: panel?.getAttribute('aria-hidden') || '',
                        shown: panel?.classList.contains('show') ?? false,
                    };
                }"""
            )
            expected_manual_text = copy_failure_buttons.first.evaluate(
                """button => {
                    const action = button.closest('.operator-action');
                    const code = action?.querySelector('code');
                    return (code?.innerText || '').trim();
                }"""
            )
            page.evaluate(
                """() => {
                    window.__gdtCopyFailureOriginals = {
                        clipboardDescriptor: Object.getOwnPropertyDescriptor(Navigator.prototype, 'clipboard'),
                        execCommand: document.execCommand,
                    };
                    Object.defineProperty(Navigator.prototype, 'clipboard', {
                        configurable: true,
                        get() {
                            return {
                                writeText: async () => { throw new Error('forced clipboard failure'); },
                                readText: async () => '',
                            };
                        },
                    });
                    document.execCommand = () => false;
                }"""
            )
            try:
                copy_failure_buttons.first.click()
                copy_failure_feedback_seen = False
                try:
                    page.wait_for_function(
                        """() => {
                            const toast = document.getElementById('toast');
                            return document.querySelector("[aria-label='Copy remediation action']")?.dataset.copyResult === 'failed'
                                && toast
                                && toast.dataset.lastToastType === 'error'
                                && toast.dataset.lastToastRole === 'alert'
                                && toast.dataset.lastToastLive === 'assertive'
                                && toast.textContent.includes('Copy failed')
                                && document.getElementById('manual-copy-panel')?.classList.contains('show')
                                && document.getElementById('manual-copy-panel')?.hidden === false
                                && !document.getElementById('manual-copy-panel')?.hasAttribute('aria-hidden')
                                && (document.getElementById('manual-copy-text')?.value || '').trim().length > 0;
                        }""",
                        timeout=timeout_ms,
                    )
                    copy_failure_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                toast_text = page.locator("#toast").inner_text(timeout=timeout_ms)
                toast_accessibility = page.evaluate(
                    """() => {
                        const toast = document.getElementById('toast');
                        return {
                            lastType: toast?.dataset.lastToastType || '',
                            lastRole: toast?.dataset.lastToastRole || '',
                            lastLive: toast?.dataset.lastToastLive || '',
                            role: toast?.getAttribute('role') || '',
                            live: toast?.getAttribute('aria-live') || '',
                        };
                    }"""
                )
                button_text = copy_failure_buttons.first.inner_text(timeout=timeout_ms)
                copy_result = page.evaluate(
                    """() => document.querySelector("[aria-label='Copy remediation action']")?.dataset.copyResult || ''"""
                )
                manual_panel_visible = page.locator("#manual-copy-panel.show").count() > 0
                manual_panel_open_state = page.evaluate(
                    """() => {
                        const panel = document.getElementById('manual-copy-panel');
                        return {
                            hidden: panel?.hidden ?? null,
                            ariaHidden: panel?.getAttribute('aria-hidden') || '',
                            shown: panel?.classList.contains('show') ?? false,
                        };
                    }"""
                )
                manual_copy_text = page.locator("#manual-copy-text").input_value(timeout=timeout_ms)
                page.keyboard.press("Escape")
                try:
                    page.wait_for_function(
                        """() => !document.getElementById('manual-copy-panel')?.classList.contains('show')
                            && document.getElementById('manual-copy-panel')?.hidden === true
                            && !document.getElementById('manual-copy-panel')?.hasAttribute('aria-hidden')
                            && (document.getElementById('manual-copy-text')?.value || '') === ''
                            && document.activeElement === document.querySelector("[aria-label='Copy remediation action']")""",
                        timeout=timeout_ms,
                    )
                except PlaywrightTimeoutError:
                    pass
                manual_panel_closed_on_escape = page.locator("#manual-copy-panel.show").count() == 0
                manual_dialog_escape_state = page.evaluate(
                    """() => {
                        const panel = document.getElementById('manual-copy-panel');
                        return {
                            hidden: panel?.hidden ?? null,
                            ariaHidden: panel?.getAttribute('aria-hidden') || '',
                            shown: panel?.classList.contains('show') ?? false,
                        };
                    }"""
                )
                manual_copy_cleared_on_escape = page.locator("#manual-copy-text").input_value(timeout=timeout_ms) == ""
                manual_focus_returned_on_escape = bool(
                    page.evaluate(
                        """() => document.activeElement === document.querySelector("[aria-label='Copy remediation action']")"""
                    )
                )
                copy_failure_buttons.first.click()
                manual_panel_reopened_for_close = False
                try:
                    page.wait_for_function(
                        """() => document.querySelector("[aria-label='Copy remediation action']")?.dataset.copyResult === 'failed'
                            && document.getElementById('manual-copy-panel')?.classList.contains('show')
                            && document.getElementById('manual-copy-panel')?.hidden === false
                            && !document.getElementById('manual-copy-panel')?.hasAttribute('aria-hidden')
                            && (document.getElementById('manual-copy-text')?.value || '').trim().length > 0""",
                        timeout=timeout_ms,
                    )
                    manual_panel_reopened_for_close = True
                except PlaywrightTimeoutError:
                    pass
                close_button = page.locator("[aria-label='Close manual copy panel']")
                close_button.click(timeout=timeout_ms)
                try:
                    page.wait_for_function(
                        """() => !document.getElementById('manual-copy-panel')?.classList.contains('show')
                            && document.getElementById('manual-copy-panel')?.hidden === true
                            && !document.getElementById('manual-copy-panel')?.hasAttribute('aria-hidden')
                            && (document.getElementById('manual-copy-text')?.value || '') === ''
                            && document.activeElement === document.querySelector("[aria-label='Copy remediation action']")""",
                        timeout=timeout_ms,
                    )
                except PlaywrightTimeoutError:
                    pass
                manual_panel_closed_on_close = page.locator("#manual-copy-panel.show").count() == 0
                manual_dialog_close_state = page.evaluate(
                    """() => {
                        const panel = document.getElementById('manual-copy-panel');
                        return {
                            hidden: panel?.hidden ?? null,
                            ariaHidden: panel?.getAttribute('aria-hidden') || '',
                            shown: panel?.classList.contains('show') ?? false,
                        };
                    }"""
                )
                manual_copy_cleared_on_close = page.locator("#manual-copy-text").input_value(timeout=timeout_ms) == ""
                manual_focus_returned_on_close = bool(
                    page.evaluate(
                        """() => document.activeElement === document.querySelector("[aria-label='Copy remediation action']")"""
                    )
                )
                copy_failure_expected_mode = "remediation_copy_failure_manual_copy_dialog"
                copy_failure_detail.update(
                    {
                        "expected_mode": copy_failure_expected_mode,
                        "button_text": button_text,
                        "copy_result_failed_ok": copy_result == "failed",
                        "toast_error_accessible_ok": "Copy failed" in toast_text
                        and toast_accessibility.get("lastType") == "error"
                        and toast_accessibility.get("lastRole") == "alert"
                        and toast_accessibility.get("lastLive") == "assertive",
                        "initial_panel_closed_ok": manual_dialog_initial_state.get("hidden") is True
                        and manual_dialog_initial_state.get("ariaHidden") == ""
                        and manual_dialog_initial_state.get("shown") is False,
                        "manual_panel_open_ok": manual_panel_visible
                        and manual_panel_open_state.get("hidden") is False
                        and manual_panel_open_state.get("ariaHidden") == ""
                        and manual_panel_open_state.get("shown") is True,
                        "manual_copy_text_length": len(manual_copy_text.strip()),
                        "manual_copy_text_matches": manual_copy_text.strip() == str(expected_manual_text).strip(),
                        "escape_closed_panel_ok": manual_panel_closed_on_escape
                        and manual_dialog_escape_state.get("hidden") is True
                        and manual_dialog_escape_state.get("ariaHidden") == ""
                        and manual_dialog_escape_state.get("shown") is False,
                        "escape_cleared_text_ok": manual_copy_cleared_on_escape,
                        "escape_focus_returned_ok": manual_focus_returned_on_escape,
                        "close_reopened_panel_ok": manual_panel_reopened_for_close,
                        "close_closed_panel_ok": manual_panel_closed_on_close
                        and manual_dialog_close_state.get("hidden") is True
                        and manual_dialog_close_state.get("ariaHidden") == ""
                        and manual_dialog_close_state.get("shown") is False,
                        "close_cleared_text_ok": manual_copy_cleared_on_close,
                        "close_focus_returned_ok": manual_focus_returned_on_close,
                    }
                )
                copy_failure_ok = (
                    copy_failure_feedback_seen
                    and copy_result == "failed"
                    and "Copy failed" in toast_text
                    and toast_accessibility.get("lastType") == "error"
                    and toast_accessibility.get("lastRole") == "alert"
                    and toast_accessibility.get("lastLive") == "assertive"
                    and manual_dialog_initial_state.get("hidden") is True
                    and manual_dialog_initial_state.get("ariaHidden") == ""
                    and manual_dialog_initial_state.get("shown") is False
                    and manual_panel_visible
                    and manual_panel_open_state.get("hidden") is False
                    and manual_panel_open_state.get("ariaHidden") == ""
                    and manual_panel_open_state.get("shown") is True
                    and manual_copy_text.strip() == str(expected_manual_text).strip()
                    and manual_panel_closed_on_escape
                    and manual_dialog_escape_state.get("hidden") is True
                    and manual_dialog_escape_state.get("ariaHidden") == ""
                    and manual_dialog_escape_state.get("shown") is False
                    and manual_copy_cleared_on_escape
                    and manual_focus_returned_on_escape
                    and manual_panel_reopened_for_close
                    and manual_panel_closed_on_close
                    and manual_dialog_close_state.get("hidden") is True
                    and manual_dialog_close_state.get("ariaHidden") == ""
                    and manual_dialog_close_state.get("shown") is False
                    and manual_copy_cleared_on_close
                    and manual_focus_returned_on_close
                )
            finally:
                page.evaluate(
                    """() => {
                        const originals = window.__gdtCopyFailureOriginals || {};
                        if (originals.clipboardDescriptor) {
                            Object.defineProperty(Navigator.prototype, 'clipboard', originals.clipboardDescriptor);
                        } else {
                            delete Navigator.prototype.clipboard;
                        }
                        if (originals.execCommand) {
                            document.execCommand = originals.execCommand;
                        }
                        delete window.__gdtCopyFailureOriginals;
                    }"""
        )
        _record_check(checks, "operator_copy_failure_feedback", copy_failure_ok, copy_failure_detail)

        async_denied_detail: dict[str, Any] = {"copy_button_count": copy_failure_button_count}
        async_denied_ok = copy_failure_button_count == 0
        if copy_failure_button_count:
            expected_manual_text = copy_failure_buttons.first.evaluate(
                """button => {
                    const action = button.closest('.operator-action');
                    const code = action?.querySelector('code');
                    return (code?.innerText || '').trim();
                }"""
            )
            page.evaluate(
                """() => {
                    hideManualCopy({ restoreFocus: false });
                    const button = document.querySelector("[aria-label='Copy remediation action']");
                    if (button) {
                        delete button.dataset.copyResult;
                        button.innerText = 'Copy remediation action';
                    }
                    window.__gdtAsyncDeniedOriginals = {
                        clipboardDescriptor: Object.getOwnPropertyDescriptor(Navigator.prototype, 'clipboard'),
                        execCommand: document.execCommand,
                    };
                    window.__gdtAsyncDeniedExecCommandCalled = false;
                    Object.defineProperty(Navigator.prototype, 'clipboard', {
                        configurable: true,
                        get() {
                            return {
                                writeText: async () => { throw new Error('async clipboard denied'); },
                                readText: async () => 'unchanged clipboard',
                            };
                        },
                    });
                    document.execCommand = () => {
                        window.__gdtAsyncDeniedExecCommandCalled = true;
                        return true;
                    };
                }"""
            )
            try:
                copy_failure_buttons.first.click()
                async_denied_feedback_seen = False
                try:
                    page.wait_for_function(
                        """() => document.querySelector("[aria-label='Copy remediation action']")?.dataset.copyResult === 'failed'
                            && document.getElementById('manual-copy-panel')?.classList.contains('show')
                            && document.getElementById('manual-copy-panel')?.hidden === false
                            && (document.getElementById('manual-copy-text')?.value || '').trim().length > 0
                            && (document.getElementById('toast')?.textContent || '').includes('Copy failed')""",
                        timeout=timeout_ms,
                    )
                    async_denied_feedback_seen = True
                except PlaywrightTimeoutError:
                    pass
                async_denied_state = page.evaluate(
                    """() => ({
                        copyResult: document.querySelector("[aria-label='Copy remediation action']")?.dataset.copyResult || '',
                        buttonText: document.querySelector("[aria-label='Copy remediation action']")?.innerText || '',
                        manualVisible: document.getElementById('manual-copy-panel')?.classList.contains('show') || false,
                        manualHidden: document.getElementById('manual-copy-panel')?.hidden ?? null,
                        manualText: document.getElementById('manual-copy-text')?.value || '',
                        toastText: document.getElementById('toast')?.textContent || '',
                        toastType: document.getElementById('toast')?.dataset.lastToastType || '',
                        execCommandCalled: Boolean(window.__gdtAsyncDeniedExecCommandCalled),
                    })"""
                )
                async_denied_expected_mode = "remediation_action_async_clipboard_denied_manual_copy"
                async_denied_manual_text = async_denied_state.get("manualText", "")
                async_denied_detail.update(
                    {
                        "expected_mode": async_denied_expected_mode,
                        "feedback_seen_ok": async_denied_feedback_seen,
                        "copy_result_failed_ok": async_denied_state.get("copyResult") == "failed",
                        "manual_panel_open_ok": async_denied_state.get("manualVisible") is True
                        and async_denied_state.get("manualHidden") is False,
                        "manual_text_matches": async_denied_manual_text.strip() == str(expected_manual_text).strip(),
                        "toast_error_ok": "Copy failed" in async_denied_state.get("toastText", "")
                        and async_denied_state.get("toastType") == "error",
                        "no_exec_command_fallback_ok": async_denied_state.get("execCommandCalled") is False,
                        "button_text": async_denied_state.get("buttonText", ""),
                        "manual_text_length": len(async_denied_manual_text.strip()),
                        "manual_text_sample": async_denied_manual_text[:700],
                        "expected_text": str(expected_manual_text)[:700],
                    }
                )
                async_denied_ok = (
                    async_denied_feedback_seen
                    and async_denied_state.get("copyResult") == "failed"
                    and async_denied_state.get("manualVisible") is True
                    and async_denied_state.get("manualHidden") is False
                    and async_denied_state.get("manualText", "").strip() == str(expected_manual_text).strip()
                    and "Copy failed" in async_denied_state.get("toastText", "")
                    and async_denied_state.get("toastType") == "error"
                    and async_denied_state.get("execCommandCalled") is False
                )
            finally:
                page.evaluate(
                    """() => {
                        const originals = window.__gdtAsyncDeniedOriginals || {};
                        if (originals.clipboardDescriptor) {
                            Object.defineProperty(Navigator.prototype, 'clipboard', originals.clipboardDescriptor);
                        } else {
                            delete Navigator.prototype.clipboard;
                        }
                        if (originals.execCommand) {
                            document.execCommand = originals.execCommand;
                        }
                        delete window.__gdtAsyncDeniedOriginals;
                        delete window.__gdtAsyncDeniedExecCommandCalled;
                        hideManualCopy({ restoreFocus: false });
                    }"""
                )
        _record_check(
            checks,
            "operator_copy_async_clipboard_denied_fail_closed",
            async_denied_ok,
            async_denied_detail,
        )

        return_page = context.new_page()
        return_page.on(
            "console",
            lambda msg: (
                console_errors.append(msg.text)
                if msg.type == "error"
                else console_warnings.append(msg.text)
                if msg.type == "warning"
                else None
            ),
        )
        return_page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        success_return_state: dict[str, Any] = {}
        session_status_state: dict[str, Any] = {}
        session_status_detail: dict[str, Any] = {}
        dismissed_return_state: dict[str, Any] = {}
        cancel_return_state: dict[str, Any] = {}
        session_status_recovery_ok = False
        return_notice_errors: list[str] = []
        try:
            return_page.goto(
                f"{base_url}/?tap_checkout=success&tap_keyword=browser%20smoke%20source%20signal&tap_checkout_session_id=cs_test_return",
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            try:
                return_page.wait_for_selector("#tap-checkout-return-notice:not([hidden])", timeout=timeout_ms)
            except PlaywrightTimeoutError as exc:
                return_notice_errors.append(f"success notice timeout: {exc}")
            try:
                return_page.wait_for_function(DASHBOARD_CONTENT_READY_JS, timeout=timeout_ms)
            except PlaywrightTimeoutError:
                return_page.wait_for_timeout(1200)
            success_return_state = return_page.evaluate(TAP_CHECKOUT_RETURN_STATE_JS)
            session_status_state = return_page.evaluate(TAP_CHECKOUT_SESSION_STATUS_VERIFY_JS)
            session_status_calls = session_status_state.get("calls") or []
            session_status_call = session_status_calls[0] if session_status_calls else {}
            session_status_response = (
                session_status_call.get("response_body") if isinstance(session_status_call, dict) else {}
            )
            session_status_message_ok = (
                "Stripe status unavailable" in session_status_state.get("status_text", "")
                and "STRIPE_SECRET_KEY is not configured" in session_status_state.get("status_text", "")
            )
            session_status_expected_mode = "stripe_secret_missing_recovery"
            session_status_expected_503_ok = (
                isinstance(session_status_call, dict)
                and session_status_call.get("method") == "GET"
                and session_status_call.get("status") == 503
                and isinstance(session_status_response, dict)
                and session_status_response.get("provider") == "stripe"
                and session_status_response.get("session_id") == "cs_test_return"
                and session_status_response.get("status") == "unavailable"
                and session_status_response.get("error") == "STRIPE_SECRET_KEY is not configured"
            )
            session_status_recovery_ok = (
                success_return_state.get("visible") is True
                and session_status_state.get("had_button") is True
                and session_status_state.get("button_type") == "button"
                and session_status_state.get("button_disabled_after") is False
                and session_status_state.get("button_busy_after") == "false"
                and session_status_expected_503_ok
                and session_status_message_ok
            )
            session_status_detail = {
                "expected_mode": session_status_expected_mode,
                "expected_503_ok": session_status_expected_503_ok,
                "recovery_ok": session_status_recovery_ok,
                "had_button": session_status_state.get("had_button"),
                "button_type": session_status_state.get("button_type"),
                "button_label": session_status_state.get("button_label"),
                "button_reenabled_ok": session_status_state.get("button_disabled_after") is False,
                "button_busy_after": session_status_state.get("button_busy_after"),
                "status_role": session_status_state.get("status_role"),
                "status_live": session_status_state.get("status_live"),
                "status_atomic": session_status_state.get("status_atomic"),
                "status_text": session_status_state.get("status_text"),
                "toast_text": session_status_state.get("toast_text"),
                "toast_type": session_status_state.get("toast_type"),
                "call_count": len(session_status_calls),
                "call_method": session_status_call.get("method") if isinstance(session_status_call, dict) else "",
                "call_status": session_status_call.get("status") if isinstance(session_status_call, dict) else None,
                "response_provider": session_status_response.get("provider")
                if isinstance(session_status_response, dict)
                else "",
                "response_session_id": session_status_response.get("session_id")
                if isinstance(session_status_response, dict)
                else "",
                "response_status": session_status_response.get("status")
                if isinstance(session_status_response, dict)
                else "",
                "response_error": session_status_response.get("error")
                if isinstance(session_status_response, dict)
                else "",
            }
            allow_checkout_503_console_error = allow_checkout_503_console_error or session_status_recovery_ok
            if success_return_state.get("visible") is True:
                return_page.locator("#tap-checkout-return-clear-btn").click()
                dismissed_return_state = return_page.evaluate(TAP_CHECKOUT_RETURN_STATE_JS)
            return_page.goto(
                f"{base_url}/?tap_checkout=cancel&tap_keyword=browser%20smoke%20source%20signal",
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            try:
                return_page.wait_for_selector("#tap-checkout-return-notice:not([hidden])", timeout=timeout_ms)
            except PlaywrightTimeoutError as exc:
                return_notice_errors.append(f"cancel notice timeout: {exc}")
            try:
                return_page.wait_for_function(DASHBOARD_CONTENT_READY_JS, timeout=timeout_ms)
            except PlaywrightTimeoutError:
                return_page.wait_for_timeout(1200)
            cancel_return_state = return_page.evaluate(TAP_CHECKOUT_RETURN_STATE_JS)
        except Exception as exc:
            return_notice_errors.append(str(exc))
        success_action_group = success_return_state.get("actionGroup", {})
        cancel_action_group = cancel_return_state.get("actionGroup", {})
        success_action_group_ok = (
            isinstance(success_action_group, dict)
            and success_action_group.get("role") == "group"
            and success_action_group.get("label") == "Checkout return actions"
            and success_action_group.get("buttonTexts") == ["Verify status", "Clear"]
            and success_action_group.get("buttonLabels")
            == ["Verify checkout session status", "Clear checkout return notice"]
            and all(button_type == "button" for button_type in success_action_group.get("buttonTypes", []))
            and int(success_action_group.get("minButtonHeight") or 0) >= 28
        )
        cancel_action_group_ok = (
            isinstance(cancel_action_group, dict)
            and cancel_action_group.get("role") == "group"
            and cancel_action_group.get("label") == "Checkout return actions"
            and cancel_action_group.get("buttonTexts") == ["Clear"]
            and cancel_action_group.get("buttonLabels") == ["Clear checkout return notice"]
            and all(button_type == "button" for button_type in cancel_action_group.get("buttonTypes", []))
            and int(cancel_action_group.get("minButtonHeight") or 0) >= 28
        )
        tap_return_success_notice_ok = (
            success_return_state.get("visible") is True
            and success_return_state.get("role") == "status"
            and success_return_state.get("live") == "polite"
            and success_return_state.get("atomic") == "true"
            and success_return_state.get("clearButtonType") == "button"
            and "tap-checkout-return-success" in success_return_state.get("className", "")
            and "Checkout success returned" in success_return_state.get("text", "")
            and "browser smoke source signal" in success_return_state.get("text", "")
            and "cs_test_return" in success_return_state.get("text", "")
            and success_return_state.get("verifyButtonType") == "button"
            and success_return_state.get("statusRole") == "status"
            and success_return_state.get("statusLive") == "polite"
            and success_return_state.get("statusAtomic") == "true"
        )
        tap_return_session_status_a11y_ok = (
            session_status_state.get("status_role") == "status"
            and session_status_state.get("status_live") == "polite"
            and session_status_state.get("status_atomic") == "true"
        )
        tap_return_dismissed_notice_ok = (
            dismissed_return_state.get("visible") is False
            and "tap_checkout" not in dismissed_return_state.get("url", "")
        )
        tap_return_cancel_notice_ok = (
            cancel_return_state.get("visible") is True
            and "tap-checkout-return-cancel" in cancel_return_state.get("className", "")
            and "Checkout canceled" in cancel_return_state.get("text", "")
            and "browser smoke source signal" in cancel_return_state.get("text", "")
        )
        tap_return_expected_mode = "tap_checkout_return_success_cancel_status_expected_flow"
        tap_return_notice_ok = (
            not return_notice_errors
            and tap_return_success_notice_ok
            and success_action_group_ok
            and tap_return_session_status_a11y_ok
            and session_status_recovery_ok
            and tap_return_dismissed_notice_ok
            and tap_return_cancel_notice_ok
            and cancel_action_group_ok
        )
        _record_check(
            checks,
            "tap_checkout_return_notice",
            tap_return_notice_ok,
            {
                "expected_mode": tap_return_expected_mode,
                "success_notice_ok": tap_return_success_notice_ok,
                "success_action_group_ok": success_action_group_ok,
                "session_status": session_status_detail,
                "session_status_a11y_ok": tap_return_session_status_a11y_ok,
                "dismissed_notice_hidden_ok": dismissed_return_state.get("visible") is False,
                "dismissed_url_clean_ok": "tap_checkout" not in dismissed_return_state.get("url", ""),
                "cancel_notice_ok": tap_return_cancel_notice_ok,
                "cancel_action_group_ok": cancel_action_group_ok,
                "success_text_has_offer_ok": "browser smoke source signal" in success_return_state.get("text", ""),
                "success_text_has_session_ok": "cs_test_return" in success_return_state.get("text", ""),
                "cancel_text_has_offer_ok": "browser smoke source signal" in cancel_return_state.get("text", ""),
                "errors": return_notice_errors,
            },
        )

        keyboard_row_detail: dict[str, Any] = {
            "expected_order": expected_row_action_order,
            "recovery_packet_count": len(recovery_packet_paths),
            "focus_order_reference": W3C_WCAG_FOCUS_ORDER_URL,
            "target_size_reference": W3C_WCAG_TARGET_SIZE_MINIMUM_URL,
        }
        keyboard_row_ok = not has_recovery_packets
        keyboard_row_gaps: list[str] = []
        row_keyboard_buttons = page.locator("#operator-blockers [data-recovery-row-actions='true'] button")
        row_keyboard_button_count = row_keyboard_buttons.count()
        keyboard_row_detail["button_count"] = row_keyboard_button_count
        if not has_recovery_packets:
            if row_keyboard_button_count:
                keyboard_row_gaps.append("recovery row action buttons rendered without recovery packets")
                keyboard_row_ok = False
            keyboard_row_detail["gaps"] = keyboard_row_gaps
        elif row_keyboard_button_count >= len(expected_row_action_order):
            page.evaluate(
                """() => Array.from(document.querySelectorAll('#operator-blockers [data-recovery-row-actions="true"] .operator-view-btn')).forEach(button => {
                    if (button.getAttribute('aria-expanded') === 'true') button.click();
                })"""
            )
            page.wait_for_timeout(150)
            row_keyboard_buttons.nth(0).focus()
            focused_sequence: list[dict[str, Any]] = []
            for _ in expected_row_action_order:
                focused_state = page.evaluate(
                    """() => {
                        const active = document.activeElement;
                        const rect = active?.getBoundingClientRect?.();
                        return {
                            text: (active?.innerText || '').trim(),
                            ariaLabel: active?.getAttribute?.('aria-label') || '',
                            type: active?.getAttribute?.('type') || '',
                            inRecoveryRowGroup: Boolean(active?.closest?.('[data-recovery-row-actions="true"]')),
                            height: rect ? Math.round(rect.height) : 0,
                        };
                    }"""
                )
                focused_sequence.append(focused_state)
                page.keyboard.press("Tab")
                page.wait_for_timeout(35)
            credential_keyboard_button = page.locator(
                "[aria-label='Copy credential update commands from blocker row']"
            ).first
            credential_keyboard_button.evaluate(
                """button => {
                    delete button.dataset.copyResult;
                    if (button.dataset.copyOriginalText) button.innerText = button.dataset.copyOriginalText;
                }"""
            )
            credential_keyboard_button.focus()
            page.keyboard.press("Enter")
            credential_keyboard_feedback_seen = False
            try:
                page.wait_for_function(
                    """async () => {
                        const button = document.querySelector("[aria-label='Copy credential update commands from blocker row']");
                        const clipboardText = navigator.clipboard?.readText ? await navigator.clipboard.readText() : '';
                        if (
                            button?.dataset.copyResult === 'copied'
                            && clipboardText.includes('getdaytrends_update_credentials.py --database-url-stdin')
                        ) {
                            window.__gdtCredentialKeyboardClipboard = clipboardText;
                            return true;
                        }
                        return false;
                    }""",
                    timeout=timeout_ms,
                )
                credential_keyboard_feedback_seen = True
            except PlaywrightTimeoutError:
                pass
            credential_keyboard_clipboard = page.evaluate(
                """async () => window.__gdtCredentialKeyboardClipboard
                    || (navigator.clipboard?.readText ? await navigator.clipboard.readText() : '')"""
            )
            normalized_keyboard_clipboard = credential_keyboard_clipboard.replace("\r\n", "\n").replace("\r", "\n")
            focused_texts = [str(item.get("text") or "") for item in focused_sequence]
            keyboard_row_secret_gaps = []
            if re.search(r"\bpostgres(?:ql)?://(?!\*\*\*)[^\s\"'<>]+", normalized_keyboard_clipboard, re.IGNORECASE):
                keyboard_row_secret_gaps.append("clipboard contains raw postgres URL")
            if re.search(r"\btenant/user\s+(?!\*\*\*)[^\s),;]+", normalized_keyboard_clipboard, re.IGNORECASE):
                keyboard_row_secret_gaps.append("clipboard contains raw tenant user")
            if focused_texts != expected_row_action_order:
                keyboard_row_gaps.append("keyboard focus order changed")
            if not all(item.get("inRecoveryRowGroup") for item in focused_sequence):
                keyboard_row_gaps.append("focus left recovery row action group")
            if any(int(item.get("height") or 0) < 28 for item in focused_sequence):
                keyboard_row_gaps.append("focused row action target height below 28px")
            if not all(str(item.get("type") or "") == "button" for item in focused_sequence):
                keyboard_row_gaps.append("focused row action button type missing")
            if not credential_keyboard_feedback_seen:
                keyboard_row_gaps.append("credential update Enter activation did not report copied")
            if SAFE_DATABASE_UPDATE_FRAGMENTS[0] not in normalized_keyboard_clipboard:
                keyboard_row_gaps.append("keyboard clipboard missing dry-run credential updater")
            if SAFE_DATABASE_UPDATE_FRAGMENTS[1] not in normalized_keyboard_clipboard:
                keyboard_row_gaps.append("keyboard clipboard missing write credential updater")
            if "Pause scheduled/background getdaytrends clients" not in normalized_keyboard_clipboard:
                keyboard_row_gaps.append("keyboard clipboard missing pause-first guidance")
            if "postgresql://" in normalized_keyboard_clipboard:
                keyboard_row_gaps.append("keyboard clipboard exposes postgres URL")
            keyboard_row_gaps.extend(keyboard_row_secret_gaps)
            keyboard_row_detail.update(
                {
                    "focused_sequence": focused_sequence,
                    "focused_texts": focused_texts,
                    "credential_keyboard_feedback_seen": credential_keyboard_feedback_seen,
                    "clipboard_text": credential_keyboard_clipboard[:1200],
                    "secret_gaps": keyboard_row_secret_gaps,
                    "gaps": keyboard_row_gaps,
                }
            )
            keyboard_row_ok = not keyboard_row_gaps
        else:
            keyboard_row_gaps.append("not enough recovery row action buttons for keyboard order check")
            keyboard_row_detail["gaps"] = keyboard_row_gaps
        _record_check(
            checks,
            "operator_recovery_row_keyboard_order_activation",
            keyboard_row_ok,
            keyboard_row_detail,
        )

        page.screenshot(path=str(screenshot_path), full_page=True)
        chrome_text = page.evaluate(
            """() => Array.from(
                document.querySelectorAll('header, .label, .panel h3, .tap-control, .tap-actions, #log-viewer, .footer')
              ).map(node => node.innerText || '').join('\\n')"""
        )
        mojibake = _visible_mojibake_markers(chrome_text)
        _record_check(checks, "dashboard_chrome_has_no_mojibake_markers", not mojibake, mojibake)
        log_viewer_text = page.locator("#log-viewer").inner_text(timeout=timeout_ms)
        log_viewer_mojibake = _visible_mojibake_markers(log_viewer_text)
        _record_check(
            checks,
            "dashboard_log_viewer_has_no_mojibake_markers",
            not log_viewer_mojibake,
            {"markers": log_viewer_mojibake, "text": log_viewer_text[:500]},
        )
        provider_team_ids = re.findall(
            r"\bteam\s+[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            log_viewer_text,
            flags=re.IGNORECASE,
        )
        _record_check(
            checks,
            "dashboard_log_viewer_has_no_provider_team_ids",
            not provider_team_ids,
            {"matches": provider_team_ids, "text": log_viewer_text[:500]},
        )

        mobile_context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
        mobile = mobile_context.new_page()
        mobile.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
        mobile.wait_for_selector("#tap-refresh-btn", timeout=timeout_ms)
        mobile.wait_for_function(DASHBOARD_CONTENT_READY_JS, timeout=timeout_ms)
        mobile.evaluate(
            """async () => {
                if (typeof loadOperatorReadiness === 'function') {
                    await loadOperatorReadiness();
                }
            }"""
        )
        mobile.wait_for_selector("#operator-blockers .operator-item", timeout=timeout_ms)
        mobile_operator_payload = mobile.evaluate(
            """async () => {
                const response = await fetch('/api/operator/readiness');
                return await response.json();
            }"""
        )
        mobile_operator_issues = [
            issue
            for bucket in ("blockers", "warnings")
            for issue in mobile_operator_payload.get(bucket, [])
            if isinstance(issue, dict)
        ]
        mobile_recovery_packet_paths = [
            str(issue.get("recovery_packet", "")).strip()
            for issue in mobile_operator_issues
            if str(issue.get("recovery_packet", "")).strip()
        ]
        mobile_has_recovery_packets = bool(mobile_recovery_packet_paths)
        mobile.wait_for_timeout(800)
        mobile_layout_state = mobile.evaluate(DASHBOARD_MOBILE_LAYOUT_STATE_JS)
        _record_check(
            checks,
            "mobile_layout_no_page_overflow",
            float(mobile_layout_state.get("overflowPx") or 0) <= 8
            and int(mobile_layout_state.get("offenderCount") or 0) == 0
            and int(mobile_layout_state.get("actionButtonIssueCount") or 0) == 0
            and (
                int(mobile_layout_state.get("recoveryActionButtonCount") or 0) >= 5
                if mobile_has_recovery_packets
                else int(mobile_layout_state.get("recoveryActionButtonCount") or 0) == 0
            ),
            {
                **mobile_layout_state,
                "mobile_issue_count": len(mobile_operator_issues),
                "mobile_recovery_packet_count": len(mobile_recovery_packet_paths),
            },
        )
        mobile_recovery_row_groups = mobile_layout_state.get("recoveryRowActionGroups") or []
        mobile_recovery_row_gaps: list[str] = []
        if mobile_has_recovery_packets and not mobile_recovery_row_groups:
            mobile_recovery_row_gaps.append("missing mobile recovery row action group")
        if not mobile_has_recovery_packets and mobile_recovery_row_groups:
            mobile_recovery_row_gaps.append("mobile recovery row action group rendered without recovery packets")
        for group in mobile_recovery_row_groups:
            if group.get("role") != "group":
                mobile_recovery_row_gaps.append("missing mobile row action group role")
            if group.get("label") != "Recovery row copy actions":
                mobile_recovery_row_gaps.append("missing mobile row action group label")
            if group.get("buttonTexts") != expected_row_action_order:
                mobile_recovery_row_gaps.append("mobile row action order changed")
            if int(group.get("minButtonHeight") or 0) < 28:
                mobile_recovery_row_gaps.append("mobile row action target height below 28px")
            if not all(button_type == "button" for button_type in group.get("buttonTypes", [])):
                mobile_recovery_row_gaps.append("mobile row action button type missing")
        _record_check(
            checks,
            "mobile_recovery_row_action_group",
            (
                bool(mobile_recovery_row_groups)
                if mobile_has_recovery_packets
                else not mobile_recovery_row_groups
            )
            and not mobile_recovery_row_gaps,
            {
                "groups": mobile_recovery_row_groups,
                "recovery_packet_count": len(mobile_recovery_packet_paths),
                "mobile_issue_count": len(mobile_operator_issues),
                "expected_order": expected_row_action_order,
                "gaps": mobile_recovery_row_gaps,
                "wcag_target_size_minimum_reference": W3C_WCAG_TARGET_SIZE_MINIMUM_URL,
            },
        )
        mobile_artifact_action_groups = mobile_layout_state.get("artifactActionGroups") or []
        mobile_artifact_action_group_by_key = {
            str(group.get("key") or ""): group
            for group in mobile_artifact_action_groups
            if isinstance(group, dict) and str(group.get("key") or "")
        }
        mobile_artifact_group_gaps: list[str] = []
        mobile_missing_artifact_group_keys = sorted(
            set(expected_artifact_action_groups) - set(mobile_artifact_action_group_by_key)
        )
        if mobile_missing_artifact_group_keys:
            mobile_artifact_group_gaps.append("missing mobile artifact action groups")
        for key, expected_group in expected_artifact_action_groups.items():
            group = mobile_artifact_action_group_by_key.get(key, {})
            if group.get("role") != "group":
                mobile_artifact_group_gaps.append(f"{key}: missing mobile group role")
            if group.get("label") != expected_group["label"]:
                mobile_artifact_group_gaps.append(f"{key}: mobile group label changed")
            if group.get("buttonTexts") != expected_group["button_texts"]:
                mobile_artifact_group_gaps.append(f"{key}: mobile button order changed")
            if group.get("buttonLabels") != expected_group["button_labels"]:
                mobile_artifact_group_gaps.append(f"{key}: mobile button aria labels changed")
            if int(group.get("minButtonHeight") or 0) < 28:
                mobile_artifact_group_gaps.append(f"{key}: mobile target height below 28px")
            if not all(button_type == "button" for button_type in group.get("buttonTypes", [])):
                mobile_artifact_group_gaps.append(f"{key}: mobile button type missing")
        _record_check(
            checks,
            "mobile_artifact_action_group",
            bool(expected_artifact_action_groups) and not mobile_artifact_group_gaps,
            {
                "groups": mobile_artifact_action_groups,
                "expected": expected_artifact_action_groups,
                "missing_keys": mobile_missing_artifact_group_keys,
                "gaps": mobile_artifact_group_gaps,
                "wcag_target_size_minimum_reference": W3C_WCAG_TARGET_SIZE_MINIMUM_URL,
            },
        )
        mobile_context.close()

        context.close()
        browser.close()

    allowed_checkout_console = "Failed to load resource: the server responded with a status of 503 (Service Unavailable)"
    actionable_console_errors = [
        error
        for error in console_errors
        if not (allow_checkout_503_console_error and error == allowed_checkout_console)
    ]
    console_detail: Any = (
        {
            "errors": actionable_console_errors,
            "allowed": [error for error in console_errors if error == allowed_checkout_console],
        }
        if allow_checkout_503_console_error and console_errors
        else console_errors
    )
    _record_check(checks, "console_has_no_errors", not actionable_console_errors, console_detail)
    _record_check(checks, "page_has_no_errors", not page_errors, page_errors)
    _record_check(checks, "same_origin_requests_ok", not request_failures, request_failures)
    return BrowserRun(
        ok=all(check["ok"] for check in checks),
        checks=checks,
        console_errors=console_errors,
        console_warnings=console_warnings,
        page_errors=page_errors,
        request_failures=request_failures,
        screenshot=str(screenshot_path),
    )


def run_smoke(
    *,
    host: str,
    port: int,
    report_path: Path,
    screenshot_path: Path,
    python_exe: str,
    timeout_seconds: float,
    local_db_only: bool = False,
    tap_source_fixture: bool = False,
    tap_source_fixture_db: Path = DEFAULT_TAP_SOURCE_FIXTURE_DB,
) -> dict[str, Any]:
    selected_port = port or _get_free_port(host)
    base_url = f"http://{host}:{selected_port}"
    checks: list[dict[str, Any]] = []
    server: subprocess.Popen[str] | None = None
    stdout_path = stderr_path = PROJECT_ROOT / "logs" / "smoke" / "missing.log"

    try:
        fixture_db = tap_source_fixture_db if tap_source_fixture else None
        if fixture_db is not None:
            _seed_tap_source_evidence_fixture(fixture_db)
        env_overrides = _server_env_overrides(local_db_only=local_db_only, tap_source_fixture_db=fixture_db)
        server, stdout_path, stderr_path = _start_server(
            host,
            selected_port,
            python_exe,
            env_overrides=env_overrides,
            log_label=f"{report_path.stem}_{selected_port}_server",
        )
        ready, attempts = _wait_for_server(base_url, timeout_seconds)
        _record_check(checks, "server_ready", ready, {"base_url": base_url, "attempts": attempts[-5:]})
        if not ready:
            browser_run = None
        else:
            browser_run = _run_browser(
                base_url,
                screenshot_path,
                int(timeout_seconds * 1000),
                require_tap_source_notes=tap_source_fixture,
            )
            checks.extend(browser_run.checks)
    finally:
        if server is not None:
            _stop_server(server)
        _sanitize_log_file(stdout_path)
        _sanitize_log_file(stderr_path)
    if tap_source_fixture:
        degraded_sources = _dashboard_degraded_log_sources([stdout_path, stderr_path])
        _record_check(
            checks,
            "server_has_no_dashboard_degraded_endpoint_logs",
            not degraded_sources,
            {"sources": degraded_sources},
        )

    summary = {
        "total": len(checks),
        "passed": sum(1 for check in checks if check["ok"]),
        "failed": sum(1 for check in checks if not check["ok"]),
    }
    payload = {
        "schema_version": 1,
        "status": "pass" if summary["failed"] == 0 else "fail",
        "generated_at": datetime.now().astimezone().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "base_url": base_url,
        "summary": summary,
        "checks": checks,
        "screenshot": str(screenshot_path),
        "mode": {
            "local_db_only": bool(local_db_only or tap_source_fixture),
            "tap_source_fixture": bool(tap_source_fixture),
            "tap_source_fixture_db": str(tap_source_fixture_db) if tap_source_fixture else "",
        },
        "server": {
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
            "stdout_tail": _tail(stdout_path),
            "stderr_tail": _tail(stderr_path),
        },
    }
    if browser_run is not None:
        payload["browser"] = {
            "console_errors": browser_run.console_errors,
            "console_warnings": browser_run.console_warnings,
            "page_errors": browser_run.page_errors,
            "request_failures": browser_run.request_failures,
        }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a live getdaytrends dashboard browser smoke.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="Port to use. Defaults to a free ephemeral port.")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="JSON report path. Defaults to dashboard_browser_latest.json, or dashboard_browser_tap_source_evidence.json with --tap-source-fixture.",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=None,
        help="Screenshot path. Defaults to dashboard_browser_latest.png, or dashboard_browser_tap_source_evidence.png with --tap-source-fixture.",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument(
        "--local-db-only",
        action="store_true",
        help="Start the dashboard with DATABASE_URL cleared so DB-backed UI smoke uses local SQLite only.",
    )
    parser.add_argument(
        "--tap-source-fixture",
        action="store_true",
        help="Seed a local SQLite TAP source-evidence fixture and require note rendering in the browser.",
    )
    parser.add_argument("--tap-source-fixture-db", type=Path, default=DEFAULT_TAP_SOURCE_FIXTURE_DB)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report_path, screenshot_path = _resolve_output_paths(
        args.report,
        args.screenshot,
        tap_source_fixture=args.tap_source_fixture,
    )
    payload = run_smoke(
        host=args.host,
        port=args.port,
        report_path=report_path,
        screenshot_path=screenshot_path,
        python_exe=args.python,
        timeout_seconds=args.timeout,
        local_db_only=args.local_db_only,
        tap_source_fixture=args.tap_source_fixture,
        tap_source_fixture_db=args.tap_source_fixture_db,
    )
    print(f"getdaytrends dashboard browser smoke: {payload['status']}")
    print(f"report: {report_path}")
    print(f"screenshot: {screenshot_path}")
    for check in payload["checks"]:
        marker = "OK" if check["ok"] else "FAIL"
        print(f"{marker} {check['name']}")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

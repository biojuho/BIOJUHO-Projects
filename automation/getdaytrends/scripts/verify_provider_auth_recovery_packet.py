"""Validate the getdaytrends provider-auth recovery packet artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts import readiness_check
except ImportError:  # pragma: no cover - used when executed from scripts/
    import readiness_check  # type: ignore


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, f"{path} is missing"
    except Exception as exc:
        return None, f"{path} is not readable: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, f"{path} root is not a JSON object"
    return payload, ""


def _packet_readiness_report(packet_report: Path) -> Path | None:
    packet, _ = _load_json(packet_report)
    if not isinstance(packet, dict):
        return None
    readiness_report = packet.get("readiness_report")
    if isinstance(readiness_report, str) and readiness_report.strip():
        return Path(readiness_report)
    return None


def _text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for child in value.values():
            strings.extend(_string_values(child))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for child in value:
            strings.extend(_string_values(child))
        return strings
    return []


def _has_value(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) or key in {"issue_types", "provider_auth_failures", "blocking_checks"}
    if isinstance(value, dict):
        return bool(value) or key == "blocking_checks"
    return value is not None


def _same_path(left: Any, right: Path) -> bool:
    try:
        return Path(str(left)).resolve() == right.resolve()
    except OSError:
        return str(left) == str(right)


def _expected_packet_report_for_verifier_command(
    packet: dict[str, Any],
    *,
    base_command: str,
    packet_report: Path,
) -> Path | None:
    commands = packet.get("verification_commands")
    if not isinstance(commands, list):
        return None
    prefix = f"{base_command} --packet-report"
    if any(str(command).startswith(prefix) for command in commands):
        return packet_report
    return None


def _checks_by_name(readiness_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = readiness_payload.get("checks")
    if not isinstance(checks, list):
        return {}
    return {
        str(check.get("name", "")): check
        for check in checks
        if isinstance(check, dict) and str(check.get("name", "")).strip()
    }


def _provider_auth_failed(readiness_payload: dict[str, Any]) -> bool:
    provider_check = _checks_by_name(readiness_payload).get("provider_auth_report")
    if not provider_check:
        return False
    evidence = provider_check.get("evidence") if isinstance(provider_check.get("evidence"), dict) else {}
    failure_count = evidence.get("provider_auth_failure_count")
    if isinstance(failure_count, int):
        return failure_count > 0
    failures = evidence.get("provider_auth_failures")
    return isinstance(failures, list) and bool(failures)


def _validate_secret_hygiene(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    secret_hygiene = packet.get("secret_hygiene") if isinstance(packet.get("secret_hygiene"), dict) else {}
    if secret_hygiene.get("masked_openai_keys") is not True:
        errors.append("secret_hygiene.masked_openai_keys must be true")
    if secret_hygiene.get("masked_google_api_keys") is not True:
        errors.append("secret_hygiene.masked_google_api_keys must be true")
    if secret_hygiene.get("contains_plaintext_secret_values") is not False:
        errors.append("secret_hygiene.contains_plaintext_secret_values must be false")

    raw = "\n".join(_string_values(packet))
    if readiness_check.OPENAI_KEY_RE.search(raw):
        errors.append("packet contains an unmasked OpenAI API key")
    if readiness_check.GOOGLE_API_KEY_RE.search(raw):
        errors.append("packet contains an unmasked Google API key")
    return errors


def validate_recovery_packet(readiness_report: Path, packet_report: Path) -> list[str]:
    readiness_payload, readiness_error = _load_json(readiness_report)
    packet, packet_error = _load_json(packet_report)
    errors: list[str] = []
    if readiness_payload is None:
        errors.append(readiness_error)
    if packet is None:
        errors.append(packet_error)
    if readiness_payload is None or packet is None:
        return errors

    expected_packet_report = _expected_packet_report_for_verifier_command(
        packet,
        base_command=readiness_check.PROVIDER_AUTH_RECOVERY_PACKET_VERIFY_COMMAND,
        packet_report=packet_report,
    )
    expected = readiness_check.build_provider_auth_recovery_packet(
        readiness_payload,
        readiness_report=readiness_report,
        recovery_packet_report=expected_packet_report,
    )
    required_keys = (
        "schema_version",
        "status",
        "generated_at",
        "readiness_report",
        "readiness_generated_at",
        "readiness_status",
        "required_env",
        "issue_types",
        "provider_auth_failure_count",
        "next_required_action",
        "blocking_checks",
        "source_checks",
        "provider_auth_failures",
        "recovery_summary",
        "evidence_freshness",
        "launch_success_criteria",
        "reference_links",
        "recovery_checklist",
        "env_template",
        "recovery_bundle",
        "verification_commands",
        "verification_command_bundle",
        "secret_hygiene",
    )
    for key in required_keys:
        if not _has_value(packet, key):
            errors.append(f"packet missing required field: {key}")

    exact_match_keys = (
        "schema_version",
        "status",
        "readiness_status",
        "required_env",
        "issue_types",
        "provider_auth_failure_count",
        "next_required_action",
        "blocking_checks",
        "source_checks",
        "provider_auth_failures",
        "launch_success_criteria",
        "reference_links",
        "recovery_checklist",
        "env_template",
        "verification_commands",
        "verification_command_bundle",
        "secret_hygiene",
    )
    for key in exact_match_keys:
        if packet.get(key) != expected.get(key):
            errors.append(f"packet field does not match current readiness contract: {key}")

    if packet.get("readiness_generated_at") != readiness_payload.get("generated_at"):
        errors.append("packet readiness_generated_at does not match readiness report generated_at")
    if not _same_path(packet.get("readiness_report"), readiness_report):
        errors.append("packet readiness_report does not match the verified readiness report path")
    freshness = packet.get("evidence_freshness") if isinstance(packet.get("evidence_freshness"), dict) else {}
    if freshness.get("readiness_generated_at") != readiness_payload.get("generated_at"):
        errors.append("packet evidence_freshness.readiness_generated_at does not match readiness report")

    if packet.get("status") not in {"blocked", "clear", "not_evaluated"}:
        errors.append("packet status must be blocked, clear, or not_evaluated")
    if packet.get("required_env") != ["OPENAI_API_KEY", "GOOGLE_API_KEY"]:
        errors.append("packet required_env must be OPENAI_API_KEY and GOOGLE_API_KEY")
    failures = packet.get("provider_auth_failures") if isinstance(packet.get("provider_auth_failures"), list) else []
    if packet.get("provider_auth_failure_count") != len(failures):
        errors.append("provider_auth_failure_count must match provider_auth_failures length")
    if packet.get("status") == "blocked" and not packet.get("issue_types"):
        errors.append("blocked packet must include issue_types")
    if packet.get("status") == "clear" and packet.get("provider_auth_failure_count") != 0:
        errors.append("clear packet must have provider_auth_failure_count 0")
    if _provider_auth_failed(readiness_payload) and packet.get("status") != "blocked":
        errors.append("failed provider auth readiness evidence must produce a blocked packet")

    bundle = str(packet.get("recovery_bundle") or "")
    for marker in (
        "## Next required action",
        "## Current blocker summary",
        "## Evidence freshness",
        "## Launch success criteria",
        "## Env template",
        "## Recovery checklist",
        "## References",
        "## Verification commands",
    ):
        if marker not in bundle:
            errors.append(f"recovery_bundle missing section: {marker}")
    for command in (
        readiness_check.CLI_SMOKE_REFRESH_COMMAND,
        readiness_check.BROWSER_SMOKE_REFRESH_COMMAND,
        readiness_check.STRICT_READINESS_REFRESH_COMMAND,
        readiness_check._packet_verifier_command(
            readiness_check.PROVIDER_AUTH_RECOVERY_PACKET_VERIFY_COMMAND,
            expected_packet_report,
        ),
        readiness_check.CANONICAL_WORKSPACE_SMOKE_REFRESH_COMMAND,
    ):
        if command not in packet.get("verification_commands", []):
            errors.append(f"verification_commands missing: {command}")

    errors.extend(_validate_secret_hygiene(packet))
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the getdaytrends provider-auth recovery packet artifact.")
    parser.add_argument("--readiness-report", type=Path)
    parser.add_argument("--packet-report", type=Path, default=readiness_check.DEFAULT_PROVIDER_AUTH_RECOVERY_PACKET)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    readiness_report = (
        args.readiness_report
        or _packet_readiness_report(args.packet_report)
        or readiness_check.DEFAULT_REPORT
    )
    errors = validate_recovery_packet(readiness_report, args.packet_report)
    if errors:
        print("getdaytrends provider-auth recovery packet: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    packet, _ = _load_json(args.packet_report)
    issue_types = ", ".join(packet.get("issue_types", [])) if isinstance(packet, dict) else ""
    failure_count = packet.get("provider_auth_failure_count") if isinstance(packet, dict) else "unknown"
    print(
        "getdaytrends provider-auth recovery packet: "
        f"PASS status={packet.get('status')} failures={failure_count} issues={issue_types or 'none'}"
    )
    print(f"readiness report: {readiness_report}")
    print(f"packet report: {args.packet_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

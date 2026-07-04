from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


PLACEHOLDER_TOKEN_RE = re.compile(r"<[^>\r\n]+>")
SENSITIVE_KEY_RE = re.compile(
    r"(?i)(SECRET|PASSWORD|PEPPER|PRIVATE_KEY|TOKEN|CREDENTIAL|SERVICE_ACCOUNT|DATABASE_URL)"
)
DATABASE_URL_PASSWORD_RE = re.compile(r"(?i)(postgres(?:ql)?://[^:\s]+:)([^@\s]+)(@)")
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:SECRET|PASSWORD|PEPPER|PRIVATE_KEY|TOKEN|CREDENTIAL|SERVICE_ACCOUNT|DATABASE_URL)[A-Z0-9_]*)\s*([:=])\s*([^,\s]+)"
)

REQUIRED_EXPLICIT_KEYS = (
    "AGRIGUARD_DB_USER",
    "AGRIGUARD_DB_NAME",
    "AGRIGUARD_AUTO_CREATE_SCHEMA",
    "AGRIGUARD_ALLOWED_ORIGINS",
    "AGRIGUARD_SECRET_KEY",
    "AGRIGUARD_QR_TOKEN_PEPPER",
    "AGRIGUARD_PUBLIC_VERIFY_BASE_URL",
    "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE",
    "ALLOW_TEST_BYPASS",
    "ALLOW_DEV_AUTH_FALLBACK",
)
DATABASE_CREDENTIAL_OPTIONS = ("AGRIGUARD_DB_PASSWORD", "AGRIGUARD_DATABASE_URL")
FORBIDDEN_TRUE_FLAGS = ("ALLOW_TEST_BYPASS", "ALLOW_DEV_AUTH_FALLBACK")
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _load_peer_module(module_name: str) -> Any:
    script_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launch_env_preflight = _load_peer_module("launch_env_preflight")


def _default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace_root(app_root: Path) -> Path:
    if app_root.parent.name == "apps":
        return app_root.parents[1]
    return app_root.parent


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _redact_message(message: object) -> str:
    text = str(message)
    text = DATABASE_URL_PASSWORD_RE.sub(r"\1<redacted>\3", text)
    return SENSITIVE_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text)


def _env_flag_enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUTHY_VALUES


def _value_present(value: str | None) -> bool:
    return bool((value or "").strip())


def _known_placeholder(value: str) -> bool:
    checker = getattr(launch_env_preflight, "_is_placeholder_value")
    return bool(checker(value))


def _placeholder_reason(value: str) -> str | None:
    stripped = value.strip()
    if PLACEHOLDER_TOKEN_RE.search(stripped):
        return "angle_bracket_placeholder"
    if "example.com" in stripped.lower():
        return "sample_domain_placeholder"
    if _known_placeholder(stripped):
        return "known_placeholder_value"
    return None


def _missing_required_keys(env: dict[str, str]) -> list[str]:
    missing = [key for key in REQUIRED_EXPLICIT_KEYS if not _value_present(env.get(key))]
    if not any(_value_present(env.get(key)) for key in DATABASE_CREDENTIAL_OPTIONS):
        missing.append("AGRIGUARD_DB_PASSWORD or AGRIGUARD_DATABASE_URL")
    return missing


def _placeholder_variables(env: dict[str, str]) -> list[dict[str, str]]:
    placeholders: list[dict[str, str]] = []
    for key in sorted(env):
        reason = _placeholder_reason(env[key])
        if reason is not None:
            placeholders.append({"key": key, "reason": reason})
    return placeholders


def _forbidden_flags_enabled(env: dict[str, str]) -> list[str]:
    return [key for key in FORBIDDEN_TRUE_FLAGS if _env_flag_enabled(env.get(key))]


def _firebase_path_shape_errors(env: dict[str, str]) -> list[str]:
    value = (env.get("AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE") or "").strip()
    if not value or _placeholder_reason(value):
        return []
    if Path(value).suffix.lower() != ".json":
        return ["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE must point to a .json file before launch preflight."]
    return []


def _redacted_variables(env: dict[str, str]) -> list[dict[str, object]]:
    variables: list[dict[str, object]] = []
    for key in sorted(env):
        variables.append(
            {
                "key": key,
                "present": _value_present(env.get(key)),
                "sensitive": bool(SENSITIVE_KEY_RE.search(key)),
                "placeholder": _placeholder_reason(env[key]) is not None,
                "value": "<redacted>",
            }
        )
    return variables


def _selected_launch_checks(checks: object) -> dict[str, object]:
    if not isinstance(checks, dict):
        return {}
    selected_keys = (
        "runtime",
        "forbidden_launch_flags_enabled",
        "dev_auth_fallback_role_set",
        "firebase_credentials_source",
        "secret_source",
        "qr_token_pepper_source",
        "public_verify_base_url_source",
        "auto_create_schema",
        "auto_create_schema_source",
        "database_url_present",
        "database_url_source",
        "database_password_source",
        "allowed_origins_count",
        "allowed_origins_source",
    )
    return {key: checks.get(key) for key in selected_keys}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def build_validation_report(*, env_file: Path, app_root: Path | None = None) -> dict[str, object]:
    app_root = (app_root or _default_app_root()).resolve()
    workspace_root = _workspace_root(app_root)
    env_file = env_file.resolve()
    env_file_found = env_file.is_file()
    env = launch_env_preflight.load_env_file(env_file) if env_file_found else {}

    missing_keys = _missing_required_keys(env)
    placeholder_variables = _placeholder_variables(env)
    forbidden_flags = _forbidden_flags_enabled(env)

    launch_validation = launch_env_preflight.validate_launch_env_with_options(env, runtime="compose")
    launch_errors = [_redact_message(error) for error in launch_validation.get("errors", [])]
    launch_warnings = [_redact_message(warning) for warning in launch_validation.get("warnings", [])]

    blocking_findings: list[str] = []
    if not env_file_found:
        blocking_findings.append(f"Env file not found: {_rel(env_file, workspace_root)}")
    blocking_findings.extend(f"Missing required launch env key: {key}" for key in missing_keys)
    blocking_findings.extend(
        f"Replace placeholder value for {item['key']} before launch preflight."
        for item in placeholder_variables
    )
    blocking_findings.extend(f"{flag} must be false for launch." for flag in forbidden_flags)
    blocking_findings.extend(_firebase_path_shape_errors(env))
    blocking_findings.extend(f"Launch shape validation: {error}" for error in launch_errors)
    blocking_findings = _dedupe(blocking_findings)

    return {
        "schema_version": 1,
        "status": "fail" if blocking_findings else "pass",
        "ready_for_preflight": not blocking_findings,
        "env_file": _rel(env_file, workspace_root),
        "env_file_found": env_file_found,
        "secrets_redacted": True,
        "required_explicit_keys": list(REQUIRED_EXPLICIT_KEYS),
        "database_credential_options": list(DATABASE_CREDENTIAL_OPTIONS),
        "missing_required_keys": missing_keys,
        "placeholder_count": len(placeholder_variables),
        "placeholder_variables": placeholder_variables,
        "forbidden_flags_enabled": forbidden_flags,
        "blocking_findings": blocking_findings,
        "variables": _redacted_variables(env),
        "launch_validation": {
            "status": launch_validation.get("status"),
            "errors": launch_errors,
            "warnings": launch_warnings,
            "checks": _selected_launch_checks(launch_validation.get("checks")),
        },
        "validation_scope": "shape_only_no_file_existence_or_secret_content_check",
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# AgriGuard Launch Env Template Validation",
        "",
        f"- Status: `{report['status']}`",
        f"- Ready for preflight: `{str(report['ready_for_preflight']).lower()}`",
        f"- Env file: `{report['env_file']}`",
        f"- Env file found: `{str(report['env_file_found']).lower()}`",
        f"- Placeholder count: `{report['placeholder_count']}`",
        f"- Secrets redacted: `{str(report['secrets_redacted']).lower()}`",
        "",
        "## Blocking Findings",
        "",
    ]

    findings = report.get("blocking_findings")
    if isinstance(findings, list) and findings:
        lines.extend(f"- `{finding}`" for finding in findings)
    else:
        lines.append("No shape-only blockers were found.")

    lines.extend(["", "## Placeholder Variables", ""])
    placeholders = report.get("placeholder_variables")
    if isinstance(placeholders, list) and placeholders:
        lines.append("| Variable | Reason |")
        lines.append("| --- | --- |")
        for item in placeholders:
            if isinstance(item, dict):
                lines.append(f"| `{item.get('key')}` | `{item.get('reason')}` |")
    else:
        lines.append("No placeholder variables were found.")

    lines.extend(["", "## Missing Required Keys", ""])
    missing = report.get("missing_required_keys")
    if isinstance(missing, list) and missing:
        lines.extend(f"- `{key}`" for key in missing)
    else:
        lines.append("No required launch keys are missing.")

    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    app_root = _default_app_root()
    workspace_root = _workspace_root(app_root)
    parser = argparse.ArgumentParser(
        description="Validate an operator-filled AgriGuard launch env file before running compose preflight."
    )
    parser.add_argument("--app-root", type=Path, default=app_root)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=workspace_root / "var" / "agriguard-launch-env-template-validation.json",
    )
    parser.add_argument("--markdown-out", type=Path, default=None)
    parser.add_argument(
        "--exit-zero-on-fail",
        action="store_true",
        help="Write validation outputs but return 0 even when the env file is not ready.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_validation_report(env_file=args.env_file, app_root=args.app_root)
    write_json(args.json_out.resolve(), report)
    if args.markdown_out:
        args.markdown_out.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.resolve().write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote launch env validation markdown: {args.markdown_out}")
    print(f"wrote launch env validation: {args.json_out}")
    return 0 if args.exit_zero_on_fail or report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

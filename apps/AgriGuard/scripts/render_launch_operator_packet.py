from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:SECRET|PASSWORD|PEPPER|PRIVATE_KEY|TOKEN|CREDENTIAL|SERVICE_ACCOUNT)[A-Z0-9_]*)\s*([:=])\s*([^,\s]+)"
)


ACTION_RULES: tuple[dict[str, object], ...] = (
    {
        "id": "set_firebase_service_account_file",
        "matches": ("AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE", "Firebase service account"),
        "variables": ("AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE",),
        "operator_action": "Set this to a Firebase Admin service account JSON file path that exists on the host and is outside the repo.",
        "validation": "Preflight must report firebase_credentials_file_exists=true and firebase_credentials_file_valid=true.",
    },
    {
        "id": "set_secret_key",
        "matches": ("AGRIGUARD_SECRET_KEY", "SECRET_KEY"),
        "variables": ("AGRIGUARD_SECRET_KEY",),
        "operator_action": "Set a strong app-scoped secret with at least 32 characters.",
        "validation": "Preflight must report secret_source=AGRIGUARD_SECRET_KEY with no placeholder or length error.",
    },
    {
        "id": "set_qr_token_pepper",
        "matches": ("AGRIGUARD_QR_TOKEN_PEPPER", "QR_TOKEN_PEPPER"),
        "variables": ("AGRIGUARD_QR_TOKEN_PEPPER",),
        "operator_action": "Set a stable app-scoped QR token pepper with at least 32 characters.",
        "validation": "Preflight must report qr_token_pepper_source=AGRIGUARD_QR_TOKEN_PEPPER with no placeholder or length error.",
    },
    {
        "id": "set_public_verify_base_url",
        "matches": ("AGRIGUARD_PUBLIC_VERIFY_BASE_URL", "PUBLIC_VERIFY_BASE_URL", "https:// URL"),
        "variables": ("AGRIGUARD_PUBLIC_VERIFY_BASE_URL",),
        "operator_action": "Set the public HTTPS verification URL that scanned QR labels should open.",
        "validation": "Preflight must report public_verify_base_url_source=AGRIGUARD_PUBLIC_VERIFY_BASE_URL and an https:// URL.",
    },
    {
        "id": "set_allowed_origins",
        "matches": ("AGRIGUARD_ALLOWED_ORIGINS", "allowed origins"),
        "variables": ("AGRIGUARD_ALLOWED_ORIGINS",),
        "operator_action": "Set the explicit production browser origins that may call the API.",
        "validation": "Preflight must report allowed_origins_source=AGRIGUARD_ALLOWED_ORIGINS and no localhost-only production error.",
    },
    {
        "id": "set_database_password",
        "matches": ("AGRIGUARD_DB_PASSWORD", "AGRIGUARD_DATABASE_URL", "database password", "DATABASE_URL"),
        "variables": ("AGRIGUARD_DB_PASSWORD", "AGRIGUARD_DATABASE_URL"),
        "operator_action": "Set either a strong compose database password or a PostgreSQL AGRIGUARD_DATABASE_URL.",
        "validation": "Preflight must report a launch-safe database_password_source without placeholder or length errors.",
    },
    {
        "id": "disable_forbidden_auth_flags",
        "matches": ("ALLOW_TEST_BYPASS", "ALLOW_DEV_AUTH_FALLBACK", "forbidden_launch_flags_enabled"),
        "variables": ("ALLOW_TEST_BYPASS", "ALLOW_DEV_AUTH_FALLBACK"),
        "operator_action": "Disable dev/test authentication bypass flags before launch.",
        "validation": "Preflight must report forbidden_launch_flags_enabled=[].",
    },
    {
        "id": "fix_docker_readiness",
        "matches": ("Docker daemon", "docker compose", "compose config", "docker"),
        "variables": (),
        "operator_action": "Start Docker Desktop and ensure compose config renders successfully.",
        "validation": "Preflight with --check-docker must report docker status as pass.",
    },
)

ENV_TEMPLATE_ENTRIES: tuple[dict[str, str], ...] = (
    {
        "key": "AGRIGUARD_DB_USER",
        "value": "agriguard",
        "comment": "Compose PostgreSQL user.",
    },
    {
        "key": "AGRIGUARD_DB_PASSWORD",
        "value": "<set-strong-db-password-16-plus-chars>",
        "comment": "Use a strong database password or set AGRIGUARD_DATABASE_URL instead.",
    },
    {
        "key": "AGRIGUARD_DB_NAME",
        "value": "agriguard",
        "comment": "Compose PostgreSQL database name.",
    },
    {
        "key": "AGRIGUARD_AUTO_CREATE_SCHEMA",
        "value": "false",
        "comment": "Keep schema auto-creation disabled for launch.",
    },
    {
        "key": "AGRIGUARD_ALLOWED_ORIGINS",
        "value": "https://app.example.com",
        "comment": "Comma-separated production browser origins; do not use localhost for launch.",
    },
    {
        "key": "AGRIGUARD_SECRET_KEY",
        "value": "<set-strong-secret-32-plus-chars>",
        "comment": "Strong app-scoped secret.",
    },
    {
        "key": "AGRIGUARD_QR_TOKEN_PEPPER",
        "value": "<set-stable-qr-token-pepper-32-plus-chars>",
        "comment": "Stable per-environment token pepper; changing it invalidates stored token hashes.",
    },
    {
        "key": "AGRIGUARD_PUBLIC_VERIFY_BASE_URL",
        "value": "https://verify.example.com",
        "comment": "Public HTTPS URL opened by scanned QR labels.",
    },
    {
        "key": "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE",
        "value": "<absolute-path-outside-repo-to-firebase-service-account.json>",
        "comment": "Host path to a Firebase Admin service account JSON file outside the repo.",
    },
    {
        "key": "ALLOW_TEST_BYPASS",
        "value": "false",
        "comment": "Must remain false for launch.",
    },
    {
        "key": "ALLOW_DEV_AUTH_FALLBACK",
        "value": "false",
        "comment": "Must remain false for launch.",
    },
)


def _default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_peer_module(module_name: str) -> Any:
    script_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


index_guarded_launch_artifacts = _load_peer_module("index_guarded_launch_artifacts")
run_guarded_launch = index_guarded_launch_artifacts.run_guarded_launch

REQUIRED_GUARDED_LAUNCH_EVIDENCE_OUTPUT_KEYS = (
    index_guarded_launch_artifacts.STATUS_ARTIFACT_ROLE,
    *index_guarded_launch_artifacts.REQUIRED_CORE_ARTIFACT_ROLES,
    "artifact_index_json",
)


def _workspace_root(app_root: Path) -> Path:
    if app_root.parent.name == "apps":
        return app_root.parents[1]
    return app_root.parent


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _operator_env_template_validation_command() -> str:
    return (
        "python apps/AgriGuard/scripts/validate_launch_env_template.py "
        "--env-file var/agriguard-launch-operator.env.template "
        "--json-out var/agriguard-launch-env-template-validation.json "
        "--markdown-out var/agriguard-launch-env-template-validation.md"
    )


def _guarded_launch_command() -> str:
    status_json = f"var/{run_guarded_launch.DEFAULT_OUTPUT_PREFIX}-status.json"
    return (
        "python apps/AgriGuard/scripts/run_guarded_launch.py "
        "--env-file var/agriguard-launch-operator.env.template "
        "--emit-handoff "
        f"--status-json-out {status_json}"
    )


def _default_status_json(output_dir: Path, output_prefix: str) -> Path:
    return output_dir / f"{output_prefix}-status.json"


def _guarded_launch_evidence_outputs(*, app_root: Path) -> dict[str, str]:
    workspace_root = _workspace_root(app_root)
    output_dir = workspace_root / "var"
    output_prefix = run_guarded_launch.DEFAULT_OUTPUT_PREFIX
    status_json = _default_status_json(output_dir, output_prefix)
    artifact_paths = index_guarded_launch_artifacts._artifact_paths(output_dir, output_prefix, status_json)
    paths = {
        key: artifact_paths[key]
        for key in REQUIRED_GUARDED_LAUNCH_EVIDENCE_OUTPUT_KEYS
        if key != "artifact_index_json"
    }
    paths["artifact_index_json"] = run_guarded_launch._default_artifact_index_json(output_dir, output_prefix)
    return {key: _rel(path, workspace_root) for key, path in paths.items()}


def _guarded_launch_evidence_validation(outputs: dict[str, str]) -> dict[str, object]:
    missing = [key for key in REQUIRED_GUARDED_LAUNCH_EVIDENCE_OUTPUT_KEYS if key not in outputs]
    empty = [key for key in REQUIRED_GUARDED_LAUNCH_EVIDENCE_OUTPUT_KEYS if not outputs.get(key)]
    return {
        "status": "pass" if not missing and not empty else "fail",
        "required_output_keys": list(REQUIRED_GUARDED_LAUNCH_EVIDENCE_OUTPUT_KEYS),
        "missing_output_keys": missing,
        "empty_output_keys": empty,
    }


def _guarded_launch_outputs_from_packet(packet: dict[str, object]) -> dict[str, str]:
    evidence = packet.get("guarded_launch_evidence")
    if not isinstance(evidence, dict):
        return {}
    outputs = evidence.get("outputs")
    if not isinstance(outputs, dict):
        return {}
    return {str(key): str(value) for key, value in outputs.items() if isinstance(key, str)}


def _extract_guarded_launch_evidence_table(markdown: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    in_section = False
    for line in markdown.splitlines():
        if line == "## Guarded Launch Evidence Outputs":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2 or cells[0] in {"Artifact", "---"}:
            continue
        key = cells[0].strip("`")
        path = cells[1].strip("`")
        if key and path:
            rows[key] = path
    return rows


def validate_markdown_evidence_table(packet: dict[str, object], markdown: str) -> dict[str, object]:
    expected = _guarded_launch_outputs_from_packet(packet)
    actual = _extract_guarded_launch_evidence_table(markdown)
    missing = [key for key in expected if key not in actual]
    extra = [key for key in actual if key not in expected]
    mismatches = [
        {"key": key, "expected": expected[key], "actual": actual[key]}
        for key in expected
        if key in actual and actual[key] != expected[key]
    ]
    return {
        "status": "pass" if not missing and not extra and not mismatches else "fail",
        "expected_output_keys": list(expected),
        "missing_rows": missing,
        "extra_rows": extra,
        "path_mismatches": mismatches,
    }


def _redact_text(value: object) -> str:
    text = str(value)
    return SENSITIVE_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _env_shape_actions(env_payload: dict[str, Any], env_validation_rel: str) -> tuple[list[dict[str, object]], list[str]]:
    raw_findings = env_payload.get("blocking_findings") if isinstance(env_payload.get("blocking_findings"), list) else []
    findings = [_redact_text(finding) for finding in raw_findings]
    if not findings:
        findings = [f"Env validation blocked strict preflight: {env_validation_rel}"]
    variables: list[str] = []
    missing = env_payload.get("missing_required_keys") if isinstance(env_payload.get("missing_required_keys"), list) else []
    variables.extend(str(key) for key in missing if isinstance(key, str))
    placeholders = (
        env_payload.get("placeholder_variables")
        if isinstance(env_payload.get("placeholder_variables"), list)
        else []
    )
    variables.extend(
        str(item.get("key"))
        for item in placeholders
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    )
    forbidden = (
        env_payload.get("forbidden_flags_enabled")
        if isinstance(env_payload.get("forbidden_flags_enabled"), list)
        else []
    )
    variables.extend(str(flag) for flag in forbidden if isinstance(flag, str))
    variables = sorted(set(variables))
    return (
        [
            {
                "id": "fix_env_shape_validation",
                "variables": variables,
                "operator_action": "Fix the launch env template findings before strict preflight can run.",
                "validation": "Env template validation must report ready_for_preflight=true.",
                "source_errors": findings,
            }
        ],
        findings,
    )


def _first_matching_rule(error: str) -> dict[str, object] | None:
    normalized = error.lower()
    for rule in ACTION_RULES:
        matches = rule["matches"]
        assert isinstance(matches, tuple)
        if any(str(term).lower() in normalized for term in matches):
            return rule
    return None


def _build_actions(errors: list[str]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    seen: set[str] = set()
    unmatched_index = 1

    for error in errors:
        rule = _first_matching_rule(error)
        if rule is None:
            action_id = f"review_preflight_error_{unmatched_index}"
            unmatched_index += 1
            actions.append(
                {
                    "id": action_id,
                    "variables": [],
                    "operator_action": f"Review unresolved preflight error: {_redact_text(error)}",
                    "validation": "Rerun launch preflight and confirm this error disappears.",
                    "source_errors": [_redact_text(error)],
                }
            )
            continue

        action_id = str(rule["id"])
        if action_id in seen:
            for action in actions:
                if action["id"] == action_id:
                    source_errors = action.setdefault("source_errors", [])
                    assert isinstance(source_errors, list)
                    source_errors.append(_redact_text(error))
                    break
            continue

        seen.add(action_id)
        variables = rule["variables"]
        assert isinstance(variables, tuple)
        actions.append(
            {
                "id": action_id,
                "variables": list(variables),
                "operator_action": rule["operator_action"],
                "validation": rule["validation"],
                "source_errors": [_redact_text(error)],
            }
        )

    return actions


def build_operator_packet(
    *,
    preflight_json: Path,
    env_validation_json: Path | None = None,
    app_root: Path | None = None,
) -> dict[str, object]:
    app_root = (app_root or _default_app_root()).resolve()
    workspace_root = _workspace_root(app_root)
    payload = _read_json(preflight_json)
    env_payload = _read_json(env_validation_json) if env_validation_json is not None else None

    preflight_rel = _rel(preflight_json, workspace_root)
    env_validation_rel = _rel(env_validation_json, workspace_root) if env_validation_json is not None else None
    if payload is None:
        if env_payload is not None and env_payload.get("status") != "pass":
            actions, errors = _env_shape_actions(env_payload, env_validation_rel or "<unknown>")
            status = "env_shape_blocked"
        else:
            actions = [
                {
                    "id": "run_launch_preflight",
                    "variables": [],
                    "operator_action": "Run the strict launch preflight before retrying compose launch.",
                    "validation": "A readable launch preflight JSON report exists.",
                    "source_errors": [f"Preflight JSON not found or unreadable: {preflight_rel}"],
                }
            ]
            status = "missing_preflight"
            errors = [actions[0]["source_errors"][0]]
        checks: dict[str, object] = {}
    else:
        status = str(payload.get("status") or "unknown")
        raw_errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
        errors = [_redact_text(error) for error in raw_errors]
        checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
        actions = _build_actions(errors)

    blocked = status != "pass" or bool(actions)
    validate_env_template = _operator_env_template_validation_command()
    rerun_preflight = (
        "python apps/AgriGuard/scripts/launch_env_preflight.py "
        "--check-docker --json-out var/agriguard-launch-env-preflight-compose-launch.json"
    )
    rerun_launch = (
        "python apps/AgriGuard/scripts/launch_compose.py "
        "--run-browser-smoke --launch-report-json var/agriguard-compose-launch-report.json"
    )
    guarded_launch = _guarded_launch_command()
    guarded_launch_outputs = _guarded_launch_evidence_outputs(app_root=app_root)

    return {
        "schema_version": 1,
        "status": "blocked" if blocked else "ready",
        "preflight_status": status,
        "preflight_json": preflight_rel,
        "env_validation_json": env_validation_rel,
        "env_validation_status": env_payload.get("status") if isinstance(env_payload, dict) else None,
        "secrets_redacted": True,
        "blocking_action_count": len(actions),
        "operator_actions": actions,
        "preflight_errors": errors,
        "preflight_warning_count": len(payload.get("warnings", [])) if isinstance(payload, dict) and isinstance(payload.get("warnings"), list) else 0,
        "preflight_checks": {
            "runtime": checks.get("runtime"),
            "docker_checked": checks.get("docker_checked"),
            "firebase_credentials_source": checks.get("firebase_credentials_source"),
            "forbidden_launch_flags_enabled": checks.get("forbidden_launch_flags_enabled"),
            "allowed_origins_source": checks.get("allowed_origins_source"),
            "public_verify_base_url_source": checks.get("public_verify_base_url_source"),
            "database_password_source": checks.get("database_password_source"),
            "database_url_source": checks.get("database_url_source"),
        },
        "operator_env_template": {
            "format": "dotenv",
            "placeholder_values_must_be_replaced": True,
            "variables": [entry["key"] for entry in ENV_TEMPLATE_ENTRIES],
            "validation_command": validate_env_template,
        },
        "guarded_launch_evidence": {
            "wrapper_command": guarded_launch,
            "outputs": guarded_launch_outputs,
            "validation": _guarded_launch_evidence_validation(guarded_launch_outputs),
        },
        "safe_rerun_commands": [validate_env_template, guarded_launch, rerun_preflight, rerun_launch],
    }


def render_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# AgriGuard Launch Operator Packet",
        "",
        f"- Status: `{packet['status']}`",
        f"- Preflight status: `{packet['preflight_status']}`",
        f"- Preflight JSON: `{packet['preflight_json']}`",
        f"- Secrets redacted: `{str(packet['secrets_redacted']).lower()}`",
        f"- Blocking action count: `{packet['blocking_action_count']}`",
        "",
        "## Required Operator Actions",
        "",
    ]

    actions = packet.get("operator_actions")
    if isinstance(actions, list) and actions:
        lines.append("| ID | Variables | Action | Validation |")
        lines.append("| --- | --- | --- | --- |")
        for action in actions:
            assert isinstance(action, dict)
            variables = action.get("variables") if isinstance(action.get("variables"), list) else []
            variable_text = ", ".join(f"`{variable}`" for variable in variables) or "-"
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{action.get('id')}`",
                        variable_text,
                        str(action.get("operator_action")),
                        str(action.get("validation")),
                    ]
                )
                + " |"
            )
    else:
        lines.append("No blocking operator actions remain in the selected preflight report.")

    lines.extend(["", "## Preflight Errors", ""])
    errors = packet.get("preflight_errors")
    if isinstance(errors, list) and errors:
        lines.extend(f"- `{error}`" for error in errors)
    else:
        lines.append("No preflight errors recorded.")

    lines.extend(["", "## Safe Rerun Commands", ""])
    commands = packet.get("safe_rerun_commands")
    if isinstance(commands, list):
        lines.extend(f"- `{command}`" for command in commands)

    evidence = packet.get("guarded_launch_evidence") if isinstance(packet.get("guarded_launch_evidence"), dict) else {}
    outputs = evidence.get("outputs") if isinstance(evidence.get("outputs"), dict) else {}
    lines.extend(["", "## Guarded Launch Evidence Outputs", ""])
    if outputs:
        lines.append("| Artifact | Path |")
        lines.append("| --- | --- |")
        for key, path in outputs.items():
            lines.append(f"| `{key}` | `{path}` |")
    else:
        lines.append("No guarded-launch evidence outputs are listed.")
    lines.append("")
    return "\n".join(lines)


def render_env_template(packet: dict[str, object]) -> str:
    action_ids: list[str] = []
    actions = packet.get("operator_actions")
    if isinstance(actions, list):
        action_ids = [
            str(action.get("id"))
            for action in actions
            if isinstance(action, dict) and isinstance(action.get("id"), str)
        ]

    lines = [
        "# AgriGuard launch env template",
        "# Replace every <...> placeholder before running launch preflight.",
        "# Keep this file out of git after real values are added.",
        f"# Packet status: {packet.get('status')}",
        f"# Blocking action IDs: {', '.join(action_ids) if action_ids else 'none'}",
        "",
    ]
    for entry in ENV_TEMPLATE_ENTRIES:
        comment = entry.get("comment")
        if comment:
            lines.append(f"# {comment}")
        lines.append(f"{entry['key']}={entry['value']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    app_root = _default_app_root()
    workspace_root = _workspace_root(app_root)
    parser = argparse.ArgumentParser(description="Render a redacted AgriGuard launch operator packet from preflight JSON.")
    parser.add_argument("--app-root", type=Path, default=app_root)
    parser.add_argument(
        "--preflight-json",
        type=Path,
        default=workspace_root / "var" / "agriguard-launch-env-preflight-compose-launch.json",
    )
    parser.add_argument(
        "--env-validation-json",
        type=Path,
        default=None,
        help="Optional env-template validation JSON used when strict preflight did not run.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=workspace_root / "var" / "agriguard-launch-operator-packet.json",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=workspace_root / "var" / "agriguard-launch-operator-packet.md",
    )
    parser.add_argument(
        "--env-template-out",
        type=Path,
        default=None,
        help="Optional dotenv template with redacted launch variable placeholders.",
    )
    parser.add_argument(
        "--exit-zero-on-blocked",
        action="store_true",
        help="Write the packet but return 0 even when launch remains blocked.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_operator_packet(
        preflight_json=args.preflight_json.resolve(),
        env_validation_json=args.env_validation_json.resolve() if args.env_validation_json else None,
        app_root=args.app_root.resolve(),
    )
    markdown = render_markdown(packet)
    evidence = packet.get("guarded_launch_evidence")
    if isinstance(evidence, dict):
        evidence["markdown_table_validation"] = validate_markdown_evidence_table(packet, markdown)
    write_json(args.json_out.resolve(), packet)
    args.markdown_out.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.resolve().write_text(markdown, encoding="utf-8")
    if args.env_template_out:
        args.env_template_out.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.env_template_out.resolve().write_text(render_env_template(packet), encoding="utf-8")
        print(f"wrote launch env template: {args.env_template_out}")
    print(f"wrote launch operator packet: {args.json_out}")
    print(f"wrote launch operator packet markdown: {args.markdown_out}")
    return 0 if args.exit_zero_on_blocked or packet["status"] == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())

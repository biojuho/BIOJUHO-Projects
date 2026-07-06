from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
DEFAULT_COMPOSE_BROWSER_BASE_URL = "http://127.0.0.1"
DEFAULT_COMPOSE_BROWSER_API_URL = "http://127.0.0.1:8002"


def _default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace_root(app_root: Path) -> Path:
    if app_root.parent.name == "apps":
        return app_root.parents[1]
    return app_root.parent


def _default_json_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-env-preflight-compose-launch.json"


def _default_browser_smoke_json_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-browser-smoke-suite-compose-launch.json"


def _default_browser_smoke_output_dir(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-browser-smoke-suite-compose-launch"


def _default_launch_report_json_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-compose-launch-report.json"


def _default_operator_packet_json_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-operator-packet.json"


def _default_operator_packet_markdown_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-operator-packet.md"


def _default_operator_env_template_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-operator.env.template"


def _default_env_validation_json_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-env-template-validation.json"


def _default_env_validation_markdown_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-env-template-validation.md"


def _default_readiness_summary_json_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-readiness-summary.json"


def _default_readiness_summary_markdown_out(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-readiness-summary.md"


def _tail(value: str | None, *, limit: int = 1200) -> str:
    if not value:
        return ""
    value = value.strip()
    return value[-limit:] if len(value) > limit else value


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _strip_optional_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            env[key] = _strip_optional_quotes(value)
    return env


def _compose_subprocess_env(env_files: list[Path]) -> dict[str, str]:
    env: dict[str, str] = {}
    for env_file in env_files:
        env.update(_load_env_file(env_file))
    env.update(os.environ)
    return env


def _read_json_file(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _summarize_preflight_json(path: Path) -> dict[str, object]:
    payload = _read_json_file(path)
    if payload is None:
        return {"found": False, "path": str(path)}
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "blocker_class": payload.get("blocker_class"),
        "errors": payload.get("errors") if isinstance(payload.get("errors"), list) else [],
        "warnings": payload.get("warnings") if isinstance(payload.get("warnings"), list) else [],
    }


def _summarize_browser_smoke_json(path: Path) -> dict[str, object]:
    payload = _read_json_file(path)
    if payload is None:
        return {"found": False, "path": str(path)}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "base_url": payload.get("base_url"),
        "api_url": payload.get("api_url"),
        "mobile": payload.get("mobile"),
        "include_unavailable_check": payload.get("include_unavailable_check"),
        "summary": summary,
        "failed_step_names": _string_list(summary.get("failed_step_names")),
        "failed_check_names": _string_list(summary.get("failed_check_names")),
        "failed_precheck_names": _string_list(summary.get("failed_precheck_names")),
        "prechecks": payload.get("prechecks") if isinstance(payload.get("prechecks"), list) else [],
    }


def _summarize_env_validation_json(path: Path) -> dict[str, object]:
    payload = _read_json_file(path)
    if payload is None:
        return {"found": False, "path": str(path)}
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "blocker_class": payload.get("blocker_class"),
        "ready_for_preflight": payload.get("ready_for_preflight"),
        "placeholder_count": payload.get("placeholder_count"),
        "missing_required_keys": (
            payload.get("missing_required_keys")
            if isinstance(payload.get("missing_required_keys"), list)
            else []
        ),
        "forbidden_flags_enabled": (
            payload.get("forbidden_flags_enabled")
            if isinstance(payload.get("forbidden_flags_enabled"), list)
            else []
        ),
    }


def _summarize_operator_packet_json(
    path: Path,
    markdown_path: Path,
    env_template_path: Path,
) -> dict[str, object]:
    payload = _read_json_file(path)
    if payload is None:
        return {
            "found": False,
            "path": str(path),
            "markdown_path": str(markdown_path),
            "env_template_path": str(env_template_path),
            "env_template_found": env_template_path.exists(),
        }
    actions = payload.get("operator_actions") if isinstance(payload.get("operator_actions"), list) else []
    action_ids = [
        action.get("id")
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    ]
    env_template = (
        payload.get("operator_env_template")
        if isinstance(payload.get("operator_env_template"), dict)
        else {}
    )
    template_variables = (
        env_template.get("variables")
        if isinstance(env_template.get("variables"), list)
        else []
    )
    summary = {
        "found": True,
        "path": str(path),
        "markdown_path": str(markdown_path),
        "env_template_path": str(env_template_path),
        "env_template_found": env_template_path.exists(),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "blocker_class": payload.get("blocker_class"),
        "env_validation_status": payload.get("env_validation_status"),
        "env_validation_blocker_class": payload.get("env_validation_blocker_class"),
        "preflight_status": payload.get("preflight_status"),
        "blocking_action_count": payload.get("blocking_action_count"),
        "operator_action_ids": action_ids,
        "env_template_variables": template_variables,
        "secrets_redacted": payload.get("secrets_redacted"),
    }
    guarded_evidence = (
        payload.get("guarded_launch_evidence")
        if isinstance(payload.get("guarded_launch_evidence"), dict)
        else {}
    )
    artifact_index_summary = (
        guarded_evidence.get("artifact_index_readiness_summary")
        if isinstance(guarded_evidence.get("artifact_index_readiness_summary"), dict)
        else {}
    )
    if artifact_index_summary:
        summary.update(
            {
                "artifact_index_status": artifact_index_summary.get("status"),
                "artifact_index_blocker_class": artifact_index_summary.get("blocker_class"),
                "consumer_packet_validation_status": artifact_index_summary.get(
                    "consumer_packet_validation_status"
                ),
                "consumer_command_metadata_status": artifact_index_summary.get(
                    "consumer_command_metadata_status"
                ),
                "artifact_index_recovery_command_status": artifact_index_summary.get(
                    "recovery_command_status"
                ),
            }
        )
    return summary


def _summarize_readiness_next_commands(payload: dict[str, object]) -> list[dict[str, str]]:
    raw_commands = payload.get("next_commands")
    if not isinstance(raw_commands, list):
        return []

    commands: list[dict[str, str]] = []
    for item in raw_commands:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        command = item.get("command")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(command, str) or not command.strip():
            continue
        summary = {"name": name, "command": command}
        shell = item.get("shell")
        if isinstance(shell, str) and shell.strip():
            summary["shell"] = shell
        commands.append(summary)
    return commands


def _summarize_readiness_summary_json(path: Path) -> dict[str, object]:
    payload = _read_json_file(path)
    if payload is None:
        return {"found": False, "path": str(path)}
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "blocker_class": payload.get("blocker_class"),
        "secrets_redacted": payload.get("secrets_redacted"),
        "next_actions": _string_list(payload.get("next_actions")),
        "next_commands": _summarize_readiness_next_commands(payload),
    }


def _command_result(
    *,
    name: str,
    command: list[str],
    completed: subprocess.CompletedProcess[str],
) -> dict[str, object]:
    return {
        "name": name,
        "command": command,
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _build_preflight_command(app_root: Path, json_out: Path, env_files: list[Path]) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "launch_env_preflight.py"),
        "--check-docker",
        "--json-out",
        str(json_out),
    ]
    for env_file in env_files:
        command.extend(["--env-file", str(env_file)])
    return command


def _build_env_validation_command(
    app_root: Path,
    *,
    env_file: Path,
    json_out: Path,
    markdown_out: Path,
) -> list[str]:
    return [
        sys.executable,
        str(app_root / "scripts" / "validate_launch_env_template.py"),
        "--app-root",
        str(app_root),
        "--env-file",
        str(env_file),
        "--json-out",
        str(json_out),
        "--markdown-out",
        str(markdown_out),
    ]


def _build_compose_command(app_root: Path, services: list[str], *, build: bool, wait: bool) -> list[str]:
    command = [
        "docker",
        "compose",
        "-f",
        str(app_root / "docker-compose.yml"),
        "up",
        "-d",
    ]
    if build:
        command.append("--build")
    if wait:
        command.append("--wait")
    command.extend(services)
    return command


def _build_browser_smoke_command(
    app_root: Path,
    *,
    base_url: str,
    api_url: str,
    json_out: Path,
    output_dir: Path,
    timeout_ms: int,
    mobile: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "run_browser_smoke_suite.py"),
        "--base-url",
        base_url,
        "--api-url",
        api_url,
        "--json-out",
        str(json_out),
        "--output-dir",
        str(output_dir),
        "--timeout-ms",
        str(timeout_ms),
    ]
    if mobile:
        command.append("--mobile")
    return command


def _build_operator_packet_command(
    app_root: Path,
    *,
    preflight_json: Path,
    env_validation_json: Path | None,
    env_validation_markdown: Path | None,
    launch_report_json: Path,
    env_files: list[Path],
    json_out: Path,
    markdown_out: Path,
    env_template_out: Path,
    readiness_summary_json: Path | None,
    readiness_summary_markdown: Path | None,
    guarded_output_dir: Path | None,
    guarded_output_prefix: str | None,
    guarded_status_json: Path | None,
    guarded_handoff_json: Path | None,
    guarded_handoff_markdown: Path | None,
    guarded_handoff_validation_json: Path | None,
    guarded_handoff_consumer_json: Path | None,
    guarded_ready_gate_json: Path | None,
    run_browser_smoke: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "render_launch_operator_packet.py"),
        "--app-root",
        str(app_root),
        "--preflight-json",
        str(preflight_json),
        "--json-out",
        str(json_out),
        "--markdown-out",
        str(markdown_out),
        "--env-template-out",
        str(env_template_out),
    ]
    if env_validation_json is not None:
        command.extend(["--env-validation-json", str(env_validation_json)])
    if env_validation_markdown is not None:
        command.extend(["--env-validation-markdown", str(env_validation_markdown)])
    command.extend(["--compose-launch-report-json", str(launch_report_json)])
    if readiness_summary_json is not None:
        command.extend(["--readiness-summary-json", str(readiness_summary_json)])
    if readiness_summary_markdown is not None:
        command.extend(["--readiness-summary-markdown", str(readiness_summary_markdown)])
    guarded_path_options = [
        ("--guarded-output-dir", guarded_output_dir),
        ("--guarded-status-json", guarded_status_json),
        ("--guarded-handoff-json", guarded_handoff_json),
        ("--guarded-handoff-markdown", guarded_handoff_markdown),
        ("--guarded-handoff-validation-json", guarded_handoff_validation_json),
        ("--guarded-handoff-consumer-json", guarded_handoff_consumer_json),
        ("--guarded-ready-gate-json", guarded_ready_gate_json),
    ]
    for flag, path in guarded_path_options:
        if path is not None:
            command.extend([flag, str(path)])
    if guarded_output_prefix:
        command.extend(["--guarded-output-prefix", guarded_output_prefix])
    for env_file in env_files:
        command.extend(["--env-file", str(env_file)])
    if not run_browser_smoke:
        command.append("--no-browser-smoke")
    command.append("--exit-zero-on-blocked")
    return command


def _build_readiness_summary_command(
    app_root: Path,
    *,
    launch_report_json: Path,
    env_validation_json: Path,
    operator_packet_json: Path,
    json_out: Path,
    markdown_out: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "summarize_launch_readiness.py"),
        "--app-root",
        str(app_root),
        "--launch-report-json",
        str(launch_report_json),
        "--env-validation-json",
        str(env_validation_json),
        "--operator-packet-json",
        str(operator_packet_json),
        "--json-out",
        str(json_out),
        "--exit-zero-on-blocked",
    ]
    if markdown_out is not None:
        command.extend(["--markdown-out", str(markdown_out)])
    return command


def _launch_blocker_class(launch_report: dict[str, object]) -> str | None:
    status = launch_report.get("status")
    if status == "pass":
        return "ready"
    stop_reason = launch_report.get("stop_reason")
    if stop_reason in {"env_shape_validation_failed", "env_shape_validation_requires_single_env_file"}:
        return "env_shape_blocked"
    if stop_reason == "preflight_failed":
        return "preflight_blocked"
    if stop_reason == "compose_failed":
        return "compose_blocked"
    if stop_reason == "browser_smoke_failed":
        return "browser_smoke_blocked"
    return None


def _refresh_launch_blocker_class(launch_report: dict[str, object]) -> None:
    launch_report["blocker_class"] = _launch_blocker_class(launch_report)


def _write_failed_launch_report(
    *,
    app_root: Path,
    launch_report_json: Path,
    launch_report: dict[str, object],
    readiness_summary_command: list[str] | None,
    readiness_summary_json: Path | None,
    command_runner: CommandRunner,
) -> None:
    _refresh_launch_blocker_class(launch_report)
    write_json(launch_report_json, launch_report)
    if readiness_summary_command is None or readiness_summary_json is None:
        return

    results = launch_report["results"]
    assert isinstance(results, list)
    child_reports = launch_report["child_reports"]
    assert isinstance(child_reports, dict)
    if readiness_summary_json.is_file():
        readiness_summary_json.unlink()
    readiness_result = command_runner(readiness_summary_command, cwd=app_root, text=True)
    results.append(
        _command_result(
            name="readiness_summary",
            command=readiness_summary_command,
            completed=readiness_result,
        )
    )
    child_reports["readiness_summary"] = _summarize_readiness_summary_json(readiness_summary_json)
    _refresh_launch_blocker_class(launch_report)
    write_json(launch_report_json, launch_report)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AgriGuard compose launch behind strict preflight.")
    parser.add_argument("--app-root", type=Path, default=_default_app_root(), help="AgriGuard app root.")
    parser.add_argument(
        "--env-file",
        action="append",
        type=Path,
        default=[],
        help="Optional env file passed to launch_env_preflight.py. May be repeated.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Preflight JSON output path. Defaults to workspace var/agriguard-launch-env-preflight-compose-launch.json.",
    )
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        help="Optional compose service to launch. May be repeated. Defaults to all services.",
    )
    parser.add_argument("--no-build", action="store_true", help="Do not pass --build to docker compose up.")
    parser.add_argument(
        "--run-browser-smoke",
        action="store_true",
        help="After compose starts successfully, run the aggregate browser smoke suite.",
    )
    parser.add_argument(
        "--no-compose-wait",
        action="store_true",
        help="Do not pass --wait to docker compose up when --run-browser-smoke is enabled.",
    )
    parser.add_argument(
        "--browser-base-url",
        default=DEFAULT_COMPOSE_BROWSER_BASE_URL,
        help=f"Frontend base URL for post-compose browser smoke. Defaults to {DEFAULT_COMPOSE_BROWSER_BASE_URL}.",
    )
    parser.add_argument(
        "--browser-api-url",
        default=DEFAULT_COMPOSE_BROWSER_API_URL,
        help=f"Backend API URL for post-compose browser smoke. Defaults to {DEFAULT_COMPOSE_BROWSER_API_URL}.",
    )
    parser.add_argument(
        "--browser-smoke-json-out",
        type=Path,
        default=None,
        help="Post-compose browser smoke JSON output path.",
    )
    parser.add_argument(
        "--browser-smoke-output-dir",
        type=Path,
        default=None,
        help="Post-compose browser smoke artifact directory.",
    )
    parser.add_argument("--browser-smoke-timeout-ms", type=int, default=30_000)
    parser.add_argument("--browser-smoke-mobile", action="store_true", help="Run post-compose browser smoke mobile variants.")
    parser.add_argument(
        "--launch-report-json",
        type=Path,
        default=None,
        help="Aggregate launch report JSON path. Defaults to workspace var/agriguard-compose-launch-report.json.",
    )
    parser.add_argument(
        "--operator-packet-json",
        type=Path,
        default=None,
        help="Operator packet JSON path written when launch preflight fails.",
    )
    parser.add_argument(
        "--operator-packet-markdown",
        type=Path,
        default=None,
        help="Operator packet Markdown path written when launch preflight fails.",
    )
    parser.add_argument(
        "--operator-env-template",
        type=Path,
        default=None,
        help="Operator dotenv template path written when launch preflight fails.",
    )
    parser.add_argument("--guarded-output-dir", type=Path, default=None)
    parser.add_argument("--guarded-output-prefix", default=None)
    parser.add_argument("--guarded-status-json", type=Path, default=None)
    parser.add_argument("--guarded-handoff-json", type=Path, default=None)
    parser.add_argument("--guarded-handoff-markdown", type=Path, default=None)
    parser.add_argument("--guarded-handoff-validation-json", type=Path, default=None)
    parser.add_argument("--guarded-handoff-consumer-json", type=Path, default=None)
    parser.add_argument("--guarded-ready-gate-json", type=Path, default=None)
    parser.add_argument(
        "--validate-env-file-shape",
        action="store_true",
        help="Validate exactly one supplied --env-file with validate_launch_env_template.py before strict preflight.",
    )
    parser.add_argument(
        "--env-validation-json-out",
        type=Path,
        default=None,
        help="Shape validation JSON output path when --validate-env-file-shape is enabled.",
    )
    parser.add_argument(
        "--env-validation-markdown-out",
        type=Path,
        default=None,
        help="Shape validation Markdown output path when --validate-env-file-shape is enabled.",
    )
    parser.add_argument(
        "--readiness-summary-json",
        type=Path,
        default=None,
        help="Optional compact launch-readiness summary JSON emitted after a failed launch stage.",
    )
    parser.add_argument(
        "--readiness-summary-markdown",
        type=Path,
        default=None,
        help="Optional compact launch-readiness summary Markdown emitted after a failed launch stage.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the command plan without running preflight or compose.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, command_runner: CommandRunner = subprocess.run) -> int:
    args = parse_args(argv)
    app_root = args.app_root.resolve()
    env_files = [env_file.resolve() for env_file in args.env_file]
    json_out = args.json_out.resolve() if args.json_out else _default_json_out(app_root)
    browser_smoke_json_out = (
        args.browser_smoke_json_out.resolve()
        if args.browser_smoke_json_out
        else _default_browser_smoke_json_out(app_root)
    )
    browser_smoke_output_dir = (
        args.browser_smoke_output_dir.resolve()
        if args.browser_smoke_output_dir
        else _default_browser_smoke_output_dir(app_root)
    )
    launch_report_json = (
        args.launch_report_json.resolve()
        if args.launch_report_json
        else _default_launch_report_json_out(app_root)
    )
    operator_packet_json = (
        args.operator_packet_json.resolve()
        if args.operator_packet_json
        else _default_operator_packet_json_out(app_root)
    )
    operator_packet_markdown = (
        args.operator_packet_markdown.resolve()
        if args.operator_packet_markdown
        else _default_operator_packet_markdown_out(app_root)
    )
    operator_env_template = (
        args.operator_env_template.resolve()
        if args.operator_env_template
        else _default_operator_env_template_out(app_root)
    )
    env_validation_json_out = (
        args.env_validation_json_out.resolve()
        if args.env_validation_json_out
        else _default_env_validation_json_out(app_root)
    )
    env_validation_markdown_out = (
        args.env_validation_markdown_out.resolve()
        if args.env_validation_markdown_out
        else _default_env_validation_markdown_out(app_root)
    )
    readiness_summary_requested = bool(args.readiness_summary_json or args.readiness_summary_markdown)
    readiness_summary_json = (
        args.readiness_summary_json.resolve()
        if args.readiness_summary_json
        else (_default_readiness_summary_json_out(app_root) if readiness_summary_requested else None)
    )
    readiness_summary_markdown = (
        args.readiness_summary_markdown.resolve()
        if args.readiness_summary_markdown
        else None
    )
    env_validation_command = (
        _build_env_validation_command(
            app_root,
            env_file=env_files[0],
            json_out=env_validation_json_out,
            markdown_out=env_validation_markdown_out,
        )
        if args.validate_env_file_shape and len(env_files) == 1
        else None
    )
    preflight_command = _build_preflight_command(app_root, json_out, env_files)
    compose_command = _build_compose_command(
        app_root,
        args.service,
        build=not args.no_build,
        wait=args.run_browser_smoke and not args.no_compose_wait,
    )
    browser_smoke_command = (
        _build_browser_smoke_command(
            app_root,
            base_url=args.browser_base_url,
            api_url=args.browser_api_url,
            json_out=browser_smoke_json_out,
            output_dir=browser_smoke_output_dir,
            timeout_ms=args.browser_smoke_timeout_ms,
            mobile=args.browser_smoke_mobile,
        )
        if args.run_browser_smoke
        else None
    )
    guarded_output_dir = args.guarded_output_dir.resolve() if args.guarded_output_dir else None
    guarded_status_json = args.guarded_status_json.resolve() if args.guarded_status_json else None
    guarded_handoff_json = args.guarded_handoff_json.resolve() if args.guarded_handoff_json else None
    guarded_handoff_markdown = (
        args.guarded_handoff_markdown.resolve() if args.guarded_handoff_markdown else None
    )
    guarded_handoff_validation_json = (
        args.guarded_handoff_validation_json.resolve() if args.guarded_handoff_validation_json else None
    )
    guarded_handoff_consumer_json = (
        args.guarded_handoff_consumer_json.resolve() if args.guarded_handoff_consumer_json else None
    )
    guarded_ready_gate_json = args.guarded_ready_gate_json.resolve() if args.guarded_ready_gate_json else None
    operator_packet_command = _build_operator_packet_command(
        app_root,
        preflight_json=json_out,
        env_validation_json=env_validation_json_out,
        env_validation_markdown=env_validation_markdown_out,
        launch_report_json=launch_report_json,
        env_files=env_files,
        json_out=operator_packet_json,
        markdown_out=operator_packet_markdown,
        env_template_out=operator_env_template,
        readiness_summary_json=readiness_summary_json,
        readiness_summary_markdown=readiness_summary_markdown,
        guarded_output_dir=guarded_output_dir,
        guarded_output_prefix=args.guarded_output_prefix,
        guarded_status_json=guarded_status_json,
        guarded_handoff_json=guarded_handoff_json,
        guarded_handoff_markdown=guarded_handoff_markdown,
        guarded_handoff_validation_json=guarded_handoff_validation_json,
        guarded_handoff_consumer_json=guarded_handoff_consumer_json,
        guarded_ready_gate_json=guarded_ready_gate_json,
        run_browser_smoke=args.run_browser_smoke,
    )
    readiness_summary_command = (
        _build_readiness_summary_command(
            app_root,
            launch_report_json=launch_report_json,
            env_validation_json=env_validation_json_out,
            operator_packet_json=operator_packet_json,
            json_out=readiness_summary_json,
            markdown_out=readiness_summary_markdown,
        )
        if readiness_summary_json is not None
        else None
    )

    if args.dry_run:
        plan = {
            "status": "dry_run",
            "preflight_command": preflight_command,
            "compose_command": compose_command,
            "browser_smoke_command": browser_smoke_command,
            "env_validation_command": env_validation_command,
            "operator_packet_command": operator_packet_command,
            "readiness_summary_command": readiness_summary_command,
            "launch_report_json": str(launch_report_json),
            "env_validation_json": str(env_validation_json_out) if args.validate_env_file_shape else None,
            "env_validation_markdown": str(env_validation_markdown_out) if args.validate_env_file_shape else None,
            "readiness_summary_json": str(readiness_summary_json) if readiness_summary_json else None,
            "readiness_summary_markdown": str(readiness_summary_markdown) if readiness_summary_markdown else None,
            "operator_packet_json": str(operator_packet_json),
            "operator_packet_markdown": str(operator_packet_markdown),
            "operator_env_template": str(operator_env_template),
            "will_validate_env_file_shape_before_preflight": args.validate_env_file_shape,
            "env_validation_requires_single_env_file": args.validate_env_file_shape and len(env_files) != 1,
            "will_run_compose_after_preflight": True,
            "will_run_browser_smoke_after_compose": args.run_browser_smoke,
            "will_write_operator_packet_on_preflight_failure": True,
        }
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    launch_report: dict[str, object] = {
        "schema_version": 1,
        "status": "running",
        "blocker_class": None,
        "stage": "preflight",
        "app_root": str(app_root),
        "preflight_json": str(json_out),
        "env_validation_json": str(env_validation_json_out) if args.validate_env_file_shape else None,
        "env_validation_markdown": str(env_validation_markdown_out) if args.validate_env_file_shape else None,
        "readiness_summary_json": str(readiness_summary_json) if readiness_summary_json else None,
        "readiness_summary_markdown": str(readiness_summary_markdown) if readiness_summary_markdown else None,
        "operator_packet_json": str(operator_packet_json),
        "operator_packet_markdown": str(operator_packet_markdown),
        "operator_env_template": str(operator_env_template),
        "browser_smoke_json": str(browser_smoke_json_out) if args.run_browser_smoke else None,
        "browser_smoke_output_dir": str(browser_smoke_output_dir) if args.run_browser_smoke else None,
        "run_browser_smoke": args.run_browser_smoke,
        "compose_wait": args.run_browser_smoke and not args.no_compose_wait,
        "services": args.service,
        "commands": {
            "env_validation": env_validation_command,
            "preflight": preflight_command,
            "operator_packet": operator_packet_command,
            "readiness_summary": readiness_summary_command,
            "compose": compose_command,
            "browser_smoke": browser_smoke_command,
        },
        "child_reports": {
            "preflight": {"found": False, "path": str(json_out)},
            "operator_packet": {
                "found": False,
                "path": str(operator_packet_json),
                "markdown_path": str(operator_packet_markdown),
                "env_template_path": str(operator_env_template),
                "env_template_found": False,
            },
            "browser_smoke": (
                {"found": False, "path": str(browser_smoke_json_out)}
                if args.run_browser_smoke
                else None
            ),
            "readiness_summary": (
                {"found": False, "path": str(readiness_summary_json)}
                if readiness_summary_json
                else None
            ),
        },
        "results": [],
    }

    results = launch_report["results"]
    assert isinstance(results, list)
    child_reports = launch_report["child_reports"]
    assert isinstance(child_reports, dict)
    if args.validate_env_file_shape:
        child_reports["env_validation"] = {"found": False, "path": str(env_validation_json_out)}
        if env_validation_command is None:
            operator_packet_result = command_runner(operator_packet_command, cwd=app_root, text=True)
            results.append(
                _command_result(
                    name="operator_packet",
                    command=operator_packet_command,
                    completed=operator_packet_result,
                )
            )
            child_reports["operator_packet"] = _summarize_operator_packet_json(
                operator_packet_json,
                operator_packet_markdown,
                operator_env_template,
            )
            launch_report["status"] = "fail"
            launch_report["stage"] = "env_shape_validation"
            launch_report["stop_reason"] = "env_shape_validation_requires_single_env_file"
            child_reports["env_validation"] = {
                "found": False,
                "path": str(env_validation_json_out),
                "blocker_class": "env_shape_blocked",
                "error": "Provide exactly one --env-file with --validate-env-file-shape.",
            }
            _write_failed_launch_report(
                app_root=app_root,
                launch_report_json=launch_report_json,
                launch_report=launch_report,
                readiness_summary_command=readiness_summary_command,
                readiness_summary_json=readiness_summary_json,
                command_runner=command_runner,
            )
            print(
                "AgriGuard launch env shape validation requires exactly one --env-file.",
                file=sys.stderr,
            )
            return 2

        env_validation_result = command_runner(env_validation_command, cwd=app_root, text=True)
        results.append(
            _command_result(
                name="env_validation",
                command=env_validation_command,
                completed=env_validation_result,
            )
        )
        child_reports["env_validation"] = _summarize_env_validation_json(env_validation_json_out)
        if env_validation_result.returncode != 0:
            operator_packet_result = command_runner(operator_packet_command, cwd=app_root, text=True)
            results.append(
                _command_result(
                    name="operator_packet",
                    command=operator_packet_command,
                    completed=operator_packet_result,
                )
            )
            child_reports["operator_packet"] = _summarize_operator_packet_json(
                operator_packet_json,
                operator_packet_markdown,
                operator_env_template,
            )
            launch_report["status"] = "fail"
            launch_report["stage"] = "env_shape_validation"
            launch_report["stop_reason"] = "env_shape_validation_failed"
            _write_failed_launch_report(
                app_root=app_root,
                launch_report_json=launch_report_json,
                launch_report=launch_report,
                readiness_summary_command=readiness_summary_command,
                readiness_summary_json=readiness_summary_json,
                command_runner=command_runner,
            )
            print(
                "AgriGuard launch env shape validation failed; strict preflight was not run.",
                file=sys.stderr,
            )
            return env_validation_result.returncode

    preflight_result = command_runner(preflight_command, cwd=app_root, text=True)
    results.append(_command_result(name="preflight", command=preflight_command, completed=preflight_result))
    child_reports["preflight"] = _summarize_preflight_json(json_out)
    if preflight_result.returncode != 0:
        operator_packet_result = command_runner(operator_packet_command, cwd=app_root, text=True)
        results.append(
            _command_result(
                name="operator_packet",
                command=operator_packet_command,
                completed=operator_packet_result,
            )
        )
        child_reports["operator_packet"] = _summarize_operator_packet_json(
            operator_packet_json,
            operator_packet_markdown,
            operator_env_template,
        )
        launch_report["status"] = "fail"
        launch_report["stage"] = "preflight"
        launch_report["stop_reason"] = "preflight_failed"
        _write_failed_launch_report(
            app_root=app_root,
            launch_report_json=launch_report_json,
            launch_report=launch_report,
            readiness_summary_command=readiness_summary_command,
            readiness_summary_json=readiness_summary_json,
            command_runner=command_runner,
        )
        print("AgriGuard launch preflight failed; docker compose up was not run.", file=sys.stderr)
        return preflight_result.returncode

    compose_result = command_runner(
        compose_command,
        cwd=app_root,
        text=True,
        env=_compose_subprocess_env(env_files),
    )
    results.append(_command_result(name="compose", command=compose_command, completed=compose_result))
    if compose_result.returncode != 0:
        launch_report["status"] = "fail"
        launch_report["stage"] = "compose"
        launch_report["stop_reason"] = "compose_failed"
        _write_failed_launch_report(
            app_root=app_root,
            launch_report_json=launch_report_json,
            launch_report=launch_report,
            readiness_summary_command=readiness_summary_command,
            readiness_summary_json=readiness_summary_json,
            command_runner=command_runner,
        )
        return compose_result.returncode

    if browser_smoke_command is None:
        launch_report["status"] = "pass"
        launch_report["stage"] = "compose"
        launch_report["stop_reason"] = None
        _refresh_launch_blocker_class(launch_report)
        write_json(launch_report_json, launch_report)
        return compose_result.returncode

    browser_smoke_result = command_runner(browser_smoke_command, cwd=app_root, text=True)
    results.append(
        _command_result(name="browser_smoke", command=browser_smoke_command, completed=browser_smoke_result)
    )
    child_reports["browser_smoke"] = _summarize_browser_smoke_json(browser_smoke_json_out)
    launch_report["status"] = "pass" if browser_smoke_result.returncode == 0 else "fail"
    launch_report["stage"] = "browser_smoke"
    launch_report["stop_reason"] = None if browser_smoke_result.returncode == 0 else "browser_smoke_failed"
    if browser_smoke_result.returncode == 0:
        _refresh_launch_blocker_class(launch_report)
        write_json(launch_report_json, launch_report)
    else:
        _write_failed_launch_report(
            app_root=app_root,
            launch_report_json=launch_report_json,
            launch_report=launch_report,
            readiness_summary_command=readiness_summary_command,
            readiness_summary_json=readiness_summary_json,
            command_runner=command_runner,
        )
    return browser_smoke_result.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

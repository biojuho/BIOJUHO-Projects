from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "mcp_service_manifest.json"
DEFAULT_PROTOCOL_VERSION = "2025-03-26"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import mcp_service_manifest as service_manifest  # noqa: E402


def build_requests(*, protocol_version: str = DEFAULT_PROTOCOL_VERSION) -> list[dict[str, Any]]:
    return [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "workspace-mcp-service-runtime-smoke", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]


def eligible_services(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for service in payload.get("services", []):
        service_id = service.get("id", "")
        transports = set(service.get("transports", []))
        if "stdio" not in transports:
            skipped.append({"id": service_id, "reason": "stdio_transport_not_declared"})
            continue
        if service.get("language") != "python":
            skipped.append({"id": service_id, "reason": "unsupported_language_for_runtime_smoke"})
            continue
        selected.append(service)
    return selected, skipped


def build_pythonpath(env: dict[str, str] | None = None) -> str:
    env_map = env or os.environ
    candidates = [
        WORKSPACE_ROOT,
        WORKSPACE_ROOT / "packages",
        WORKSPACE_ROOT / "automation",
        WORKSPACE_ROOT / "automation" / "DailyNews" / "src",
        WORKSPACE_ROOT / "automation" / "DailyNews" / "scripts",
        WORKSPACE_ROOT / "apps" / "desci-platform",
    ]
    entries = [str(path) for path in candidates if path.exists()]
    if env_map.get("PYTHONPATH"):
        entries.append(env_map["PYTHONPATH"])
    return os.pathsep.join(entries)


def resolve_python_executable() -> str:
    venv_rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    candidates = [
        WORKSPACE_ROOT / ".venv" / venv_rel,
        WORKSPACE_ROOT / "venv" / venv_rel,
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def runtime_command(service: dict[str, Any], *, python_exe: str) -> list[str]:
    command = list(service["command"])
    if command and command[0].lower() in {"python", "python.exe"}:
        command[0] = python_exe
    return command


def run_service_smoke(
    service: dict[str, Any],
    *,
    timeout_seconds: float = 20.0,
    protocol_version: str = DEFAULT_PROTOCOL_VERSION,
    python_exe: str | None = None,
) -> dict[str, Any]:
    python_exe = python_exe or resolve_python_executable()
    command = runtime_command(service, python_exe=python_exe)
    env = os.environ.copy()
    env["PYTHONPATH"] = build_pythonpath(env)
    requests = build_requests(protocol_version=protocol_version)
    payload = "".join(json.dumps(request, separators=(",", ":")) + "\n" for request in requests)
    service_cwd = WORKSPACE_ROOT / service["cwd"]
    try:
        process = subprocess.run(
            command,
            cwd=service_cwd,
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            env=env,
        )
        return build_service_result(service, command, process)
    except subprocess.TimeoutExpired as exc:
        return build_failed_service_result(
            service,
            command,
            f"runtime timed out after {timeout_seconds}s",
            stderr_tail=tail_text(exc.stderr or ""),
        )
    except OSError as exc:
        return build_failed_service_result(service, command, f"runtime launch failed: {exc}")


def build_failed_service_result(
    service: dict[str, Any],
    command: list[str],
    error: str,
    *,
    stderr_tail: str = "",
) -> dict[str, Any]:
    return {
        "id": service["id"],
        "name": service["name"],
        "status": "fail",
        "command": format_command(command),
        "cwd": service["cwd"],
        "transport": "stdio",
        "expected_min_tools": service.get("expected_min_tools", 0),
        "expected_tools": sorted(service.get("expected_tools", [])),
        "tool_count": 0,
        "tools": [],
        "missing_expected_tools": sorted(service.get("expected_tools", [])),
        "long_running_tool_count": 0,
        "long_running_tools": [],
        "task_capability_advertised": False,
        "server_name": "",
        "server_version": "",
        "capability_keys": [],
        "required_env": service.get("required_env", []),
        "missing_env": missing_env(service),
        "stderr_tail": stderr_tail,
        "errors": [error],
    }


def build_service_result(
    service: dict[str, Any],
    command: list[str],
    process: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    responses = parse_responses(process.stdout)
    errors = validate_responses(service, responses, process.returncode)
    initialize = result_for_id(responses, 1)
    tools_result = result_for_id(responses, 2)
    tools = tools_from_result(tools_result)
    tool_names = sorted(tool["name"] for tool in tools)
    expected_tools = sorted(service.get("expected_tools", []))
    missing_expected_tools = sorted(set(expected_tools) - set(tool_names))
    long_running_tools = long_running_tool_names(tools)
    server_info = initialize.get("serverInfo", {}) if isinstance(initialize.get("serverInfo"), dict) else {}
    capabilities = initialize.get("capabilities", {}) if isinstance(initialize.get("capabilities"), dict) else {}
    task_capability_advertised = "tasks" in capabilities
    return {
        "id": service["id"],
        "name": service["name"],
        "status": "pass" if not errors else "fail",
        "command": format_command(command),
        "cwd": service["cwd"],
        "transport": "stdio",
        "expected_min_tools": service.get("expected_min_tools", 0),
        "expected_tools": expected_tools,
        "tool_count": len(tools),
        "tools": tool_names,
        "missing_expected_tools": missing_expected_tools,
        "long_running_tool_count": len(long_running_tools),
        "long_running_tools": long_running_tools,
        "task_capability_advertised": task_capability_advertised,
        "server_name": server_info.get("name", ""),
        "server_version": server_info.get("version", ""),
        "capability_keys": sorted(capabilities),
        "required_env": service.get("required_env", []),
        "missing_env": missing_env(service),
        "stderr_tail": tail_text(process.stderr),
        "errors": errors,
    }


def validate_responses(service: dict[str, Any], responses: list[dict[str, Any]], returncode: int) -> list[str]:
    errors: list[str] = []
    if returncode != 0:
        errors.append(f"runtime exited with return code {returncode}")
    initialize = result_for_id(responses, 1)
    if not initialize:
        errors.append("missing initialize response")
    elif "serverInfo" not in initialize:
        errors.append("initialize response missing serverInfo")
    capabilities = initialize.get("capabilities", {}) if isinstance(initialize.get("capabilities"), dict) else {}
    if "tools" not in capabilities:
        errors.append("initialize response must advertise tools capability")

    tools_result = result_for_id(responses, 2)
    tools = tools_from_result(tools_result)
    if not tools_result:
        errors.append("missing tools/list response")
    elif "tools" not in tools_result:
        errors.append("tools/list response missing tools")
    expected_min_tools = service.get("expected_min_tools", 0)
    if len(tools) < expected_min_tools:
        errors.append(f"expected at least {expected_min_tools} tools, got {len(tools)}")
    expected_tools = sorted(service.get("expected_tools", []))
    if expected_tools:
        tool_names = {tool["name"] for tool in tools}
        missing_expected_tools = sorted(set(expected_tools) - tool_names)
        if missing_expected_tools:
            errors.append(f"missing expected tools: {', '.join(missing_expected_tools)}")
    long_running_tools = long_running_tool_names(tools)
    if long_running_tools and "tasks" not in capabilities:
        errors.append(
            "long-running MCP tools require tasks capability: "
            + ", ".join(long_running_tools)
        )
    return errors


def run(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    timeout_seconds: float = 20.0,
    protocol_version: str = DEFAULT_PROTOCOL_VERSION,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict[str, Any]:
    payload = service_manifest.load_manifest(manifest_path)
    manifest_errors = service_manifest.validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    selected, skipped = eligible_services(payload)
    service_results = [
        run_service_smoke(
            service,
            timeout_seconds=timeout_seconds,
            protocol_version=protocol_version,
            python_exe=resolve_python_executable(),
        )
        for service in selected
    ]
    report = build_report(payload, service_results, skipped, manifest_errors=manifest_errors)
    if json_out:
        write_json_atomic(json_out, report)
    if markdown_out:
        write_text_atomic(markdown_out, render_markdown(report))
    if report["status"] != "pass":
        raise ValueError("\n".join(report["errors"]))
    return report


def build_report(
    manifest_payload: dict[str, Any],
    service_results: list[dict[str, Any]],
    skipped_services: list[dict[str, Any]],
    *,
    manifest_errors: list[str] | None = None,
) -> dict[str, Any]:
    manifest_errors = manifest_errors or []
    service_errors = [
        f"{service['id']}: {error}"
        for service in service_results
        for error in service.get("errors", [])
    ]
    status_counts = Counter(service["status"] for service in service_results)
    missing_env_count = sum(1 for service in service_results if service.get("missing_env"))
    task_capable_count = sum(1 for service in service_results if service.get("task_capability_advertised"))
    errors = [*manifest_errors, *service_errors]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass" if not errors else "fail",
        "manifest_generated_at": manifest_payload.get("generated_at"),
        "summary": {
            "total_manifest_services": len(manifest_payload.get("services", [])),
            "checked_services": len(service_results),
            "skipped_services": len(skipped_services),
            "passed_services": status_counts.get("pass", 0),
            "failed_services": status_counts.get("fail", 0),
            "credential_gated_checked_services": missing_env_count,
            "total_tools_listed": sum(service.get("tool_count", 0) for service in service_results),
            "task_capable_services": task_capable_count,
            "long_running_tools_listed": sum(
                service.get("long_running_tool_count", 0) for service in service_results
            ),
        },
        "services": service_results,
        "skipped_services": skipped_services,
        "errors": errors,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# MCP Service Runtime Smoke",
        "",
        f"- Status: `{report['status']}`",
        f"- Manifest generated at: `{report['manifest_generated_at']}`",
        f"- Checked services: `{summary['checked_services']}`",
        f"- Skipped services: `{summary['skipped_services']}`",
        f"- Passed services: `{summary['passed_services']}`",
        f"- Failed services: `{summary['failed_services']}`",
        f"- Credential-gated checked services: `{summary['credential_gated_checked_services']}`",
        f"- Total tools listed: `{summary['total_tools_listed']}`",
        f"- Task-capable services: `{summary.get('task_capable_services', 0)}`",
        f"- Long-running tools listed: `{summary.get('long_running_tools_listed', 0)}`",
        "",
        "## Services",
        "",
    ]
    for service in report["services"]:
        missing_env = ", ".join(service["missing_env"]) if service["missing_env"] else "none"
        expected_tools = service.get("expected_tools", [])
        missing_expected_tools = service.get("missing_expected_tools", [])
        long_running_tools = service.get("long_running_tools", [])
        lines.extend(
            [
                f"### {service['id']}",
                "",
                f"- Status: `{service['status']}`",
                f"- Server: `{service['server_name']}` / `{service['server_version']}`",
                f"- Command: `{service['command']}`",
                f"- Tools listed: `{service['tool_count']}`",
                f"- Expected minimum tools: `{service['expected_min_tools']}`",
                f"- Expected runtime tools: `{', '.join(expected_tools) if expected_tools else 'none'}`",
                f"- Missing expected tools: `{', '.join(missing_expected_tools) if missing_expected_tools else 'none'}`",
                f"- Task capability advertised: `{str(service.get('task_capability_advertised', False)).lower()}`",
                f"- Long-running tools: `{', '.join(long_running_tools) if long_running_tools else 'none'}`",
                f"- Missing env for tool calls: `{missing_env}`",
                f"- Capability keys: `{', '.join(service['capability_keys'])}`",
                "",
            ]
        )
    if report["skipped_services"]:
        lines.extend(["## Skipped Services", ""])
        for service in report["skipped_services"]:
            lines.append(f"- `{service['id']}`: `{service['reason']}`")
        lines.append("")
    lines.extend(["## Errors", ""])
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def parse_responses(stdout: str) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            responses.append(payload)
    return responses


def result_for_id(responses: list[dict[str, Any]], response_id: int) -> dict[str, Any]:
    for response in responses:
        if response.get("id") == response_id:
            result = response.get("result")
            return result if isinstance(result, dict) else {}
    return {}


def tools_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    tools = result.get("tools", [])
    if not isinstance(tools, list):
        return []
    return [tool for tool in tools if isinstance(tool, dict) and isinstance(tool.get("name"), str)]


def long_running_tool_names(tools: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for tool in tools:
        execution = tool.get("execution")
        if not isinstance(execution, dict):
            continue
        if execution.get("taskSupport") == "required":
            names.append(tool["name"])
    return sorted(names)


def missing_env(service: dict[str, Any]) -> list[str]:
    return [name for name in service.get("required_env", []) if not os.environ.get(name)]


def format_command(command: list[str]) -> str:
    return " ".join(f'"{part}"' if any(ch.isspace() for ch in part) else part for part in command)


def tail_text(text: str, *, line_count: int = 12) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-line_count:])


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test stdio MCP services from the repo-local service manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--protocol-version", default=DEFAULT_PROTOCOL_VERSION)
    args = parser.parse_args(argv)
    try:
        report = run(
            args.manifest,
            timeout_seconds=args.timeout,
            protocol_version=args.protocol_version,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"mcp service runtime smoke failed: {exc}", file=sys.stderr)
        return 1
    print(
        "mcp service runtime smoke valid: "
        f"{report['summary']['checked_services']} checked, "
        f"{report['summary']['passed_services']} passed, "
        f"{report['summary']['total_tools_listed']} tools"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

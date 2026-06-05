#!/usr/bin/env python3
"""Run a live mcpo smoke for the Canva MCP stdio server."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
CANVA_MCP_ROOT = WORKSPACE_ROOT / "mcp" / "canva-mcp"
DEFAULT_API_KEY_ENV = "CANVA_MCP_PROXY_API_KEY"
DEFAULT_REQUIRED_PATHS = ("/auth-status", "/generate-design", "/search-designs")


def run_live_smoke(
    *,
    canva_root: Path = CANVA_MCP_ROOT,
    api_key: str,
    host: str = "127.0.0.1",
    port: int | None = None,
    build: bool = True,
    timeout_seconds: float = 60.0,
    required_paths: tuple[str, ...] = DEFAULT_REQUIRED_PATHS,
) -> dict[str, Any]:
    port = port or find_free_port(host)
    build_result = run_build(canva_root) if build else _skipped_check("build", "build skipped by caller")
    checks = [build_result]
    process_result: dict[str, Any] | None = None
    stdout_tail = ""
    stderr_tail = ""
    if build_result["ok"]:
        command = proxy_command(host=host, port=port, api_key=api_key)
        process = subprocess.Popen(
            command,
            cwd=canva_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            process_result = probe_proxy(
                base_url=f"http://{host}:{port}",
                api_key=api_key,
                process=process,
                timeout_seconds=timeout_seconds,
                required_paths=required_paths,
            )
            checks.extend(process_result["checks"])
        finally:
            stdout_tail, stderr_tail = stop_process_tree(process)
    ok = all(check["ok"] for check in checks)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service": "canva-mcp",
        "source_pattern": "open-webui/mcpo live MCP-to-OpenAPI proxy smoke with strict Bearer auth.",
        "ok": ok,
        "host": host,
        "port": port,
        "api_key_env": DEFAULT_API_KEY_ENV,
        "auth_header": "Authorization: Bearer <redacted>",
        "commands": {
            "build_cwd": "mcp/canva-mcp",
            "build": "npm run build:server",
            "proxy_cwd": "mcp/canva-mcp",
            "proxy": f"uvx mcpo --host {host} --port {port} --api-key <redacted> --strict-auth -- node dist/server/stdio.js",
        },
        "summary": {
            "checks": len(checks),
            "passed": sum(1 for check in checks if check["ok"]),
            "failed": sum(1 for check in checks if not check["ok"]),
            "openapi_path_count": process_result.get("openapi_path_count") if process_result else None,
        },
        "checks": checks,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }


def run_build(canva_root: Path) -> dict[str, Any]:
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    completed = subprocess.run(
        [npm, "run", "build:server"],
        cwd=canva_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "name": "build",
        "ok": completed.returncode == 0,
        "detail": "npm run build:server",
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def proxy_command(*, host: str, port: int, api_key: str) -> list[str]:
    return [
        "uvx",
        "mcpo",
        "--host",
        host,
        "--port",
        str(port),
        "--api-key",
        api_key,
        "--strict-auth",
        "--",
        "node",
        "dist/server/stdio.js",
    ]


def probe_proxy(
    *,
    base_url: str,
    api_key: str,
    process: subprocess.Popen[str] | None = None,
    timeout_seconds: float = 60.0,
    required_paths: tuple[str, ...] = DEFAULT_REQUIRED_PATHS,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    openapi_payload, openapi_error = _wait_for_openapi(
        base_url=base_url,
        api_key=api_key,
        process=process,
        timeout_seconds=timeout_seconds,
    )
    checks.append(
        {
            "name": "authenticated-openapi",
            "ok": openapi_error is None,
            "detail": openapi_error or f"{base_url}/openapi.json returned JSON",
        }
    )
    docs_status, docs_error = _fetch_status(base_url + "/docs", api_key=api_key)
    checks.append(
        {
            "name": "authenticated-docs",
            "ok": docs_status == 200,
            "detail": docs_error or f"{base_url}/docs returned {docs_status}",
        }
    )
    unauth_status, unauth_error = _fetch_status(base_url + "/openapi.json", api_key=None)
    checks.append(
        {
            "name": "unauthenticated-openapi-rejected",
            "ok": unauth_status == 401,
            "detail": unauth_error or f"{base_url}/openapi.json returned {unauth_status} without auth",
        }
    )
    paths = openapi_payload.get("paths", {}) if isinstance(openapi_payload, dict) else {}
    missing_paths = sorted(path for path in required_paths if path not in paths)
    checks.append(
        {
            "name": "required-openapi-paths",
            "ok": not missing_paths,
            "detail": "required paths present" if not missing_paths else f"missing: {', '.join(missing_paths)}",
        }
    )
    return {
        "ok": all(check["ok"] for check in checks),
        "openapi_path_count": len(paths),
        "checks": checks,
    }


def find_free_port(host: str) -> int:
    with socket.socket() as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def stop_process_tree(process: subprocess.Popen[str]) -> tuple[str, str]:
    descendant_pids = windows_descendant_pids(process.pid) if os.name == "nt" else []
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            process.terminate()
    for pid in descendant_pids:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    try:
        stdout, stderr = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=10)
    return _tail(stdout), _tail(stderr)


def windows_descendant_pids(root_pid: int) -> list[int]:
    command = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId | "
        "ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        rows = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return []
    return descendant_pids_from_rows(root_pid, rows)


def descendant_pids_from_rows(root_pid: int, rows: list[dict[str, Any]]) -> list[int]:
    children_by_parent: dict[int, list[int]] = {}
    for row in rows:
        try:
            pid = int(row["ProcessId"])
            parent_pid = int(row["ParentProcessId"])
        except (KeyError, TypeError, ValueError):
            continue
        children_by_parent.setdefault(parent_pid, []).append(pid)

    descendants: list[int] = []
    stack = list(children_by_parent.get(root_pid, []))
    while stack:
        pid = stack.pop()
        descendants.append(pid)
        stack.extend(children_by_parent.get(pid, []))
    return descendants


def format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Canva MCP Proxy Live Smoke",
        "",
        "## Summary",
        "",
        f"- Service: `{result['service']}`",
        f"- OK: `{str(result['ok']).lower()}`",
        f"- Host: `{result['host']}`",
        f"- Port: `{result['port']}`",
        f"- Checks: {result['summary']['passed']}/{result['summary']['checks']} passed",
        f"- OpenAPI path count: {result['summary']['openapi_path_count']}",
        f"- Auth header: `{result['auth_header']}`",
        f"- Generated at: `{result['generated_at']}`",
        "",
        "## Commands",
        "",
        f"- Build cwd: `{result['commands']['build_cwd']}`",
        f"- Build: `{result['commands']['build']}`",
        f"- Proxy cwd: `{result['commands']['proxy_cwd']}`",
        f"- Proxy: `{result['commands']['proxy']}`",
        "",
        "## Checks",
        "",
        "| Check | OK | Detail |",
        "| --- | --- | --- |",
    ]
    for check in result["checks"]:
        lines.append(
            f"| {_markdown_cell(check['name'])} | {str(check['ok']).lower()} | {_markdown_cell(check['detail'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_json(result: dict[str, Any], path: Path | None) -> None:
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if path is None:
        print(rendered, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def write_markdown(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_markdown(result), encoding="utf-8")


def _wait_for_openapi(
    *,
    base_url: str,
    api_key: str,
    process: subprocess.Popen[str] | None,
    timeout_seconds: float,
) -> tuple[dict[str, Any], str | None]:
    deadline = time.time() + timeout_seconds
    last_error = "proxy did not respond"
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            return {}, f"proxy exited with returncode {process.returncode}: {last_error}"
        payload, error = _fetch_json(base_url + "/openapi.json", api_key=api_key)
        if error is None:
            return payload, None
        last_error = error
        time.sleep(1)
    return {}, f"timed out waiting for openapi: {last_error}"


def _fetch_json(url: str, *, api_key: str | None) -> tuple[dict[str, Any], str | None]:
    status, error, body = _fetch(url, api_key=api_key)
    if status != 200:
        return {}, error or f"{url} returned {status}"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON from {url}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"JSON root from {url} is not an object"
    return payload, None


def _fetch_status(url: str, *, api_key: str | None) -> tuple[int | None, str | None]:
    status, error, _body = _fetch(url, api_key=api_key)
    return status, error


def _fetch(url: str, *, api_key: str | None) -> tuple[int | None, str | None, str]:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return int(response.status), None, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), None, exc.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return None, str(exc), ""


def _skipped_check(name: str, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": True, "detail": detail, "returncode": None}


def _tail(text: str, limit: int = 2000) -> str:
    return text[-limit:] if text else ""


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a live Canva MCP mcpo smoke.")
    parser.add_argument("--canva-root", type=Path, default=CANVA_MCP_ROOT)
    parser.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--allow-fail", action="store_true")
    args = parser.parse_args(argv)

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"{args.api_key_env} is required for live proxy smoke", file=sys.stderr)
        return 2

    result = run_live_smoke(
        canva_root=args.canva_root,
        api_key=api_key,
        host=args.host,
        port=args.port,
        build=not args.skip_build,
        timeout_seconds=args.timeout_seconds,
    )
    if args.markdown_out:
        write_markdown(result, args.markdown_out)
    write_json(result, args.json_out)
    return 0 if result["ok"] or args.allow_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())

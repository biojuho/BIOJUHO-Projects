#!/usr/bin/env python3
"""Validate local prerequisites for a mcpo-style Canva MCP proxy."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from canva_mcp_openapi_contract import extract_tools, load_tools_source  # noqa: E402

DEFAULT_TOOLS_SOURCE = WORKSPACE_ROOT / "mcp" / "canva-mcp" / "src" / "server" / "tools.ts"
DEFAULT_STDIO_SOURCE = WORKSPACE_ROOT / "mcp" / "canva-mcp" / "src" / "server" / "stdio.ts"
DEFAULT_DIST_STDIO = WORKSPACE_ROOT / "mcp" / "canva-mcp" / "dist" / "server" / "stdio.js"
DEFAULT_OPENAPI_CONTRACT = (
    WORKSPACE_ROOT / "docs" / "reports" / "2026-06" / "CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.json"
)
DEFAULT_API_KEY_ENV = "CANVA_MCP_PROXY_API_KEY"


def build_readiness(
    *,
    tools_source: Path = DEFAULT_TOOLS_SOURCE,
    stdio_source: Path = DEFAULT_STDIO_SOURCE,
    dist_stdio: Path = DEFAULT_DIST_STDIO,
    openapi_contract: Path = DEFAULT_OPENAPI_CONTRACT,
    api_key_env: str = DEFAULT_API_KEY_ENV,
    port: int = 8000,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    contract_payload, contract_error = _load_json(openapi_contract)
    tools, tools_error = _load_tools(tools_source)

    source_tool_paths = {f"/{tool['name']}" for tool in tools}
    contract_paths = set(contract_payload.get("paths", {})) if isinstance(contract_payload, dict) else set()
    missing_contract_paths = sorted(source_tool_paths - contract_paths)
    extra_contract_paths = sorted(contract_paths - source_tool_paths)
    checks = [
        _file_check("tools-source", tools_source, extra_detail=tools_error),
        _file_check("stdio-source", stdio_source),
        _file_check("dist-stdio", dist_stdio),
        _file_check("openapi-contract", openapi_contract, extra_detail=contract_error),
        {
            "name": "api-key-env",
            "ok": bool(os.environ.get(api_key_env)),
            "detail": f"{api_key_env} is configured" if os.environ.get(api_key_env) else f"{api_key_env} is not set",
        },
        {
            "name": "contract-api-key-security",
            "ok": _has_api_key_security(contract_payload),
            "detail": "OpenAPI contract defines X-API-Key security",
        },
        {
            "name": "contract-tool-sync",
            "ok": not tools_error and not contract_error and not missing_contract_paths and not extra_contract_paths,
            "detail": _contract_sync_detail(missing_contract_paths, extra_contract_paths),
        },
    ]
    ok = all(check["ok"] for check in checks)
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "service": "canva-mcp",
        "source_pattern": "open-webui/mcpo MCP-to-OpenAPI proxy with API-key protected docs.",
        "readiness": {
            "ok": ok,
            "checks": checks,
        },
        "commands": {
            "build_cwd": "mcp/canva-mcp",
            "build": "npm run build:server",
            "proxy_cwd": "mcp/canva-mcp",
            "proxy": f"uvx mcpo --port {port} --api-key <{api_key_env}> -- node dist/server/stdio.js",
            "docs_url": f"http://localhost:{port}/docs",
            "openapi_url": f"http://localhost:{port}/openapi.json",
        },
        "tool_count": len(source_tool_paths),
        "openapi_path_count": len(contract_paths),
    }


def format_markdown(readiness: dict[str, Any]) -> str:
    lines = [
        "# Canva MCP Proxy Readiness",
        "",
        "## Summary",
        "",
        f"- Service: `{readiness['service']}`",
        f"- Ready: `{str(readiness['readiness']['ok']).lower()}`",
        f"- Tool count: {readiness['tool_count']}",
        f"- OpenAPI path count: {readiness['openapi_path_count']}",
        f"- Generated at: `{readiness['generated_at']}`",
        "",
        "## Commands",
        "",
        f"- Build cwd: `{readiness['commands']['build_cwd']}`",
        f"- Build: `{readiness['commands']['build']}`",
        f"- Proxy cwd: `{readiness['commands']['proxy_cwd']}`",
        f"- Proxy: `{readiness['commands']['proxy']}`",
        f"- Docs: `{readiness['commands']['docs_url']}`",
        f"- OpenAPI: `{readiness['commands']['openapi_url']}`",
        "",
        "## Checks",
        "",
        "| Check | OK | Detail |",
        "| --- | --- | --- |",
    ]
    for check in readiness["readiness"]["checks"]:
        lines.append(
            f"| {_markdown_cell(check['name'])} | {str(check['ok']).lower()} | {_markdown_cell(check['detail'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_json(payload: dict[str, Any], path: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if path is None:
        print(rendered, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_markdown(payload), encoding="utf-8")


def _load_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, str(exc)
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return {}, "JSON root is not an object"
    return payload, None


def _load_tools(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return extract_tools(load_tools_source(path)), None
    except (OSError, ValueError) as exc:
        return [], str(exc)


def _file_check(name: str, path: Path, *, extra_detail: str | None = None) -> dict[str, Any]:
    exists = path.is_file()
    detail = str(path.relative_to(WORKSPACE_ROOT) if _is_relative_to(path, WORKSPACE_ROOT) else path)
    if extra_detail:
        detail = f"{detail}: {extra_detail}"
    return {"name": name, "ok": exists and not extra_detail, "detail": detail}


def _has_api_key_security(contract_payload: dict[str, Any]) -> bool:
    schemes = contract_payload.get("components", {}).get("securitySchemes", {})
    api_key = schemes.get("ApiKeyAuth")
    return (
        isinstance(api_key, dict)
        and api_key.get("type") == "apiKey"
        and api_key.get("in") == "header"
        and api_key.get("name") == "X-API-Key"
    )


def _contract_sync_detail(missing_paths: list[str], extra_paths: list[str]) -> str:
    if not missing_paths and not extra_paths:
        return "OpenAPI paths match tools.ts"
    details: list[str] = []
    if missing_paths:
        details.append(f"missing: {', '.join(missing_paths)}")
    if extra_paths:
        details.append(f"extra: {', '.join(extra_paths)}")
    return "; ".join(details)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Canva MCP mcpo-style proxy readiness.")
    parser.add_argument("--tools-source", type=Path, default=DEFAULT_TOOLS_SOURCE)
    parser.add_argument("--stdio-source", type=Path, default=DEFAULT_STDIO_SOURCE)
    parser.add_argument("--dist-stdio", type=Path, default=DEFAULT_DIST_STDIO)
    parser.add_argument("--openapi-contract", type=Path, default=DEFAULT_OPENAPI_CONTRACT)
    parser.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--allow-not-ready", action="store_true")
    args = parser.parse_args(argv)

    readiness = build_readiness(
        tools_source=args.tools_source,
        stdio_source=args.stdio_source,
        dist_stdio=args.dist_stdio,
        openapi_contract=args.openapi_contract,
        api_key_env=args.api_key_env,
        port=args.port,
    )
    if args.markdown_out:
        write_markdown(readiness, args.markdown_out)
    write_json(readiness, args.json_out)
    return 0 if readiness["readiness"]["ok"] or args.allow_not_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())

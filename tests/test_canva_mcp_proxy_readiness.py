from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "canva_mcp_proxy_readiness.py"


def load_readiness_module():
    spec = importlib.util.spec_from_file_location("canva_mcp_proxy_readiness", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_fixture(tmp_path: Path, *, stale_contract: bool = False, api_key_security: bool = True) -> dict[str, Path]:
    tools_source = tmp_path / "src" / "server" / "tools.ts"
    stdio_source = tmp_path / "src" / "server" / "stdio.ts"
    dist_stdio = tmp_path / "dist" / "server" / "stdio.js"
    contract_path = tmp_path / "contract.json"
    tools_source.parent.mkdir(parents=True)
    dist_stdio.parent.mkdir(parents=True)
    tools_source.write_text(
        """
        export const tools: Tool[] = [
          {
            name: "auth-status",
            description: "Check Canva authentication status.",
            inputSchema: AuthStatusSchema,
            annotations: { readOnlyHint: true },
          },
          {
            name: "generate-design",
            description: "Generate a Canva design.",
            inputSchema: GenerateDesignSchema,
          },
        ];
        """,
        encoding="utf-8",
    )
    stdio_source.write_text("export async function main() {}\n", encoding="utf-8")
    dist_stdio.write_text("console.log('stdio');\n", encoding="utf-8")
    security_schemes = {}
    if api_key_security:
        security_schemes["ApiKeyAuth"] = {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    paths = {"/auth-status": {"post": {}}, "/generate-design": {"post": {}}}
    if stale_contract:
        paths = {"/auth-status": {"post": {}}, "/stale-tool": {"post": {}}}
    contract_path.write_text(
        json.dumps({"openapi": "3.1.0", "paths": paths, "components": {"securitySchemes": security_schemes}}),
        encoding="utf-8",
    )
    return {
        "tools_source": tools_source,
        "stdio_source": stdio_source,
        "dist_stdio": dist_stdio,
        "contract_path": contract_path,
    }


def test_build_readiness_accepts_matching_contract_and_api_key(tmp_path: Path, monkeypatch) -> None:
    readiness_module = load_readiness_module()
    paths = write_fixture(tmp_path)
    monkeypatch.setenv("CANVA_MCP_PROXY_API_KEY", "local-test-key")

    readiness = readiness_module.build_readiness(
        tools_source=paths["tools_source"],
        stdio_source=paths["stdio_source"],
        dist_stdio=paths["dist_stdio"],
        openapi_contract=paths["contract_path"],
        port=8910,
    )

    assert readiness["readiness"]["ok"] is True
    assert readiness["tool_count"] == 2
    assert readiness["openapi_path_count"] == 2
    assert readiness["commands"]["proxy"] == (
        "uvx mcpo --port 8910 --api-key <CANVA_MCP_PROXY_API_KEY> -- node dist/server/stdio.js"
    )
    assert {check["name"]: check["ok"] for check in readiness["readiness"]["checks"]} == {
        "tools-source": True,
        "stdio-source": True,
        "dist-stdio": True,
        "openapi-contract": True,
        "api-key-env": True,
        "contract-api-key-security": True,
        "contract-tool-sync": True,
    }


def test_build_readiness_reports_stale_contract_and_missing_api_key(tmp_path: Path, monkeypatch) -> None:
    readiness_module = load_readiness_module()
    paths = write_fixture(tmp_path, stale_contract=True, api_key_security=False)
    monkeypatch.delenv("CANVA_MCP_PROXY_API_KEY", raising=False)

    readiness = readiness_module.build_readiness(
        tools_source=paths["tools_source"],
        stdio_source=paths["stdio_source"],
        dist_stdio=paths["dist_stdio"],
        openapi_contract=paths["contract_path"],
    )

    checks = {check["name"]: check for check in readiness["readiness"]["checks"]}
    assert readiness["readiness"]["ok"] is False
    assert checks["api-key-env"]["ok"] is False
    assert checks["contract-api-key-security"]["ok"] is False
    assert checks["contract-tool-sync"]["ok"] is False
    assert "missing: /generate-design" in checks["contract-tool-sync"]["detail"]
    assert "extra: /stale-tool" in checks["contract-tool-sync"]["detail"]


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = write_fixture(tmp_path)
    json_out = tmp_path / "readiness.json"
    markdown_out = tmp_path / "readiness.md"
    env = os.environ.copy()
    env["CANVA_MCP_PROXY_API_KEY"] = "local-test-key"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--tools-source",
            str(paths["tools_source"]),
            "--stdio-source",
            str(paths["stdio_source"]),
            "--dist-stdio",
            str(paths["dist_stdio"]),
            "--openapi-contract",
            str(paths["contract_path"]),
            "--port",
            "8910",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["readiness"]["ok"] is True
    report = markdown_out.read_text(encoding="utf-8")
    assert "# Canva MCP Proxy Readiness" in report
    assert "- Ready: `true`" in report
    assert "uvx mcpo --port 8910 --api-key <CANVA_MCP_PROXY_API_KEY> -- node dist/server/stdio.js" in report

from __future__ import annotations

import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "canva_mcp_proxy_live_smoke.py"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("canva_mcp_proxy_live_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeMcpoHandler(BaseHTTPRequestHandler):
    api_key = "test-key"
    paths = {"/auth-status": {"post": {}}, "/generate-design": {"post": {}}, "/search-designs": {"post": {}}}

    def do_GET(self) -> None:  # noqa: N802
        if self.headers.get("Authorization") != f"Bearer {self.api_key}":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"detail":"Unauthorized"}')
            return
        if self.path == "/openapi.json":
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"openapi": "3.1.0", "paths": self.paths}).encode("utf-8"))
            return
        if self.path == "/docs":
            self.send_response(200)
            self.send_header("content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"docs")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def serve_fake_mcpo(paths: dict[str, dict] | None = None):
    handler = type("CustomFakeMcpoHandler", (FakeMcpoHandler,), {})
    if paths is not None:
        handler.paths = paths
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_probe_proxy_accepts_bearer_auth_and_rejects_unauthenticated() -> None:
    smoke_module = load_smoke_module()
    server, base_url = serve_fake_mcpo()
    try:
        result = smoke_module.probe_proxy(base_url=base_url, api_key="test-key", timeout_seconds=1)
    finally:
        server.shutdown()

    assert result["ok"] is True
    assert result["openapi_path_count"] == 3
    assert {check["name"]: check["ok"] for check in result["checks"]} == {
        "authenticated-openapi": True,
        "authenticated-docs": True,
        "unauthenticated-openapi-rejected": True,
        "required-openapi-paths": True,
    }


def test_probe_proxy_reports_missing_required_paths() -> None:
    smoke_module = load_smoke_module()
    server, base_url = serve_fake_mcpo(paths={"/auth-status": {"post": {}}})
    try:
        result = smoke_module.probe_proxy(base_url=base_url, api_key="test-key", timeout_seconds=1)
    finally:
        server.shutdown()

    checks = {check["name"]: check for check in result["checks"]}
    assert result["ok"] is False
    assert checks["required-openapi-paths"]["ok"] is False
    assert "missing: /generate-design, /search-designs" in checks["required-openapi-paths"]["detail"]


def test_format_markdown_redacts_api_key_and_summarizes_checks() -> None:
    smoke_module = load_smoke_module()
    result = {
        "service": "canva-mcp",
        "ok": True,
        "host": "127.0.0.1",
        "port": 8123,
        "summary": {"passed": 4, "checks": 4, "openapi_path_count": 22},
        "auth_header": "Authorization: Bearer <redacted>",
        "generated_at": "2026-06-05T00:00:00+00:00",
        "commands": {
            "build_cwd": "mcp/canva-mcp",
            "build": "npm run build:server",
            "proxy_cwd": "mcp/canva-mcp",
            "proxy": "uvx mcpo --host 127.0.0.1 --port 8123 --api-key <redacted> --strict-auth -- node dist/server/stdio.js",
        },
        "checks": [{"name": "authenticated-openapi", "ok": True, "detail": "ok"}],
    }

    report = smoke_module.format_markdown(result)

    assert "# Canva MCP Proxy Live Smoke" in report
    assert "- OK: `true`" in report
    assert "- Checks: 4/4 passed" in report
    assert "<redacted>" in report
    assert "test-key" not in report


def test_descendant_pids_from_rows_returns_nested_children() -> None:
    smoke_module = load_smoke_module()
    rows = [
        {"ProcessId": 10, "ParentProcessId": 1},
        {"ProcessId": 11, "ParentProcessId": 10},
        {"ProcessId": 12, "ParentProcessId": 11},
        {"ProcessId": 20, "ParentProcessId": 1},
        {"ProcessId": "bad", "ParentProcessId": 12},
    ]

    assert set(smoke_module.descendant_pids_from_rows(10, rows)) == {11, 12}

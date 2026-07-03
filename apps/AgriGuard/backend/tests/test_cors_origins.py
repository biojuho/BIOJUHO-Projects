from __future__ import annotations

import json
import re
from pathlib import Path

import main

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
AGRIGUARD_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
}


def test_default_allowed_origins_include_manifest_dev_frontend_port() -> None:
    origins = set(main.DEFAULT_ALLOWED_ORIGINS.split(","))

    assert AGRIGUARD_ORIGINS.issubset(origins)


def test_env_examples_include_current_dev_frontend_origins() -> None:
    for relative_path in [
        "apps/AgriGuard/.env.example",
        "apps/AgriGuard/backend/.env.example",
    ]:
        text = (WORKSPACE_ROOT / relative_path).read_text(encoding="utf-8")

        for origin in AGRIGUARD_ORIGINS:
            assert origin in text


def test_compose_services_pass_current_dev_frontend_origins() -> None:
    for relative_path in [
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "apps/AgriGuard/docker-compose.yml",
    ]:
        text = (WORKSPACE_ROOT / relative_path).read_text(encoding="utf-8")

        assert "ALLOWED_ORIGINS" in text
        for origin in AGRIGUARD_ORIGINS:
            assert origin in text


def test_backend_dockerfile_uses_existing_dependency_manifest() -> None:
    dockerfile = (WORKSPACE_ROOT / "apps/AgriGuard/backend/Dockerfile").read_text(encoding="utf-8")

    assert (WORKSPACE_ROOT / "apps/AgriGuard/backend/pyproject.toml").exists()
    assert "COPY pyproject.toml" in dockerfile
    assert "pip install --no-cache-dir ." in dockerfile
    assert "requirements.txt" not in dockerfile


def test_frontend_dockerfile_uses_node_runtime_matching_package_engine() -> None:
    dockerfile = (WORKSPACE_ROOT / "apps/AgriGuard/frontend/Dockerfile").read_text(encoding="utf-8")
    package = json.loads((WORKSPACE_ROOT / "apps/AgriGuard/frontend/package.json").read_text(encoding="utf-8"))

    assert package["engines"]["node"].startswith(">=24")
    assert "FROM node:24-alpine AS build" in dockerfile
    assert "FROM node:22" not in dockerfile


def test_frontend_dockerignore_excludes_local_build_and_test_artifacts() -> None:
    dockerignore = (WORKSPACE_ROOT / "apps/AgriGuard/frontend/.dockerignore").read_text(encoding="utf-8")

    for pattern in [
        "node_modules/",
        "dist/",
        "coverage/",
        "playwright-report/",
        "test-results/",
        ".env.*",
        "build_*.out",
        "build_err.txt",
        "build_out.txt",
    ]:
        assert pattern in dockerignore


def test_backend_dockerignore_excludes_local_runtime_and_test_artifacts() -> None:
    dockerignore = (WORKSPACE_ROOT / "apps/AgriGuard/backend/.dockerignore").read_text(encoding="utf-8")

    for pattern in [
        "__pycache__/",
        ".venv/",
        "*.egg-info/",
        ".deepeval/",
        ".pytest_cache/",
        ".coverage",
        "var/",
        "tests/",
        "test_*.py",
        ".env.*",
    ]:
        assert pattern in dockerignore


def test_agriguard_compose_database_url_ignores_host_sqlite_default() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert "DATABASE_URL=${AGRIGUARD_DATABASE_URL:-postgresql://agriguard:agriguard_secret@postgres:5432/agriguard}" in compose
    assert "DATABASE_URL=${DATABASE_URL:-" not in compose
    assert "ALLOWED_ORIGINS=${AGRIGUARD_ALLOWED_ORIGINS:-" in compose
    assert "ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-" not in compose


def test_workspace_root_resolution_supports_container_copy_layout() -> None:
    assert main._resolve_workspace_root(Path("/app/main.py")) == Path("/app").resolve()


def _nginx_location_block(text: str, location: str) -> str:
    match = re.search(rf"location {re.escape(location)} \{{(?P<body>.*?)\n\s*\}}", text, re.DOTALL)
    assert match is not None
    return match.group("body")


def test_nginx_api_websocket_proxy_strips_api_prefix_with_upgrade_headers() -> None:
    configs = {
        "apps/AgriGuard/frontend/nginx.conf": "http://backend:8002/ws/",
        "apps/AgriGuard/nginx/nginx.conf": "http://backend/ws/",
    }

    for relative_path, expected_proxy_pass in configs.items():
        text = (WORKSPACE_ROOT / relative_path).read_text(encoding="utf-8")
        block = _nginx_location_block(text, "/api/ws/")

        assert f"proxy_pass {expected_proxy_pass};" in block
        assert "proxy_http_version 1.1;" in block
        assert "proxy_set_header Upgrade $http_upgrade;" in block
        assert 'proxy_set_header Connection "upgrade";' in block
        assert "proxy_read_timeout 3600s;" in block
        assert "proxy_send_timeout 3600s;" in block

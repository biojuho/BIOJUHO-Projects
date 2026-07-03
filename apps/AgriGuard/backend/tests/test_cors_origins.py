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

    assert (
        "DATABASE_URL=${AGRIGUARD_DATABASE_URL:-postgresql://${AGRIGUARD_DB_USER:-agriguard}:"
        "${AGRIGUARD_DB_PASSWORD:-agriguard_secret}@postgres:5432/${AGRIGUARD_DB_NAME:-agriguard}}" in compose
    )
    assert "postgresql://agriguard:agriguard_secret@postgres:5432/agriguard" not in compose
    assert "DATABASE_URL=${DATABASE_URL:-" not in compose
    assert "ALLOWED_ORIGINS=${AGRIGUARD_ALLOWED_ORIGINS:-" in compose
    assert "ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-" not in compose


def test_agriguard_compose_postgres_healthcheck_uses_configured_database_identity() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert "pg_isready -U agriguard -d agriguard" not in compose
    assert "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}" in compose


def test_agriguard_compose_binds_postgres_to_loopback_only() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert '"127.0.0.1:5432:5432"' in compose
    assert '"5432:5432"' not in compose


def test_agriguard_compose_binds_backend_api_to_loopback_only() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert '"127.0.0.1:8002:8002"' in compose
    assert '"8002:8002"' not in compose


def test_agriguard_compose_binds_mqtt_to_loopback_only() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert '"127.0.0.1:1883:1883"' in compose
    assert '"1883:1883"' not in compose


def test_agriguard_compose_persists_mosquitto_data_volume() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert "- mosquitto-data:/mosquitto/data" in compose
    assert "\n  mosquitto-data:" in compose


def test_agriguard_compose_waits_for_mosquitto_health_before_backend() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert "mosquitto_pub -h localhost -p 1883 -t agriguard/healthcheck -m healthy -q 0" in compose
    assert "mosquitto:\n        condition: service_healthy" in compose
    assert "mosquitto:\n        condition: service_started" not in compose


def test_agriguard_backend_healthcheck_uses_api_root_not_docs_ui() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert "urllib.request.urlopen('http://localhost:8002/')" in compose
    assert "http://localhost:8002/docs" not in compose


def test_agriguard_backend_local_env_file_is_optional_for_clean_checkout() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert "path: ./backend/.env" in compose
    assert "required: false" in compose
    assert "- ./backend/.env" not in compose


def test_agriguard_compose_passes_secret_key_without_backend_env_file() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert "SECRET_KEY=${AGRIGUARD_SECRET_KEY:-${SECRET_KEY:-}}" in compose


def test_agriguard_compose_does_not_publish_unconfigured_https_port() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")
    edge_nginx = (WORKSPACE_ROOT / "apps/AgriGuard/nginx/nginx.conf").read_text(encoding="utf-8")

    assert '"443:443"' not in compose
    assert "listen 443" not in edge_nginx
    assert "ssl_certificate" not in edge_nginx


def test_agriguard_compose_waits_for_frontend_health_before_nginx() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert "frontend:\n        condition: service_healthy" in compose
    assert compose.count('test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost/ || exit 1"]') >= 2
    assert "start_period: 10s" in compose


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


def test_nginx_configs_set_baseline_security_headers() -> None:
    headers = [
        'add_header X-Content-Type-Options "nosniff" always;',
        'add_header X-Frame-Options "DENY" always;',
        'add_header Referrer-Policy "strict-origin-when-cross-origin" always;',
    ]

    frontend = (WORKSPACE_ROOT / "apps/AgriGuard/frontend/nginx.conf").read_text(encoding="utf-8")
    edge = (WORKSPACE_ROOT / "apps/AgriGuard/nginx/nginx.conf").read_text(encoding="utf-8")

    for header in headers:
        assert frontend.count(header) >= 3
        assert header in edge


def test_nginx_configs_disable_server_version_tokens() -> None:
    frontend = (WORKSPACE_ROOT / "apps/AgriGuard/frontend/nginx.conf").read_text(encoding="utf-8")
    edge = (WORKSPACE_ROOT / "apps/AgriGuard/nginx/nginx.conf").read_text(encoding="utf-8")

    assert "server_tokens off;" in frontend
    assert "server_tokens off;" in edge


def test_frontend_nginx_does_not_cache_spa_shell() -> None:
    frontend = (WORKSPACE_ROOT / "apps/AgriGuard/frontend/nginx.conf").read_text(encoding="utf-8")
    block = _nginx_location_block(frontend, "/")

    assert 'add_header Cache-Control "no-cache" always;' in block
    assert 'add_header X-Content-Type-Options "nosniff" always;' in block
    assert 'add_header X-Frame-Options "DENY" always;' in block
    assert 'add_header Referrer-Policy "strict-origin-when-cross-origin" always;' in block

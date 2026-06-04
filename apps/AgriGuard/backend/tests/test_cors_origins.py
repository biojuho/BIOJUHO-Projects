from __future__ import annotations

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


def test_agriguard_compose_database_url_ignores_host_sqlite_default() -> None:
    compose = (WORKSPACE_ROOT / "apps/AgriGuard/docker-compose.yml").read_text(encoding="utf-8")

    assert "DATABASE_URL=${AGRIGUARD_DATABASE_URL:-postgresql://agriguard:agriguard_secret@postgres:5432/agriguard}" in compose
    assert "DATABASE_URL=${DATABASE_URL:-" not in compose
    assert "ALLOWED_ORIGINS=${AGRIGUARD_ALLOWED_ORIGINS:-" in compose
    assert "ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-" not in compose


def test_workspace_root_resolution_supports_container_copy_layout() -> None:
    assert main._resolve_workspace_root(Path("/app/main.py")) == Path("/app").resolve()

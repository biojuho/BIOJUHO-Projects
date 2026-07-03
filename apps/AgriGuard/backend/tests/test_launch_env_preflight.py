from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "launch_env_preflight.py"
SPEC = importlib.util.spec_from_file_location("launch_env_preflight", SCRIPT_PATH)
assert SPEC is not None
launch_env_preflight = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(launch_env_preflight)


def test_launch_env_preflight_fails_without_secret() -> None:
    report = launch_env_preflight.validate_launch_env({})

    assert report["status"] == "fail"
    assert "Set AGRIGUARD_SECRET_KEY or SECRET_KEY before launch." in report["errors"]


def test_launch_env_preflight_rejects_placeholder_secret() -> None:
    report = launch_env_preflight.validate_launch_env({"AGRIGUARD_SECRET_KEY": "change_me"})

    assert report["status"] == "fail"
    assert "AGRIGUARD_SECRET_KEY uses a placeholder or development-only value." in report["errors"]


def test_launch_env_preflight_rejects_short_secret() -> None:
    report = launch_env_preflight.validate_launch_env({"SECRET_KEY": "too-short"})

    assert report["status"] == "fail"
    assert "SECRET_KEY must be at least 32 characters." in report["errors"]


def test_launch_env_preflight_rejects_production_unsafe_runtime_values() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "a" * 32,
            "AUTO_CREATE_SCHEMA": "true",
            "DATABASE_URL": "sqlite:///local.db",
            "ALLOWED_ORIGINS": "*",
        }
    )

    assert report["status"] == "fail"
    assert "AUTO_CREATE_SCHEMA must not be enabled for launch." in report["errors"]
    assert "Use a PostgreSQL DATABASE_URL/AGRIGUARD_DATABASE_URL for launch, not SQLite." in report["errors"]
    assert "ALLOWED_ORIGINS/AGRIGUARD_ALLOWED_ORIGINS must not include wildcard '*'." in report["errors"]


def test_launch_env_preflight_passes_with_strong_secret_and_scoped_origins() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_DATABASE_URL": "postgresql://agriguard:secret@postgres:5432/agriguard",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
        }
    )

    assert report["status"] == "pass"
    assert report["errors"] == []


def test_launch_env_preflight_loads_env_file_and_environment_override(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "AGRIGUARD_SECRET_KEY=change_me",
                "AGRIGUARD_DATABASE_URL=postgresql://agriguard:secret@postgres:5432/agriguard",
                "AGRIGUARD_ALLOWED_ORIGINS=https://agriguard.example",
            ]
        ),
        encoding="utf-8",
    )

    effective = launch_env_preflight.build_effective_env(
        [env_file],
        environ={"AGRIGUARD_SECRET_KEY": "o" * 32},
    )
    report = launch_env_preflight.validate_launch_env(effective)

    assert effective["AGRIGUARD_SECRET_KEY"] == "o" * 32
    assert report["status"] == "pass"

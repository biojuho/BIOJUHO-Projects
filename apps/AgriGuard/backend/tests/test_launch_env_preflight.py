from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "launch_env_preflight.py"
SPEC = importlib.util.spec_from_file_location("launch_env_preflight", SCRIPT_PATH)
assert SPEC is not None
launch_env_preflight = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(launch_env_preflight)


def _healthy_env() -> dict[str, str]:
    return {
        "AGRIGUARD_SECRET_KEY": "s" * 32,
        "AGRIGUARD_DATABASE_URL": "postgresql://agriguard:secret@postgres:5432/agriguard",
        "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
    }


def _runner_from_results(
    results: dict[tuple[str, ...], subprocess.CompletedProcess[str]],
):
    def runner(command, **kwargs):
        return results[tuple(command)]

    return runner


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
            "AGRIGUARD_AUTO_CREATE_SCHEMA": "true",
            "AGRIGUARD_DATABASE_URL": "sqlite:///local.db",
            "AGRIGUARD_ALLOWED_ORIGINS": "*",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_AUTO_CREATE_SCHEMA must not be enabled for launch." in report["errors"]
    assert "Use a PostgreSQL AGRIGUARD_DATABASE_URL for launch, not SQLite." in report["errors"]
    assert "AGRIGUARD_ALLOWED_ORIGINS must not include wildcard '*'." in report["errors"]


def test_launch_env_preflight_compose_mode_ignores_host_auto_create_schema() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AUTO_CREATE_SCHEMA": "true",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
        }
    )

    assert report["status"] == "pass"
    assert report["checks"]["runtime"] == "compose"
    assert report["checks"]["auto_create_schema"] is None
    assert report["checks"]["auto_create_schema_source"] == "AGRIGUARD_AUTO_CREATE_SCHEMA"


def test_launch_env_preflight_direct_mode_rejects_host_auto_create_schema() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AUTO_CREATE_SCHEMA": "true",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert "AUTO_CREATE_SCHEMA must not be enabled for launch." in report["errors"]


def test_launch_env_preflight_compose_mode_ignores_host_database_url() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "DATABASE_URL": "sqlite:///workspace-default.db",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
        }
    )

    assert report["status"] == "pass"
    assert report["checks"]["runtime"] == "compose"
    assert report["checks"]["database_url_present"] is False
    assert report["checks"]["database_url_source"] is None


def test_launch_env_preflight_compose_mode_ignores_host_allowed_origins() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "ALLOWED_ORIGINS": "https://generic.example",
        }
    )

    assert report["status"] == "pass"
    assert report["checks"]["allowed_origins_count"] == 0
    assert report["checks"]["allowed_origins_source"] is None
    assert "No explicit allowed origins configured; runtime defaults may be used." in report["warnings"]


def test_launch_env_preflight_direct_mode_accepts_host_allowed_origins() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "ALLOWED_ORIGINS": "https://generic.example",
        },
        runtime="direct",
    )

    assert report["status"] == "pass"
    assert report["checks"]["allowed_origins_count"] == 1
    assert report["checks"]["allowed_origins_source"] == "ALLOWED_ORIGINS"


def test_launch_env_preflight_compose_mode_rejects_app_scoped_wildcard_origin() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "AGRIGUARD_ALLOWED_ORIGINS": "*",
        }
    )

    assert report["status"] == "fail"
    assert "AGRIGUARD_ALLOWED_ORIGINS must not include wildcard '*'." in report["errors"]


def test_launch_env_preflight_direct_mode_rejects_host_sqlite_database_url() -> None:
    report = launch_env_preflight.validate_launch_env(
        {
            "AGRIGUARD_SECRET_KEY": "s" * 32,
            "DATABASE_URL": "sqlite:///workspace-default.db",
            "AGRIGUARD_ALLOWED_ORIGINS": "https://agriguard.example",
        },
        runtime="direct",
    )

    assert report["status"] == "fail"
    assert "Use a PostgreSQL DATABASE_URL for launch, not SQLite." in report["errors"]


def test_launch_env_preflight_passes_with_strong_secret_and_scoped_origins() -> None:
    report = launch_env_preflight.validate_launch_env(_healthy_env())

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


def test_launch_report_skips_docker_checks_by_default() -> None:
    report = launch_env_preflight.build_launch_report(_healthy_env())

    assert report["status"] == "pass"
    assert report["checks"]["docker_checked"] is False
    assert "docker" not in report["checks"]


def test_launch_report_docker_check_passes_when_daemon_and_compose_config_pass(tmp_path: Path) -> None:
    app_root = tmp_path
    compose_path = str(app_root / "docker-compose.yml")
    runner = _runner_from_results(
        {
            ("docker", "info", "--format", "{{.ServerVersion}}"): subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="29.2.1\n",
                stderr="",
            ),
            ("docker", "compose", "-f", compose_path, "config", "--quiet"): subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            ),
        }
    )

    report = launch_env_preflight.build_launch_report(
        _healthy_env(),
        check_docker=True,
        app_root=app_root,
        command_runner=runner,
    )

    assert report["status"] == "pass"
    assert report["checks"]["docker_checked"] is True
    assert report["checks"]["docker"]["docker_info"]["ok"] is True
    assert report["checks"]["docker"]["compose_config"]["ok"] is True


def test_launch_report_docker_check_fails_when_daemon_unreachable(tmp_path: Path) -> None:
    app_root = tmp_path
    compose_path = str(app_root / "docker-compose.yml")
    runner = _runner_from_results(
        {
            ("docker", "info", "--format", "{{.ServerVersion}}"): subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="failed to connect to the docker API",
            ),
            ("docker", "compose", "-f", compose_path, "config", "--quiet"): subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            ),
        }
    )

    report = launch_env_preflight.build_launch_report(
        _healthy_env(),
        check_docker=True,
        app_root=app_root,
        command_runner=runner,
    )

    assert report["status"] == "fail"
    assert "Docker daemon is not reachable for launch compose startup." in report["errors"]
    assert report["checks"]["docker"]["docker_info"]["stderr_tail"] == "failed to connect to the docker API"


def test_launch_report_docker_check_fails_when_compose_config_is_invalid(tmp_path: Path) -> None:
    app_root = tmp_path
    compose_path = str(app_root / "docker-compose.yml")
    runner = _runner_from_results(
        {
            ("docker", "info", "--format", "{{.ServerVersion}}"): subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="29.2.1\n",
                stderr="",
            ),
            ("docker", "compose", "-f", compose_path, "config", "--quiet"): subprocess.CompletedProcess(
                args=[],
                returncode=15,
                stdout="",
                stderr="invalid compose file",
            ),
        }
    )

    report = launch_env_preflight.build_launch_report(
        _healthy_env(),
        check_docker=True,
        app_root=app_root,
        command_runner=runner,
    )

    assert report["status"] == "fail"
    assert "AgriGuard docker-compose.yml failed compose config validation." in report["errors"]
    assert report["checks"]["docker"]["compose_config"]["stderr_tail"] == "invalid compose file"

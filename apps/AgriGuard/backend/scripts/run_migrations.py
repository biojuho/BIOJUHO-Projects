from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
ALEMBIC_DIR = BACKEND_DIR / "alembic"
BASELINE_REVISION = "0001"
BASELINE_TABLES = {
    "users",
    "products",
    "tracking_events",
    "certificates",
    "sensor_readings",
}

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_backend_env

load_backend_env(override=False)


def _display_database_target() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return "alembic.ini fallback"

    if "@" not in database_url:
        return database_url

    scheme, suffix = database_url.split("://", 1)
    _, host_part = suffix.rsplit("@", 1)
    return f"{scheme}://***@{host_part}"


def build_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

    return config


def _needs_legacy_baseline(database_url: str | None) -> bool:
    if not database_url:
        return False

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())

            if not BASELINE_TABLES.issubset(tables):
                return False

            if "alembic_version" not in tables:
                return True

            versions = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
            return len(versions) == 0
    finally:
        engine.dispose()


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    config = build_config()

    print(f"Running Alembic migrations against {_display_database_target()}...")

    if _needs_legacy_baseline(database_url):
        print("Detected a pre-Alembic baseline database; stamping revision " f"{BASELINE_REVISION} before upgrade.")
        command.stamp(config, BASELINE_REVISION)

    command.upgrade(config, "head")
    print("Alembic migrations applied successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"Migration failed: {exc}", file=sys.stderr)
        raise

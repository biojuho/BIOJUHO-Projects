import os
from pathlib import Path

from env_loader import load_backend_env
from sqlalchemy import text
from sqlalchemy.orm import declarative_base, sessionmaker

# Load the backend-local .env before resolving DATABASE_URL so local uvicorn runs
# do not silently pin themselves to SQLite during module import.
load_backend_env(override=False)

DEFAULT_SQLITE_DB = Path(__file__).resolve().with_name("agriguard.db")
DEFAULT_SQLITE_URL = f"sqlite:///{DEFAULT_SQLITE_DB.as_posix()}"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_SQLITE_URL)


def is_sqlite_url(database_url: str) -> bool:
    return database_url.startswith("sqlite")


def _get_bool_env(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def should_auto_create_schema(database_url: str | None = None) -> bool:
    configured = _get_bool_env("AUTO_CREATE_SCHEMA")
    if configured is not None:
        return configured
    return is_sqlite_url(database_url or get_database_url())


DATABASE_URL = get_database_url()

# Use shared db engine factory for standardizations
from shared.db.engine import get_sqlalchemy_engine
engine = get_sqlalchemy_engine("agriguard", DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def initialize_database() -> None:
    # Alembic owns schema changes in PostgreSQL; keep create_all only for local SQLite convenience.
    if should_auto_create_schema(DATABASE_URL):
        Base.metadata.create_all(bind=engine)


def verify_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

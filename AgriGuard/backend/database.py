import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from env_loader import load_backend_env

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


def create_db_engine(database_url: str | None = None) -> Engine:
    database_url = database_url or get_database_url()

    if is_sqlite_url(database_url):
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


DATABASE_URL = get_database_url()
engine = create_db_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def initialize_database() -> None:
    # Alembic owns schema changes in PostgreSQL; keep create_all only for local SQLite convenience.
    if should_auto_create_schema(DATABASE_URL):
        Base.metadata.create_all(bind=engine)


def verify_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

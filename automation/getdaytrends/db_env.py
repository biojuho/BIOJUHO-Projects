"""Database environment helpers for GetDayTrends.

GetDayTrends runs inside a monorepo where a workspace-level DATABASE_URL may
belong to another app. Use project-scoped env names by default so scheduled
jobs can fall back to SQLite when no GetDayTrends database is configured.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

PROJECT_DATABASE_URL_ENV_NAMES = ("GETDAYTRENDS_DATABASE_URL", "DATABASE_URL_GETDAYTRENDS")
ALLOW_SHARED_DATABASE_URL_ENV = "GETDAYTRENDS_ALLOW_SHARED_DATABASE_URL"
SHARED_DATABASE_URL_ENV = "DATABASE_URL"
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_flag(environ: Mapping[str, str], name: str, default: bool = False) -> bool:
    value = environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in _TRUE_VALUES


def database_url_from_env(environ: Mapping[str, str] | None = None) -> str:
    """Return the GetDayTrends Postgres URL from project-scoped env vars."""
    env = os.environ if environ is None else environ
    for name in PROJECT_DATABASE_URL_ENV_NAMES:
        value = env.get(name, "").strip()
        if value:
            return value

    if _env_flag(env, ALLOW_SHARED_DATABASE_URL_ENV):
        return env.get(SHARED_DATABASE_URL_ENV, "").strip()

    return ""

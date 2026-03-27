from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = BACKEND_DIR / ".env"


def resolve_env_file() -> Path:
    raw_path = os.environ.get("AGRIGUARD_ENV_FILE")
    if not raw_path:
        return DEFAULT_ENV_FILE

    env_path = Path(raw_path)
    if env_path.is_absolute():
        return env_path

    return (BACKEND_DIR / env_path).resolve()


def load_backend_env(*, override: bool = False) -> Path | None:
    env_file = resolve_env_file()
    if not env_file.exists():
        return None

    load_dotenv(env_file, override=override)
    return env_file

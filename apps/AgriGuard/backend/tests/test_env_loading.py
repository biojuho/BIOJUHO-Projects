from __future__ import annotations

import importlib
import os


def test_database_loads_backend_env_file_when_database_url_missing(monkeypatch, tmp_path):
    env_url = "postgresql://tester:secret@localhost:5432/testdb"
    env_file = tmp_path / ".env"
    env_file.write_text(f"DATABASE_URL={env_url}\n", encoding="utf-8")

    original_database_url = os.environ.get("DATABASE_URL")
    original_env_file = os.environ.get("AGRIGUARD_ENV_FILE")
    database_module = None

    try:
        monkeypatch.setenv("AGRIGUARD_ENV_FILE", str(env_file))
        monkeypatch.delenv("DATABASE_URL", raising=False)

        import database as database_module

        database_module = importlib.reload(database_module)

        assert database_module.get_database_url() == env_url
    finally:
        if database_module is not None:
            database_module.engine.dispose()

        if original_database_url is None:
            monkeypatch.delenv("DATABASE_URL", raising=False)
        else:
            monkeypatch.setenv("DATABASE_URL", original_database_url)

        if original_env_file is None:
            monkeypatch.delenv("AGRIGUARD_ENV_FILE", raising=False)
        else:
            monkeypatch.setenv("AGRIGUARD_ENV_FILE", original_env_file)

        if database_module is not None:
            importlib.reload(database_module)

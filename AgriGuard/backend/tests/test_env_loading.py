from __future__ import annotations

import importlib


def test_database_loads_backend_env_file_when_database_url_missing(monkeypatch, tmp_path):
    env_url = "postgresql://tester:secret@localhost:5432/testdb"
    env_file = tmp_path / ".env"
    env_file.write_text(f"DATABASE_URL={env_url}\n", encoding="utf-8")

    monkeypatch.setenv("AGRIGUARD_ENV_FILE", str(env_file))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import database as database_module

    database_module = importlib.reload(database_module)

    assert database_module.get_database_url() == env_url

from database import DEFAULT_SQLITE_URL, should_auto_create_schema


def test_should_auto_create_schema_defaults_to_true_for_sqlite(monkeypatch):
    monkeypatch.delenv("AUTO_CREATE_SCHEMA", raising=False)
    assert should_auto_create_schema(DEFAULT_SQLITE_URL) is True


def test_should_auto_create_schema_defaults_to_false_for_postgres(monkeypatch):
    monkeypatch.delenv("AUTO_CREATE_SCHEMA", raising=False)
    assert should_auto_create_schema("postgresql://user:pass@localhost:5432/agriguard") is False


def test_should_auto_create_schema_honors_env_override(monkeypatch):
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    assert should_auto_create_schema("postgresql://user:pass@localhost:5432/agriguard") is True

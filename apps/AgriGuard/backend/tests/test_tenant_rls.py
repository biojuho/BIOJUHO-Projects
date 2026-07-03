from __future__ import annotations

from dataclasses import dataclass

from database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from tenant_rls import (
    RLS_GLOBAL_OPERATOR_SETTING,
    RLS_OWNER_IDS_SETTING,
    apply_tenant_rls_context,
    build_tenant_rls_context,
)


@dataclass
class _Dialect:
    name: str


@dataclass
class _Bind:
    dialect: _Dialect


class _FakePostgresSession:
    def __init__(self) -> None:
        self.calls = []

    def get_bind(self):
        return _Bind(dialect=_Dialect(name="postgresql"))

    def execute(self, statement, params):
        self.calls.append((str(statement), dict(params)))


def test_build_tenant_rls_context_uses_sorted_owner_keys_and_operator_flag():
    context = build_tenant_rls_context(
        {
            "uid": "uid-1",
            "email": "owner@example.com",
            "owner_id": "farmer-1",
            "tenant_id": "tenant-1",
            "organization": "org-1",
            "role": "operator",
        }
    )

    assert context.applied is False
    assert context.is_global_operator is True
    assert context.owner_ids == ("farmer-1", "org-1", "owner@example.com", "tenant-1", "uid-1")


def test_build_tenant_rls_context_omits_owner_keys_with_setting_delimiter():
    context = build_tenant_rls_context(
        {
            "uid": "uid-1",
            "email": "owner@example.com",
            "owner_id": "tenant-1,tenant-2",
            "tenant_id": "tenant-1",
        }
    )

    assert context.owner_ids == ("owner@example.com", "tenant-1", "uid-1")


def test_apply_tenant_rls_context_is_noop_for_sqlite():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    try:
        context = apply_tenant_rls_context(db, {"uid": "farmer-1", "role": "sensor_operator"})
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    assert context.applied is False
    assert context.dialect_name == "sqlite"
    assert context.owner_ids == ("farmer-1",)
    assert context.is_global_operator is False


def test_apply_tenant_rls_context_sets_local_postgres_settings():
    db = _FakePostgresSession()

    context = apply_tenant_rls_context(
        db,
        {
            "uid": "farmer-1",
            "email": "farmer-1@example.com",
            "tenant_id": "tenant-1",
            "role": "sensor_operator",
        },
    )

    assert context.applied is True
    assert context.dialect_name == "postgresql"
    assert context.owner_ids == ("farmer-1", "farmer-1@example.com", "tenant-1")
    assert context.is_global_operator is False
    assert db.calls == [
        (
            "SELECT set_config(:setting_name, :setting_value, true)",
            {
                "setting_name": RLS_OWNER_IDS_SETTING,
                "setting_value": "farmer-1,farmer-1@example.com,tenant-1",
            },
        ),
        (
            "SELECT set_config(:setting_name, :setting_value, true)",
            {
                "setting_name": RLS_GLOBAL_OPERATOR_SETTING,
                "setting_value": "false",
            },
        ),
    ]


def test_apply_tenant_rls_context_sets_global_operator_flag():
    db = _FakePostgresSession()

    context = apply_tenant_rls_context(db, {"uid": "ops-1", "role": "quality_manager"})

    assert context.applied is True
    assert context.is_global_operator is True
    assert db.calls[-1][1] == {
        "setting_name": RLS_GLOBAL_OPERATOR_SETTING,
        "setting_value": "true",
    }

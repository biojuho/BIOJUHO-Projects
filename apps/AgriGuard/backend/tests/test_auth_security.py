from __future__ import annotations

import pytest
from fastapi import HTTPException

import auth
from admin import AdminAuth


class _FakeRequest:
    def __init__(self, password: str) -> None:
        self._password = password
        self.session: dict[str, bool] = {}

    async def form(self) -> dict[str, str]:
        return {"password": self._password}


def test_firebase_missing_rejects_without_explicit_dev_fallback(monkeypatch):
    monkeypatch.setattr(auth, "FIREBASE_AVAILABLE", False)
    monkeypatch.setattr(auth, "_firebase_initialized", False)
    monkeypatch.delenv("ALLOW_DEV_AUTH_FALLBACK", raising=False)
    monkeypatch.delenv("ALLOW_TEST_BYPASS", raising=False)

    with pytest.raises(HTTPException) as excinfo:
        auth.verify_firebase_token("any-token")

    assert excinfo.value.status_code == 503


def test_test_bypass_still_requires_explicit_flag(monkeypatch):
    monkeypatch.setenv("ALLOW_TEST_BYPASS", "true")

    user = auth.verify_firebase_token("test-token")

    assert user["uid"] == "test-user-id"


@pytest.mark.asyncio
async def test_admin_login_has_no_default_password(monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    backend = AdminAuth(secret_key="test-secret")
    request = _FakeRequest("agri" + "guard-admin")

    assert await backend.login(request) is False
    assert request.session == {}


@pytest.mark.asyncio
async def test_admin_login_uses_configured_password(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "configured-secret")
    backend = AdminAuth(secret_key="test-secret")
    request = _FakeRequest("configured-secret")

    assert await backend.login(request) is True
    assert request.session["admin_authenticated"] is True

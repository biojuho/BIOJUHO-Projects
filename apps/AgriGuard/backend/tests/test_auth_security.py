from __future__ import annotations

import auth
import pytest
from admin import AdminAuth
from fastapi import HTTPException


class _FakeRequest:
    def __init__(self, password: str) -> None:
        self._password = password
        self.session: dict[str, bool] = {}

    async def form(self) -> dict[str, str]:
        return {"password": self._password}


class _FakeFirebaseAuth:
    class ExpiredIdTokenError(Exception):
        pass

    class RevokedIdTokenError(Exception):
        pass

    class InvalidIdTokenError(Exception):
        pass

    @staticmethod
    def verify_id_token(token: str) -> dict:
        assert token == "firebase-token"
        return {
            "uid": "operator-user",
            "email": "operator@example.com",
            "name": "Operator User",
            "role": "operator",
            "roles": ["quality_manager"],
        }


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


def test_dev_auth_fallback_role_is_explicit(monkeypatch):
    monkeypatch.setattr(auth, "FIREBASE_AVAILABLE", False)
    monkeypatch.setattr(auth, "_firebase_initialized", False)
    monkeypatch.setenv("ALLOW_DEV_AUTH_FALLBACK", "true")
    monkeypatch.delenv("DEV_AUTH_FALLBACK_ROLE", raising=False)

    user_without_role = auth.verify_firebase_token("dev-token")
    assert "role" not in user_without_role

    monkeypatch.setenv("DEV_AUTH_FALLBACK_ROLE", "operator")
    user_with_role = auth.verify_firebase_token("dev-token")
    assert user_with_role["role"] == "operator"


def test_firebase_token_preserves_operator_claims(monkeypatch):
    monkeypatch.setattr(auth, "FIREBASE_AVAILABLE", True)
    monkeypatch.setattr(auth, "_firebase_initialized", True)
    monkeypatch.setattr(auth, "auth", _FakeFirebaseAuth)

    user = auth.verify_firebase_token("firebase-token")

    assert user["uid"] == "operator-user"
    assert user["role"] == "operator"
    assert user["roles"] == ["quality_manager"]


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

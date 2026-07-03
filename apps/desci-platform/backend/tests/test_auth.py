from __future__ import annotations

import pytest
import services.auth as auth_module
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_authorization():
    with pytest.raises(HTTPException) as exc:
        await auth_module.get_current_user(None)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Authorization header missing"


@pytest.mark.asyncio
async def test_get_current_user_uses_test_bypass(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ALLOW_TEST_BYPASS", "true")

    user = await auth_module.get_current_user("Bearer test-token-bypass")

    assert user == {"uid": "test-user-id", "email": "test@example.com", "name": "Test User"}


@pytest.mark.asyncio
async def test_get_current_user_rejects_test_bypass_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ALLOW_TEST_BYPASS", "true")
    monkeypatch.delenv("ALLOW_DEV_AUTH_FALLBACK", raising=False)
    monkeypatch.setattr(auth_module, "FIREBASE_AVAILABLE", False)

    with pytest.raises(HTTPException) as exc:
        await auth_module.get_current_user("Bearer test-token-bypass")

    assert exc.value.status_code == 503
    assert exc.value.detail == "Firebase authentication is not configured."


@pytest.mark.asyncio
async def test_get_current_user_requires_config_without_dev_fallback(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("ALLOW_DEV_AUTH_FALLBACK", raising=False)
    monkeypatch.setattr(auth_module, "FIREBASE_AVAILABLE", False)

    with pytest.raises(HTTPException) as exc:
        await auth_module.get_current_user("Bearer real-token")

    assert exc.value.status_code == 503
    assert exc.value.detail == "Firebase authentication is not configured."


@pytest.mark.asyncio
async def test_get_current_user_uses_dev_fallback(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ALLOW_DEV_AUTH_FALLBACK", "true")
    monkeypatch.setattr(auth_module, "FIREBASE_AVAILABLE", False)

    user = await auth_module.get_current_user("Bearer real-token")

    assert user == {"uid": "dev-user-id", "email": "dev@example.com", "name": "Development User"}


@pytest.mark.asyncio
async def test_get_current_user_accepts_frontend_dev_auth_token_with_dev_fallback(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("ALLOW_TEST_BYPASS", raising=False)
    monkeypatch.setenv("ALLOW_DEV_AUTH_FALLBACK", "true")
    monkeypatch.setattr(auth_module, "FIREBASE_AVAILABLE", True)

    user = await auth_module.get_current_user("Bearer test-token-bypass")

    assert user == {"uid": "dev-user-id", "email": "dev@example.com", "name": "Development User"}


@pytest.mark.asyncio
async def test_get_current_user_rejects_dev_fallback_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ALLOW_DEV_AUTH_FALLBACK", "true")
    monkeypatch.setattr(auth_module, "FIREBASE_AVAILABLE", False)

    with pytest.raises(HTTPException) as exc:
        await auth_module.get_current_user("Bearer real-token")

    assert exc.value.status_code == 503
    assert exc.value.detail == "Firebase authentication is not configured."


def test_service_account_json_configured_requires_required_fields() -> None:
    from main import _firebase_service_account_json_configured

    assert _firebase_service_account_json_configured('{"project_id":"demo"}') is False
    assert _firebase_service_account_json_configured("not-json") is False
    assert (
        _firebase_service_account_json_configured(
            '{"project_id":"demo","client_email":"firebase-admin@example.com","private_key":"key"}'
        )
        is True
    )


def test_google_credentials_file_configured_requires_existing_file(tmp_path) -> None:
    from main import _google_credentials_file_configured

    missing_path = tmp_path / "missing.json"
    existing_path = tmp_path / "firebase.json"
    existing_path.write_text("{}", encoding="utf-8")

    assert _google_credentials_file_configured(str(missing_path)) is False
    assert _google_credentials_file_configured(str(existing_path)) is True

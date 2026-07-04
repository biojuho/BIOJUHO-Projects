from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

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


def _run_auth_subprocess(tmp_path: Path, credentials_path: Path, code: str) -> subprocess.CompletedProcess[str]:
    backend_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)
    env["AGRIGUARD_ENV_FILE"] = str(tmp_path / "missing.env")
    env.pop("ALLOW_DEV_AUTH_FALLBACK", None)
    env.pop("ALLOW_TEST_BYPASS", None)

    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )


def test_firebase_missing_rejects_without_explicit_dev_fallback(monkeypatch):
    monkeypatch.setattr(auth, "FIREBASE_AVAILABLE", False)
    monkeypatch.setattr(auth, "_firebase_initialized", False)
    monkeypatch.delenv("ALLOW_DEV_AUTH_FALLBACK", raising=False)
    monkeypatch.delenv("ALLOW_TEST_BYPASS", raising=False)

    with pytest.raises(HTTPException) as excinfo:
        auth.verify_firebase_token("any-token")

    assert excinfo.value.status_code == 503


def test_firebase_credentials_directory_does_not_crash_import(tmp_path):
    credentials_dir = tmp_path / "firebase-service-account.json"
    credentials_dir.mkdir()
    result = _run_auth_subprocess(
        tmp_path,
        credentials_dir,
        "import auth; assert auth._firebase_initialized is False",
    )

    assert result.returncode == 0, result.stderr
    assert "path is not a file" in result.stderr


def test_malformed_firebase_credentials_does_not_crash_import(tmp_path):
    credentials_file = tmp_path / "firebase-service-account.json"
    credentials_file.write_text("\ufeff{not json", encoding="utf-8")

    result = _run_auth_subprocess(
        tmp_path,
        credentials_file,
        "import auth; print(auth._firebase_initialized)",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
    assert "Firebase service account key could not initialize" in result.stderr
    assert "Token verification disabled" in result.stderr


def test_invalid_firebase_credentials_fail_closed_after_import(tmp_path):
    credentials_file = tmp_path / "firebase-service-account.json"
    credentials_file.write_text('{"type": "service_account"}', encoding="utf-8")
    code = """
import auth
from fastapi import HTTPException

try:
    auth.verify_firebase_token("firebase-token")
except HTTPException as exc:
    assert exc.status_code == 503
else:
    raise AssertionError("expected Firebase token verification to fail closed")
assert auth._firebase_initialized is False
"""

    result = _run_auth_subprocess(tmp_path, credentials_file, code)

    assert result.returncode == 0, result.stderr
    assert "Firebase service account key could not initialize" in result.stderr


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

"""
Firebase Authentication Module.

This module stays importable in lean smoke environments where firebase-admin
is not installed. In that mode, auth falls back to mock/development users.
"""

import json
import logging
import os

from dotenv import load_dotenv
from fastapi import Header, HTTPException, status

log = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import auth, credentials

    FIREBASE_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in lean smoke environments
    firebase_admin = None  # type: ignore[assignment]
    auth = None  # type: ignore[assignment]
    credentials = None  # type: ignore[assignment]
    FIREBASE_AVAILABLE = False
    log.warning("firebase-admin not installed. Auth will use mock user fallback.")

load_dotenv()

# Initialize Firebase Admin SDK (only once)
# Note: main.py might already initialize it, so we check first.
if FIREBASE_AVAILABLE and not firebase_admin._apps:
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./serviceAccountKey.json")
    if service_account_json:
        try:
            cred = credentials.Certificate(json.loads(service_account_json))
            firebase_admin.initialize_app(cred)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            log.warning("Invalid FIREBASE_SERVICE_ACCOUNT_JSON. Token verification disabled: %s", exc)
    elif os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        log.warning("No Firebase service account key found. Token verification disabled.")


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_production() -> bool:
    return os.getenv("ENV", "development").strip().lower() == "production"


async def get_current_user(authorization: str | None = Header(None)) -> object:
    """
    Verify Firebase ID tokens when firebase-admin is available.

    In local smoke environments without firebase-admin or service-account
    configuration, return a mock development user instead of failing import-time.
    """

    token = _bearer_token(authorization)

    if not _is_production() and token == "test-token-bypass":
        if _env_flag("ALLOW_TEST_BYPASS"):
            return _test_user()
        if _env_flag("ALLOW_DEV_AUTH_FALLBACK"):
            return _dev_fallback_user()

    if not FIREBASE_AVAILABLE or not firebase_admin._apps:
        return _dev_fallback_user()

    return _verify_firebase_token(token)


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use 'Bearer <token>'",
        )
    return parts[1]


def _test_user() -> dict[str, str]:
    return {"uid": "test-user-id", "email": "test@example.com", "name": "Test User"}


def _dev_fallback_user() -> dict[str, str]:
    if _is_production() or not _env_flag("ALLOW_DEV_AUTH_FALLBACK"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured.",
        )
    return {"uid": "dev-user-id", "email": "dev@example.com", "name": "Development User"}


def _verify_firebase_token(token: str) -> dict[str, str | None]:
    try:
        decoded_token = auth.verify_id_token(token)
        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name", decoded_token.get("email", "Unknown")),
            "picture": decoded_token.get("picture"),
        }
    except auth.ExpiredIdTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token expired: {exc}",
        ) from exc
    except auth.RevokedIdTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token revoked: {exc}",
        ) from exc
    except auth.InvalidIdTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {exc}",
        ) from exc


async def get_optional_current_user(authorization: str | None = Header(None)) -> object:
    """Return the current user when a bearer token is provided, else ``None``."""

    if not authorization:
        return None
    return await get_current_user(authorization)

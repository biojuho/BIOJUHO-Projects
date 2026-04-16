"""
Firebase Authentication Module.

This module stays importable in lean smoke environments where firebase-admin
is not installed. In that mode, auth falls back to mock/development users.
"""

import os

from dotenv import load_dotenv
from fastapi import Header, HTTPException, status

try:
    import firebase_admin
    from firebase_admin import auth, credentials

    FIREBASE_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in lean smoke environments
    firebase_admin = None  # type: ignore[assignment]
    auth = None  # type: ignore[assignment]
    credentials = None  # type: ignore[assignment]
    FIREBASE_AVAILABLE = False
    print("[WARNING] firebase-admin not installed. Auth will use mock user fallback.")

load_dotenv()

# Initialize Firebase Admin SDK (only once)
# Note: main.py might already initialize it, so we check first.
if FIREBASE_AVAILABLE and not firebase_admin._apps:
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./serviceAccountKey.json")
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        print("[WARNING] No Firebase service account key found. Token verification disabled.")


async def get_current_user(authorization: str | None = Header(None)):
    """
    Verify Firebase ID tokens when firebase-admin is available.

    In local smoke environments without firebase-admin or service-account
    configuration, return a mock development user instead of failing import-time.
    """

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

    token = parts[1]

    if os.getenv("ALLOW_TEST_BYPASS", "").lower() == "true" and token == "test-token-bypass":
        return {"uid": "test-user-id", "email": "test@example.com", "name": "Test User"}

    if not FIREBASE_AVAILABLE or not firebase_admin._apps:
        return {"uid": "dev-user-id", "email": "dev@example.com", "name": "Development User"}

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

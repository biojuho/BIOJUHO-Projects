"""
Firebase Authentication Module for AgriGuard
Handles token verification for protected routes.
Pattern adapted from desci-platform/biolinker/services/auth.py.
"""

import os
import sys

from env_loader import load_backend_env
from fastapi import Header, HTTPException, status

try:
    import firebase_admin
    from firebase_admin import auth, credentials

    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("[WARNING] firebase-admin not installed. Auth will use mock user fallback.", file=sys.stderr)

load_backend_env(override=False)

# Initialize Firebase Admin SDK (only once)
_firebase_initialized = False
if FIREBASE_AVAILABLE and not firebase_admin._apps:
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "firebase-service-account.json")
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
    else:
        print("[WARNING] No Firebase service account key found. Token verification disabled.", file=sys.stderr)
elif FIREBASE_AVAILABLE and firebase_admin._apps:
    _firebase_initialized = True


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


OPERATOR_ROLES = frozenset({"admin", "operator", "quality_manager"})


def user_roles(user: dict) -> set[str]:
    values: list[str] = []
    role = user.get("role")
    if isinstance(role, str):
        values.append(role)
    roles = user.get("roles")
    if isinstance(roles, str):
        values.extend(roles.split(","))
    if isinstance(roles, list):
        values.extend(str(value) for value in roles)
    return {value.strip().lower() for value in values if value and value.strip()}


def is_operator_user(user: dict, *, extra_roles: set[str] | None = None) -> bool:
    roles = set(OPERATOR_ROLES)
    if extra_roles:
        roles.update(value.strip().lower() for value in extra_roles if value.strip())
    return bool(user_roles(user) & roles)


def user_owner_keys(user: dict) -> set[str]:
    keys = {
        str(user.get("uid") or "").strip(),
        str(user.get("email") or "").strip(),
        str(user.get("owner_id") or "").strip(),
        str(user.get("tenant_id") or "").strip(),
        str(user.get("organization") or "").strip(),
    }
    return {key for key in keys if key}


def can_access_owner(user: dict, owner_id: str | None) -> bool:
    if is_operator_user(user):
        return True
    normalized_owner = str(owner_id or "").strip()
    return bool(normalized_owner and normalized_owner in user_owner_keys(user))


def verify_firebase_token(token: str) -> dict:
    """
    Verify a Firebase ID token and return decoded user info.
    Falls back to mock user if Firebase is not configured.
    """
    # Test bypass for development
    if os.getenv("ALLOW_TEST_BYPASS", "").lower() == "true" and token == "test-token":
        return {
            "uid": "test-user-id",
            "email": "test@example.com",
            "name": "Test User",
        }

    # Development fallback must be explicit; otherwise auth is fail-closed.
    if not FIREBASE_AVAILABLE or not _firebase_initialized:
        if not _env_flag("ALLOW_DEV_AUTH_FALLBACK"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Firebase authentication is not configured.",
            )
        fallback_user = {
            "uid": "dev-user-id",
            "email": "dev@example.com",
            "name": "Development User",
        }
        fallback_role = os.getenv("DEV_AUTH_FALLBACK_ROLE", "").strip()
        if fallback_role:
            fallback_user["role"] = fallback_role
        return fallback_user

    try:
        decoded_token = auth.verify_id_token(token)
        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name", decoded_token.get("email", "Unknown")),
            "role": decoded_token.get("role"),
            "roles": decoded_token.get("roles", []),
        }
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please log in again.",
        )
    except auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked. Please log in again.",
        )
    except auth.InvalidIdTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
        )


async def get_current_user(authorization: str | None = Header(None)) -> dict:
    """
    FastAPI dependency that extracts the Bearer token from the Authorization
    header and returns the authenticated user dict.
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
    return verify_firebase_token(token)

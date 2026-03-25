"""
Firebase Authentication Module for AgriGuard
Handles token verification for protected routes.
Pattern adapted from desci-platform/biolinker/services/auth.py.
"""
import os
from typing import Optional
from fastapi import Header, HTTPException, status

from env_loader import load_backend_env

try:
    import firebase_admin
    from firebase_admin import credentials, auth
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("[WARNING] firebase-admin not installed. Auth will use mock user fallback.")

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
        print("[WARNING] No Firebase service account key found. Token verification disabled.")
elif FIREBASE_AVAILABLE and firebase_admin._apps:
    _firebase_initialized = True


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

    # If Firebase is not available or not initialized, return mock user
    if not FIREBASE_AVAILABLE or not _firebase_initialized:
        return {
            "uid": "dev-user-id",
            "email": "dev@example.com",
            "name": "Development User",
        }

    try:
        decoded_token = auth.verify_id_token(token)
        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name", decoded_token.get("email", "Unknown")),
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


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
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

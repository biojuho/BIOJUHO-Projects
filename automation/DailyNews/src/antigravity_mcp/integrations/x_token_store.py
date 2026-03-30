"""Secure token storage for X (Twitter) API credentials.

Stores encrypted tokens in ``data/x_tokens.json``.
Falls back to environment variables if the data directory is unavailable.

Pattern mirrors ``scripts/token_store.py`` (Canva OAuth token store).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_DATA_DIR = _PROJECT_ROOT / "data"
_TOKEN_FILE = _DATA_DIR / "x_tokens.json"

# ---------------------------------------------------------------------------
# Fernet encryption (best-effort; degrades to plain JSON gracefully)
# ---------------------------------------------------------------------------

_fernet: Any = None
_ENCRYPTION_AVAILABLE = False

try:
    from cryptography.fernet import Fernet  # type: ignore

    def _derive_key() -> bytes:
        seed = f"{os.getenv('COMPUTERNAME', 'unknown')}:{_PROJECT_ROOT}:x".encode()
        raw = hashlib.sha256(seed).digest()
        return base64.urlsafe_b64encode(raw)

    _fernet = Fernet(_derive_key())
    _ENCRYPTION_AVAILABLE = True
except ImportError:
    logger.debug("cryptography not installed; X tokens will be stored as plain JSON.")


def _encrypt(plaintext: str) -> str:
    if _fernet is None:
        return plaintext
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")


def _decrypt(ciphertext: str) -> str:
    if _fernet is None:
        return ciphertext
    return _fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def _read_store() -> dict[str, str]:
    if not _TOKEN_FILE.exists():
        return {}
    try:
        return json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_store(data: dict[str, str]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

#: Keys managed by this store.
_MANAGED_KEYS = (
    "X_API_KEY",
    "X_API_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_TOKEN_SECRET",
    "X_BEARER_TOKEN",
)


def save_token(name: str, value: str) -> None:
    """Persist a credential by name (encrypted if cryptography is available)."""
    try:
        store = _read_store()
        store[name] = _encrypt(value)
        _write_store(store)
    except Exception as exc:
        logger.warning("Failed to save X token %s to store: %s", name, exc)


def load_token(name: str) -> str | None:
    """Load a credential from the store, falling back to the environment."""
    store = _read_store()
    encrypted = store.get(name)
    if encrypted is not None:
        try:
            return _decrypt(encrypted)
        except Exception:
            logger.warning("Failed to decrypt X token %s; falling back to env.", name)
    return os.getenv(name)


def is_encrypted() -> bool:
    return _ENCRYPTION_AVAILABLE


def has_credentials() -> bool:
    """Return True if all required OAuth 1.0a credentials are available."""
    required = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    return all(load_token(k) for k in required)

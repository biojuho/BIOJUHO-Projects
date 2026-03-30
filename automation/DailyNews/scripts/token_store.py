"""Secure token storage for Canva OAuth rotating refresh tokens.

Stores tokens in ``data/canva_tokens.json``.  When the ``cryptography``
package is available the file contents are encrypted with Fernet
(a symmetric-key scheme).  Otherwise tokens are stored as plain JSON.

If the ``data/`` directory cannot be created for some reason the module
falls back to writing directly to ``.env`` via ``python-dotenv.set_key``.

Usage::

    from token_store import save_token, load_token

    save_token("CANVA_REFRESH_TOKEN", "<value>")
    value = load_token("CANVA_REFRESH_TOKEN")
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_TOKEN_FILE = _DATA_DIR / "canva_tokens.json"
_ENV_PATH = _PROJECT_ROOT / ".env"

# ---------------------------------------------------------------------------
# Encryption helpers (best-effort: graceful degradation to plain JSON)
# ---------------------------------------------------------------------------

_fernet_instance: Any = None
_ENCRYPTION_AVAILABLE = False

try:
    from cryptography.fernet import Fernet  # type: ignore

    def _derive_key() -> bytes:
        """Derive a deterministic Fernet key from the machine-id and project path.

        This is *not* a substitute for a proper secrets vault, but it prevents
        tokens from being stored as plain text on disk. The key material is
        derived from values unique to the current machine + project location.
        """
        seed = f"{os.getenv('COMPUTERNAME', 'unknown')}:{_PROJECT_ROOT}".encode()
        raw = hashlib.sha256(seed).digest()
        return base64.urlsafe_b64encode(raw)

    _fernet_instance = Fernet(_derive_key())
    _ENCRYPTION_AVAILABLE = True
except ImportError:
    pass


def _encrypt(plaintext: str) -> str:
    if _fernet_instance is None:
        return plaintext
    return _fernet_instance.encrypt(plaintext.encode("utf-8")).decode("ascii")


def _decrypt(ciphertext: str) -> str:
    if _fernet_instance is None:
        return ciphertext
    return _fernet_instance.decrypt(ciphertext.encode("ascii")).decode("utf-8")


# ---------------------------------------------------------------------------
# Internal file I/O
# ---------------------------------------------------------------------------


def _read_store() -> dict[str, str]:
    """Read the token store file.  Returns an empty dict on any failure."""
    if not _TOKEN_FILE.exists():
        return {}
    try:
        raw = _TOKEN_FILE.read_text(encoding="utf-8")
        data: dict[str, str] = json.loads(raw)
        return data
    except Exception:
        return {}


def _write_store(data: dict[str, str]) -> None:
    """Write *data* to the token store file, creating directories as needed."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Fallback: write to .env
# ---------------------------------------------------------------------------


def _fallback_save(name: str, value: str) -> None:
    """Write a token to .env via python-dotenv as a last resort."""
    try:
        from dotenv import set_key  # type: ignore

        set_key(str(_ENV_PATH), name, value)
    except Exception:
        pass  # non-fatal; token remains in memory for this session


def _fallback_load(name: str) -> str | None:
    """Try to read a token from environment (loaded from .env at startup)."""
    return os.getenv(name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_token(name: str, value: str) -> None:
    """Persist a token by *name*.

    Attempts to store in ``data/canva_tokens.json`` (encrypted if possible).
    Falls back to writing directly to ``.env`` if the data directory is
    unusable.
    """
    try:
        store = _read_store()
        store[name] = _encrypt(value)
        _write_store(store)
    except Exception:
        _fallback_save(name, value)


def load_token(name: str) -> str | None:
    """Load a previously saved token by *name*.

    Checks the JSON store first, then falls back to the environment.
    Returns ``None`` if the token has never been saved.
    """
    store = _read_store()
    encrypted = store.get(name)
    if encrypted is not None:
        try:
            return _decrypt(encrypted)
        except Exception:
            # Decryption can fail if the key material changed (e.g. project
            # was moved).  Fall through to .env.
            pass
    return _fallback_load(name)


def is_encrypted() -> bool:
    """Return whether the token store is using encryption."""
    return _ENCRYPTION_AVAILABLE

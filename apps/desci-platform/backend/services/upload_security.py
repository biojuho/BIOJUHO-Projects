"""Helpers for treating multipart upload filenames as local display labels."""

from __future__ import annotations

import posixpath
import re
from typing import Any
from urllib.parse import unquote, urlsplit

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_DEFAULT_UPLOAD_FILENAME = "upload.bin"


def normalize_client_upload_filename(filename: str | None, *, default: str = _DEFAULT_UPLOAD_FILENAME) -> str:
    """Return a local filename label without preserving URL/path semantics."""
    raw = str(filename or "").strip()
    if not raw:
        return default

    split = urlsplit(raw)
    if split.scheme == "data":
        return default
    if split.scheme and (split.path or split.netloc):
        raw = split.path or split.netloc

    raw = unquote(raw).replace("\\", "/")
    label = posixpath.basename(raw.rstrip("/"))
    label = _CONTROL_CHARS.sub("", label).strip()
    if label in {"", ".", ".."}:
        return default
    return label


def normalize_upload_file(file: Any) -> Any:
    """Normalize ``UploadFile.filename`` in place and return the same object."""
    file.filename = normalize_client_upload_filename(getattr(file, "filename", None))
    return file

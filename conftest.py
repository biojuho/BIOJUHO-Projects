"""Workspace-level pytest configuration.

getdaytrends has a bare ``models`` module that collides with
biolinker/models.py when both are collected in the same pytest process.
Run getdaytrends tests separately::

    python -m pytest getdaytrends/tests/ -q
"""

from __future__ import annotations

# ---------- pytest 8.4 + Python 3.13 capture workaround ----------
# Background threads (logging, metrics) may write to stdout/stderr after
# pytest's capture teardown closes the underlying tmpfile, raising
# ``ValueError: I/O operation on closed file`` during session shutdown.
# This does NOT mask real test failures — only the noisy shutdown crash.
import sys as _sys

_orig_unraisablehook = _sys.unraisablehook


def _silence_capture_io_error(unraisable):
    if (
        isinstance(unraisable.exc_value, ValueError)
        and "I/O operation on closed file" in str(unraisable.exc_value)
    ):
        return  # suppress known pytest capture teardown noise
    _orig_unraisablehook(unraisable)


_sys.unraisablehook = _silence_capture_io_error
# ------------------------------------------------------------------

import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent
TMP_ROOT = WORKSPACE_ROOT / ".smoke-tmp" / "workspace-tests"

collect_ignore_glob = ["getdaytrends/tests/*"]


@pytest.fixture(autouse=True)
def _force_workspace_temp(monkeypatch):
    """Keep pytest temp artifacts inside the workspace on locked-down Windows setups."""
    previous_tempdir = tempfile.tempdir
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TMP", str(TMP_ROOT))
    monkeypatch.setenv("TEMP", str(TMP_ROOT))
    monkeypatch.setenv("TMPDIR", str(TMP_ROOT))
    tempfile.tempdir = str(TMP_ROOT)
    yield
    tempfile.tempdir = previous_tempdir


@pytest.fixture()
def tmp_path():
    """Provide a workspace-local replacement for pytest's default tmp_path fixture."""
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"tmp-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

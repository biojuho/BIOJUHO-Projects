from __future__ import annotations

import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_DIR.parents[2]
backend_path = str(BACKEND_DIR)
TMP_ROOT = WORKSPACE_ROOT / ".smoke-tmp" / "agriguard-backend"

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


@pytest.fixture(autouse=True)
def _force_workspace_temp(monkeypatch):
    previous_tempdir = tempfile.tempdir
    TMP_ROOT.mkdir(exist_ok=True)
    monkeypatch.setenv("TMP", str(TMP_ROOT))
    monkeypatch.setenv("TEMP", str(TMP_ROOT))
    monkeypatch.setenv("TMPDIR", str(TMP_ROOT))
    tempfile.tempdir = str(TMP_ROOT)
    yield
    tempfile.tempdir = previous_tempdir


@pytest.fixture()
def tmp_path():
    TMP_ROOT.mkdir(exist_ok=True)
    path = TMP_ROOT / f"tmp-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SRC_DIR = PROJECT_ROOT / "src"
TMP_ROOT = WORKSPACE_ROOT / ".smoke-tmp" / "dailynews-tests"

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from antigravity_mcp.config import get_settings
from antigravity_mcp.state.store import PipelineStateStore


@pytest.fixture(autouse=True)
def _force_workspace_temp(monkeypatch):
    """Use a workspace-local temp dir to avoid Windows temp permission failures."""
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
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"tmp-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def state_store(tmp_path):
    """Provide an isolated PipelineStateStore backed by a temporary SQLite DB."""
    db_path = tmp_path / "test_pipeline_state.db"
    store = PipelineStateStore(path=db_path)
    yield store
    store.close()


@pytest.fixture
def load_script_module(monkeypatch, tmp_path):
    def _load(module_name: str):
        sys.modules.pop(module_name, None)
        module = importlib.import_module(module_name)
        runtime = importlib.import_module("runtime")

        try:
            from shared.test_utils.fixtures import SystemFixtureFactory
            SystemFixtureFactory.patch_runtime_paths(monkeypatch, runtime, tmp_path)
        except ImportError:
            # Fallback for systems without shared repo module
            pass

        return module, runtime

    return _load


@pytest.fixture(autouse=True)
def reset_cached_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SRC_DIR = PROJECT_ROOT / "src"

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

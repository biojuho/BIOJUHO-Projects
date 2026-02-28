from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def load_script_module(monkeypatch, tmp_path):
    def _load(module_name: str):
        sys.modules.pop(module_name, None)
        module = importlib.import_module(module_name)
        runtime = importlib.import_module("runtime")

        data_dir = tmp_path / "data"
        log_dir = tmp_path / "logs"
        data_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(runtime, "DATA_DIR", data_dir, raising=False)
        monkeypatch.setattr(runtime, "LOG_DIR", log_dir, raising=False)
        monkeypatch.setattr(runtime, "PIPELINE_STATE_DB", data_dir / "pipeline_state.db", raising=False)
        monkeypatch.setattr(runtime, "SCHEDULER_LOG_PATH", log_dir / "scheduler.log", raising=False)
        return module, runtime

    return _load

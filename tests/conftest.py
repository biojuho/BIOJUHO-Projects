"""Shared pytest fixtures for workspace-level tests."""

import sys
from pathlib import Path

import pytest

# Ensure canonical workspace paths are importable.
# shared.paths adds the workspace root, packages/, automation/, etc.
_ROOT = Path(__file__).resolve().parents[1]
# Bootstrap: ensure shared/ is importable before importing shared.paths
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.paths import ensure_importable  # noqa: E402

ensure_importable(include_dailynews=True)


@pytest.fixture(autouse=True)
def _reset_llm_singleton():
    """Auto-reset the shared.llm singleton between tests to prevent pollution."""
    from shared.llm import reset_client
    from shared.llm.client import LLMClient

    reset_client()
    LLMClient.reset()
    yield
    reset_client()
    LLMClient.reset()

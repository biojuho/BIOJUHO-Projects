"""Shared pytest fixtures for workspace-level tests."""

import sys
from pathlib import Path

import pytest

# Ensure workspace root is on sys.path
_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


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

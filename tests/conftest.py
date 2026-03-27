"""Shared pytest fixtures for workspace-level tests."""

import sys
from pathlib import Path

import pytest

# Ensure canonical workspace paths are importable without relying on legacy
# junctions such as shared/ or DailyNews/.
_ROOT = Path(__file__).resolve().parents[1]
for candidate in (
    _ROOT,
    _ROOT / "packages",
    _ROOT / "automation",
    _ROOT / "apps" / "desci-platform",
    _ROOT / "automation" / "DailyNews" / "src",
    _ROOT / "automation" / "DailyNews" / "scripts",
):
    candidate_text = str(candidate)
    if candidate.exists() and candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)


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

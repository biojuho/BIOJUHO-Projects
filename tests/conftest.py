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
    """Auto-reset the shared.llm singleton between tests when available.

    Some isolated QC environments intentionally install only the dependencies
    needed for a narrow test slice. In those cases shared.llm may be
    unavailable because optional packages such as pydantic are not present.
    Tests that do not touch shared.llm should still be able to run.
    """
    try:
        from shared.llm import reset_client
        from shared.llm.client import LLMClient
    except ModuleNotFoundError as exc:
        # Only swallow missing third-party dependencies for unrelated test
        # slices. Internal shared.* import errors should still fail loudly.
        missing_module = exc.name or ""
        if missing_module and not missing_module.startswith("shared"):
            yield
            return
        raise

    reset_client()
    LLMClient.reset()
    yield
    reset_client()
    LLMClient.reset()

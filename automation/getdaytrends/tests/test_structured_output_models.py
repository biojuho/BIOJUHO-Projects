"""Guard the structured-output backend model IDs against dead endpoints.

Google retired the dated Gemini 2.5 *-preview-* endpoints (pro-preview-03-25
shut down 2025-12-02; the 2.5 preview wave after 2025-07-15), so those IDs now
404. This pins the live GA aliases so a deprecated preview endpoint cannot creep
back in. Claude tiers are checked to be the current 4.x models.
"""

from __future__ import annotations

import structured_output
from structured_output import _get_model_name, reset_instructor_client


def _set_backend(name: str) -> None:
    structured_output._instructor_backend = name


def teardown_function() -> None:
    reset_instructor_client()


def test_gemini_models_are_live_ga_not_dead_preview_endpoints():
    _set_backend("gemini")
    heavy = _get_model_name("heavy")
    light = _get_model_name("lightweight")
    for name in (heavy, light):
        assert "preview" not in name, f"dead -preview- Gemini endpoint resurfaced: {name}"
    assert heavy == "gemini-2.5-pro"
    assert light == "gemini-2.5-flash"


def test_claude_tiers_use_current_4x_models():
    _set_backend("anthropic")
    assert _get_model_name("heavy") == "claude-sonnet-4-6-20250514"
    assert _get_model_name("lightweight") == "claude-haiku-4-5-20251001"

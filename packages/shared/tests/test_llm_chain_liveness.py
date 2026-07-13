"""
Regression tests for the 2026-07-11 DailyNews outage (PR #318).

Root cause: retired model ids left in TIER_CHAINS (404 at call time) plus a
Gemini invalid-key error message that did not match FALLBACK_ERRORS, so the
chain died instead of falling back.
"""

import sys

sys.path.insert(0, "packages")

from shared.llm.config import (
    FALLBACK_ERRORS,
    MODEL_COSTS,
    MODEL_TO_TIER,
    TIER_CHAINS,
)
from shared.llm.models import TaskTier

# Model ids confirmed retired (live 404) on 2026-07-11.
RETIRED_MODELS = {
    "claude-sonnet-4-20250514",
    "gemini-2.5-pro-preview-03-25",
}


def test_tier_chains_contain_no_retired_models() -> None:
    for tier, chain in TIER_CHAINS.items():
        for provider, model in chain:
            assert model not in RETIRED_MODELS, (
                f"{tier}: {provider}/{model} is retired and returns 404"
            )


def test_heavy_chain_head_is_live_sonnet() -> None:
    assert TIER_CHAINS[TaskTier.HEAVY][0] == (
        "anthropic",
        "claude-sonnet-4-5-20250929",
    )


def test_replacement_model_registered_in_tier_and_cost_tables() -> None:
    assert MODEL_TO_TIER["claude-sonnet-4-5-20250929"] is TaskTier.HEAVY
    assert MODEL_COSTS["claude-sonnet-4-5-20250929"] == (3.0, 15.0)


def test_gemini_invalid_key_message_matches_fallback_patterns() -> None:
    # Exact phrasing Gemini returns for a revoked/rotated key.
    msg = "400 API key not valid. Please pass a valid API key.".lower()
    assert any(pattern in msg for pattern in FALLBACK_ERRORS)


def test_gemini_invalid_key_error_triggers_client_fallback() -> None:
    from shared.llm.client import _should_fallback

    err = Exception("400 API key not valid. Please pass a valid API key.")
    assert _should_fallback(err)

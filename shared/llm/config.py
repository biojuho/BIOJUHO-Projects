"""shared.llm.config - Key loading, tier fallback chains, cost tables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .models import TaskTier

# ---------------------------------------------------------------------------
# Load root .env (the single source of truth for LLM keys)
# ---------------------------------------------------------------------------
_ROOT_DIR = Path(__file__).resolve().parents[2]  # d:\AI 프로젝트
_ROOT_ENV = _ROOT_DIR / ".env"
load_dotenv(_ROOT_ENV)


def _key(name: str) -> str:
    return (os.getenv(name) or "").strip()


def load_keys() -> dict[str, str]:
    """Load all LLM API keys from environment."""
    return {
        "anthropic": _key("ANTHROPIC_API_KEY"),
        "gemini": _key("GOOGLE_API_KEY") or _key("GEMINI_API_KEY"),
        "openai": _key("OPENAI_API_KEY"),
        "grok": _key("XAI_API_KEY"),
        "deepseek": _key("DEEPSEEK_API_KEY"),
        "moonshot": _key("MOONSHOT_API_KEY"),
    }


# ---------------------------------------------------------------------------
# Tier-aware fallback chains
# ---------------------------------------------------------------------------
TIER_CHAINS: dict[TaskTier, list[tuple[str, str]]] = {
    TaskTier.HEAVY: [
        ("anthropic", "claude-sonnet-4-20250514"),
        ("gemini", "gemini-2.5-pro"),
        ("grok", "grok-3"),
        ("openai", "gpt-4o"),
    ],
    TaskTier.MEDIUM: [
        ("gemini", "gemini-2.5-flash"),
        ("anthropic", "claude-3-5-haiku-20241022"),
        ("grok", "grok-3-mini-fast"),
        ("openai", "gpt-4o-mini"),
    ],
    TaskTier.LIGHTWEIGHT: [
        ("gemini", "gemini-2.0-flash"),
        ("grok", "grok-3-mini-fast"),
        ("deepseek", "deepseek-chat"),
        ("openai", "gpt-4o-mini"),
    ],
}

# ---------------------------------------------------------------------------
# Backward-compatible: Anthropic model name → TaskTier
# ---------------------------------------------------------------------------
MODEL_TO_TIER: dict[str, TaskTier] = {
    "claude-3-haiku-20240307": TaskTier.LIGHTWEIGHT,
    "claude-3-5-haiku-20241022": TaskTier.MEDIUM,
    "claude-sonnet-4-20250514": TaskTier.HEAVY,
    "claude-3-5-sonnet-20241022": TaskTier.HEAVY,
}

# ---------------------------------------------------------------------------
# Model cost table (USD per 1M tokens: input, output)
# ---------------------------------------------------------------------------
MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (0.8, 4.0),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.0, 0.0),
    "gemini-2.0-flash": (0.0, 0.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "grok-3": (3.0, 15.0),
    "grok-3-mini-fast": (0.3, 0.5),
    "deepseek-chat": (0.14, 0.28),
}

# ---------------------------------------------------------------------------
# Fallback error patterns (triggers next backend)
# ---------------------------------------------------------------------------
FALLBACK_ERRORS: tuple[str, ...] = (
    "credit balance is too low",
    "insufficient_quota",
    "rate_limit_exceeded",
    "authentication_error",
    "billing",
    "quota exceeded",
    "resource_exhausted",
    "not_found",
    "not found",
    "model not found",
    "invalid api key",
    "invalid_api_key",
)

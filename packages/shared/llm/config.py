"""shared.llm.config - Key loading, tier fallback chains, cost tables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .models import LLMPolicy, TaskTier

# ---------------------------------------------------------------------------
# Load root .env (the single source of truth for LLM keys)
# ---------------------------------------------------------------------------
_ROOT_DIR = Path(__file__).resolve().parents[3]
_ROOT_ENV = _ROOT_DIR / ".env"
load_dotenv(_ROOT_ENV)


# ---------------------------------------------------------------------------
# Budget-aware auto-downgrade thresholds (USD/day)
# ---------------------------------------------------------------------------
# When today's cumulative cost exceeds a threshold, HEAVY requests auto-
# downgrade to MEDIUM, and MEDIUM to LIGHTWEIGHT.  The hard cap triggers
# the existing RATE_LIMIT.lock mechanism.
LLM_DAILY_BUDGET = float(os.getenv("LLM_DAILY_BUDGET", "2.00"))
LLM_BUDGET_DOWNGRADE_HEAVY = float(os.getenv("LLM_BUDGET_DOWNGRADE_HEAVY", "1.50"))
LLM_BUDGET_DOWNGRADE_MEDIUM = float(os.getenv("LLM_BUDGET_DOWNGRADE_MEDIUM", "1.80"))


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
        "mimo": _key("XIAOMI_MIMO_API_KEY"),
    }


# ---------------------------------------------------------------------------
# Tier-aware fallback chains
# ---------------------------------------------------------------------------
TIER_CHAINS: dict[TaskTier, list[tuple[str, str]]] = {
    TaskTier.HEAVY: [
        ("anthropic", "claude-sonnet-4-20250514"),
        ("gemini", "gemini-2.5-pro-preview-03-25"),
        ("mimo", "mimo-v2-pro"),  # $0.09/1M, GPT-5급 성능
        ("grok", "grok-3"),
        ("ollama", "qwen3-coder:30b-a3b-q4_K_M"),  # ★ 로컬 $0: 코드생성·추론 특화
        ("openai", "gpt-4o"),
    ],
    TaskTier.MEDIUM: [
        ("gemini", "gemini-2.5-flash-lite"),  # Free 1,000RPD, 초저비용 $0.10/$0.40
        ("gemini", "gemini-2.5-flash"),  # ✅ 2.5 Flash (2.0 deprecated 제거됨)
        ("mimo", "mimo-v2-pro"),  # $0.09/1M, Haiku 대체 폴백
        ("anthropic", "claude-haiku-4-5-20251001"),
        ("grok", "grok-3-mini-fast"),
        ("ollama", "qwen3-coder:30b-a3b-q4_K_M"),  # ★ 로컬 $0 폴백
        ("openai", "gpt-4o-mini"),
    ],
    TaskTier.LIGHTWEIGHT: [
        ("gemini", "gemini-2.5-flash-lite"),  # ★ 주력: Free 1,000RPD, $0.10/$0.40
        ("gemini", "gemini-2.5-flash"),  # ✅ 2.5 Flash (2.0 deprecated 제거됨)
        ("mimo", "mimo-v2-pro"),  # $0.09/1M, 한국어 안정 + 초저비용
        ("grok", "grok-3-mini-fast"),  # 저렴 $0.3/$0.5, 빠름
        ("anthropic", "claude-haiku-4-5-20251001"),  # 안정적 폴백
        ("openai", "gpt-4o-mini"),
        ("ollama", "deepseek-r1:14b"),  # 로컬 추론 특화 (API 비용 $0)
        ("ollama", "phi3:3.8b"),  # 로컬 Ollama 폴백 (API 비용 $0)
        ("bitnet", "bitnet-b1.58-2b-4t"),  # 최후방 로컬 폴백 (API 비용 $0)
    ],
}

STRUCTURED_TASK_KINDS = frozenset(
    {"classification", "keyword_extraction", "search_query_generation", "json_extraction"}
)
LONGFORM_TASK_KINDS = frozenset({"summary", "analysis", "literature_review", "grant_writing", "youtube_longform"})

# ---------------------------------------------------------------------------
# Backward-compatible: Anthropic model name → TaskTier
# ---------------------------------------------------------------------------
MODEL_TO_TIER: dict[str, TaskTier] = {
    "claude-3-haiku-20240307": TaskTier.LIGHTWEIGHT,
    "claude-3-5-haiku-20241022": TaskTier.MEDIUM,
    "claude-haiku-4-5-20251001": TaskTier.MEDIUM,
    "claude-sonnet-4-20250514": TaskTier.HEAVY,
    "claude-3-5-sonnet-20241022": TaskTier.HEAVY,
    # Ollama local models
    "qwen3-coder:30b-a3b-q4_K_M": TaskTier.MEDIUM,
    "deepseek-r1:14b": TaskTier.LIGHTWEIGHT,
    "phi3:3.8b": TaskTier.LIGHTWEIGHT,
}

# ---------------------------------------------------------------------------
# Model cost table (USD per 1M tokens: input, output)
# ---------------------------------------------------------------------------
MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.8, 4.0),
    "claude-3-5-haiku-20241022": (0.8, 4.0),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "gemini-2.5-pro-preview-03-25": (1.25, 10.0),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.15, 3.50),  # Free tier에서는 $0, 유료 시 적용
    "gemini-2.5-flash-lite": (0.10, 0.40),  # Free 1,000RPD, 유료 시 초저비용
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "grok-3": (3.0, 15.0),
    "grok-3-mini-fast": (0.3, 0.5),
    "deepseek-chat": (0.14, 0.28),
    "mimo-v2-pro": (0.09, 0.09),  # Xiaomi MiMo-V2-Pro
    # Local inference — no API cost
    "bitnet-b1.58-2b-4t": (0.0, 0.0),
    "qwen3-coder:30b-a3b-q4_K_M": (0.0, 0.0),  # Ollama: Qwen3-Coder 30B quantized
    "deepseek-r1:14b": (0.0, 0.0),  # Ollama: DeepSeek-R1 14B
    "phi3:3.8b": (0.0, 0.0),  # Ollama local
    "qwen2.5:3b": (0.0, 0.0),  # Ollama local
    "gemma:2b": (0.0, 0.0),  # Ollama local
    "tinyllama:1.1b": (0.0, 0.0),  # Ollama local
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
    # DeepSeek 한국어 프롬프트 오류 → 즉시 폴백 (KI: resilient_llm_operations)
    "invalid_request_error",
    "invalid request",
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = _key(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def is_deepseek_longform_enabled() -> bool:
    """Feature flag for DeepSeek Korean long-form generation."""
    return _env_flag("ENABLE_DEEPSEEK_KO_LONGFORM", default=False)


# ---------------------------------------------------------------------------
# Reasoning Engine Configuration
# ---------------------------------------------------------------------------
REASONING_CONFIG = {
    "enabled": _env_flag("REASONING_ENGINE_ENABLED", default=True),
    "cot_samples": int(_key("REASONING_COT_SAMPLES") or "3"),
    "cot_consensus_threshold": float(_key("REASONING_COT_CONSENSUS") or "0.7"),
    "sage_confidence_high": float(_key("REASONING_SAGE_HIGH") or "0.85"),
    "sage_confidence_low": float(_key("REASONING_SAGE_LOW") or "0.5"),
    "fot_max_depth": int(_key("REASONING_FOT_MAX_DEPTH") or "3"),
    "smart_router_enabled": _env_flag("REASONING_SMART_ROUTER", default=True),
    "prefer_local": _env_flag("REASONING_PREFER_LOCAL", default=False),
}


def get_routing_chain(tier: TaskTier, policy: LLMPolicy | None = None) -> list[tuple[str, str]]:
    """Return the backend chain for the given tier and task policy.

    NOTE: DeepSeek removed from all chains (2026-03-22)
    due to persistent Korean prompt errors and high error rate.
    """
    chain = list(TIER_CHAINS[tier])
    if (
        policy is not None
        and policy.task_kind == "json_extraction"
        and policy.response_mode == "json"
    ):
        preferred = [item for item in chain if item[0] == "anthropic"]
        preferred.extend(item for item in chain if item[0] == "openai")
        preferred.extend(item for item in chain if item[0] == "gemini")
        chain = _dedupe_chain(preferred or chain)

    return chain


def _dedupe_chain(chain: list[tuple[str, str]]) -> list[tuple[str, str]]:
    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in chain:
        if item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped

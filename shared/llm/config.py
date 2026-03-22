"""shared.llm.config - Key loading, tier fallback chains, cost tables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .models import LLMPolicy, TaskTier

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
        "mimo": _key("XIAOMI_MIMO_API_KEY"),
    }


# ---------------------------------------------------------------------------
# Tier-aware fallback chains
# ---------------------------------------------------------------------------
TIER_CHAINS: dict[TaskTier, list[tuple[str, str]]] = {
    TaskTier.HEAVY: [
        ("anthropic", "claude-sonnet-4-20250514"),
        ("gemini", "gemini-2.5-pro-preview-03-25"),
        ("mimo", "mimo-v2-pro"),                     # $0.09/1M, GPT-5급 성능
        ("grok", "grok-3"),
        ("openai", "gpt-4o"),
    ],
    TaskTier.MEDIUM: [
        ("gemini", "gemini-2.0-flash"),
        ("mimo", "mimo-v2-pro"),                     # $0.09/1M, Haiku 대체 폴백
        ("anthropic", "claude-haiku-4-5-20251001"),
        ("grok", "grok-3-mini-fast"),
        ("openai", "gpt-4o-mini"),
    ],
    TaskTier.LIGHTWEIGHT: [
        ("gemini", "gemini-2.0-flash"),              # Free tier 15RPM, 한국어 최강
        ("mimo", "mimo-v2-pro"),                     # $0.09/1M, 한국어 안정 + 초저비용
        ("grok", "grok-3-mini-fast"),                # 저렴 $0.3/$0.5, 빠름
        ("anthropic", "claude-haiku-4-5-20251001"),  # 안정적 폴백
        ("deepseek", "deepseek-chat"),               # 5순위: 잔액 부족 시 자동 스킵 (fallback)
        ("openai", "gpt-4o-mini"),
        ("ollama", "phi3:3.8b"),                     # 로컬 Ollama 폴백 (API 비용 $0)
        ("bitnet", "bitnet-b1.58-2b-4t"),            # 최후방 로컬 폴백 (API 비용 $0)
    ],
}

STRUCTURED_TASK_KINDS = frozenset(
    {"classification", "keyword_extraction", "search_query_generation", "json_extraction"}
)
LONGFORM_TASK_KINDS = frozenset(
    {"summary", "analysis", "literature_review", "grant_writing", "youtube_longform"}
)

# ---------------------------------------------------------------------------
# Backward-compatible: Anthropic model name → TaskTier
# ---------------------------------------------------------------------------
MODEL_TO_TIER: dict[str, TaskTier] = {
    "claude-3-haiku-20240307": TaskTier.LIGHTWEIGHT,
    "claude-3-5-haiku-20241022": TaskTier.MEDIUM,
    "claude-haiku-4-5-20251001": TaskTier.MEDIUM,
    "claude-sonnet-4-20250514": TaskTier.HEAVY,
    "claude-3-5-sonnet-20241022": TaskTier.HEAVY,
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
    "gemini-2.5-flash": (0.15, 3.50),               # Free tier에서는 $0, 유료 시 적용
    "gemini-2.0-flash": (0.0, 0.0),                  # Free tier 15RPM 무료
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "grok-3": (3.0, 15.0),
    "grok-3-mini-fast": (0.3, 0.5),
    "deepseek-chat": (0.14, 0.28),
    "mimo-v2-pro": (0.09, 0.09),                 # Xiaomi MiMo-V2-Pro
    # Local inference — no API cost
    "bitnet-b1.58-2b-4t": (0.0, 0.0),
    "phi3:3.8b": (0.0, 0.0),            # Ollama local
    "qwen2.5:3b": (0.0, 0.0),           # Ollama local
    "gemma:2b": (0.0, 0.0),             # Ollama local
    "tinyllama:1.1b": (0.0, 0.0),       # Ollama local
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


def get_routing_chain(tier: TaskTier, policy: LLMPolicy | None = None) -> list[tuple[str, str]]:
    """Return the backend chain for the given tier and task policy."""
    chain = list(TIER_CHAINS[tier])
    task_kind = (policy.task_kind if policy else "generic") or "generic"

    if task_kind in STRUCTURED_TASK_KINDS:
        chain = _dedupe_chain([("deepseek", "deepseek-chat"), *chain])
    elif task_kind in LONGFORM_TASK_KINDS and not is_deepseek_longform_enabled():
        chain = [entry for entry in chain if entry[0] != "deepseek"]
    elif task_kind in LONGFORM_TASK_KINDS and is_deepseek_longform_enabled():
        chain = _dedupe_chain([*chain, ("deepseek", "deepseek-chat")])

    # NOTE: LIGHTWEIGHT 티어는 TIER_CHAINS 정의 순서를 그대로 따릅니다.
    # gemini 선두 체인 (DeepSeek 한국어 오류 회피 움직) — 2026-03

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

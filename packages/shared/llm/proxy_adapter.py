"""shared.llm.proxy_adapter - Optional LiteLLM proxy routing.

Phase 1 MVP. When ``LITELLM_PROXY_URL`` is set, callers of :mod:`shared.llm.client`
route through a single OpenAI-compatible gateway that fans out to the 9 backends
and emits Langfuse traces. Default behaviour (env unset) is unchanged.

The adapter only exposes ``call`` and ``acall``; routing/cache/budget logic stays
in :mod:`shared.llm.client`.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from .models import LLMResponse, TaskTier

log = logging.getLogger("shared.llm.proxy")

_TIER_TO_ALIAS: dict[TaskTier, str] = {
    TaskTier.HEAVY: "tier-heavy",
    TaskTier.MEDIUM: "tier-medium",
    TaskTier.LIGHTWEIGHT: "tier-lightweight",
}

_PROXY_TIMEOUT_SECONDS = 30.0


def is_proxy_enabled() -> bool:
    return bool(os.getenv("LITELLM_PROXY_URL", "").strip())


def _build_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not system:
        return list(messages)
    if messages and messages[0].get("role") == "system":
        return list(messages)
    return [{"role": "system", "content": system}, *messages]


def _resolve_model_alias(tier: TaskTier) -> str:
    return _TIER_TO_ALIAS.get(tier, "tier-medium")


def _make_client(*, async_client: bool):
    try:
        import openai
    except ImportError as exc:
        raise RuntimeError("openai SDK not installed; cannot use LiteLLM proxy") from exc

    base_url = os.environ["LITELLM_PROXY_URL"].rstrip("/")
    api_key = os.getenv("LITELLM_MASTER_KEY", "sk-litellm-master-dev")
    if async_client:
        return openai.AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=_PROXY_TIMEOUT_SECONDS)
    return openai.OpenAI(base_url=base_url, api_key=api_key, timeout=_PROXY_TIMEOUT_SECONDS)


def _coerce_response(completion: Any, *, tier: TaskTier, t0: float) -> LLMResponse:
    choice = completion.choices[0]
    text = (getattr(choice.message, "content", "") or "").strip()
    usage = getattr(completion, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    return LLMResponse(
        text=text,
        model=getattr(completion, "model", "") or _resolve_model_alias(tier),
        backend="litellm-proxy",
        tier=tier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=(time.perf_counter() - t0) * 1000,
    )


def call(
    *,
    tier: TaskTier,
    messages: list[dict[str, Any]],
    max_tokens: int,
    system: str,
) -> LLMResponse:
    client = _make_client(async_client=False)
    t0 = time.perf_counter()
    completion = client.chat.completions.create(
        model=_resolve_model_alias(tier),
        messages=_build_messages(system, messages),
        max_tokens=max_tokens,
    )
    return _coerce_response(completion, tier=tier, t0=t0)


async def acall(
    *,
    tier: TaskTier,
    messages: list[dict[str, Any]],
    max_tokens: int,
    system: str,
) -> LLMResponse:
    client = _make_client(async_client=True)
    t0 = time.perf_counter()
    completion = await client.chat.completions.create(
        model=_resolve_model_alias(tier),
        messages=_build_messages(system, messages),
        max_tokens=max_tokens,
    )
    return _coerce_response(completion, tier=tier, t0=t0)

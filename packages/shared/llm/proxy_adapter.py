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

LOGGER_NAME = "shared.llm.proxy"
log = logging.getLogger(LOGGER_NAME)

_PROXY_URL_ENV = "LITELLM_PROXY_URL"
_PROXY_MASTER_KEY_ENV = "LITELLM_MASTER_KEY"
_DEFAULT_PROXY_MASTER_KEY = "sk-litellm-master-dev"
_PROXY_BACKEND_NAME = "litellm-proxy"
_MILLISECONDS_PER_SECOND = 1000
_COMPLETION_USAGE_ATTR = "usage"
_COMPLETION_MODEL_ATTR = "model"
_PROMPT_TOKENS_ATTR = "prompt_tokens"
_COMPLETION_TOKENS_ATTR = "completion_tokens"
_MESSAGE_ROLE_KEY = "role"
_MESSAGE_CONTENT_KEY = "content"
_SYSTEM_ROLE = "system"
_HEAVY_TIER_ALIAS = "tier-heavy"
_MEDIUM_TIER_ALIAS = "tier-medium"
_LIGHTWEIGHT_TIER_ALIAS = "tier-lightweight"

_TIER_TO_ALIAS: dict[TaskTier, str] = {
    TaskTier.HEAVY: _HEAVY_TIER_ALIAS,
    TaskTier.MEDIUM: _MEDIUM_TIER_ALIAS,
    TaskTier.LIGHTWEIGHT: _LIGHTWEIGHT_TIER_ALIAS,
}

_PROXY_TIMEOUT_SECONDS = 30.0


def is_proxy_enabled() -> bool:
    return bool(os.getenv(_PROXY_URL_ENV, "").strip())


def _build_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not system:
        return list(messages)
    if messages and messages[0].get(_MESSAGE_ROLE_KEY) == _SYSTEM_ROLE:
        return list(messages)
    return [{_MESSAGE_ROLE_KEY: _SYSTEM_ROLE, _MESSAGE_CONTENT_KEY: system}, *messages]


def _resolve_model_alias(tier: TaskTier) -> str:
    return _TIER_TO_ALIAS.get(tier, _MEDIUM_TIER_ALIAS)


def _make_client(*, async_client: bool):
    base_url = os.environ[_PROXY_URL_ENV].rstrip("/")
    try:
        import openai
    except ImportError as exc:
        raise RuntimeError("openai SDK not installed; cannot use LiteLLM proxy") from exc

    api_key = os.getenv(_PROXY_MASTER_KEY_ENV, _DEFAULT_PROXY_MASTER_KEY)
    if async_client:
        return openai.AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=_PROXY_TIMEOUT_SECONDS)
    return openai.OpenAI(base_url=base_url, api_key=api_key, timeout=_PROXY_TIMEOUT_SECONDS)


def _coerce_response(completion: Any, *, tier: TaskTier, t0: float) -> LLMResponse:
    choice = completion.choices[0]
    text = (getattr(choice.message, _MESSAGE_CONTENT_KEY, "") or "").strip()
    usage = getattr(completion, _COMPLETION_USAGE_ATTR, None)
    input_tokens = int(getattr(usage, _PROMPT_TOKENS_ATTR, 0) or 0)
    output_tokens = int(getattr(usage, _COMPLETION_TOKENS_ATTR, 0) or 0)
    return LLMResponse(
        text=text,
        model=getattr(completion, _COMPLETION_MODEL_ATTR, "") or _resolve_model_alias(tier),
        backend=_PROXY_BACKEND_NAME,
        tier=tier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=(time.perf_counter() - t0) * _MILLISECONDS_PER_SECOND,
    )


def _response_format(response_mode: str, json_schema: dict | None) -> dict[str, Any] | None:
    """프록시(OpenAI 호환)용 response_format. 기존엔 JSON 모드를 통째로 누락했었다."""
    if json_schema is not None:
        from .backends import _normalize_strict_schema

        return {
            "type": "json_schema",
            "json_schema": {"name": "response", "strict": True, "schema": _normalize_strict_schema(json_schema)},
        }
    if response_mode == "json":
        return {"type": "json_object"}
    return None


def call(
    *,
    tier: TaskTier,
    messages: list[dict[str, Any]],
    max_tokens: int,
    system: str,
    response_mode: str = "text",
    json_schema: dict | None = None,
) -> LLMResponse:
    client = _make_client(async_client=False)
    t0 = time.perf_counter()
    kwargs: dict[str, Any] = {
        "model": _resolve_model_alias(tier),
        "messages": _build_messages(system, messages),
        "max_tokens": max_tokens,
    }
    response_format = _response_format(response_mode, json_schema)
    if response_format is not None:
        kwargs["response_format"] = response_format
    completion = client.chat.completions.create(**kwargs)
    return _coerce_response(completion, tier=tier, t0=t0)


async def acall(
    *,
    tier: TaskTier,
    messages: list[dict[str, Any]],
    max_tokens: int,
    system: str,
    response_mode: str = "text",
    json_schema: dict | None = None,
) -> LLMResponse:
    client = _make_client(async_client=True)
    t0 = time.perf_counter()
    kwargs: dict[str, Any] = {
        "model": _resolve_model_alias(tier),
        "messages": _build_messages(system, messages),
        "max_tokens": max_tokens,
    }
    response_format = _response_format(response_mode, json_schema)
    if response_format is not None:
        kwargs["response_format"] = response_format
    completion = await client.chat.completions.create(**kwargs)
    return _coerce_response(completion, tier=tier, t0=t0)

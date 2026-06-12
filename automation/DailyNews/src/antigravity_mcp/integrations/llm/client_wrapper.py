from __future__ import annotations

import hashlib
import json
import logging
import os
from collections import OrderedDict
from pathlib import Path
from typing import Any

from antigravity_mcp.config import emit_metric, get_settings
from antigravity_mcp.integrations.llm.response_parser import is_meta_response
from antigravity_mcp.integrations.llm_providers import (
    call_anthropic,
    call_google_genai,
    call_ollama,
    call_openai,
)
from antigravity_mcp.integrations.shared_llm_resolver import resolve_shared_llm
from antigravity_mcp.state.store import PipelineStateStore
from shared.circuit_breaker import CircuitBreaker
from shared.harness.token_tracker import TokenBudget
from shared.llm import tracing
from shared.llm.models import TaskTier

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Raised when all LLM providers fail and no text could be generated."""


# Per-provider circuit breakers so a single broken provider doesn't block all LLM calls.
_llm_breakers: dict[str, CircuitBreaker] = {
    "shared.llm": CircuitBreaker("llm:shared", failure_threshold=3, cooldown_sec=120),
    "gemini": CircuitBreaker("llm:gemini", failure_threshold=3, cooldown_sec=90),
    "ollama": CircuitBreaker("llm:ollama", failure_threshold=2, cooldown_sec=120),
    "anthropic": CircuitBreaker("llm:anthropic", failure_threshold=3, cooldown_sec=90),
    "openai": CircuitBreaker("llm:openai", failure_threshold=3, cooldown_sec=90),
}

_L1_MAX_SIZE = 128
_L1_CACHE: OrderedDict[str, str] = OrderedDict()
WORKSPACE_SMOKE_USAGE_ENV = "WORKSPACE_SMOKE_USAGE_OUT"


def _initial_meta(cache_scope: str) -> dict[str, Any]:
    return {
        "cache_scope": cache_scope,
        "provider": "",
        "model_name": "",
        "input_tokens": 0,
        "output_tokens": 0,
    }


def _merged_prompt(prompt: str | tuple[str, str]) -> str:
    return f"{prompt[0]}\n\n{prompt[1]}" if isinstance(prompt, tuple) else prompt


def _meta_retry_prompt(prompt: str | tuple[str, str]) -> str | tuple[str, str]:
    instruction = (
        "IMPORTANT: Generate a brand-new news brief using ONLY the articles provided above. "
        "Do NOT reference any previous conversation or report. "
        "Do NOT ask for clarification. Output the brief directly."
    )
    if isinstance(prompt, tuple):
        return prompt[0], f"{instruction}\n\n{prompt[1]}"
    return f"{instruction}\n\n{prompt}"


def _l1_get(key: str) -> str | None:
    if key not in _L1_CACHE:
        return None
    _L1_CACHE.move_to_end(key)
    return _L1_CACHE[key]


def _l1_put(key: str, value: str) -> None:
    _L1_CACHE[key] = value
    _L1_CACHE.move_to_end(key)
    if len(_L1_CACHE) > _L1_MAX_SIZE:
        _L1_CACHE.popitem(last=False)


def _emit_workspace_smoke_usage(meta: dict[str, Any], *, cache_scope: str) -> None:
    out_path = os.getenv(WORKSPACE_SMOKE_USAGE_ENV)
    if not out_path:
        return
    input_tokens = int(meta.get("input_tokens", 0) or 0)
    output_tokens = int(meta.get("output_tokens", 0) or 0)
    cost_value = meta.get("cost_usd")
    cost_usd = float(cost_value) if isinstance(cost_value, (int, float)) and not isinstance(cost_value, bool) else None
    if input_tokens <= 0 and output_tokens <= 0 and cost_usd is None:
        return

    usage: dict[str, int | float] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    if cost_usd is not None and cost_usd >= 0:
        usage["cost_usd"] = round(cost_usd, 6)
    payload = {
        "usage": usage,
        "provider": meta.get("provider", ""),
        "model_name": meta.get("model_name", ""),
        "cache_scope": cache_scope,
    }
    try:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("failed to write workspace smoke usage sidecar: %s", exc)


class LLMClientWrapper:
    def __init__(self, *, state_store: PipelineStateStore | None = None, token_budget: TokenBudget) -> None:
        self.settings = get_settings()
        self._state_store = state_store
        self.token_budget = token_budget

        TaskTier, LLMPolicy, get_llm_client, _ = resolve_shared_llm()
        self._task_tier = getattr(TaskTier, "MEDIUM", None) if TaskTier else None
        self._policy_cls = LLMPolicy
        self._llm_client = None
        try:
            self._llm_client = get_llm_client() if get_llm_client else None
        except Exception as exc:
            logger.error("Failed to initialize shared.llm client: %s — LLM features disabled.", exc)

    @property
    def is_available(self) -> bool:
        return self._llm_client is not None and self._task_tier is not None

    async def generate_text(
        self,
        prompt: str | tuple[str, str],
        *,
        max_tokens: int = 2000,
        cache_scope: str = "generic",
    ) -> tuple[str, dict[str, Any], list[str]]:
        if not self.token_budget.can_afford(500 + max_tokens):
            logger.warning("generate_text aborted: Token budget exceeded.")
            raise LLMUnavailableError("Token budget exceeded")

        system_text = prompt[0] if isinstance(prompt, tuple) else ""
        user_text = prompt[1] if isinstance(prompt, tuple) else prompt
        with tracing.start_span(
            tier=self._task_tier or TaskTier.MEDIUM,
            system=system_text,
            messages=[{"role": "user", "content": user_text}],
            dispatcher=f"dailynews.{cache_scope}",
        ) as span:
            text, meta, warnings = await self._complete_text(
                prompt=prompt,
                max_tokens=max_tokens,
                cache_scope=cache_scope,
            )
            span.record_text(
                text=text,
                model=str(meta.get("model_name", "")),
                backend=str(meta.get("provider", "") or "unknown"),
                input_tokens=int(meta.get("input_tokens", 0) or 0),
                output_tokens=int(meta.get("output_tokens", 0) or 0),
            )
            return text, meta, warnings

    async def _complete_text(
        self,
        *,
        prompt: str | tuple[str, str],
        max_tokens: int,
        cache_scope: str,
    ) -> tuple[str, dict[str, Any], list[str]]:
        warnings: list[str] = []
        prompt_hash = self._build_prompt_hash(prompt=prompt, cache_scope=cache_scope)
        meta = _initial_meta(cache_scope)

        cached = self._cached_text(prompt_hash, meta)
        if cached is not None:
            return cached, meta, warnings

        text = await self._generate_uncached_text(prompt=prompt, max_tokens=max_tokens, meta=meta, warnings=warnings)

        if not text:
            logger.error("All LLM providers failed for cache_scope=%s", cache_scope)
            raise LLMUnavailableError(
                f"All LLM providers failed for scope '{cache_scope}'. Check API keys and provider availability."
            )

        text = await self._retry_meta_response(
            text=text,
            prompt=prompt,
            max_tokens=max_tokens,
            cache_scope=cache_scope,
            meta=meta,
            warnings=warnings,
        )
        self._record_success(prompt_hash=prompt_hash, text=text, meta=meta, cache_scope=cache_scope)

        return text, meta, warnings

    def _cached_text(self, prompt_hash: str, meta: dict[str, Any]) -> str | None:
        cached = _l1_get(prompt_hash)
        if cached is not None:
            if self._state_store is not None:
                self._state_store.increment_llm_cache_hits(prompt_hash)
            meta["provider"] = "l1-cache"
            return cached

        if self._state_store is None:
            return None
        cached_text = self._state_store.get_cached_llm_response(prompt_hash)
        if cached_text:
            _l1_put(prompt_hash, cached_text)
            meta["provider"] = "sqlite-cache"
            return cached_text
        return None

    async def _generate_uncached_text(
        self,
        *,
        prompt: str | tuple[str, str],
        max_tokens: int,
        meta: dict[str, Any],
        warnings: list[str],
    ) -> str | None:
        text = await self._try_shared_llm(prompt=prompt, max_tokens=max_tokens, meta=meta, warnings=warnings)
        if text:
            return text
        return await self._try_fallback_providers(_merged_prompt(prompt), meta, warnings)

    async def _retry_meta_response(
        self,
        *,
        text: str,
        prompt: str | tuple[str, str],
        max_tokens: int,
        cache_scope: str,
        meta: dict[str, Any],
        warnings: list[str],
    ) -> str:
        if not is_meta_response(text):
            return text

        logger.warning(
            "Meta-response detected for scope=%s (provider=%s); retrying with explicit context.",
            cache_scope,
            meta.get("provider"),
        )
        warnings.append(f"meta_response_detected:{cache_scope}; retrying")
        meta2 = dict(meta)
        retry_prompt = _meta_retry_prompt(prompt)
        retry_text = await self._generate_uncached_text(
            prompt=retry_prompt,
            max_tokens=max_tokens,
            meta=meta2,
            warnings=warnings,
        )
        if retry_text and not is_meta_response(retry_text):
            meta.update(meta2)
            warnings.append("meta_response_retry_succeeded")
            return retry_text
        return text

    def _record_success(self, *, prompt_hash: str, text: str, meta: dict[str, Any], cache_scope: str) -> None:
        if self._state_store is not None:
            self._state_store.put_llm_cache(
                prompt_hash,
                text,
                model_name=str(meta["model_name"]),
                input_tokens=int(meta["input_tokens"]),
                output_tokens=int(meta["output_tokens"]),
            )
        _l1_put(prompt_hash, text)
        emit_metric(
            "llm_call",
            provider=meta["provider"],
            model=meta["model_name"],
            cache_scope=cache_scope,
            input_tokens=meta["input_tokens"],
            output_tokens=meta["output_tokens"],
        )
        _emit_workspace_smoke_usage(meta, cache_scope=cache_scope)

        total_tokens = meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
        if total_tokens > 0:
            self.token_budget.record(
                tool_name=f"llm_{cache_scope.split(':')[0]}",
                tokens=total_tokens,
                detail_level=self.token_budget.get_detail_level().value,
            )

    async def _try_shared_llm(
        self,
        *,
        prompt: str | tuple[str, str],
        max_tokens: int,
        meta: dict[str, Any],
        warnings: list[str],
    ) -> str | None:
        if not self._llm_client or not self._task_tier or not self._policy_cls:
            return None
        if not _llm_breakers["shared.llm"].allow_request():
            warnings.append("shared.llm_circuit_open")
            return None

        try:
            policy = self._policy_cls()
            messages = (
                [{"role": "user", "content": prompt}]
                if isinstance(prompt, str)
                else [{"role": "user", "content": prompt[1]}]
            )
            system_text = prompt[0] if isinstance(prompt, tuple) else ""
            rs = await self._llm_client.acreate(
                tier=self._task_tier,
                messages=messages,
                max_tokens=max_tokens,
                system=system_text,
                policy=policy,
            )
            _llm_breakers["shared.llm"].record_success()
            meta["provider"] = "shared.llm"
            meta["model_name"] = rs.model
            meta["input_tokens"] = rs.input_tokens
            meta["output_tokens"] = rs.output_tokens
            return rs.text
        except Exception as exc:
            _llm_breakers["shared.llm"].record_failure()
            logger.warning("shared.llm execution failed: %s", exc)
            warnings.append(f"shared.llm_failed:{type(exc).__name__}")
            return None

    async def _try_fallback_providers(self, prompt: str, meta: dict[str, Any], warnings: list[str]) -> str | None:
        # Resolve API keys from environment for each fallback provider
        _PROVIDER_KEY_MAP = {
            "gemini": os.getenv("GOOGLE_API_KEY", ""),
            "ollama": "local",  # No API key required for local Ollama
            "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
            "openai": os.getenv("OPENAI_API_KEY", ""),
        }
        clients = [
            ("gemini", call_google_genai),
            ("anthropic", call_anthropic),
            ("openai", call_openai),
            ("ollama", call_ollama),
        ]
        for provider_name, call_fn in clients:
            api_key = _PROVIDER_KEY_MAP.get(provider_name, "")
            if not api_key:
                logger.debug("Fallback provider %s skipped: no API key configured", provider_name)
                continue
            if not _llm_breakers[provider_name].allow_request():
                continue
            try:
                result = await call_fn(prompt, api_key)
                if not result:
                    _llm_breakers[provider_name].record_failure()
                    logger.warning("Fallback provider %s returned no text", provider_name)
                    warnings.append(f"{provider_name}_fallback_empty")
                    continue
                _llm_breakers[provider_name].record_success()
                meta["provider"] = provider_name
                meta["model_name"] = "fallback_model"
                return result
            except Exception as exc:
                _llm_breakers[provider_name].record_failure()
                logger.warning("Fallback provider %s failed: %s", provider_name, exc)
                warnings.append(f"{provider_name}_fallback_failed")
        return None

    def _build_prompt_hash(self, *, prompt: str | tuple[str, str], cache_scope: str) -> str:
        prompt_text = f"{prompt[0]}\n{prompt[1]}" if isinstance(prompt, tuple) else prompt
        raw = json.dumps(
            {"prompt": prompt_text, "scope": cache_scope},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from typing import Any

from antigravity_mcp.config import emit_metric, get_settings
from antigravity_mcp.integrations.llm_providers import (
    call_anthropic,
    call_google_genai,
    call_openai,
)
from shared.circuit_breaker import CircuitBreaker
from shared.harness.token_tracker import TokenBudget
from antigravity_mcp.integrations.shared_llm_resolver import resolve_shared_llm
from antigravity_mcp.state.store import PipelineStateStore
from antigravity_mcp.integrations.llm.response_parser import is_meta_response

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Raised when all LLM providers fail and no text could be generated."""


# Per-provider circuit breakers so a single broken provider doesn't block all LLM calls.
_llm_breakers: dict[str, CircuitBreaker] = {
    "shared.llm": CircuitBreaker("llm:shared", failure_threshold=3, cooldown_sec=120),
    "gemini": CircuitBreaker("llm:gemini", failure_threshold=3, cooldown_sec=90),
    "anthropic": CircuitBreaker("llm:anthropic", failure_threshold=3, cooldown_sec=90),
    "openai": CircuitBreaker("llm:openai", failure_threshold=3, cooldown_sec=90),
}

_L1_MAX_SIZE = 128
_L1_CACHE: OrderedDict[str, str] = OrderedDict()


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
        temperature: float = 0.7,
        cache_scope: str = "generic",
    ) -> tuple[str, dict[str, Any], list[str]]:
        if not self.token_budget.can_afford(500 + max_tokens):
            logger.warning("generate_text aborted: Token budget exceeded.")
            raise LLMUnavailableError("Token budget exceeded")

        return await self._complete_text(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            cache_scope=cache_scope,
        )

    async def _complete_text(
        self,
        *,
        prompt: str | tuple[str, str],
        max_tokens: int,
        temperature: float,
        cache_scope: str,
    ) -> tuple[str, dict[str, Any], list[str]]:
        warnings: list[str] = []
        prompt_hash = self._build_prompt_hash(prompt=prompt, cache_scope=cache_scope)
        meta: dict[str, Any] = {
            "cache_scope": cache_scope,
            "provider": "",
            "model_name": "",
            "input_tokens": 0,
            "output_tokens": 0,
        }

        cached = _l1_get(prompt_hash)
        if cached is not None:
            if self._state_store is not None:
                self._state_store.increment_llm_cache_hits(prompt_hash)
            meta["provider"] = "l1-cache"
            return cached, meta, warnings

        if self._state_store is not None:
            cached_text = self._state_store.get_cached_llm_response(prompt_hash)
            if cached_text:
                _l1_put(prompt_hash, cached_text)
                meta["provider"] = "sqlite-cache"
                return cached_text, meta, warnings

        text = await self._try_shared_llm(
            prompt=prompt, max_tokens=max_tokens, temperature=temperature, meta=meta, warnings=warnings
        )
        if not text:
            merged_prompt = f"{prompt[0]}\n\n{prompt[1]}" if isinstance(prompt, tuple) else prompt
            text = await self._try_fallback_providers(merged_prompt, meta, warnings)

        if not text:
            logger.error("All LLM providers failed for cache_scope=%s", cache_scope)
            raise LLMUnavailableError(
                f"All LLM providers failed for scope '{cache_scope}'. "
                "Check API keys and provider availability."
            )

        if is_meta_response(text):
            logger.warning(
                "Meta-response detected for scope=%s (provider=%s); retrying with explicit context.",
                cache_scope, meta.get("provider"),
            )
            warnings.append(f"meta_response_detected:{cache_scope}; retrying")
            meta2: dict[str, Any] = {k: v for k, v in meta.items()}
            merged_prompt_retry = (
                f"{prompt[0]}\n\n"
                "IMPORTANT: Generate a brand-new news brief using ONLY the articles provided above. "
                "Do NOT reference any previous conversation or report. "
                "Do NOT ask for clarification. Output the brief directly.\n\n"
                f"{prompt[1]}"
                if isinstance(prompt, tuple)
                else (
                    "IMPORTANT: Generate a brand-new news brief using ONLY the articles provided above. "
                    "Do NOT reference any previous conversation or report. "
                    "Do NOT ask for clarification. Output the brief directly.\n\n"
                    + prompt
                )
            )
            retry_text = await self._try_shared_llm(
                prompt=merged_prompt_retry if isinstance(prompt, str) else (prompt[0], merged_prompt_retry.split("\n\n", 1)[-1]),
                max_tokens=max_tokens, temperature=temperature, meta=meta2, warnings=warnings,
            )
            if not retry_text:
                merged = merged_prompt_retry if isinstance(merged_prompt_retry, str) else "\n\n".join(merged_prompt_retry)
                retry_text = await self._try_fallback_providers(merged, meta2, warnings)
            if retry_text and not is_meta_response(retry_text):
                text = retry_text
                meta.update(meta2)
                warnings.append("meta_response_retry_succeeded")

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

        total_tokens = meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
        if total_tokens > 0:
            self.token_budget.record(
                tool_name=f"llm_{cache_scope.split(':')[0]}",
                tokens=total_tokens,
                detail_level=self.token_budget.get_detail_level().value
            )

        return text, meta, warnings

    async def _try_shared_llm(
        self,
        *,
        prompt: str | tuple[str, str],
        max_tokens: int,
        temperature: float,
        meta: dict[str, Any],
        warnings: list[str],
    ) -> str | None:
        if not self._llm_client or not self._task_tier or not self._policy_cls:
            return None
        if not _llm_breakers["shared.llm"].allow_request():
            warnings.append("shared.llm_circuit_open")
            return None

        try:
            policy = self._policy_cls(tier=self._task_tier, temperature=temperature, max_tokens=max_tokens)
            if isinstance(prompt, tuple):
                rs = await self._llm_client.generate_with_policy(
                    system_prompt=prompt[0], user_prompt=prompt[1], policy=policy
                )
            else:
                rs = await self._llm_client.generate_with_policy(user_prompt=prompt, policy=policy)
            _llm_breakers["shared.llm"].record_success()
            meta["provider"] = "shared.llm"
            meta["model_name"] = rs.model_name
            meta["input_tokens"] = rs.input_tokens
            meta["output_tokens"] = rs.output_tokens
            return rs.text
        except Exception as exc:
            _llm_breakers["shared.llm"].record_failure()
            logger.warning("shared.llm execution failed: %s", exc)
            warnings.append(f"shared.llm_failed:{type(exc).__name__}")
            return None

    async def _try_fallback_providers(
        self, prompt: str, meta: dict[str, Any], warnings: list[str]
    ) -> str | None:
        clients = [
            ("gemini", call_google_genai),
            ("anthropic", call_anthropic),
            ("openai", call_openai),
        ]
        for provider_name, call_fn in clients:
            if not _llm_breakers[provider_name].allow_request():
                continue
            try:
                result = await call_fn(prompt)
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

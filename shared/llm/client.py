"""shared.llm.client - Unified LLM client with tier-based routing and fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Optional

from .backends import BackendManager
from .config import FALLBACK_ERRORS, MODEL_TO_TIER, get_routing_chain, load_keys
from .language_bridge import (
    inspect_response,
    merge_bridge_meta,
    normalize_policy,
    prepare_request,
    should_retry_after_quality_gate,
)
from .models import BridgeMeta, LLMPolicy, LLMResponse, TaskTier
from .stats import CostTracker

log = logging.getLogger("shared.llm")

_FAIL_TTL = 300
_CACHE_TTL: dict[str, int] = {
    "lightweight": 60,   # real-time data like trends — short TTL
    "medium": 180,
    "heavy": 600,        # deep analysis — worth reusing longer
}
_CACHE_MAX = 128

_failed_backends: dict[TaskTier, dict[str, float]] = {
    TaskTier.LIGHTWEIGHT: {},
    TaskTier.MEDIUM: {},
    TaskTier.HEAVY: {},
}

_response_cache: dict[str, tuple[LLMResponse, float]] = {}


def _is_failed(tier: TaskTier, backend: str) -> bool:
    ts = _failed_backends[tier].get(backend)
    if ts is None:
        return False
    if time.monotonic() - ts > _FAIL_TTL:
        del _failed_backends[tier][backend]
        return False
    return True


def _mark_failed(tier: TaskTier, backend: str) -> None:
    _failed_backends[tier][backend] = time.monotonic()


def _should_fallback(error: Exception) -> bool:
    msg = str(error).lower()
    return any(pattern in msg for pattern in FALLBACK_ERRORS)


def _make_cache_key(
    tier: TaskTier,
    messages: list[dict],
    system: str,
    policy: LLMPolicy,
) -> str:
    raw = json.dumps(
        {
            "t": tier.value,
            "s": system,
            "m": messages,
            "policy": {
                "locale": policy.locale,
                "input_language": policy.input_language,
                "output_language": policy.output_language,
                "task_kind": policy.task_kind,
                "enforce_korean_output": policy.enforce_korean_output,
                "allow_source_quotes": policy.allow_source_quotes,
                "preserve_terms": policy.preserve_terms,
                "response_mode": policy.response_mode,
            },
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _get_cache_ttl(tier: TaskTier) -> int:
    return _CACHE_TTL.get(tier.value, 180)


def _get_cached(key: str, tier: TaskTier) -> LLMResponse | None:
    entry = _response_cache.get(key)
    if entry is None:
        return None
    resp, ts = entry
    if time.monotonic() - ts > _get_cache_ttl(tier):
        del _response_cache[key]
        return None
    log.debug("Cache HIT: %s...", key[:8])
    return resp


def _put_cache(key: str, resp: LLMResponse) -> None:
    if len(_response_cache) >= _CACHE_MAX:
        oldest_key = next(iter(_response_cache))
        del _response_cache[oldest_key]
    _response_cache[key] = (resp, time.monotonic())


class LLMClient:
    """Unified LLM client with task-aware routing and Korean-first language controls."""

    def __init__(self, **key_overrides: str) -> None:
        keys = load_keys()
        keys.update({k: v for k, v in key_overrides.items() if v})
        self._backends = BackendManager(keys)
        if not self._backends.has_any_key():
            raise ValueError(
                "No LLM API keys configured. "
                "Set at least one key (ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY, etc.) "
                "in your .env file."
            )
        self._tracker = CostTracker()
        self._bridge_metrics = {
            "bridge_calls": 0,
            "bridge_passes": 0,
            "bridge_fallbacks": 0,
            "deepseek_calls": 0,
            "deepseek_repairs": 0,
            "structured_parse_failures": 0,
            "task_latency_totals": {},
            "task_call_counts": {},
        }

    def _resolve_tier(self, tier: Optional[TaskTier], model: Optional[str]) -> TaskTier:
        if tier is not None:
            return tier
        if model and model in MODEL_TO_TIER:
            return MODEL_TO_TIER[model]
        return TaskTier.MEDIUM

    def create(
        self,
        *,
        tier: Optional[TaskTier] = None,
        model: Optional[str] = None,
        messages: list[dict],
        max_tokens: int = 1000,
        system: str = "",
        policy: Optional[LLMPolicy] = None,
    ) -> LLMResponse:
        resolved_tier = self._resolve_tier(tier, model)
        resolved_policy = normalize_policy(policy)
        cache_key = _make_cache_key(resolved_tier, messages, system, resolved_policy)
        cached = _get_cached(cache_key, resolved_tier)
        if cached is not None:
            return cached

        response = self._dispatch(
            resolved_tier=resolved_tier,
            messages=messages,
            max_tokens=max_tokens,
            system=system,
            policy=resolved_policy,
            async_mode=False,
        )
        _put_cache(cache_key, response)
        return response

    async def acreate(
        self,
        *,
        tier: Optional[TaskTier] = None,
        model: Optional[str] = None,
        messages: list[dict],
        max_tokens: int = 1000,
        system: str = "",
        policy: Optional[LLMPolicy] = None,
    ) -> LLMResponse:
        resolved_tier = self._resolve_tier(tier, model)
        resolved_policy = normalize_policy(policy)
        return await self._dispatch(
            resolved_tier=resolved_tier,
            messages=messages,
            max_tokens=max_tokens,
            system=system,
            policy=resolved_policy,
            async_mode=True,
        )

    def get_stats(self) -> dict:
        s = self._tracker.get_stats()
        bridge_calls = max(self._bridge_metrics["bridge_calls"], 1)
        deepseek_calls = max(self._bridge_metrics["deepseek_calls"], 1)
        per_task_latency = {}
        for task_kind, total in self._bridge_metrics["task_latency_totals"].items():
            calls = self._bridge_metrics["task_call_counts"].get(task_kind, 1)
            per_task_latency[task_kind] = round(total / max(calls, 1), 1)
        return {
            "total_calls": s.total_calls,
            "total_errors": s.total_errors,
            "success_rate": s.success_rate,
            "total_cost_usd": s.total_cost_usd,
            "calls_by_backend": s.calls_by_backend,
            "calls_by_tier": s.calls_by_tier,
            "cost_by_backend": s.cost_by_backend,
            "ko_output_pass_rate": round(self._bridge_metrics["bridge_passes"] / bridge_calls * 100, 1),
            "bridge_fallback_rate": round(self._bridge_metrics["bridge_fallbacks"] / bridge_calls * 100, 1),
            "deepseek_usage_rate": round(self._bridge_metrics["deepseek_calls"] / max(s.total_calls, 1) * 100, 1),
            "deepseek_to_non_deepseek_repair_rate": round(
                self._bridge_metrics["deepseek_repairs"] / deepseek_calls * 100, 1
            ),
            "structured_parse_fail_rate": round(
                self._bridge_metrics["structured_parse_failures"] / bridge_calls * 100, 1
            ),
            "per_task_latency_ms": per_task_latency,
        }

    @staticmethod
    def reset() -> None:
        for tier in _failed_backends:
            _failed_backends[tier].clear()
        _response_cache.clear()

    @property
    def backend(self) -> str:
        stats = self._tracker.get_stats()
        if stats.calls_by_backend:
            return max(stats.calls_by_backend, key=stats.calls_by_backend.get)  # type: ignore[arg-type]
        return "none"

    def _record_bridge_attempt(self, response: LLMResponse, policy: LLMPolicy) -> None:
        if response.bridge_meta.bridge_applied:
            self._bridge_metrics["bridge_calls"] += 1
        if response.backend == "deepseek":
            self._bridge_metrics["deepseek_calls"] += 1
        if "json_invalid" in response.bridge_meta.quality_flags:
            self._bridge_metrics["structured_parse_failures"] += 1
        if response.bridge_meta.bridge_applied and not response.bridge_meta.quality_flags:
            self._bridge_metrics["bridge_passes"] += 1

        task_kind = policy.task_kind or "generic"
        self._bridge_metrics["task_latency_totals"][task_kind] = (
            self._bridge_metrics["task_latency_totals"].get(task_kind, 0.0) + response.latency_ms
        )
        self._bridge_metrics["task_call_counts"][task_kind] = (
            self._bridge_metrics["task_call_counts"].get(task_kind, 0) + 1
        )

    def _finalize_success(
        self,
        *,
        response: LLMResponse,
        backend_name: str,
        rejected_meta: BridgeMeta | None,
        repaired_from_deepseek: bool,
    ) -> LLMResponse:
        if rejected_meta is not None:
            response.bridge_meta = merge_bridge_meta(rejected_meta, response.bridge_meta)
        if repaired_from_deepseek and backend_name != "deepseek":
            self._bridge_metrics["deepseek_repairs"] += 1
        return response

    def _iter_chain(self, resolved_tier: TaskTier, policy: LLMPolicy) -> list[tuple[str, str]]:
        return get_routing_chain(resolved_tier, policy)

    def _record_failure(
        self,
        *,
        resolved_tier: TaskTier,
        backend_name: str,
        default_model: str,
        elapsed_ms: float,
        error: Exception,
    ) -> Exception:
        self._tracker.record(
            backend=backend_name,
            model=default_model,
            tier=resolved_tier,
            success=False,
            error=str(error),
        )
        if _should_fallback(error):
            _mark_failed(resolved_tier, backend_name)
            log.warning(
                f"[{resolved_tier.value}] {backend_name}/{default_model} failed "
                f"({elapsed_ms:.0f}ms) -> fallback: {error}"
        )
        return error

    def _record_success_usage(
        self,
        *,
        resolved_tier: TaskTier,
        backend_name: str,
        default_model: str,
        response: LLMResponse,
    ) -> None:
        rec = self._tracker.record(
            backend=backend_name,
            model=default_model,
            tier=resolved_tier,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            success=True,
        )
        response.cost_usd = rec.cost_usd

    def _dispatch(
        self,
        *,
        resolved_tier: TaskTier,
        messages: list[dict],
        max_tokens: int,
        system: str,
        policy: LLMPolicy,
        async_mode: bool,
    ):
        chain = self._iter_chain(resolved_tier, policy)
        last_error: Optional[Exception] = None
        rejected_meta: Optional[BridgeMeta] = None
        repaired_from_deepseek = False

        if async_mode:
            return self._dispatch_async(
                chain=chain,
                resolved_tier=resolved_tier,
                messages=messages,
                max_tokens=max_tokens,
                system=system,
                policy=policy,
                rejected_meta=rejected_meta,
                repaired_from_deepseek=repaired_from_deepseek,
                last_error=last_error,
            )

        for backend_name, default_model in chain:
            if _is_failed(resolved_tier, backend_name) or not self._backends.has_key(backend_name):
                continue

            wrapped_system, wrapped_messages, request_meta, resolved_policy = prepare_request(
                system, messages, policy, backend_name
            )
            t0 = time.perf_counter()
            try:
                response = self._backends.call(
                    backend=backend_name,
                    model=default_model,
                    messages=wrapped_messages,
                    max_tokens=max_tokens,
                    system=wrapped_system,
                    tier=resolved_tier,
                    response_mode=policy.response_mode,
                )
                response.latency_ms = (time.perf_counter() - t0) * 1000
                response.policy = resolved_policy
                self._record_success_usage(
                    resolved_tier=resolved_tier,
                    backend_name=backend_name,
                    default_model=default_model,
                    response=response,
                )
                response.bridge_meta = inspect_response(response.text, resolved_policy, request_meta)
                self._record_bridge_attempt(response, resolved_policy)
                if should_retry_after_quality_gate(backend_name, resolved_policy, response.bridge_meta):
                    self._bridge_metrics["bridge_fallbacks"] += 1
                    rejected = BridgeMeta(
                        bridge_applied=response.bridge_meta.bridge_applied,
                        detected_input_language=response.bridge_meta.detected_input_language,
                        detected_output_language=response.bridge_meta.detected_output_language,
                        quality_flags=list(response.bridge_meta.quality_flags),
                        fallback_reason="deepseek_quality_gate_failed",
                    )
                    rejected_meta = rejected if rejected_meta is None else merge_bridge_meta(rejected_meta, rejected)
                    repaired_from_deepseek = repaired_from_deepseek or backend_name == "deepseek"
                    last_error = RuntimeError(
                        f"Language bridge rejected {backend_name}/{default_model}: {response.bridge_meta.quality_flags}"
                    )
                    log.warning(str(last_error))
                    continue
                return self._finalize_success(
                    response=response,
                    backend_name=backend_name,
                    rejected_meta=rejected_meta,
                    repaired_from_deepseek=repaired_from_deepseek,
                )
            except Exception as error:
                elapsed = (time.perf_counter() - t0) * 1000
                last_error = self._record_failure(
                    resolved_tier=resolved_tier,
                    backend_name=backend_name,
                    default_model=default_model,
                    elapsed_ms=elapsed,
                    error=error,
                )
                if _should_fallback(error):
                    continue
                raise

        raise RuntimeError(
            f"All backends failed for tier={resolved_tier.value}. Last error: {last_error}"
        )

    async def _dispatch_async(
        self,
        *,
        chain: list[tuple[str, str]],
        resolved_tier: TaskTier,
        messages: list[dict],
        max_tokens: int,
        system: str,
        policy: LLMPolicy,
        rejected_meta: BridgeMeta | None,
        repaired_from_deepseek: bool,
        last_error: Optional[Exception],
    ) -> LLMResponse:
        for backend_name, default_model in chain:
            if _is_failed(resolved_tier, backend_name) or not self._backends.has_key(backend_name):
                continue

            wrapped_system, wrapped_messages, request_meta, resolved_policy = prepare_request(
                system, messages, policy, backend_name
            )
            t0 = time.perf_counter()
            try:
                response = await self._backends.acall(
                    backend=backend_name,
                    model=default_model,
                    messages=wrapped_messages,
                    max_tokens=max_tokens,
                    system=wrapped_system,
                    tier=resolved_tier,
                    response_mode=policy.response_mode,
                )
                response.latency_ms = (time.perf_counter() - t0) * 1000
                response.policy = resolved_policy
                self._record_success_usage(
                    resolved_tier=resolved_tier,
                    backend_name=backend_name,
                    default_model=default_model,
                    response=response,
                )
                response.bridge_meta = inspect_response(response.text, resolved_policy, request_meta)
                self._record_bridge_attempt(response, resolved_policy)
                if should_retry_after_quality_gate(backend_name, resolved_policy, response.bridge_meta):
                    self._bridge_metrics["bridge_fallbacks"] += 1
                    rejected = BridgeMeta(
                        bridge_applied=response.bridge_meta.bridge_applied,
                        detected_input_language=response.bridge_meta.detected_input_language,
                        detected_output_language=response.bridge_meta.detected_output_language,
                        quality_flags=list(response.bridge_meta.quality_flags),
                        fallback_reason="deepseek_quality_gate_failed",
                    )
                    rejected_meta = rejected if rejected_meta is None else merge_bridge_meta(rejected_meta, rejected)
                    repaired_from_deepseek = repaired_from_deepseek or backend_name == "deepseek"
                    last_error = RuntimeError(
                        f"Language bridge rejected {backend_name}/{default_model}: {response.bridge_meta.quality_flags}"
                    )
                    log.warning(str(last_error))
                    continue
                return self._finalize_success(
                    response=response,
                    backend_name=backend_name,
                    rejected_meta=rejected_meta,
                    repaired_from_deepseek=repaired_from_deepseek,
                )
            except Exception as error:
                elapsed = (time.perf_counter() - t0) * 1000
                last_error = self._record_failure(
                    resolved_tier=resolved_tier,
                    backend_name=backend_name,
                    default_model=default_model,
                    elapsed_ms=elapsed,
                    error=error,
                )
                if _should_fallback(error):
                    continue
                raise

        raise RuntimeError(
            f"All backends failed for tier={resolved_tier.value}. Last error: {last_error}"
        )

"""shared.llm.client - Unified LLM client with tier-based routing and fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any

from .backends import BackendManager
from .config import (
    FALLBACK_ERRORS,
    LLM_BUDGET_DOWNGRADE_HEAVY,
    LLM_BUDGET_DOWNGRADE_MEDIUM,
    MODEL_TO_TIER,
    get_routing_chain,
    load_keys,
)
from .errors import classify_error, should_fallback_to_next_backend
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
    "lightweight": 60,  # real-time data like trends — short TTL
    "medium": 180,
    "heavy": 600,  # deep analysis — worth reusing longer
}
_CACHE_MAX = 128

_failed_backends: dict[TaskTier, dict[str, float]] = {
    TaskTier.LIGHTWEIGHT: {},
    TaskTier.MEDIUM: {},
    TaskTier.HEAVY: {},
}

# BUG-002 fix: thread-safe lock for all mutable global state
_cache_lock = threading.Lock()

# BUG-010 fix: LRU-style OrderedDict (most recently used move to end)
_response_cache: OrderedDict[str, tuple[LLMResponse, float]] = OrderedDict()


def _is_failed(tier: TaskTier, backend: str) -> bool:
    with _cache_lock:
        ts = _failed_backends[tier].get(backend)
        if ts is None:
            return False
        if time.monotonic() - ts > _FAIL_TTL:
            del _failed_backends[tier][backend]
            return False
        return True


def _mark_failed(tier: TaskTier, backend: str) -> None:
    with _cache_lock:
        _failed_backends[tier][backend] = time.monotonic()


def _should_fallback(error: Exception) -> bool:
    # Primary: structured error classification (GiniGen-inspired)
    if should_fallback_to_next_backend(error):
        return True
    # Legacy fallback: string pattern matching (backward compat)
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
    # BUG-020 fix: SHA-256 instead of MD5 for cache key integrity
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _get_cache_ttl(tier: TaskTier) -> int:
    return _CACHE_TTL.get(tier.value, 180)


def _get_cached(key: str, tier: TaskTier) -> LLMResponse | None:
    with _cache_lock:
        entry = _response_cache.get(key)
        if entry is None:
            return None
        resp, ts = entry
        if time.monotonic() - ts > _get_cache_ttl(tier):
            del _response_cache[key]
            return None
        # BUG-010 fix: LRU — move accessed key to end
        _response_cache.move_to_end(key)
        log.debug("Cache HIT: %s...", key[:8])
        return resp


def _purge_expired_cache() -> None:
    """Remove all TTL-expired entries to prevent stale memory accumulation."""
    now = time.monotonic()
    expired = [k for k, (_, ts) in _response_cache.items() if now - ts > _CACHE_TTL_HEAVY]
    for k in expired:
        del _response_cache[k]


def _put_cache(key: str, resp: LLMResponse) -> None:
    with _cache_lock:
        # M-11 fix: 주기적으로 만료 엔트리 퍼지
        if len(_response_cache) >= _CACHE_MAX:
            _purge_expired_cache()
        if key in _response_cache:
            _response_cache.move_to_end(key)
            _response_cache[key] = (resp, time.monotonic())
            return
        if len(_response_cache) >= _CACHE_MAX:
            _response_cache.popitem(last=False)
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

    def _resolve_tier(self, tier: TaskTier | None, model: str | None) -> TaskTier:
        if tier is not None:
            resolved = tier
        elif model and model in MODEL_TO_TIER:
            resolved = MODEL_TO_TIER[model]
        else:
            resolved = TaskTier.MEDIUM
        return self._budget_downgrade(resolved)

    def _budget_downgrade(self, tier: TaskTier) -> TaskTier:
        """Downgrade tier when daily cost approaches budget limits."""
        if tier == TaskTier.LIGHTWEIGHT:
            return tier
        try:
            today_cost = self._tracker.get_today_cost()
        except Exception:
            return tier
        if tier == TaskTier.HEAVY and today_cost >= LLM_BUDGET_DOWNGRADE_HEAVY:
            log.info("Budget downgrade: HEAVY→MEDIUM (today=$%.4f >= $%.2f)", today_cost, LLM_BUDGET_DOWNGRADE_HEAVY)
            return TaskTier.MEDIUM
        if tier == TaskTier.MEDIUM and today_cost >= LLM_BUDGET_DOWNGRADE_MEDIUM:
            log.info(
                "Budget downgrade: MEDIUM→LIGHTWEIGHT (today=$%.4f >= $%.2f)", today_cost, LLM_BUDGET_DOWNGRADE_MEDIUM
            )
            return TaskTier.LIGHTWEIGHT
        return tier

    def create(
        self,
        *,
        tier: TaskTier | None = None,
        model: str | None = None,
        messages: list[dict],
        max_tokens: int = 1000,
        system: str = "",
        policy: LLMPolicy | None = None,
    ) -> LLMResponse:
        from pathlib import Path

        lock_file = Path(__file__).resolve().parents[0] / "data" / "RATE_LIMIT.lock"
        if lock_file.exists():
            raise RuntimeError("Rate Limit Exceeded: Daily budget reached. API request blocked by FinOps Dashboard.")

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
        tier: TaskTier | None = None,
        model: str | None = None,
        messages: list[dict],
        max_tokens: int = 1000,
        system: str = "",
        policy: LLMPolicy | None = None,
    ) -> LLMResponse:
        from pathlib import Path

        lock_file = Path(__file__).resolve().parents[0] / "data" / "RATE_LIMIT.lock"
        if lock_file.exists():
            raise RuntimeError("Rate Limit Exceeded: Daily budget reached. API request blocked by FinOps Dashboard.")

        resolved_tier = self._resolve_tier(tier, model)
        resolved_policy = normalize_policy(policy)

        # BUG-004 fix: Apply cache to acreate() (was only on sync create())
        cache_key = _make_cache_key(resolved_tier, messages, system, resolved_policy)
        cached = _get_cached(cache_key, resolved_tier)
        if cached is not None:
            return cached

        response = await self._dispatch(
            resolved_tier=resolved_tier,
            messages=messages,
            max_tokens=max_tokens,
            system=system,
            policy=resolved_policy,
            async_mode=True,
        )
        _put_cache(cache_key, response)
        return response

    def get_stats(self) -> dict[str, Any]:
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

    def close(self) -> None:
        """Release tracker resources held by the singleton client."""
        try:
            self._tracker.close()
        except Exception:
            pass

    @staticmethod
    def reset() -> None:
        with _cache_lock:
            for tier in _failed_backends:
                _failed_backends[tier].clear()
            _response_cache.clear()

    def create_with_reasoning(
        self,
        *,
        tier: TaskTier | None = None,
        messages: list[dict],
        max_tokens: int = 2000,
        system: str = "",
        policy: LLMPolicy | None = None,
        force_strategy: str | None = None,
    ) -> LLMResponse:
        """Create a response with automatic reasoning strategy selection.

        Uses SmartRouter to analyze query complexity and apply the
        optimal reasoning strategy (direct, SAGE, CoT, or FoT).

        This is the enhanced version of create() — use when the query
        may benefit from deeper reasoning. For simple/known tasks,
        continue using create() directly.

        Args:
            force_strategy: Override auto-routing. Options: "direct",
                "sage", "cot", "fot". If None, auto-selects.

        Returns:
            LLMResponse with additional reasoning metadata in bridge_meta.
        """
        from .reasoning.smart_router import SmartRouter

        router = SmartRouter(self)
        result = router.route_and_reason(
            messages=messages,
            system=system,
            policy=policy,
            tier=tier,
            max_tokens=max_tokens,
            force_strategy=force_strategy,
        )

        # Wrap ReasoningResult back into an LLMResponse for compatibility
        response = LLMResponse(
            text=result.text,
            model=f"reasoning:{result.strategy_used}",
            backend=f"reasoning:{result.complexity.value}",
            tier=tier or TaskTier.MEDIUM,
            cost_usd=result.total_cost_usd,
            latency_ms=result.total_latency_ms,
        )
        response.bridge_meta = BridgeMeta(
            bridge_applied=True,
            quality_flags=[],
            fallback_reason="",
            detected_input_language="",
            detected_output_language="",
        )
        return response

    async def acreate_with_reasoning(
        self,
        *,
        tier: TaskTier | None = None,
        messages: list[dict],
        max_tokens: int = 2000,
        system: str = "",
        policy: LLMPolicy | None = None,
        force_strategy: str | None = None,
    ) -> LLMResponse:
        """Async version of create_with_reasoning()."""
        from .reasoning.smart_router import SmartRouter

        router = SmartRouter(self)
        result = await router.aroute_and_reason(
            messages=messages,
            system=system,
            policy=policy,
            tier=tier,
            max_tokens=max_tokens,
            force_strategy=force_strategy,
        )

        response = LLMResponse(
            text=result.text,
            model=f"reasoning:{result.strategy_used}",
            backend=f"reasoning:{result.complexity.value}",
            tier=tier or TaskTier.MEDIUM,
            cost_usd=result.total_cost_usd,
            latency_ms=result.total_latency_ms,
        )
        response.bridge_meta = BridgeMeta(
            bridge_applied=True,
            quality_flags=[],
            fallback_reason="",
            detected_input_language="",
            detected_output_language="",
        )
        return response

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
        from shared.telemetry.cost_tracker import detect_project_context

        project_name = detect_project_context()

        classified = classify_error(error)
        self._tracker.record(
            backend=backend_name,
            model=default_model,
            tier=resolved_tier,
            success=False,
            error=str(error),
            project=project_name,
        )
        if _should_fallback(error):
            _mark_failed(resolved_tier, backend_name)
            log.warning(
                f"[{resolved_tier.value}] {backend_name}/{default_model} failed "
                f"({elapsed_ms:.0f}ms, type={classified.error_type}, "
                f"retryable={classified.retryable}) -> fallback: {error}"
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
        from shared.telemetry.cost_tracker import detect_project_context

        project_name = detect_project_context()

        rec = self._tracker.record(
            backend=backend_name,
            model=default_model,
            tier=resolved_tier,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            success=True,
            project=project_name,
        )
        response.cost_usd = rec.cost_usd

        # Prometheus business metrics (no-op if prometheus_client missing)
        try:
            from shared.business_metrics import biz

            biz.llm_request(
                default_model,
                service=project_name or "unknown",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=rec.cost_usd,
            )
        except ImportError:
            pass

    def _prepare_backend_call(
        self,
        *,
        resolved_tier: TaskTier,
        backend_name: str,
        messages: list[dict],
        system: str,
        policy: LLMPolicy,
    ) -> tuple | None:
        """Prepare a backend call. Returns None if this backend should be skipped."""
        if _is_failed(resolved_tier, backend_name) or not self._backends.has_key(backend_name):
            return None
        wrapped_system, wrapped_messages, request_meta, resolved_policy = prepare_request(
            system, messages, policy, backend_name
        )
        return wrapped_system, wrapped_messages, request_meta, resolved_policy

    def _handle_backend_result(
        self,
        *,
        response: LLMResponse,
        t0: float,
        resolved_tier: TaskTier,
        backend_name: str,
        default_model: str,
        request_meta,
        resolved_policy: LLMPolicy,
        rejected_meta: BridgeMeta | None,
        repaired_from_deepseek: bool,
    ) -> tuple[LLMResponse | None, BridgeMeta | None, bool, Exception | None]:
        """Process a successful backend response.

        Returns:
            (final_response, updated_rejected_meta, updated_repaired_flag, quality_error)
            If final_response is not None, dispatch is complete.
            If quality_error is not None, this backend was rejected and should fallback.
        """
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
            quality_error = RuntimeError(
                f"Language bridge rejected {backend_name}/{default_model}: {response.bridge_meta.quality_flags}"
            )
            log.warning(str(quality_error))
            return None, rejected_meta, repaired_from_deepseek, quality_error

        final = self._finalize_success(
            response=response,
            backend_name=backend_name,
            rejected_meta=rejected_meta,
            repaired_from_deepseek=repaired_from_deepseek,
        )
        return final, rejected_meta, repaired_from_deepseek, None

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

        if async_mode:
            return self._dispatch_async(
                chain=chain,
                resolved_tier=resolved_tier,
                messages=messages,
                max_tokens=max_tokens,
                system=system,
                policy=policy,
            )

        last_error: Exception | None = None
        rejected_meta: BridgeMeta | None = None
        repaired_from_deepseek = False

        for backend_name, default_model in chain:
            prepared = self._prepare_backend_call(
                resolved_tier=resolved_tier,
                backend_name=backend_name,
                messages=messages,
                system=system,
                policy=policy,
            )
            if prepared is None:
                continue

            wrapped_system, wrapped_messages, request_meta, resolved_policy = prepared
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
                final, rejected_meta, repaired_from_deepseek, quality_error = self._handle_backend_result(
                    response=response,
                    t0=t0,
                    resolved_tier=resolved_tier,
                    backend_name=backend_name,
                    default_model=default_model,
                    request_meta=request_meta,
                    resolved_policy=resolved_policy,
                    rejected_meta=rejected_meta,
                    repaired_from_deepseek=repaired_from_deepseek,
                )
                if final is not None:
                    return final
                last_error = quality_error
                continue
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

        raise RuntimeError(f"All backends failed for tier={resolved_tier.value}. Last error: {last_error}")

    async def _dispatch_async(
        self,
        *,
        chain: list[tuple[str, str]],
        resolved_tier: TaskTier,
        messages: list[dict],
        max_tokens: int,
        system: str,
        policy: LLMPolicy,
    ) -> LLMResponse:
        last_error: Exception | None = None
        rejected_meta: BridgeMeta | None = None
        repaired_from_deepseek = False

        for backend_name, default_model in chain:
            prepared = self._prepare_backend_call(
                resolved_tier=resolved_tier,
                backend_name=backend_name,
                messages=messages,
                system=system,
                policy=policy,
            )
            if prepared is None:
                continue

            wrapped_system, wrapped_messages, request_meta, resolved_policy = prepared
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
                final, rejected_meta, repaired_from_deepseek, quality_error = self._handle_backend_result(
                    response=response,
                    t0=t0,
                    resolved_tier=resolved_tier,
                    backend_name=backend_name,
                    default_model=default_model,
                    request_meta=request_meta,
                    resolved_policy=resolved_policy,
                    rejected_meta=rejected_meta,
                    repaired_from_deepseek=repaired_from_deepseek,
                )
                if final is not None:
                    return final
                last_error = quality_error
                continue
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

        raise RuntimeError(f"All backends failed for tier={resolved_tier.value}. Last error: {last_error}")

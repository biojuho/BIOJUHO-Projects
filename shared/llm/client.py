"""shared.llm.client - Unified LLM client with tier-based routing and fallback."""

from __future__ import annotations

import logging
import time
from typing import Optional

from .backends import BackendManager
from .config import FALLBACK_ERRORS, MODEL_TO_TIER, TIER_CHAINS, load_keys
from .models import LLMResponse, TaskTier
from .stats import CostTracker

log = logging.getLogger("shared.llm")

# Per-tier failed backend tracking with TTL (auto-expires after _FAIL_TTL seconds)
_FAIL_TTL = 300  # 5 minutes

_failed_backends: dict[TaskTier, dict[str, float]] = {
    TaskTier.LIGHTWEIGHT: {},
    TaskTier.MEDIUM: {},
    TaskTier.HEAVY: {},
}


def _is_failed(tier: TaskTier, backend: str) -> bool:
    """Check if a backend is in the failed set and hasn't expired."""
    ts = _failed_backends[tier].get(backend)
    if ts is None:
        return False
    if time.monotonic() - ts > _FAIL_TTL:
        del _failed_backends[tier][backend]
        return False
    return True


def _mark_failed(tier: TaskTier, backend: str) -> None:
    """Mark a backend as failed with current timestamp."""
    _failed_backends[tier][backend] = time.monotonic()


def _should_fallback(error: Exception) -> bool:
    """Check if an error should trigger fallback to the next backend."""
    msg = str(error).lower()
    return any(pattern in msg for pattern in FALLBACK_ERRORS)


class LLMClient:
    """Unified LLM client with tier-based routing and automatic fallback.

    Usage (sync):
        client = LLMClient()
        resp = client.create(tier=TaskTier.HEAVY, messages=[...], system="...")

    Usage (async):
        resp = await client.acreate(tier=TaskTier.MEDIUM, messages=[...])

    Backward-compatible (model name auto-maps to tier):
        resp = client.create(model="claude-3-haiku-20240307", messages=[...])
    """

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

    def _resolve_tier(self, tier: Optional[TaskTier], model: Optional[str]) -> TaskTier:
        """Resolve the task tier from explicit tier or model name."""
        if tier is not None:
            return tier
        if model and model in MODEL_TO_TIER:
            return MODEL_TO_TIER[model]
        # Default to MEDIUM for unknown models
        return TaskTier.MEDIUM

    def create(
        self,
        *,
        tier: Optional[TaskTier] = None,
        model: Optional[str] = None,
        messages: list[dict],
        max_tokens: int = 1000,
        system: str = "",
    ) -> LLMResponse:
        """Sync LLM call with tier-based routing and automatic fallback."""
        resolved_tier = self._resolve_tier(tier, model)
        chain = TIER_CHAINS[resolved_tier]
        last_error: Optional[Exception] = None
        for backend_name, default_model in chain:
            if _is_failed(resolved_tier, backend_name):
                continue
            if not self._backends.has_key(backend_name):
                continue

            t0 = time.perf_counter()
            try:
                resp = self._backends.call(
                    backend=backend_name,
                    model=default_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    system=system,
                    tier=resolved_tier,
                )
                elapsed = (time.perf_counter() - t0) * 1000
                resp.latency_ms = elapsed

                # Calculate cost
                rec = self._tracker.record(
                    backend=backend_name,
                    model=default_model,
                    tier=resolved_tier,
                    input_tokens=resp.input_tokens,
                    output_tokens=resp.output_tokens,
                    success=True,
                )
                resp.cost_usd = rec.cost_usd
                return resp

            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000
                self._tracker.record(
                    backend=backend_name,
                    model=default_model,
                    tier=resolved_tier,
                    success=False,
                    error=str(e),
                )
                if _should_fallback(e):
                    _mark_failed(resolved_tier, backend_name)
                    log.warning(
                        f"[{resolved_tier.value}] {backend_name}/{default_model} failed "
                        f"({elapsed:.0f}ms) → fallback: {e}"
                    )
                    last_error = e
                    continue
                raise

        raise RuntimeError(
            f"All backends failed for tier={resolved_tier.value}. "
            f"Last error: {last_error}"
        )

    async def acreate(
        self,
        *,
        tier: Optional[TaskTier] = None,
        model: Optional[str] = None,
        messages: list[dict],
        max_tokens: int = 1000,
        system: str = "",
    ) -> LLMResponse:
        """Async LLM call with tier-based routing and automatic fallback."""
        resolved_tier = self._resolve_tier(tier, model)
        chain = TIER_CHAINS[resolved_tier]

        last_error: Optional[Exception] = None
        for backend_name, default_model in chain:
            if _is_failed(resolved_tier, backend_name):
                continue
            if not self._backends.has_key(backend_name):
                continue

            t0 = time.perf_counter()
            try:
                resp = await self._backends.acall(
                    backend=backend_name,
                    model=default_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    system=system,
                    tier=resolved_tier,
                )
                elapsed = (time.perf_counter() - t0) * 1000
                resp.latency_ms = elapsed

                rec = self._tracker.record(
                    backend=backend_name,
                    model=default_model,
                    tier=resolved_tier,
                    input_tokens=resp.input_tokens,
                    output_tokens=resp.output_tokens,
                    success=True,
                )
                resp.cost_usd = rec.cost_usd
                return resp

            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000
                self._tracker.record(
                    backend=backend_name,
                    model=default_model,
                    tier=resolved_tier,
                    success=False,
                    error=str(e),
                )
                if _should_fallback(e):
                    _mark_failed(resolved_tier, backend_name)
                    log.warning(
                        f"[{resolved_tier.value}] {backend_name}/{default_model} failed "
                        f"({elapsed:.0f}ms) → fallback: {e}"
                    )
                    last_error = e
                    continue
                raise

        raise RuntimeError(
            f"All backends failed for tier={resolved_tier.value}. "
            f"Last error: {last_error}"
        )

    def get_stats(self) -> dict:
        """Return usage statistics as a dict."""
        s = self._tracker.get_stats()
        return {
            "total_calls": s.total_calls,
            "total_errors": s.total_errors,
            "success_rate": s.success_rate,
            "total_cost_usd": s.total_cost_usd,
            "calls_by_backend": s.calls_by_backend,
            "calls_by_tier": s.calls_by_tier,
            "cost_by_backend": s.cost_by_backend,
        }

    @staticmethod
    def reset() -> None:
        """Reset session state (clear failed backends and TTL entries)."""
        for tier in _failed_backends:
            _failed_backends[tier].clear()

    @property
    def backend(self) -> str:
        """Return the most recently successful backend name (for compatibility)."""
        stats = self._tracker.get_stats()
        if stats.calls_by_backend:
            return max(stats.calls_by_backend, key=stats.calls_by_backend.get)  # type: ignore[arg-type]
        return "none"

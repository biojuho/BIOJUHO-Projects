"""shared.llm.tracing - Optional Langfuse SDK trace propagation.

Phase 2 MVP. Wraps every native-chain LLM dispatch with a Langfuse generation
span when ``LANGFUSE_PUBLIC_KEY``, ``LANGFUSE_SECRET_KEY``, and ``LANGFUSE_HOST``
are all set. Default behaviour (env unset OR langfuse SDK missing) is a no-op
context manager - zero impact on latency or error semantics.

The proxy path (Phase 1) routes through LiteLLM, which already emits its own
Langfuse callbacks; this module instruments only the native backend chain so
that observability is symmetric whether or not the proxy is enabled.

Public surface::

    from shared.llm.tracing import is_tracing_enabled, start_span

    with start_span(tier=tier, system=system, messages=msgs) as span:
        response = native_chain(...)
        span.record_response(response)
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import AbstractContextManager
from typing import Any

from .models import LLMResponse, TaskTier

log = logging.getLogger("shared.llm.tracing")

_REQUIRED_ENV_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")
_INPUT_TRUNCATE = 4000
_ERROR_MESSAGE_TRUNCATE = 500


def is_tracing_enabled() -> bool:
    """True iff all Langfuse env keys are present and non-empty."""
    return all(os.getenv(k, "").strip() for k in _REQUIRED_ENV_KEYS)


_TRUNCATE_SUFFIX = "...[truncated]"


def _truncate(value: Any, limit: int = _INPUT_TRUNCATE) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    keep = max(0, limit - len(_TRUNCATE_SUFFIX))
    return text[:keep] + _TRUNCATE_SUFFIX


def _summarize_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(messages, list):
        return out
    for raw in messages:
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or "user")
        content = raw.get("content", "")
        if isinstance(content, list):
            parts: list[str] = []
            for chunk in content:
                if isinstance(chunk, dict):
                    parts.append(str(chunk.get("text", "")))
                else:
                    parts.append(str(chunk))
            content = " ".join(parts)
        out.append({"role": role, "content": _truncate(content)})
    return out


class _NoOpSpan(AbstractContextManager):
    """Returned when tracing is disabled. All methods are zero-cost no-ops."""

    enabled = False

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        return None

    def record_response(self, response: LLMResponse) -> None:  # noqa: D401
        return None

    def record_error(self, error: BaseException) -> None:  # noqa: D401
        return None


class _LangfuseSpan(AbstractContextManager):
    """Active Langfuse generation span.

    All Langfuse SDK calls are wrapped in best-effort try/except so a tracing
    backend outage can never propagate into the LLM client call path.
    """

    enabled = True

    def __init__(
        self,
        *,
        tier: TaskTier,
        system: str,
        messages: list[dict[str, Any]],
        dispatcher: str,
    ) -> None:
        self._tier = tier
        self._system = system
        self._messages = messages
        self._dispatcher = dispatcher
        self._t0 = 0.0
        self._client: Any = None
        self._generation: Any = None
        self._finalized = False

    def __enter__(self) -> _LangfuseSpan:
        self._t0 = time.perf_counter()
        try:
            from langfuse import Langfuse  # lazy import - opt-in dependency
        except ImportError:
            log.debug("langfuse SDK not installed; tracing remains no-op")
            return self
        except Exception as imp_err:  # noqa: BLE001
            log.warning("langfuse import failed (%s); tracing disabled", imp_err)
            return self

        try:
            self._client = Langfuse()
            self._generation = self._client.generation(
                name=f"llm.{self._dispatcher}.{self._tier.value}",
                input={
                    "system": _truncate(self._system),
                    "messages": _summarize_messages(self._messages),
                },
                metadata={
                    "tier": self._tier.value,
                    "dispatcher": self._dispatcher,
                },
            )
        except Exception as init_err:  # noqa: BLE001
            log.warning(
                "Langfuse span init failed (%s); continuing untraced",
                init_err,
            )
            self._client = None
            self._generation = None
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._generation is None:
            return None
        try:
            if exc is not None and not self._finalized:
                self.record_error(exc)
            try:
                self._generation.end()
            except Exception as end_err:  # noqa: BLE001
                log.warning("Langfuse generation.end failed (%s)", end_err)
            if self._client is not None and hasattr(self._client, "flush"):
                try:
                    self._client.flush()
                except Exception as flush_err:  # noqa: BLE001
                    log.warning("Langfuse client.flush failed (%s)", flush_err)
        finally:
            self._finalized = True
        return None

    def record_response(self, response: LLMResponse) -> None:
        if self._generation is None or self._finalized:
            return
        try:
            self._generation.update(
                output={"text": _truncate(getattr(response, "text", ""))},
                model=getattr(response, "model", "") or "",
                usage={
                    "input": int(getattr(response, "input_tokens", 0) or 0),
                    "output": int(getattr(response, "output_tokens", 0) or 0),
                },
                metadata={
                    "backend": getattr(response, "backend", "") or "",
                    "latency_ms": float(getattr(response, "latency_ms", 0.0) or 0.0),
                    "elapsed_ms": (time.perf_counter() - self._t0) * 1000.0,
                },
                level="DEFAULT",
            )
            self._finalized = True
        except Exception as upd_err:  # noqa: BLE001
            log.warning("Langfuse generation.update(success) failed (%s)", upd_err)

    def record_error(self, error: BaseException) -> None:
        if self._generation is None or self._finalized:
            return
        try:
            self._generation.update(
                level="ERROR",
                status_message=_truncate(str(error), _ERROR_MESSAGE_TRUNCATE),
                metadata={
                    "error_class": error.__class__.__name__,
                    "elapsed_ms": (time.perf_counter() - self._t0) * 1000.0,
                },
            )
            self._finalized = True
        except Exception as upd_err:  # noqa: BLE001
            log.warning("Langfuse generation.update(error) failed (%s)", upd_err)


def start_span(
    *,
    tier: TaskTier,
    system: str,
    messages: list[dict[str, Any]],
    dispatcher: str = "native",
) -> AbstractContextManager:
    """Begin a generation span; return a no-op when tracing is disabled.

    The returned object always exposes ``record_response`` and ``record_error``
    so the caller never needs to branch on ``is_tracing_enabled()``.
    """
    if not is_tracing_enabled():
        return _NoOpSpan()
    return _LangfuseSpan(
        tier=tier,
        system=system,
        messages=messages,
        dispatcher=dispatcher,
    )

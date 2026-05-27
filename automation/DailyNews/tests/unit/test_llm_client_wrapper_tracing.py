"""Phase 3 tracing instrumentation tests for LLMClientWrapper.generate_text.

Confirms the public entry point opens a tracing span tagged with the
cache_scope and records the resulting text + provider + model + tokens. Spy
runs against the real (no-op when env unset) tracing.start_span.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class _Budget:
    def can_afford(self, _tokens: int) -> bool:
        return True

    def record(self, **_kwargs) -> None:
        return None

    def get_detail_level(self):
        return SimpleNamespace(value="standard")


def _spy_tracing(monkeypatch, client_wrapper):
    calls: list[dict] = []
    original = client_wrapper.tracing.start_span

    def _spy(*, tier, system, messages, dispatcher="native"):
        span = original(tier=tier, system=system, messages=messages, dispatcher=dispatcher)
        recorded: dict = {"tier": tier, "dispatcher": dispatcher, "messages": messages, "system": system}
        calls.append(recorded)
        original_record_text = span.record_text
        original_record_error = span.record_error

        def _record_text(**kw):
            recorded["record_text"] = kw
            return original_record_text(**kw)

        def _record_error(err):
            recorded["record_error"] = err
            return original_record_error(err)

        span.record_text = _record_text  # type: ignore[method-assign]
        span.record_error = _record_error  # type: ignore[method-assign]
        return span

    monkeypatch.setattr(client_wrapper.tracing, "start_span", _spy)
    return calls


@pytest.mark.asyncio
async def test_generate_text_traces_success(monkeypatch):
    from antigravity_mcp.integrations.llm import client_wrapper

    client_wrapper._L1_CACHE.clear()
    calls = _spy_tracing(monkeypatch, client_wrapper)

    async def fake_complete(*, prompt, max_tokens, cache_scope):
        meta = {
            "cache_scope": cache_scope,
            "provider": "shared.llm",
            "model_name": "claude-sonnet-4-6",
            "input_tokens": 120,
            "output_tokens": 80,
        }
        return "generated brief content", meta, []

    wrapper = client_wrapper.LLMClientWrapper(state_store=None, token_budget=_Budget())
    monkeypatch.setattr(wrapper, "_complete_text", fake_complete)

    text, meta, warnings = await wrapper.generate_text(("SYS", "USR"), cache_scope="deep_dive:technology")

    assert text == "generated brief content"
    assert meta["provider"] == "shared.llm"
    assert warnings == []

    assert len(calls) == 1
    call = calls[0]
    assert call["dispatcher"] == "dailynews.deep_dive:technology"
    assert call["system"] == "SYS"
    assert call["messages"] == [{"role": "user", "content": "USR"}]
    rt = call["record_text"]
    assert rt["text"] == "generated brief content"
    assert rt["model"] == "claude-sonnet-4-6"
    assert rt["backend"] == "shared.llm"
    assert rt["input_tokens"] == 120
    assert rt["output_tokens"] == 80


@pytest.mark.asyncio
async def test_generate_text_traces_llm_unavailable_via_exit(monkeypatch):
    from antigravity_mcp.integrations.llm import client_wrapper

    client_wrapper._L1_CACHE.clear()
    calls = _spy_tracing(monkeypatch, client_wrapper)

    async def fail_complete(*, prompt, max_tokens, cache_scope):
        raise client_wrapper.LLMUnavailableError("all providers down")

    wrapper = client_wrapper.LLMClientWrapper(state_store=None, token_budget=_Budget())
    monkeypatch.setattr(wrapper, "_complete_text", fail_complete)

    with pytest.raises(client_wrapper.LLMUnavailableError):
        await wrapper.generate_text("prompt-only", cache_scope="summary")

    assert calls[0]["dispatcher"] == "dailynews.summary"
    # record_text never called on failure; record_error not called explicitly here
    # but the no-op span's __exit__ silently captures - test just verifies wiring
    assert "record_text" not in calls[0]


@pytest.mark.asyncio
async def test_generate_text_aborts_before_span_when_budget_exceeded(monkeypatch):
    """Budget exceeded must skip the span - tracing should not see a no-op call."""
    from antigravity_mcp.integrations.llm import client_wrapper

    client_wrapper._L1_CACHE.clear()
    calls = _spy_tracing(monkeypatch, client_wrapper)

    class _BrokeBudget(_Budget):
        def can_afford(self, _tokens: int) -> bool:
            return False

    wrapper = client_wrapper.LLMClientWrapper(state_store=None, token_budget=_BrokeBudget())

    with pytest.raises(client_wrapper.LLMUnavailableError, match="Token budget exceeded"):
        await wrapper.generate_text("p", cache_scope="x")

    assert calls == []

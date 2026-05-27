"""Langfuse trace propagation unit tests (Phase 2).

Covers ``shared.llm.tracing``:
  - env-gated activation
  - no-op span when disabled / SDK missing
  - active span init, response/error recording, exit flush
  - resilience against SDK exceptions (must never propagate into caller)
"""

from __future__ import annotations

import logging
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from shared.llm import tracing
from shared.llm.models import LLMResponse, TaskTier

# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def _enable_env(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3020")
    yield


@pytest.fixture
def _disable_env(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    yield


@pytest.fixture
def fake_langfuse(monkeypatch):
    """Install a fake ``langfuse`` module exposing a configurable ``Langfuse``."""

    generation = MagicMock(name="generation")
    client_instance = MagicMock(name="langfuse_client")
    client_instance.generation.return_value = generation
    client_factory = MagicMock(name="Langfuse", return_value=client_instance)

    fake_mod = SimpleNamespace(Langfuse=client_factory)
    monkeypatch.setitem(sys.modules, "langfuse", fake_mod)
    yield SimpleNamespace(
        module=fake_mod,
        factory=client_factory,
        client=client_instance,
        generation=generation,
    )


def _sample_response(text: str = "hello") -> LLMResponse:
    return LLMResponse(
        text=text,
        model="gpt-test",
        backend="openai",
        tier=TaskTier.MEDIUM,
        input_tokens=42,
        output_tokens=17,
        latency_ms=123.4,
    )


# ─── is_tracing_enabled ──────────────────────────────────────────────


def test_is_tracing_enabled_false_when_any_key_missing(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "http://x")
    assert tracing.is_tracing_enabled() is False


def test_is_tracing_enabled_false_when_empty_string(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "   ")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "http://x")
    assert tracing.is_tracing_enabled() is False


def test_is_tracing_enabled_true_when_all_set(_enable_env):
    assert tracing.is_tracing_enabled() is True


# ─── _truncate / _summarize_messages helpers ─────────────────────────


def test_truncate_short_string_unchanged():
    assert tracing._truncate("hi") == "hi"


def test_truncate_none_returns_empty():
    assert tracing._truncate(None) == ""


def test_truncate_long_string_marked():
    long = "x" * 5000
    out = tracing._truncate(long, limit=100)
    assert len(out) == 100
    assert out.endswith("...[truncated]")


def test_summarize_messages_string_content():
    msgs = [{"role": "user", "content": "hello"}]
    assert tracing._summarize_messages(msgs) == [{"role": "user", "content": "hello"}]


def test_summarize_messages_list_content_joins_text():
    msgs = [{"role": "user", "content": [{"text": "a"}, {"text": "b"}, "c"]}]
    out = tracing._summarize_messages(msgs)
    assert out[0]["content"] == "a b c"


def test_summarize_messages_skips_non_dict_entries():
    msgs = [{"role": "user", "content": "x"}, "garbage", {"role": "assistant", "content": "y"}]
    out = tracing._summarize_messages(msgs)
    assert [m["role"] for m in out] == ["user", "assistant"]


def test_summarize_messages_default_role_when_missing():
    msgs = [{"content": "x"}]
    assert tracing._summarize_messages(msgs)[0]["role"] == "user"


def test_summarize_messages_non_list_input_returns_empty():
    assert tracing._summarize_messages("not a list") == []  # type: ignore[arg-type]


# ─── start_span: no-op behaviour when disabled ───────────────────────


def test_start_span_returns_noop_when_env_unset(_disable_env):
    span = tracing.start_span(tier=TaskTier.MEDIUM, system="sys", messages=[{"role": "user", "content": "hi"}])
    assert isinstance(span, tracing._NoOpSpan)
    assert span.enabled is False


def test_noop_span_supports_context_and_records(_disable_env):
    with tracing.start_span(tier=TaskTier.HEAVY, system="", messages=[]) as span:
        span.record_response(_sample_response())
        span.record_error(RuntimeError("boom"))
    # nothing should raise; span is a no-op


# ─── _LangfuseSpan: active path ──────────────────────────────────────


def test_active_span_initializes_generation(_enable_env, fake_langfuse):
    msgs = [{"role": "user", "content": "ping"}]
    with tracing.start_span(tier=TaskTier.HEAVY, system="SYS", messages=msgs, dispatcher="native") as span:
        assert span.enabled is True
        assert fake_langfuse.factory.called
        assert fake_langfuse.client.generation.called
        call = fake_langfuse.client.generation.call_args
        assert call.kwargs["name"] == "llm.native.heavy"
        assert call.kwargs["metadata"] == {"tier": "heavy", "dispatcher": "native"}
        assert call.kwargs["input"]["system"] == "SYS"
        assert call.kwargs["input"]["messages"] == [{"role": "user", "content": "ping"}]


def test_active_span_record_response_updates_generation(_enable_env, fake_langfuse):
    response = _sample_response("output text")
    with tracing.start_span(tier=TaskTier.MEDIUM, system="", messages=[]) as span:
        span.record_response(response)
    upd = fake_langfuse.generation.update
    assert upd.called
    kwargs = upd.call_args.kwargs
    assert kwargs["output"] == {"text": "output text"}
    assert kwargs["model"] == "gpt-test"
    assert kwargs["usage"] == {"input": 42, "output": 17}
    assert kwargs["metadata"]["backend"] == "openai"
    assert kwargs["metadata"]["latency_ms"] == pytest.approx(123.4)
    assert kwargs["level"] == "DEFAULT"


def test_active_span_record_error_uses_error_level(_enable_env, fake_langfuse):
    with tracing.start_span(tier=TaskTier.LIGHTWEIGHT, system="", messages=[]) as span:
        span.record_error(ValueError("nope"))
    kwargs = fake_langfuse.generation.update.call_args.kwargs
    assert kwargs["level"] == "ERROR"
    assert "nope" in kwargs["status_message"]
    assert kwargs["metadata"]["error_class"] == "ValueError"


def test_active_span_auto_records_unhandled_exception(_enable_env, fake_langfuse):
    with pytest.raises(RuntimeError):
        with tracing.start_span(tier=TaskTier.MEDIUM, system="", messages=[]):
            raise RuntimeError("crash inside dispatch")
    upd = fake_langfuse.generation.update
    assert upd.called
    assert upd.call_args.kwargs["level"] == "ERROR"
    assert "crash inside dispatch" in upd.call_args.kwargs["status_message"]


def test_active_span_finalizes_only_once(_enable_env, fake_langfuse):
    """If record_response was called, __exit__ must not double-record on raise."""
    with pytest.raises(RuntimeError):
        with tracing.start_span(tier=TaskTier.MEDIUM, system="", messages=[]) as span:
            span.record_response(_sample_response())
            raise RuntimeError("after success")
    # update called exactly once (the success record)
    assert fake_langfuse.generation.update.call_count == 1
    assert fake_langfuse.generation.update.call_args.kwargs["level"] == "DEFAULT"


def test_active_span_calls_end_and_flush(_enable_env, fake_langfuse):
    with tracing.start_span(tier=TaskTier.MEDIUM, system="", messages=[]):
        pass
    assert fake_langfuse.generation.end.called
    assert fake_langfuse.client.flush.called


# ─── Resilience: SDK errors never propagate ──────────────────────────


def test_missing_langfuse_sdk_falls_back_to_no_record(_enable_env, monkeypatch, caplog):
    # Ensure no fake module is registered and import will fail
    monkeypatch.delitem(sys.modules, "langfuse", raising=False)
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

    def _block_langfuse(name, *args, **kwargs):
        if name == "langfuse":
            raise ImportError("simulated missing langfuse")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _block_langfuse)
    with caplog.at_level(logging.DEBUG, logger="shared.llm.tracing"):
        with tracing.start_span(tier=TaskTier.MEDIUM, system="", messages=[]) as span:
            span.record_response(_sample_response())
            span.record_error(RuntimeError("x"))
    # Should not raise; debug log present
    assert any("langfuse SDK not installed" in r.message for r in caplog.records)


def test_langfuse_client_constructor_failure_logs_and_degrades(_enable_env, monkeypatch, caplog):
    fake = SimpleNamespace(Langfuse=MagicMock(side_effect=RuntimeError("auth")))
    monkeypatch.setitem(sys.modules, "langfuse", fake)
    with caplog.at_level(logging.WARNING, logger="shared.llm.tracing"):
        with tracing.start_span(tier=TaskTier.MEDIUM, system="", messages=[]) as span:
            span.record_response(_sample_response())
    assert any("Langfuse span init failed" in r.message for r in caplog.records)


def test_generation_update_exception_swallowed(_enable_env, fake_langfuse, caplog):
    fake_langfuse.generation.update.side_effect = RuntimeError("network")
    with caplog.at_level(logging.WARNING, logger="shared.llm.tracing"):
        with tracing.start_span(tier=TaskTier.MEDIUM, system="", messages=[]) as span:
            span.record_response(_sample_response())
    assert any("generation.update(success) failed" in r.message for r in caplog.records)


def test_generation_end_exception_swallowed(_enable_env, fake_langfuse, caplog):
    fake_langfuse.generation.end.side_effect = RuntimeError("end-boom")
    with caplog.at_level(logging.WARNING, logger="shared.llm.tracing"):
        with tracing.start_span(tier=TaskTier.MEDIUM, system="", messages=[]):
            pass
    assert any("generation.end failed" in r.message for r in caplog.records)


def test_flush_exception_swallowed(_enable_env, fake_langfuse, caplog):
    fake_langfuse.client.flush.side_effect = RuntimeError("flush-boom")
    with caplog.at_level(logging.WARNING, logger="shared.llm.tracing"):
        with tracing.start_span(tier=TaskTier.MEDIUM, system="", messages=[]):
            pass
    assert any("client.flush failed" in r.message for r in caplog.records)


# ─── Integration: client.py wires native dispatch through start_span ─


def test_client_dispatch_invokes_tracing(monkeypatch):
    """When env is unset, client.py still calls tracing.start_span and gets a no-op."""
    from shared.llm import client as client_mod

    captured: list[dict] = []
    original = tracing.start_span

    def _spy(*, tier, system, messages, dispatcher="native"):
        captured.append({"tier": tier, "dispatcher": dispatcher})
        return original(tier=tier, system=system, messages=messages, dispatcher=dispatcher)

    monkeypatch.setattr(client_mod.tracing, "start_span", _spy)

    fake_backend = MagicMock()
    fake_backend.call.return_value = _sample_response("ok")
    monkeypatch.setattr(
        client_mod.LLMClient,
        "_iter_chain",
        lambda self, tier, policy: [("openai", "gpt-4")],
    )
    monkeypatch.setattr(
        client_mod.LLMClient,
        "_prepare_backend_call",
        lambda self, **kw: ("sys", [{"role": "user", "content": "x"}], {}, kw["policy"]),
    )
    monkeypatch.setattr(
        client_mod.LLMClient,
        "_handle_backend_result",
        lambda self, **kw: (kw["response"], None, False, None),
    )

    from shared.llm.models import LLMPolicy

    instance = client_mod.LLMClient.__new__(client_mod.LLMClient)
    instance._backends = fake_backend
    instance._bridge_metrics = {}  # noqa: SLF001

    result = instance._dispatch(
        resolved_tier=TaskTier.MEDIUM,
        messages=[{"role": "user", "content": "x"}],
        max_tokens=10,
        system="sys",
        policy=LLMPolicy(),
        async_mode=False,
    )
    assert result.text == "ok"
    assert len(captured) == 1
    assert captured[0]["dispatcher"] == "native"
    assert captured[0]["tier"] is TaskTier.MEDIUM

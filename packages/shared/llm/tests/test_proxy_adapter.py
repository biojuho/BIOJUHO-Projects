"""LiteLLM proxy adapter unit tests.

Covers the Phase 1 MVP entry-point — when ``LITELLM_PROXY_URL`` is set the
``LLMClient`` should route through :mod:`shared.llm.proxy_adapter` first, falling
back to the native backend chain on any proxy failure.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.llm import proxy_adapter
from shared.llm.models import LLMResponse, TaskTier


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("LITELLM_PROXY_URL", raising=False)
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    yield


def test_is_proxy_enabled_respects_env(monkeypatch):
    assert proxy_adapter.is_proxy_enabled() is False
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://localhost:8010")
    assert proxy_adapter.is_proxy_enabled() is True
    monkeypatch.setenv("LITELLM_PROXY_URL", "   ")
    assert proxy_adapter.is_proxy_enabled() is False


@pytest.mark.parametrize(
    ("tier", "expected"),
    [
        (TaskTier.HEAVY, "tier-heavy"),
        (TaskTier.MEDIUM, "tier-medium"),
        (TaskTier.LIGHTWEIGHT, "tier-lightweight"),
    ],
)
def test_resolve_model_alias(tier, expected):
    assert proxy_adapter._resolve_model_alias(tier) == expected


def test_build_messages_prepends_system_when_missing():
    out = proxy_adapter._build_messages("SYS", [{"role": "user", "content": "hi"}])
    assert out[0] == {"role": "system", "content": "SYS"}
    assert out[1]["content"] == "hi"


def test_build_messages_keeps_existing_system():
    msgs = [{"role": "system", "content": "ORIG"}, {"role": "user", "content": "hi"}]
    out = proxy_adapter._build_messages("OVERRIDE", msgs)
    assert out == msgs


def test_build_messages_passthrough_without_system():
    msgs = [{"role": "user", "content": "hi"}]
    out = proxy_adapter._build_messages("", msgs)
    assert out == msgs


def test_call_proxies_to_openai_client(monkeypatch):
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://localhost:8010")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")

    fake_completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=" hello "))],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        model="tier-medium",
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_completion

    with patch.object(proxy_adapter, "_make_client", return_value=fake_client) as mk:
        response = proxy_adapter.call(
            tier=TaskTier.MEDIUM,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=128,
            system="SYS",
        )
        mk.assert_called_once_with(async_client=False)

    fake_client.chat.completions.create.assert_called_once()
    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "tier-medium"
    assert kwargs["max_tokens"] == 128
    assert kwargs["messages"][0] == {"role": "system", "content": "SYS"}

    assert isinstance(response, LLMResponse)
    assert response.backend == "litellm-proxy"
    assert response.text == "hello"
    assert response.input_tokens == 11
    assert response.output_tokens == 7
    assert response.tier == TaskTier.MEDIUM


def test_call_handles_missing_usage(monkeypatch):
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://localhost:8010")
    fake_completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        usage=None,
        model="tier-heavy",
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_completion
    with patch.object(proxy_adapter, "_make_client", return_value=fake_client):
        response = proxy_adapter.call(
            tier=TaskTier.HEAVY,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10,
            system="",
        )
    assert response.input_tokens == 0
    assert response.output_tokens == 0
    assert response.text == "ok"


def test_make_client_requires_proxy_url(monkeypatch):
    monkeypatch.delenv("LITELLM_PROXY_URL", raising=False)
    with pytest.raises(KeyError):
        proxy_adapter._make_client(async_client=False)


@pytest.mark.asyncio
async def test_acall_proxies_to_async_openai_client(monkeypatch):
    """Async path must mirror the sync `call` contract — was previously
    untested, leaving a regression hole in the await/AsyncOpenAI wiring."""
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://localhost:8010")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")

    fake_completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=" hello-async "))],
        usage=SimpleNamespace(prompt_tokens=4, completion_tokens=6),
        model="tier-heavy",
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_completion)

    with patch.object(proxy_adapter, "_make_client", return_value=fake_client) as mk:
        response = await proxy_adapter.acall(
            tier=TaskTier.HEAVY,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=64,
            system="SYS-A",
        )
        mk.assert_called_once_with(async_client=True)

    fake_client.chat.completions.create.assert_awaited_once()
    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "tier-heavy"
    assert kwargs["max_tokens"] == 64
    assert kwargs["messages"][0] == {"role": "system", "content": "SYS-A"}

    assert isinstance(response, LLMResponse)
    assert response.backend == "litellm-proxy"
    assert response.text == "hello-async"
    assert response.input_tokens == 4
    assert response.output_tokens == 6
    assert response.tier == TaskTier.HEAVY


def test_coerce_response_handles_none_content(monkeypatch):
    """Upstream APIs occasionally return `message.content = None` (e.g. when
    a tool call is returned in lieu of text). `.strip()` on None would crash —
    the adapter must coerce to empty string."""
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://localhost:8010")
    fake_completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=0),
        model="tier-lightweight",
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_completion
    with patch.object(proxy_adapter, "_make_client", return_value=fake_client):
        response = proxy_adapter.call(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10,
            system="",
        )
    assert response.text == ""
    assert response.input_tokens == 2
    assert response.output_tokens == 0


def test_client_dispatch_invokes_proxy_when_enabled(monkeypatch):
    """Integration-shape test: LLMClient routes through proxy when env set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-for-init")
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://localhost:8010")

    from shared.llm import client as client_mod
    from shared.llm.client import LLMClient

    sentinel_response = LLMResponse(
        text="from-proxy",
        model="tier-medium",
        backend="litellm-proxy",
        tier=TaskTier.MEDIUM,
        input_tokens=5,
        output_tokens=3,
    )

    LLMClient.reset()
    client = LLMClient()
    try:
        with patch.object(client_mod.proxy_adapter, "call", return_value=sentinel_response) as proxy_call:
            response = client.create(
                tier=TaskTier.MEDIUM,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=64,
                system="",
            )
        proxy_call.assert_called_once()
        assert response.text == "from-proxy"
        assert response.backend == "litellm-proxy"
    finally:
        client.close()
        LLMClient.reset()


def test_client_dispatch_falls_back_when_proxy_raises(monkeypatch):
    """Proxy failure must not break the native chain."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-for-init")
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://localhost:8010")

    from shared.llm import client as client_mod
    from shared.llm.client import LLMClient

    LLMClient.reset()
    client = LLMClient()

    # Stub the native call too so we can detect fallback without real keys
    native_response = LLMResponse(
        text="from-native",
        model="claude-haiku",
        backend="anthropic",
        tier=TaskTier.LIGHTWEIGHT,
    )
    try:
        with patch.object(client_mod.proxy_adapter, "call", side_effect=RuntimeError("proxy down")), \
             patch.object(client, "_dispatch_via_proxy_sync", side_effect=RuntimeError("proxy down")), \
             patch.object(client, "_iter_chain", return_value=[("anthropic", "claude-haiku")]), \
             patch.object(client._backends, "has_key", return_value=True), \
             patch.object(client._backends, "call", return_value=native_response):
            response = client.create(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=64,
                system="",
            )
        assert response.text == "from-native"
        assert response.backend == "anthropic"
    finally:
        client.close()
        LLMClient.reset()


@pytest.mark.asyncio
async def test_client_acreate_invokes_proxy_when_enabled(monkeypatch):
    """Async dispatch must also route through the proxy when env set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-for-init")
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://localhost:8010")

    from shared.llm import client as client_mod
    from shared.llm.client import LLMClient

    sentinel_response = LLMResponse(
        text="from-proxy-async",
        model="tier-medium",
        backend="litellm-proxy",
        tier=TaskTier.MEDIUM,
        input_tokens=9,
        output_tokens=4,
    )

    LLMClient.reset()
    client = LLMClient()
    try:
        with patch.object(client_mod.proxy_adapter, "acall", new=AsyncMock(return_value=sentinel_response)) as proxy_acall:
            response = await client.acreate(
                tier=TaskTier.MEDIUM,
                messages=[{"role": "user", "content": "hi-async"}],
                max_tokens=64,
                system="",
            )
        proxy_acall.assert_awaited_once()
        assert response.text == "from-proxy-async"
        assert response.backend == "litellm-proxy"
    finally:
        client.close()
        LLMClient.reset()


@pytest.mark.asyncio
async def test_client_acreate_falls_back_when_proxy_raises(monkeypatch):
    """Async proxy failure must transparently fall through to the native chain."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-for-init")
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://localhost:8010")

    from shared.llm import client as client_mod
    from shared.llm.client import LLMClient

    LLMClient.reset()
    client = LLMClient()

    native_response = LLMResponse(
        text="from-native-async",
        model="claude-haiku",
        backend="anthropic",
        tier=TaskTier.LIGHTWEIGHT,
    )
    try:
        with patch.object(client_mod.proxy_adapter, "acall", new=AsyncMock(side_effect=RuntimeError("proxy down"))), \
             patch.object(client, "_dispatch_via_proxy_async", new=AsyncMock(side_effect=RuntimeError("proxy down"))), \
             patch.object(client, "_iter_chain", return_value=[("anthropic", "claude-haiku")]), \
             patch.object(client._backends, "has_key", return_value=True), \
             patch.object(client._backends, "acall", new=AsyncMock(return_value=native_response)):
            response = await client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{"role": "user", "content": "hi-async"}],
                max_tokens=64,
                system="",
            )
        assert response.text == "from-native-async"
        assert response.backend == "anthropic"
    finally:
        client.close()
        LLMClient.reset()

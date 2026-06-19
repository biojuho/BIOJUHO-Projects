import asyncio
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from shared.llm import backends as backends_mod


def test_openai_client_uses_explicit_timeout(monkeypatch):
    manager = backends_mod.BackendManager({"openai": "test-key"})
    fake_openai = ModuleType("openai")
    fake_openai.OpenAI = MagicMock(return_value=MagicMock())
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    manager._get_openai()

    assert fake_openai.OpenAI.call_args.kwargs["timeout"] == backends_mod._DEFAULT_TIMEOUT


def test_gemini_client_uses_http_timeout_options(monkeypatch):
    manager = backends_mod.BackendManager({"gemini": "test-key"})
    fake_google = ModuleType("google")
    fake_genai = ModuleType("google.genai")
    fake_types = ModuleType("google.genai.types")
    fake_genai.Client = MagicMock(return_value=MagicMock())
    fake_types.HttpOptions = MagicMock(side_effect=lambda **kwargs: kwargs)
    fake_google.genai = fake_genai
    fake_genai.types = fake_types
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

    manager._get_gemini()

    assert fake_types.HttpOptions.call_args.kwargs["timeout"] == 120_000  # ms
    assert fake_genai.Client.call_args.kwargs["http_options"]["timeout"] == 120_000


def test_close_awaits_async_clients_without_running_loop():
    manager = backends_mod.BackendManager({})
    state = {"closed": False}

    class AsyncClosable:
        async def close(self):
            state["closed"] = True

    manager._clients = {"anthropic_async": AsyncClosable()}

    manager.close()

    assert state["closed"] is True
    assert manager._clients == {}


@pytest.mark.asyncio
async def test_close_schedules_async_clients_on_running_loop():
    manager = backends_mod.BackendManager({})
    closed_event = asyncio.Event()
    state = {"sync_closed": False}

    class AsyncClosable:
        async def close(self):
            closed_event.set()

    class SyncClosable:
        def close(self):
            state["sync_closed"] = True

    manager._clients = {
        "anthropic_async": AsyncClosable(),
        "openai": SyncClosable(),
    }

    manager.close()
    await asyncio.wait_for(closed_event.wait(), timeout=1)

    assert state["sync_closed"] is True
    assert manager._clients == {}

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from shared.llm import backends as backends_mod


def test_openai_client_uses_explicit_timeout():
    manager = backends_mod.BackendManager({"openai": "test-key"})

    with patch("openai.OpenAI", return_value=MagicMock()) as mock_openai:
        manager._get_openai()

    assert mock_openai.call_args.kwargs["timeout"] == backends_mod._DEFAULT_TIMEOUT


def test_gemini_client_uses_http_timeout_options():
    manager = backends_mod.BackendManager({"gemini": "test-key"})

    with patch("google.genai.Client", return_value=MagicMock()) as mock_client, patch(
        "google.genai.types.HttpOptions",
        side_effect=lambda **kwargs: kwargs,
    ) as mock_http_options:
        manager._get_gemini()

    assert mock_http_options.call_args.kwargs["timeout"] == 120
    assert mock_client.call_args.kwargs["http_options"]["timeout"] == 120


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

"""LiteLLM-proxy path now threads JSON mode + native schema (previously dropped entirely)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from shared.llm import proxy_adapter
from shared.llm.models import TaskTier

MSG = [{"role": "user", "content": "x"}]
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


def _fake_completion() -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        model="proxy-medium",
    )


def _capture_call(**call_kwargs) -> dict:
    client = MagicMock()
    client.chat.completions.create.return_value = _fake_completion()
    with patch.object(proxy_adapter, "_make_client", return_value=client):
        proxy_adapter.call(tier=TaskTier.MEDIUM, messages=MSG, max_tokens=50, system="", **call_kwargs)
    return client.chat.completions.create.call_args.kwargs


def test_json_mode_sets_json_object() -> None:
    assert _capture_call(response_mode="json")["response_format"] == {"type": "json_object"}


def test_json_schema_sets_strict_normalized() -> None:
    rf = _capture_call(json_schema=SCHEMA)["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["schema"]["additionalProperties"] is False


def test_text_mode_sends_no_response_format() -> None:
    assert "response_format" not in _capture_call()

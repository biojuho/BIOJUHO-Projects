"""Anthropic backend modernization regression tests (2026-06).

Guards the verified fixes in _call_anthropic / _stream_anthropic + errors.py:
- the assistant-prefill "{" JSON hack is removed (it 400s on Claude 4.6+, which
  silently routed every JSON-mode Anthropic call to the next backend),
- the retired ``anthropic-beta: prompt-caching-2024-07-31`` header is no longer
  sent (caching is GA via cache_control, which is preserved),
- stop_reason=='refusal' raises a fallback-able error BEFORE content is read,
  classified as the retryable RefusalError.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from shared.llm.backends import BackendManager
from shared.llm.errors import RefusalError, classify_error, should_fallback_to_next_backend
from shared.llm.models import TaskTier

MESSAGES = [{"role": "user", "content": "give me json"}]


@pytest.fixture
def mgr() -> BackendManager:
    return BackendManager(keys={"anthropic": "sk-test"})


def _mock_anthropic(mgr: BackendManager, resp: object) -> MagicMock:
    mock_client = MagicMock()
    mock_client.messages.create.return_value = resp
    mgr._clients["anthropic"] = mock_client
    return mock_client


def _ok_resp(text: str = '{"k": 1}') -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


class TestNoAssistantPrefill:
    def test_json_mode_appends_no_assistant_turn(self, mgr: BackendManager) -> None:
        client = _mock_anthropic(mgr, _ok_resp('{"k": 1}'))
        mgr._call_anthropic("claude-sonnet-4-6", MESSAGES, 100, "", TaskTier.HEAVY, response_mode="json")
        sent = client.messages.create.call_args.kwargs["messages"]
        assert all(m["role"] != "assistant" for m in sent), sent

    def test_json_text_not_double_brace_mangled(self, mgr: BackendManager) -> None:
        _mock_anthropic(mgr, _ok_resp('{"k": 1}'))
        result = mgr._call_anthropic(
            "claude-sonnet-4-6", MESSAGES, 100, "", TaskTier.HEAVY, response_mode="json"
        )
        assert result.text == '{"k": 1}'  # no spurious leading '{'


class TestNoRetiredBetaHeader:
    def test_create_called_without_prompt_caching_beta(self, mgr: BackendManager) -> None:
        client = _mock_anthropic(mgr, _ok_resp("hi"))
        mgr._call_anthropic("claude-sonnet-4-6", MESSAGES, 100, "sys", TaskTier.HEAVY)
        kwargs = client.messages.create.call_args.kwargs
        extra = kwargs.get("extra_headers") or {}
        assert "anthropic-beta" not in extra
        # caching itself is preserved via the system cache_control block
        assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}


class TestRefusalGuard:
    def test_refusal_stop_reason_raises_before_content(self, mgr: BackendManager) -> None:
        resp = SimpleNamespace(
            content=[SimpleNamespace(text="I can't help with that.")],
            stop_reason="refusal",
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        _mock_anthropic(mgr, resp)
        with pytest.raises(ValueError, match="refusal"):
            mgr._call_anthropic("claude-fable-5", MESSAGES, 100, "", TaskTier.HEAVY)

    def test_refusal_classifies_as_fallbackable(self) -> None:
        err = classify_error(
            ValueError("Anthropic refusal: model declined response (stop_reason=refusal, model=x)")
        )
        assert isinstance(err, RefusalError)
        assert err.retryable is True
        assert should_fallback_to_next_backend(err) is True

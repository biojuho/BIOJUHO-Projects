"""B-017: LLM 백엔드 빈 응답 방어 테스트.

모든 백엔드에서 API가 빈 content/choices를 반환할 때
ValueError로 명확하게 실패하는지 검증.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from packages.shared.llm.backends import BackendManager
from packages.shared.llm.models import TaskTier


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mgr():
    """BackendManager with dummy keys."""
    return BackendManager(keys={
        "anthropic": "sk-test",
        "gemini": "gem-test",
        "openai": "oai-test",
        "grok": "grok-test",
        "deepseek": "ds-test",
    })


MESSAGES = [{"role": "user", "content": "hello"}]


# ── 1. Anthropic: empty content ──────────────────────────────────────

class TestAnthropicEmptyContent:
    def test_empty_content_list_raises(self, mgr):
        """resp.content == [] → ValueError."""
        mock_resp = SimpleNamespace(
            content=[],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=10, output_tokens=0),
        )
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_resp
        mgr._clients["anthropic"] = mock_client

        with pytest.raises(ValueError, match="Anthropic empty response"):
            mgr._call_anthropic("claude-sonnet-4-20250514", MESSAGES, 100, "", TaskTier.MEDIUM)

    def test_none_text_raises(self, mgr):
        """resp.content[0].text == None → ValueError."""
        mock_resp = SimpleNamespace(
            content=[SimpleNamespace(text=None)],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=10, output_tokens=0),
        )
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_resp
        mgr._clients["anthropic"] = mock_client

        with pytest.raises(ValueError, match="content\\[0\\].text is None"):
            mgr._call_anthropic("claude-sonnet-4-20250514", MESSAGES, 100, "", TaskTier.MEDIUM)

    def test_valid_response_passes(self, mgr):
        """정상 응답은 LLMResponse 반환."""
        mock_resp = SimpleNamespace(
            content=[SimpleNamespace(text="Hello!")],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_resp
        mgr._clients["anthropic"] = mock_client

        result = mgr._call_anthropic("claude-sonnet-4-20250514", MESSAGES, 100, "", TaskTier.MEDIUM)
        assert result.text == "Hello!"
        assert result.backend == "anthropic"


# ── 2. OpenAI-compatible: empty choices ──────────────────────────────

class TestOpenAICompatEmptyChoices:
    def _make_mgr_with_mock(self, mgr, resp):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = resp
        mgr._clients["openai"] = mock_client
        return mgr

    def test_empty_choices_raises(self, mgr):
        resp = SimpleNamespace(choices=[], usage=None)
        mgr = self._make_mgr_with_mock(mgr, resp)
        with pytest.raises(ValueError, match="Empty response.*no choices"):
            mgr._call_openai_compat("openai", "gpt-4o", MESSAGES, 100, "", TaskTier.MEDIUM)

    def test_none_message_content_raises(self, mgr):
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0),
        )
        mgr = self._make_mgr_with_mock(mgr, resp)
        with pytest.raises(ValueError, match="message.content is None"):
            mgr._call_openai_compat("openai", "gpt-4o", MESSAGES, 100, "", TaskTier.MEDIUM)

    def test_valid_response_passes(self, mgr):
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Hi"))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=3),
        )
        mgr = self._make_mgr_with_mock(mgr, resp)
        result = mgr._call_openai_compat("openai", "gpt-4o", MESSAGES, 100, "", TaskTier.MEDIUM)
        assert result.text == "Hi"


# ── 3. Gemini sync: IndexError on resp.text ──────────────────────────

class TestGeminiSyncEmptyResponse:
    def test_index_error_on_text_raises(self, mgr):
        """resp.text가 IndexError → ValueError 변환 확인."""
        mock_resp = MagicMock()
        type(mock_resp).text = property(lambda self: (_ for _ in ()).throw(IndexError("no candidates")))
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mgr._clients["gemini"] = mock_client

        with pytest.raises(ValueError, match="Gemini response text access failed"):
            mgr._call_gemini("gemini-2.0-flash", MESSAGES, 100, "", TaskTier.MEDIUM)

    def test_none_text_raises(self, mgr):
        """resp.text == None → ValueError."""
        mock_resp = MagicMock()
        mock_resp.text = None
        mock_resp.prompt_feedback = None
        mock_resp.candidates = []
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mgr._clients["gemini"] = mock_client

        with pytest.raises(ValueError, match="Gemini empty response"):
            mgr._call_gemini("gemini-2.0-flash", MESSAGES, 100, "", TaskTier.MEDIUM)


# ── 4. Gemini async: IndexError 방어 (B-017 핵심 수정) ────────────────

class TestGeminiAsyncEmptyResponse:
    @pytest.mark.asyncio
    async def test_index_error_on_text_raises(self, mgr):
        """async Gemini도 IndexError를 ValueError로 변환."""
        mock_resp = MagicMock()
        type(mock_resp).text = property(lambda self: (_ for _ in ()).throw(IndexError("no candidates")))
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        mgr._clients["gemini"] = mock_client

        with pytest.raises(ValueError, match="Gemini async response text access failed"):
            await mgr._acall_gemini("gemini-2.0-flash", MESSAGES, 100, "", TaskTier.MEDIUM)

    @pytest.mark.asyncio
    async def test_none_text_raises(self, mgr):
        mock_resp = MagicMock()
        mock_resp.text = None
        mock_resp.prompt_feedback = None
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        mgr._clients["gemini"] = mock_client

        with pytest.raises(ValueError, match="Gemini empty response"):
            await mgr._acall_gemini("gemini-2.0-flash", MESSAGES, 100, "", TaskTier.MEDIUM)


# ── 5. BitNet: invalid result dict ───────────────────────────────────

class TestBitNetInvalidResult:
    def test_missing_text_key_raises(self, mgr):
        with patch("packages.shared.llm.bitnet_runner.run_inference", return_value={"model": "bitnet-b1.58"}):
            with pytest.raises(ValueError, match="BitNet returned invalid result"):
                mgr._call_bitnet("bitnet-b1.58", MESSAGES, 100, "", TaskTier.LIGHTWEIGHT)

    def test_missing_model_key_raises(self, mgr):
        with patch("packages.shared.llm.bitnet_runner.run_inference", return_value={"text": "ok"}):
            with pytest.raises(ValueError, match="BitNet returned invalid result"):
                mgr._call_bitnet("bitnet-b1.58", MESSAGES, 100, "", TaskTier.LIGHTWEIGHT)

    def test_non_dict_result_raises(self, mgr):
        with patch("packages.shared.llm.bitnet_runner.run_inference", return_value="garbage"):
            with pytest.raises(ValueError, match="BitNet returned invalid result"):
                mgr._call_bitnet("bitnet-b1.58", MESSAGES, 100, "", TaskTier.LIGHTWEIGHT)

    def test_valid_result_passes(self, mgr):
        with patch("packages.shared.llm.bitnet_runner.run_inference",
                    return_value={"text": "hello", "model": "bitnet-b1.58", "tokens_generated": 5}):
            result = mgr._call_bitnet("bitnet-b1.58", MESSAGES, 100, "", TaskTier.LIGHTWEIGHT)
            assert result.text == "hello"
            assert result.backend == "bitnet"


# ── 6. LiteLLM sync/async: empty choices ─────────────────────────────

class TestLiteLLMEmptyChoices:
    def test_sync_empty_choices_raises(self, mgr):
        mock_resp = SimpleNamespace(choices=[], usage=None)
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = mock_resp
        import packages.shared.llm.backends as _backends_mod
        original = getattr(_backends_mod, "litellm", None)
        _backends_mod.litellm = mock_litellm
        try:
            with patch.object(_backends_mod, "LITELLM_AVAILABLE", True):
                with pytest.raises(ValueError, match="LiteLLM.*Empty response"):
                    mgr._call_via_litellm("grok", "grok-3", "xai/grok-3", MESSAGES, 100, "", TaskTier.MEDIUM)
        finally:
            if original is not None:
                _backends_mod.litellm = original
            elif hasattr(_backends_mod, "litellm"):
                delattr(_backends_mod, "litellm")

    @pytest.mark.asyncio
    async def test_async_empty_choices_raises(self, mgr):
        mock_resp = SimpleNamespace(choices=[], usage=None)
        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(return_value=mock_resp)
        import packages.shared.llm.backends as _backends_mod
        original = getattr(_backends_mod, "litellm", None)
        _backends_mod.litellm = mock_litellm
        try:
            with patch.object(_backends_mod, "LITELLM_AVAILABLE", True):
                with pytest.raises(ValueError, match="async LiteLLM.*Empty response"):
                    await mgr._acall_via_litellm("grok", "grok-3", "xai/grok-3", MESSAGES, 100, "", TaskTier.MEDIUM)
        finally:
            if original is not None:
                _backends_mod.litellm = original
            elif hasattr(_backends_mod, "litellm"):
                delattr(_backends_mod, "litellm")

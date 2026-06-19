"""Opt-in native structured-output schema channel (LLMPolicy.json_schema).

Pins request shape + strict normalization + per-provider gating + Gemini SDK acceptance.
The channel is additive: with json_schema=None (every current caller) behavior is unchanged.
Adoption against a live provider still needs one real call to confirm (strict schemas 400 on
malformed input even on OpenAI/Grok) — these tests catch shape/normalization errors here.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import shared.llm.backends as backends_mod
from shared.llm.backends import (
    BackendManager,
    _chat_completion_kwargs,
    _gemini_config,
    _normalize_strict_schema,
)
from shared.llm.models import LLMPolicy, TaskTier

MESSAGES = [{"role": "user", "content": "extract"}]
SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "default": "x"},
        "age": {"type": "integer", "minimum": 0},
        "tags": {"type": "array", "items": {"type": "string", "maxLength": 5}},
    },
}


class TestNormalizeStrictSchema:
    def test_object_gets_additional_props_false_and_all_required(self) -> None:
        out = _normalize_strict_schema(SCHEMA)
        assert out["additionalProperties"] is False
        assert set(out["required"]) == {"name", "age", "tags"}

    def test_unsupported_constraints_dropped(self) -> None:
        out = _normalize_strict_schema(SCHEMA)
        assert "default" not in out["properties"]["name"]
        assert "minimum" not in out["properties"]["age"]
        assert "maxLength" not in out["properties"]["tags"]["items"]

    def test_recurses_into_items(self) -> None:
        out = _normalize_strict_schema(SCHEMA)
        assert out["properties"]["tags"]["items"]["type"] == "string"

    def test_non_dict_passthrough(self) -> None:
        assert _normalize_strict_schema("x") == "x"


class TestOpenAIResponseFormat:
    def test_json_schema_produces_strict_response_format(self) -> None:
        kw = _chat_completion_kwargs("gpt-5.5", MESSAGES, 100, "text", TaskTier.HEAVY, json_schema=SCHEMA)
        rf = kw["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["strict"] is True
        assert rf["json_schema"]["schema"]["additionalProperties"] is False

    def test_no_schema_falls_back_to_json_object(self) -> None:
        kw = _chat_completion_kwargs("gpt-5.5", MESSAGES, 100, "json", TaskTier.HEAVY)
        assert kw["response_format"] == {"type": "json_object"}


class TestGeminiResponseSchema:
    def test_config_sets_response_json_schema(self) -> None:
        cfg = _gemini_config(100, "text", tier=TaskTier.HEAVY, model="gemini-3.1-pro-preview", json_schema=SCHEMA)
        assert cfg["response_json_schema"] == SCHEMA
        assert cfg["response_mime_type"] == "application/json"

    def test_gemini_schema_accepted_by_sdk(self) -> None:
        types = pytest.importorskip("google.genai.types")
        cfg = _gemini_config(100, "text", tier=TaskTier.HEAVY, model="gemini-3.1-pro-preview", json_schema=SCHEMA)
        obj = types.GenerateContentConfig(**cfg)  # must not raise on the installed SDK
        assert obj is not None


class TestProviderApplicationAndGating:
    def test_anthropic_sets_output_config(self) -> None:
        mgr = BackendManager(keys={"anthropic": "k"})
        client = MagicMock()
        client.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(text='{"name":"a"}')],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )
        mgr._clients["anthropic"] = client
        mgr._call_anthropic("claude-sonnet-4-6", MESSAGES, 100, "", TaskTier.HEAVY, "json", SCHEMA)
        oc = client.messages.create.call_args.kwargs["output_config"]
        assert oc["format"]["type"] == "json_schema"
        assert oc["format"]["schema"]["additionalProperties"] is False

    def test_uncertified_backend_keeps_json_object(self) -> None:
        # deepseek is NOT strict-capable -> json_object fallback, never a json_schema response_format.
        mgr = BackendManager(keys={"deepseek": "k"})
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"x":1}'))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )
        mgr._clients["deepseek"] = client
        with patch.object(backends_mod, "LITELLM_AVAILABLE", False):
            mgr._call_openai_compat("deepseek", "deepseek-chat", MESSAGES, 100, "", TaskTier.MEDIUM, "json", SCHEMA)
        rf = client.chat.completions.create.call_args.kwargs.get("response_format")
        assert rf == {"type": "json_object"}


class TestAdditiveDefault:
    def test_policy_json_schema_defaults_none(self) -> None:
        assert LLMPolicy().json_schema is None

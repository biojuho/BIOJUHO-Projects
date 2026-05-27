"""Phase 3 tracing instrumentation tests for structured_output.

Verifies that ``extract_structured`` and ``extract_structured_list`` open a
tracing span (sync no-op when observability env is unset) and record either
success text or the captured exception. Pure unit tests; no live SDK calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import structured_output
from pydantic import BaseModel
from structured_output import (
    _tier_str_to_enum,
    extract_structured,
    extract_structured_list,
    reset_instructor_client,
)

from shared.llm.models import TaskTier


class _Item(BaseModel):
    name: str = "x"


@pytest.fixture(autouse=True)
def _reset_client():
    reset_instructor_client()
    yield
    reset_instructor_client()


def test_tier_str_to_enum_mapping():
    assert _tier_str_to_enum("heavy") is TaskTier.HEAVY
    assert _tier_str_to_enum("medium") is TaskTier.MEDIUM
    assert _tier_str_to_enum("lightweight") is TaskTier.LIGHTWEIGHT
    assert _tier_str_to_enum("unknown") is TaskTier.LIGHTWEIGHT


@pytest.fixture
def spy_tracing(monkeypatch):
    calls: list[dict] = []
    original = structured_output.tracing.start_span

    def _spy(*, tier, system, messages, dispatcher="native"):
        span = original(tier=tier, system=system, messages=messages, dispatcher=dispatcher)
        recorded: dict = {
            "tier": tier,
            "system": system,
            "messages": messages,
            "dispatcher": dispatcher,
        }
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

    monkeypatch.setattr(structured_output.tracing, "start_span", _spy)
    return calls


@pytest.mark.asyncio
async def test_extract_structured_success_traces(monkeypatch, spy_tracing):
    fake_client = object()
    monkeypatch.setattr(structured_output, "_get_instructor_client", lambda: fake_client)
    monkeypatch.setattr(structured_output, "_get_model_name", lambda tier: f"model-{tier}")
    monkeypatch.setattr(structured_output, "_instructor_backend", "anthropic")
    monkeypatch.setattr(
        structured_output,
        "_instructor_create",
        AsyncMock(return_value=_Item(name="alpha")),
    )

    result = await extract_structured("scoring prompt", _Item, tier="heavy")
    assert result is not None
    assert result.name == "alpha"

    assert len(spy_tracing) == 1
    call = spy_tracing[0]
    assert call["dispatcher"].startswith("gdt.structured.")
    assert call["tier"] is TaskTier.HEAVY
    assert call["messages"] == [{"role": "user", "content": "scoring prompt"}]
    assert call["record_text"]["model"] == "model-heavy"
    assert call["record_text"]["backend"].startswith("instructor.")


@pytest.mark.asyncio
async def test_extract_structured_runtime_error_traces_and_returns_none(monkeypatch, spy_tracing):
    monkeypatch.setattr(structured_output, "_get_instructor_client", lambda: object())
    monkeypatch.setattr(structured_output, "_get_model_name", lambda tier: "m")
    monkeypatch.setattr(structured_output, "_instructor_backend", "gemini")
    err = RuntimeError("backend down")
    monkeypatch.setattr(structured_output, "_instructor_create", AsyncMock(side_effect=err))

    result = await extract_structured("prompt", _Item)
    assert result is None
    assert spy_tracing[0]["record_error"] is err


@pytest.mark.asyncio
async def test_extract_structured_generic_exception_traces(monkeypatch, spy_tracing):
    monkeypatch.setattr(structured_output, "_get_instructor_client", lambda: object())
    monkeypatch.setattr(structured_output, "_get_model_name", lambda tier: "m")
    monkeypatch.setattr(structured_output, "_instructor_backend", "anthropic")
    err = ValueError("schema mismatch")
    monkeypatch.setattr(structured_output, "_instructor_create", AsyncMock(side_effect=err))

    result = await extract_structured("prompt", _Item)
    assert result is None
    assert spy_tracing[0]["record_error"] is err


@pytest.mark.asyncio
async def test_extract_structured_list_success_traces(monkeypatch, spy_tracing):
    fake_client = object()
    monkeypatch.setattr(structured_output, "_get_instructor_client", lambda: fake_client)
    monkeypatch.setattr(structured_output, "_get_model_name", lambda tier: "m")
    monkeypatch.setattr(structured_output, "_instructor_backend", "anthropic")

    class _Wrapper:
        items = [_Item(name="a"), _Item(name="b"), _Item(name="c")]

    monkeypatch.setattr(structured_output, "_instructor_create", AsyncMock(return_value=_Wrapper()))

    items = await extract_structured_list("prompt", _Item, tier="lightweight", expected_count=3)
    assert items is not None
    assert len(items) == 3
    assert spy_tracing[0]["dispatcher"].startswith("gdt.structured_list.")
    assert spy_tracing[0]["tier"] is TaskTier.LIGHTWEIGHT
    assert spy_tracing[0]["record_text"]["text"] == "items=3"


@pytest.mark.asyncio
async def test_extract_structured_list_exception_traces(monkeypatch, spy_tracing):
    monkeypatch.setattr(structured_output, "_get_instructor_client", lambda: object())
    monkeypatch.setattr(structured_output, "_get_model_name", lambda tier: "m")
    monkeypatch.setattr(structured_output, "_instructor_backend", "anthropic")
    err = ConnectionError("net flaky")
    monkeypatch.setattr(structured_output, "_instructor_create", AsyncMock(side_effect=err))

    items = await extract_structured_list("prompt", _Item)
    assert items is None
    assert spy_tracing[0]["record_error"] is err

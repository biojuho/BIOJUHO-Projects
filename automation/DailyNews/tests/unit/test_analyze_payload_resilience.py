"""generate_base_payload LLM 장애 방어 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from antigravity_mcp.domain.models import ChannelDraft, ContentItem, GeneratedPayload
from antigravity_mcp.pipelines.analyze_steps import ReportAssemblyContext, generate_base_payload
from antigravity_mcp.state.store import PipelineStateStore


def _make_ctx(tmp_path, *, items=None) -> ReportAssemblyContext:
    if items is None:
        items = [
            ContentItem(
                source_name="Test",
                category="Tech",
                title="Test Article",
                link="https://example.com/1",
                summary="Summary text",
            )
        ]
    return ReportAssemblyContext(
        category="Tech",
        items=items,
        window_name="morning",
        window_start="2026-04-05T00:00:00Z",
        window_end="2026-04-05T12:00:00Z",
        state_store=PipelineStateStore(path=tmp_path / "test.db"),
        report_id="report-test-001",
        generation_mode="auto",
        fingerprint="abc123",
        source_links=["https://example.com/1"],
        enriched_items=items,
        analysis_meta={},
    )


class TestGenerateBasePayloadResilience:
    """GAP #2: LLM 호출 실패 시 파이프라인 크래시 방지."""

    @pytest.mark.asyncio
    async def test_llm_exception_returns_empty_payload(self, tmp_path):
        """LLM 어댑터가 예외를 던지면 빈 페이로드를 반환한다."""
        ctx = _make_ctx(tmp_path)
        adapter = MagicMock()
        adapter.build_report_payload = AsyncMock(side_effect=TimeoutError("LLM timeout"))

        payload = await generate_base_payload(ctx, adapter)

        assert payload.summary_lines == []
        assert payload.quality_state == "llm_error"
        assert any("LLM generation failed" in w for w in ctx.warnings)

    @pytest.mark.asyncio
    async def test_llm_json_decode_error_handled(self, tmp_path):
        """LLM이 잘못된 JSON을 반환해서 파싱 실패해도 크래시하지 않는다."""
        ctx = _make_ctx(tmp_path)
        adapter = MagicMock()
        adapter.build_report_payload = AsyncMock(side_effect=ValueError("Invalid JSON in LLM response"))

        payload = await generate_base_payload(ctx, adapter)

        assert payload.quality_state == "llm_error"
        assert ctx.summary_lines == []

    @pytest.mark.asyncio
    async def test_empty_enriched_items_skips_llm(self, tmp_path):
        """enriched_items가 비어있으면 LLM 호출 자체를 스킵한다."""
        ctx = _make_ctx(tmp_path, items=[])
        ctx.enriched_items = []
        adapter = MagicMock()
        adapter.build_report_payload = AsyncMock()

        payload = await generate_base_payload(ctx, adapter)

        adapter.build_report_payload.assert_not_called()
        assert payload.quality_state == "empty"
        assert any("No enriched items" in w for w in ctx.warnings)

    @pytest.mark.asyncio
    async def test_normal_path_succeeds(self, tmp_path):
        """정상 경로: LLM이 올바른 페이로드를 반환하면 ctx에 정상 반영된다."""
        ctx = _make_ctx(tmp_path)
        expected_payload = GeneratedPayload(
            summary_lines=["AI 기술 동향 요약"],
            insights=["반도체 시장 성장세"],
            channel_drafts=[ChannelDraft(channel="x", status="draft", content="Tech brief")],
            generation_mode="auto",
            parse_meta={"used_fallback": False, "missing_sections": [], "sections_found": {}},
            quality_state="ok",
        )
        adapter = MagicMock()
        adapter.build_report_payload = AsyncMock(return_value=(expected_payload, []))

        payload = await generate_base_payload(ctx, adapter)

        assert payload.summary_lines == ["AI 기술 동향 요약"]
        assert ctx.insights == ["반도체 시장 성장세"]
        assert ctx.quality_state == "ok"

    @pytest.mark.asyncio
    async def test_payload_with_none_fields_uses_defaults(self, tmp_path):
        """페이로드 필드가 None이어도 ctx에는 빈 리스트가 할당된다."""
        ctx = _make_ctx(tmp_path)
        broken_payload = GeneratedPayload(
            summary_lines=None,  # type: ignore[arg-type]
            insights=None,  # type: ignore[arg-type]
            channel_drafts=None,  # type: ignore[arg-type]
            generation_mode="auto",
            parse_meta={},
            quality_state=None,  # type: ignore[arg-type]
        )
        adapter = MagicMock()
        adapter.build_report_payload = AsyncMock(return_value=(broken_payload, []))

        payload = await generate_base_payload(ctx, adapter)

        assert ctx.summary_lines == []
        assert ctx.insights == []
        assert ctx.channel_drafts == []
        assert ctx.quality_state == "ok"

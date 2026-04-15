from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from antigravity_mcp.domain.models import ContentItem, GeneratedPayload
from antigravity_mcp.integrations import llm_adapter as llm_module
from antigravity_mcp.integrations.llm_adapter import (
    LLMAdapter,
    bullet_set_overlap,
    topic_overlap_score,
)


def test_topic_overlap_score_same_story_korean() -> None:
    bullets = [
        "국민연금이 환헤지 비율을 10%에서 15%로 확대, 최대 30조원 규모 원화 방어막 구축 [A1]",
        "달러-원 환율이 1500원 위협받는 상황에서 연기금이 직접 외환시장 개입 [A1]",
        "국민연금의 환헤지 확대는 '전략적' 결정으로 원화 방어 체계 강화 [A1]",
    ]
    score = topic_overlap_score(bullets)
    assert score >= 0.15, f"same-story bullets should overlap, got {score:.3f}"


def test_topic_overlap_score_distinct_stories_korean() -> None:
    bullets = [
        "차기 연준의장 후보가 개인 포트폴리오에 암호화폐 보유 중 [A1]",
        "라쿠텐의 4,400만 고객이 XRP로 결제 가능해짐 [A2]",
        "이더리움 재단이 보안 감사에 100만 달러 지원 프로그램 론칭 [A3]",
    ]
    score = topic_overlap_score(bullets)
    assert score < 0.10, f"distinct stories should barely overlap, got {score:.3f}"


def test_topic_overlap_score_handles_edge_cases() -> None:
    assert topic_overlap_score([]) == 0.0
    assert topic_overlap_score(["only one line"]) == 0.0
    assert topic_overlap_score(["", ""]) == 0.0
    assert topic_overlap_score(["same line", "same line"]) == pytest.approx(1.0, abs=0.01)


def test_bullet_set_overlap_returns_both_scores() -> None:
    summary = [
        "국민연금이 환헤지 비율을 15%로 확대",
        "국민연금 환헤지 확대로 30조원 원화 방어",
        "국민연금 외환시장 개입 공식화",
    ]
    insights = [
        "연준 암호화폐 노출 리스크가 커진다",
        "라쿠텐 XRP 결제 대중화가 가속된다",
    ]
    s, i = bullet_set_overlap(summary, insights)
    assert s >= 0.18, f"repeating-summary should score high, got {s:.3f}"
    assert i < 0.10, f"distinct insights should score low, got {i:.3f}"


def _make_payload(summary: list[str], insights: list[str]) -> GeneratedPayload:
    return GeneratedPayload(
        summary_lines=list(summary),
        insights=list(insights),
        channel_drafts=[],
        generation_mode="v1-brief",
        parse_meta={},
        quality_state="ok",
    )


def _make_items() -> list[ContentItem]:
    return [
        ContentItem(
            source_name="연합뉴스",
            category="Economy_KR",
            title="국민연금 환헤지 확대",
            link="https://example.com/a",
            summary="국민연금이 환헤지 비율을 확대했다",
        ),
        ContentItem(
            source_name="매일경제",
            category="Economy_KR",
            title="원화 방어막 구축",
            link="https://example.com/b",
            summary="연기금이 외환시장 개입을 확대한다",
        ),
    ]


@pytest.mark.asyncio
async def test_topic_diversity_retry_accepts_better_response(monkeypatch) -> None:
    adapter = LLMAdapter.__new__(LLMAdapter)
    adapter._client = type("C", (), {})()
    adapter._client.generate_text = AsyncMock()
    adapter._draft_gen = None

    original = _make_payload(
        summary=[
            "국민연금이 환헤지 비율을 10%에서 15%로 확대, 최대 30조원 원화 방어막 [A1]",
            "달러-원 환율 1500원 위협 상황에서 연기금 직접 외환시장 개입 [A1]",
            "국민연금의 환헤지 확대는 원화 약세 방어를 위한 전략적 결정 [A1]",
        ],
        insights=[
            "국민연금 환헤지 확대는 외환시장에 직접 개입하는 전례 없는 조치 [A1]",
            "연기금의 환헤지 확대가 원화 약세 방어의 마지막 보루 역할 [A1]",
        ],
    )
    retry = _make_payload(
        summary=[
            "국민연금이 환헤지 비율을 15%로 확대 [A1]",
            "한국은행이 기준금리 동결 결정 [A2]",
            "삼성전자가 HBM4 양산 일정 발표 [A3]",
        ],
        insights=[
            "금리 정책과 외환 정책이 동시에 원화 압박 완화 [A1][A2]",
            "반도체 고대역폭 메모리 경쟁력이 경상수지 개선을 견인 [A3]",
        ],
    )

    adapter._parser = type(
        "P",
        (),
        {"parse_response": staticmethod(lambda **kw: (retry, []))},
    )()
    adapter._client.generate_text.return_value = ("retry raw text", {"model_name": "m", "provider": "p"}, [])

    payload, warnings = await adapter._enforce_topic_diversity(
        payload=original,
        category="Economy_KR",
        items=_make_items(),
        window_name="morning",
        generation_mode="v1-brief",
        system_prompt="sys",
        user_prompt="usr",
    )

    assert payload.parse_meta["topic_diversity_retry"] == "accepted"
    assert payload.summary_lines == retry.summary_lines
    assert payload.parse_meta["topic_overlap_summary"] < 0.15
    assert adapter._client.generate_text.await_count == 1


@pytest.mark.asyncio
async def test_topic_diversity_retry_rejected_when_no_improvement(monkeypatch) -> None:
    adapter = LLMAdapter.__new__(LLMAdapter)
    adapter._client = type("C", (), {})()
    adapter._client.generate_text = AsyncMock()
    adapter._draft_gen = None

    original = _make_payload(
        summary=[
            "국민연금이 환헤지 비율을 15%로 확대 [A1]",
            "국민연금 환헤지 확대로 30조원 원화 방어 [A1]",
            "국민연금 외환시장 개입 공식화 [A1]",
        ],
        insights=[
            "국민연금 환헤지가 원화 방어의 핵심 축 [A1]",
            "국민연금 외환 개입은 통화 정책의 보조 수단 [A1]",
        ],
    )
    still_bad = _make_payload(
        summary=[
            "국민연금이 환헤지 확대를 발표 [A1]",
            "국민연금 환헤지 확대 배경 분석 [A1]",
            "국민연금 환헤지 확대 파급 효과 [A1]",
        ],
        insights=[
            "국민연금 환헤지 전략 전환의 의미 [A1]",
            "국민연금 환헤지 확대가 남기는 과제 [A1]",
        ],
    )

    adapter._parser = type(
        "P",
        (),
        {"parse_response": staticmethod(lambda **kw: (still_bad, []))},
    )()
    adapter._client.generate_text.return_value = ("retry raw text", {"model_name": "m", "provider": "p"}, [])

    payload, warnings = await adapter._enforce_topic_diversity(
        payload=original,
        category="Economy_KR",
        items=_make_items(),
        window_name="morning",
        generation_mode="v1-brief",
        system_prompt="sys",
        user_prompt="usr",
    )

    assert payload.parse_meta["topic_diversity_retry"] == "rejected"
    assert payload.summary_lines == original.summary_lines
    assert any("diversity_retry_rejected" in w for w in warnings)


@pytest.mark.asyncio
async def test_topic_diversity_skipped_when_already_diverse() -> None:
    adapter = LLMAdapter.__new__(LLMAdapter)
    adapter._client = type("C", (), {})()
    adapter._client.generate_text = AsyncMock()
    adapter._draft_gen = None

    good = _make_payload(
        summary=[
            "차기 연준의장 후보가 암호화폐 보유 중 [A1]",
            "라쿠텐 4,400만 고객 XRP 결제 도입 [A2]",
            "이더리움 재단 보안 감사 100만 달러 지원 [A3]",
        ],
        insights=[
            "연준 크립토 노출이 통화정책 독립성에 새 변수 [A1]",
            "유통 거대 기업의 암호화폐 결제는 실용성 분기점 [A2]",
        ],
    )
    adapter._parser = type("P", (), {"parse_response": staticmethod(lambda **kw: (good, []))})()

    payload, warnings = await adapter._enforce_topic_diversity(
        payload=good,
        category="Crypto",
        items=_make_items(),
        window_name="morning",
        generation_mode="v1-brief",
        system_prompt="sys",
        user_prompt="usr",
    )

    assert payload.parse_meta["topic_diversity_retry"] == "not_needed"
    assert adapter._client.generate_text.await_count == 0


@pytest.mark.asyncio
async def test_topic_diversity_skipped_for_v2_modes() -> None:
    adapter = LLMAdapter.__new__(LLMAdapter)
    adapter._client = type("C", (), {})()
    adapter._client.generate_text = AsyncMock()
    adapter._draft_gen = None
    adapter._parser = type("P", (), {"parse_response": staticmethod(lambda **kw: (None, []))})()

    bad = _make_payload(
        summary=["국민연금 환헤지 확대", "국민연금 원화 방어", "국민연금 외환 개입"],
        insights=["국민연금 환헤지 파급", "국민연금 환헤지 의미"],
    )

    payload, warnings = await adapter._enforce_topic_diversity(
        payload=bad,
        category="Economy_KR",
        items=_make_items(),
        window_name="morning",
        generation_mode="v2-deep",
        system_prompt="sys",
        user_prompt="usr",
    )

    assert "topic_diversity_retry" not in payload.parse_meta
    assert adapter._client.generate_text.await_count == 0

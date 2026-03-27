"""Pydantic AI 트렌드 분석 에이전트 테스트 — TestModel 사용 (실제 LLM 호출 없음)."""
from __future__ import annotations

import pytest
import pydantic_ai.models as models
from pydantic_ai.models.test import TestModel

from agents.trend_analyzer import (
    TrendScore,
    BatchTrendScores,
    trend_agent,
    batch_agent,
    AnalysisDeps,
)

# 테스트에서 실수로 실제 API 호출 방지
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def deps():
    return AnalysisDeps(country="korea", category="테크", current_time="2026-03-20 11:00 KST")


@pytest.mark.asyncio
async def test_single_trend_analysis(deps):
    """단일 트렌드 분석이 TrendScore 구조를 반환하는지 확인."""
    with trend_agent.override(model=TestModel()):
        result = await trend_agent.run("트렌드: ChatGPT", deps=deps)
        score = result.output

        assert isinstance(score, TrendScore)
        assert 0 <= score.viral_potential <= 100
        assert score.keyword  # 비어있지 않음
        assert score.category
        assert score.why_trending
        assert score.sentiment


@pytest.mark.asyncio
async def test_batch_trend_analysis(deps):
    """배치 분석이 BatchTrendScores 구조를 반환하는지 확인."""
    with batch_agent.override(model=TestModel()):
        result = await batch_agent.run(
            "1. ChatGPT\n2. Bitcoin\n3. 삼성전자",
            deps=deps,
        )
        batch = result.output

        assert isinstance(batch, BatchTrendScores)
        assert isinstance(batch.trends, list)


@pytest.mark.asyncio
async def test_output_type_validation(deps):
    """TrendScore 필드 제약 조건 검증."""
    with trend_agent.override(model=TestModel()):
        result = await trend_agent.run("트렌드: AI", deps=deps)
        score = result.output

        # viral_potential은 0-100 범위
        assert 0 <= score.viral_potential <= 100
        # 필수 필드가 모두 존재
        assert score.keyword is not None
        assert score.category is not None
        assert score.sentiment is not None
        assert score.peak_status is not None


@pytest.mark.asyncio
async def test_deps_injection(deps):
    """의존성이 에이전트 컨텍스트에 올바르게 주입되는지 확인."""
    with trend_agent.override(model=TestModel()):
        result = await trend_agent.run("test", deps=deps)
        assert result.output is not None  # 에이전트가 정상 동작

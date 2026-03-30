"""
Pydantic AI 기반 트렌드 분석 에이전트 — Phase 3-B 예제.

기존 getdaytrends analyzer.py의 LLM 스코어링을 Pydantic AI Agent로 구현.
구조화된 출력 보장, 자동 재시도, TestModel로 테스트 가능.

Usage::
    from agents.trend_analyzer import analyze_trend

    result = await analyze_trend("ChatGPT", context="AI 챗봇 경쟁 심화...")

테스트::
    python -m pytest agents/test_trend_analyzer.py -v
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

# Workspace root를 path에 추가
_WORKSPACE = Path(__file__).resolve().parents[1]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

# Pydantic AI
from pydantic_ai import Agent, RunContext

# ── 의존성 ──────────────────────────────────────────


@dataclass
class AnalysisDeps:
    """분석 에이전트의 런타임 의존성."""

    country: str = "korea"
    category: str = ""
    current_time: str = ""


# ── 구조화 출력 모델 ────────────────────────────────


class TrendScore(BaseModel):
    """트렌드 바이럴 스코어링 결과."""

    keyword: str = Field(description="트렌드 키워드")
    viral_potential: int = Field(ge=0, le=100, description="바이럴 잠재력 (0-100)")
    category: str = Field(description="카테고리 (테크, 경제, 사회, 연예, 스포츠 등)")
    why_trending: str = Field(description="왜 지금 트렌딩인지 1-2문장 설명")
    sentiment: str = Field(description="감성 (긍정/부정/중립/혼합)")
    peak_status: str = Field(description="트렌드 단계 (상승중/정점/하락중/신규)")
    content_angle: str = Field(description="콘텐츠 생성 시 추천 앵글")
    risk_note: str | None = Field(default=None, description="주의사항 (민감한 주제 등)")


class BatchTrendScores(BaseModel):
    """배치 트렌드 스코어링 결과."""

    trends: list[TrendScore] = Field(description="스코어링된 트렌드 목록")


# ── 에이전트 정의 ───────────────────────────────────

# 모델 선택: 환경변수 우선, 기본값 Gemini 2.5 Flash-Lite (무료)
# 테스트 환경에서는 'test' 모델 사용 (실제 API 호출 없음)
# 2026-03-22: gemini-2.0-flash deprecated (EOL 2026-06-01) → 2.5-flash-lite로 변경
_DEFAULT_MODEL = os.environ.get("PYDANTIC_AI_MODEL", "google-gla:gemini-2.5-flash-lite")

_SYSTEM_SINGLE = (
    "당신은 소셜 미디어 트렌드 분석 전문가입니다. "
    "주어진 트렌드 키워드와 컨텍스트를 분석하여 바이럴 잠재력을 0-100 점수로 평가합니다. "
    "한국어로 응답하세요."
)

_SYSTEM_BATCH = (
    "당신은 소셜 미디어 트렌드 분석 전문가입니다. "
    "주어진 트렌드 목록을 각각 분석하여 바이럴 잠재력을 0-100 점수로 평가합니다. "
    "한국어로 응답하세요."
)


def _get_model():
    """API 키가 있으면 실제 모델, 없으면 TestModel 반환."""
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        return _DEFAULT_MODEL
    # API 키 없으면 test 모델 (CI/테스트 환경)
    return "test"


trend_agent = Agent(
    _get_model(),
    deps_type=AnalysisDeps,
    output_type=TrendScore,
    instructions=_SYSTEM_SINGLE,
)

batch_agent = Agent(
    _get_model(),
    deps_type=AnalysisDeps,
    output_type=BatchTrendScores,
    instructions=_SYSTEM_BATCH,
)


@trend_agent.instructions
def add_time_context(ctx: RunContext[AnalysisDeps]) -> str:
    """현재 시각과 국가 정보를 동적으로 주입."""
    parts = []
    if ctx.deps.current_time:
        parts.append(f"현재 시각: {ctx.deps.current_time}")
    if ctx.deps.country:
        parts.append(f"분석 대상 국가: {ctx.deps.country}")
    if ctx.deps.category:
        parts.append(f"카테고리 힌트: {ctx.deps.category}")
    return "\n".join(parts)


@batch_agent.instructions
def add_batch_context(ctx: RunContext[AnalysisDeps]) -> str:
    """배치 분석용 컨텍스트."""
    parts = []
    if ctx.deps.current_time:
        parts.append(f"현재 시각: {ctx.deps.current_time}")
    if ctx.deps.country:
        parts.append(f"분석 대상 국가: {ctx.deps.country}")
    return "\n".join(parts)


# ── 공개 API ────────────────────────────────────────


async def analyze_trend(
    keyword: str,
    context: str = "",
    country: str = "korea",
    category: str = "",
) -> TrendScore:
    """단일 트렌드 분석. 구조화된 TrendScore 반환 보장."""
    from datetime import datetime, timedelta, timezone

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")

    deps = AnalysisDeps(country=country, category=category, current_time=now)

    prompt = f"트렌드 키워드: {keyword}"
    if context:
        prompt += f"\n\n컨텍스트:\n{context}"

    result = await trend_agent.run(prompt, deps=deps)
    return result.output


async def analyze_trends_batch(
    keywords_with_context: list[dict[str, str]],
    country: str = "korea",
) -> list[TrendScore]:
    """배치 트렌드 분석. [{"keyword": "...", "context": "..."}, ...]"""
    from datetime import datetime, timedelta, timezone

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")

    deps = AnalysisDeps(country=country, current_time=now)

    lines = []
    for i, item in enumerate(keywords_with_context, 1):
        line = f"{i}. {item['keyword']}"
        if item.get("context"):
            line += f" — {item['context'][:200]}"
        lines.append(line)

    prompt = f"다음 {len(lines)}개 트렌드를 각각 분석하세요:\n\n" + "\n".join(lines)

    result = await batch_agent.run(prompt, deps=deps)
    return result.output.trends


# ── CLI ─────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio

    async def _demo():
        print("=== Pydantic AI Trend Analyzer Demo ===\n")

        score = await analyze_trend(
            "ChatGPT",
            context="OpenAI GPT-5 출시 임박, 구글 Gemini와 경쟁 심화",
            category="테크",
        )
        print(f"Keyword: {score.keyword}")
        print(f"Viral: {score.viral_potential}/100")
        print(f"Category: {score.category}")
        print(f"Why: {score.why_trending}")
        print(f"Sentiment: {score.sentiment}")
        print(f"Angle: {score.content_angle}")

    asyncio.run(_demo())

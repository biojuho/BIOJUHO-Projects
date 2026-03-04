"""
getdaytrends v2.1 - Viral Scoring & Trend Analysis
Claude를 활용한 바이럴 포텐셜 스코어링 + 히스토리 패턴 감지 + 트렌드 클러스터링.
"""

import json
import logging
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# shared.llm 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import AppConfig
from models import MultiSourceContext, RawTrend, ScoredTrend, TrendCluster, TrendSource
from shared.llm import LLMClient, TaskTier, get_client

log = logging.getLogger(__name__)


def _robust_json_parse(text: str | None) -> dict | None:
    """마크다운 코드블록 제거 + trailing comma 수정 후 JSON 파싱."""
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # JSON 객체 추출
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


SCORING_PROMPT_TEMPLATE = """당신은 X(Twitter) 트렌드 분석기입니다.

키워드: {keyword}
현재 볼륨: {volume}

수집된 실시간 데이터:
{context}

분석 요구사항:
1. 24시간 추정 볼륨과 트렌드 가속도
2. 바이럴 가능성이 가장 높은 핵심 이슈
3. X에서 반직관적으로 해석할 수 있는 3가지 앵글

JSON으로만 응답하세요 (반드시 쌍따옴표 사용, 마크다운 백틱 없이):
{{
    "keyword": "{keyword}",
    "volume_last_24h": 1000,
    "trend_acceleration": "+10%",
    "viral_potential": 85,
    "top_insight": "가장 뜨거운 이슈 1문장",
    "suggested_angles": [
        "반직관적 앵글",
        "데이터 기반 앵글",
        "미래 예측 앵글"
    ],
    "best_hook_starter": "이 트렌드로 트윗을 시작할 최고의 한 문장"
}}"""


def score_trend(
    keyword: str,
    context: MultiSourceContext,
    volume: str,
    client: LLMClient,
) -> ScoredTrend:
    """LLM 기반 단일 트렌드 바이럴 스코어링."""
    prompt = SCORING_PROMPT_TEMPLATE.format(
        keyword=keyword,
        volume=volume,
        context=context.to_combined_text(),
    )

    try:
        response = client.create(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.text
        parsed = _robust_json_parse(raw_text)

        if not parsed:
            log.warning(f"스코어링 JSON 파싱 실패: {keyword}")
            return _default_scored_trend(keyword, context)

        return ScoredTrend(
            keyword=keyword,
            rank=0,
            volume_last_24h=parsed.get("volume_last_24h", 0),
            trend_acceleration=parsed.get("trend_acceleration", "+0%"),
            viral_potential=min(max(parsed.get("viral_potential", 0), 0), 100),
            top_insight=parsed.get("top_insight", ""),
            suggested_angles=parsed.get("suggested_angles", []),
            best_hook_starter=parsed.get("best_hook_starter", ""),
            context=context,
            sources=[TrendSource.GETDAYTRENDS],
        )

    except Exception as e:
        log.error(f"스코어링 실패 ({keyword}): {e}")
        return _default_scored_trend(keyword, context)


def _default_scored_trend(keyword: str, context: MultiSourceContext) -> ScoredTrend:
    """스코어링 실패 시 기본값."""
    return ScoredTrend(
        keyword=keyword,
        rank=0,
        context=context,
        sources=[TrendSource.GETDAYTRENDS],
    )


CLUSTERING_PROMPT = """다음 트렌드 키워드 목록에서 의미적으로 유사한 키워드를 그루핑해주세요.
각 그룹에서 가장 대표적인 키워드 하나를 representative로 선택하세요.
단독 키워드는 자기 자신만 members에 넣으세요.

키워드 목록:
{keywords}

JSON 배열로만 응답 (마크다운 백틱 없이):
[
  {{"representative": "대표 키워드", "members": ["키워드1", "키워드2"]}},
  {{"representative": "단독 키워드", "members": ["단독 키워드"]}}
]"""


def _parse_json_array(text: str) -> list | None:
    """JSON 배열 파싱 (마크다운 코드블록 제거)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def cluster_trends(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    client: LLMClient,
) -> tuple[list[RawTrend], dict[str, MultiSourceContext], list[TrendCluster]]:
    """
    트렌드 클러스터링: 유사 키워드 그루핑 후 대표만 남김.
    대표 키워드의 컨텍스트에 멤버 컨텍스트 병합.
    """
    if len(raw_trends) <= 2:
        clusters = [TrendCluster(representative=t.name, members=[t.name]) for t in raw_trends]
        return raw_trends, contexts, clusters

    keywords = [t.name for t in raw_trends]
    prompt = CLUSTERING_PROMPT.format(keywords="\n".join(f"- {k}" for k in keywords))

    try:
        response = client.create(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        parsed = _parse_json_array(response.text)
    except Exception as e:
        log.warning(f"클러스터링 API 실패, 스킵: {e}")
        parsed = None

    if not parsed:
        clusters = [TrendCluster(representative=t.name, members=[t.name]) for t in raw_trends]
        return raw_trends, contexts, clusters

    # 클러스터 구성
    clusters: list[TrendCluster] = []
    representative_names: set[str] = set()
    trend_map = {t.name: t for t in raw_trends}

    for group in parsed:
        rep = group.get("representative", "")
        members = group.get("members", [rep])
        # 대표가 실제 키워드에 있는지 확인
        if rep not in trend_map:
            valid = [m for m in members if m in trend_map]
            rep = valid[0] if valid else ""
        if not rep:
            continue

        # 멤버 컨텍스트 병합
        merged_twitter, merged_reddit, merged_news = [], [], []
        for m in members:
            ctx = contexts.get(m, MultiSourceContext())
            if ctx.twitter_insight and "오류" not in ctx.twitter_insight:
                merged_twitter.append(ctx.twitter_insight)
            if ctx.reddit_insight and "없음" not in ctx.reddit_insight:
                merged_reddit.append(ctx.reddit_insight)
            if ctx.news_insight and "없음" not in ctx.news_insight:
                merged_news.append(ctx.news_insight)

        merged_ctx = MultiSourceContext(
            twitter_insight="\n".join(merged_twitter) if merged_twitter else contexts.get(rep, MultiSourceContext()).twitter_insight,
            reddit_insight="\n".join(merged_reddit) if merged_reddit else contexts.get(rep, MultiSourceContext()).reddit_insight,
            news_insight="\n".join(merged_news) if merged_news else contexts.get(rep, MultiSourceContext()).news_insight,
        )
        contexts[rep] = merged_ctx

        clusters.append(TrendCluster(representative=rep, members=members, merged_context=merged_ctx))
        representative_names.add(rep)

    # 대표 키워드만 남긴 raw_trends 재구성
    filtered = [t for t in raw_trends if t.name in representative_names]

    # 클러스터에 포함 안 된 키워드도 보존
    clustered_all = set()
    for c in clusters:
        clustered_all.update(c.members)
    for t in raw_trends:
        if t.name not in clustered_all:
            filtered.append(t)
            clusters.append(TrendCluster(representative=t.name, members=[t.name]))

    merged_count = sum(len(c.members) for c in clusters if len(c.members) > 1)
    if merged_count:
        log.info(f"클러스터링: {len(raw_trends)}개 → {len(filtered)}개 (병합 {merged_count}개 키워드)")

    return filtered, contexts, clusters


def analyze_trends(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    config: AppConfig,
) -> list[ScoredTrend]:
    """
    전체 트렌드 스코어링 후 viral_potential 내림차순 정렬.
    enable_clustering이면 유사 트렌드를 먼저 그루핑.
    """
    client = get_client()

    # 클러스터링
    clusters = []
    if config.enable_clustering:
        raw_trends, contexts, clusters = cluster_trends(
            raw_trends, contexts, client,
        )

    scored: list[ScoredTrend] = []

    for i, trend in enumerate(raw_trends):
        keyword = trend.name
        context = contexts.get(keyword, MultiSourceContext())

        log.info(f"  스코어링 [{i + 1}/{len(raw_trends)}]: '{keyword}'")
        result = score_trend(
            keyword=keyword,
            context=context,
            volume=trend.volume,
            client=client,
        )
        result.rank = trend.volume_numeric  # 원본 볼륨 기반 순위 참고용
        result.country = trend.country or config.country

        # 소스 정보 보강
        sources = [TrendSource.GETDAYTRENDS]
        if context.twitter_insight and "미설정" not in context.twitter_insight:
            sources.append(TrendSource.TWITTER)
        if context.reddit_insight and "없음" not in context.reddit_insight:
            sources.append(TrendSource.REDDIT)
        if context.news_insight and "없음" not in context.news_insight:
            sources.append(TrendSource.GOOGLE_NEWS)
        result.sources = sources

        scored.append(result)

        # API rate limit 방지
        if i < len(raw_trends) - 1:
            time.sleep(2)

    # viral_potential 내림차순 정렬
    scored.sort(key=lambda x: x.viral_potential, reverse=True)

    # 순위 재할당
    for i, s in enumerate(scored):
        s.rank = i + 1

    log.info(f"스코어링 완료: {len(scored)}개 (최고 점수: {scored[0].viral_potential if scored else 0})")
    return scored


def detect_trend_patterns(
    conn: sqlite3.Connection, keyword: str, days: int = 7
) -> dict:
    """SQLite 히스토리 기반 반복 트렌드 감지."""
    from db import get_trend_history

    history = get_trend_history(conn, keyword, days)

    if not history:
        return {
            "seen_count": 0,
            "avg_score": 0.0,
            "is_recurring": False,
            "score_trend": "new",
        }

    scores = [h["viral_potential"] for h in history]
    avg_score = sum(scores) / len(scores) if scores else 0

    # 점수 추세 판단
    if len(scores) >= 2:
        recent_avg = sum(scores[: len(scores) // 2]) / max(len(scores) // 2, 1)
        older_avg = sum(scores[len(scores) // 2 :]) / max(len(scores) - len(scores) // 2, 1)
        if recent_avg > older_avg + 5:
            score_trend = "rising"
        elif recent_avg < older_avg - 5:
            score_trend = "falling"
        else:
            score_trend = "stable"
    else:
        score_trend = "new"

    return {
        "seen_count": len(history),
        "avg_score": round(avg_score, 1),
        "first_seen": history[-1]["scored_at"] if history else None,
        "last_seen": history[0]["scored_at"] if history else None,
        "is_recurring": len(history) >= 3,
        "score_trend": score_trend,
    }

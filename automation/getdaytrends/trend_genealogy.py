"""
getdaytrends — Trend Genealogy (v5.0)
트렌드 계보 분석(인과관계 감지) + 파생 트렌드 예측.
analyzer.py에서 분리됨.
"""

import json
import sqlite3

from loguru import logger as log
from shared.llm import LLMClient, TaskTier
from shared.llm.models import LLMPolicy

_JSON_POLICY = LLMPolicy(response_mode="json", task_kind="json_extraction")


# ══════════════════════════════════════════════════════
#  Trend Pattern Detection
# ══════════════════════════════════════════════════════


async def detect_trend_patterns(conn: sqlite3.Connection, keyword: str, days: int = 7) -> dict:
    """SQLite 히스토리 기반 반복 트렌드 감지."""
    from db import get_trend_history

    history = await get_trend_history(conn, keyword, days)

    if not history:
        return {
            "seen_count": 0,
            "avg_score": 0.0,
            "is_recurring": False,
            "score_trend": "new",
        }

    scores = [h["viral_potential"] for h in history]
    avg_score = sum(scores) / len(scores) if scores else 0

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


# ══════════════════════════════════════════════════════
#  [A] Trend Genealogy — 트렌드 계보 분석 + 파생 예측
# ══════════════════════════════════════════════════════

_GENEALOGY_PROMPT = """당신은 트렌드 인과관계 분석 전문가입니다.
현재 시각: {current_time}

현재 트렌드 키워드 목록:
{current_keywords}

최근 72시간 내 이전 트렌드 히스토리:
{history_keywords}

[분석 과제]
1. 현재 트렌드 중 이전 트렌드에서 파생된 것이 있는지 판단하라.
   - "파생"이란: 이전 트렌드가 원인이 되어 새로운 트렌드가 발생한 관계.
   - 예: "대통령 담화" → "환율 급등" → "수출기업 실적 전망"
2. 각 현재 트렌드에 대해, 향후 24시간 내 파생될 수 있는 후속 트렌드를 1-2개 예측하라.

[JSON 배열로만 응답]
[
  {{
    "keyword": "현재 트렌드 키워드",
    "parent_keyword": "이 트렌드의 원인이 된 이전 트렌드 (없으면 빈 문자열)",
    "predicted_children": ["24시간 내 파생 예상 키워드1", "파생 예상 키워드2"],
    "confidence": 0.8
  }}
]
규칙:
- 억지 연결 금지. 인과관계가 명확할 때만 parent_keyword 설정
- confidence: 0.0~1.0, 연결 확신도
- predicted_children: 최대 2개, 구체적이고 검색 가능한 키워드"""


def _parse_json_array(text: str | None) -> list | None:
    """JSON 배열 파싱."""
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


async def analyze_trend_genealogy(
    current_trends: list,
    history_trends: list[dict],
    client: "LLMClient",
    config=None,
) -> list[dict]:
    """[A] 현재 트렌드와 과거 트렌드 간 계보 관계 분석 + 파생 예측.

    Returns:
        [{"keyword": str, "parent_keyword": str, "predicted_children": [...], "confidence": float}]
    """
    if not current_trends:
        return []

    from datetime import datetime as _dt

    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    current_keywords = "\n".join(
        f"- {t.keyword} (카테고리: {t.category}, 바이럴: {t.viral_potential})" for t in current_trends[:15]
    )

    history_keywords = "없음 (첫 실행)"
    if history_trends:
        history_keywords = "\n".join(
            f"- {h.get('keyword', '?')} (최고점수: {h.get('peak_viral_score', 0)}, "
            f"마지막: {h.get('last_seen_at', '?')[:16]})"
            for h in history_trends[:20]
        )

    prompt = _GENEALOGY_PROMPT.format(
        current_time=current_time,
        current_keywords=current_keywords,
        history_keywords=history_keywords,
    )

    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=1500,
            policy=_JSON_POLICY,
            system="트렌드 인과관계 분석 전문가. JSON 배열로만 응답.",
            messages=[{"role": "user", "content": prompt}],
        )
        results = _parse_json_array(response.text)
        if not results:
            log.warning("[Genealogy] JSON 파싱 실패")
            return []

        valid = []
        for r in results:
            if not isinstance(r, dict) or "keyword" not in r:
                continue
            valid.append(
                {
                    "keyword": r.get("keyword", ""),
                    "parent_keyword": r.get("parent_keyword", ""),
                    "predicted_children": r.get("predicted_children", [])[:2],
                    "confidence": min(max(float(r.get("confidence", 0.0)), 0.0), 1.0),
                }
            )

        log.info(
            f"[Genealogy] 계보 분석 완료: {len(valid)}개 트렌드, "
            f"연결 발견: {sum(1 for v in valid if v['parent_keyword'])}개"
        )
        return valid

    except Exception as e:
        log.error(f"[Genealogy] 분석 실패: {e}")
        return []


def enrich_trends_with_genealogy(
    trends: list,
    genealogy_results: list[dict],
) -> list:
    """[A] 계보 분석 결과를 ScoredTrend에 반영."""
    if not genealogy_results:
        return trends

    genealogy_map = {g["keyword"]: g for g in genealogy_results}

    for trend in trends:
        g = genealogy_map.get(trend.keyword)
        if not g:
            continue
        if g.get("parent_keyword"):
            trend.parent_trends = [g["parent_keyword"]]
            trend.genealogy_depth = 1
        if g.get("predicted_children"):
            trend.predicted_children = g["predicted_children"]

    return trends

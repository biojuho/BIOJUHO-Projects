"""
getdaytrends — Trend Genealogy (v5.0)
트렌드 계보 분석(인과관계 감지) + 파생 트렌드 예측.
analyzer.py에서 분리됨.
"""

import json
import re
import sqlite3
from datetime import datetime

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


def _json_array_candidates(stripped: str) -> list[str]:
    candidates = [stripped]
    fence_match = re.match(r"^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$", stripped, re.IGNORECASE)
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end != -1 and start < end:
        candidates.append(stripped[start : end + 1])

    return candidates


def _array_from_json_value(parsed: object) -> list | None:
    if isinstance(parsed, list):
        return parsed
    if not isinstance(parsed, dict):
        return None
    for key in ("items", "results", "data", "trends"):
        value = parsed.get(key)
        if isinstance(value, list):
            return value
    return None


def _parse_json_array(text: str | None) -> list | None:
    """JSON array parsing with markdown and wrapper-object fallbacks."""
    if not text:
        return None
    stripped = text.strip()
    seen: set[str] = set()
    for candidate in _json_array_candidates(stripped):
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        parsed_array = _array_from_json_value(parsed)
        if parsed_array is not None:
            return parsed_array
    return None

async def analyze_trend_genealogy(
    current_trends: list,
    history_trends: list[dict],
    client: "LLMClient",
    config=None,
) -> list[dict]:
    """Analyze causal trend genealogy and return normalized relationships."""
    if not current_trends:
        return []

    try:
        response = await _request_genealogy_analysis(client, current_trends, history_trends)
        results = _parse_json_array(response.text)
        if not results:
            log.warning("[Genealogy] JSON parsing failed")
            return []

        valid = _valid_genealogy_results(results)
        log.info(
            f"[Genealogy] completed: {len(valid)} trends, "
            f"linked: {sum(1 for item in valid if item['parent_keyword'])}"
        )
        return valid

    except Exception as exc:
        log.error(f"[Genealogy] analysis failed: {exc}")
        return []


async def _request_genealogy_analysis(client: "LLMClient", current_trends: list, history_trends: list[dict]) -> object:
    return await client.acreate(
        tier=TaskTier.LIGHTWEIGHT,
        max_tokens=1500,
        policy=_JSON_POLICY,
        system="Trend causality analyst. Reply only with a JSON array.",
        messages=[{"role": "user", "content": _genealogy_prompt(current_trends, history_trends)}],
    )


def _genealogy_prompt(current_trends: list, history_trends: list[dict]) -> str:
    return _GENEALOGY_PROMPT.format(
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M (KST)"),
        current_keywords=_current_trend_lines(current_trends),
        history_keywords=_history_trend_lines(history_trends),
    )


def _current_trend_lines(current_trends: list) -> str:
    return "\n".join(
        f"- {trend.keyword} (category: {trend.category}, viral: {trend.viral_potential})"
        for trend in current_trends[:15]
    )


def _history_trend_lines(history_trends: list[dict]) -> str:
    if not history_trends:
        return "none (first run)"
    return "\n".join(
        f"- {item.get('keyword', '?')} (peak: {item.get('peak_viral_score', 0)}, "
        f"last: {item.get('last_seen_at', '?')[:16]})"
        for item in history_trends[:20]
    )


def _valid_genealogy_results(results: list) -> list[dict]:
    valid = []
    for item in results:
        normalized = _normalize_genealogy_result(item)
        if normalized:
            valid.append(normalized)
    return valid


def _normalize_genealogy_result(item: object) -> dict | None:
    if not isinstance(item, dict) or "keyword" not in item:
        return None
    return {
        "keyword": item.get("keyword", ""),
        "parent_keyword": item.get("parent_keyword", ""),
        "predicted_children": item.get("predicted_children", [])[:2],
        "confidence": min(max(float(item.get("confidence", 0.0)), 0.0), 1.0),
    }


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

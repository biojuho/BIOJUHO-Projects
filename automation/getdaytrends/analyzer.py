"""
getdaytrends v3.0 - Viral Scoring & Trend Analysis
Claude를 활용한 바이럴 포텐셜 스코어링 + 히스토리 패턴 감지 + 트렌드 클러스터링.
async/await 기반 병렬 스코어링 + JSON structured output + 스코어 캐시 + 재시도 지원.
v3.0: 배치 스코어링(5개/호출, 비용 ~70% 절감) + sentiment/safety_flag 분석 추가.
"""

import asyncio
import json
import re
import sqlite3

from loguru import logger as log

from shared.llm import LLMClient, TaskTier, get_client
from shared.llm.models import LLMPolicy

# -- 추출된 모듈 re-export (후방 호환) --
try:
    from .analysis.parsing import (
        INSTRUCTOR_AVAILABLE,
        _default_scored_trend,
        _parse_json,
        _parse_json_array,
        _parse_scored_trend_from_dict,
        _score_batch_instructor,
    )
    from .config import AppConfig
    from .db import compute_fingerprint, get_cached_score
    from .models import MultiSourceContext, RawTrend, ScoredTrend, TrendSource
    from .trend_clustering import _jaccard_similarity, cluster_trends, cluster_trends_local
    from .trend_genealogy import (
        analyze_trend_genealogy,
        detect_trend_patterns,
        enrich_trends_with_genealogy,
    )
    from .utils import run_async, sanitize_keyword
except ImportError:
    from analysis.parsing import (  # noqa: F401
        INSTRUCTOR_AVAILABLE,
        _default_scored_trend,
        _parse_json,
        _parse_json_array,
        _parse_scored_trend_from_dict,
        _score_batch_instructor,
    )
    from config import AppConfig
    from db import compute_fingerprint, get_cached_score
    from models import MultiSourceContext, RawTrend, ScoredTrend, TrendSource
    from trend_clustering import _jaccard_similarity, cluster_trends, cluster_trends_local  # noqa: F401
    from trend_genealogy import (  # noqa: F401
        analyze_trend_genealogy,
        detect_trend_patterns,
        enrich_trends_with_genealogy,
    )
    from utils import run_async, sanitize_keyword


_PACKAGES_PATH_INJECTED = False  # B-013 fix: sys.path 중복 삽입 방지 플래그


def _extract_json_string_field(text: str, field: str) -> str | None:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if not match:
        return None
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return match.group(1)


def _extract_json_int_field(text: str, field: str) -> int | None:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*(-?\d+)', text)
    return int(match.group(1)) if match else None


def _extract_json_bool_field(text: str, field: str) -> bool | None:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*(true|false)', text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).lower() == "true"


def _extract_json_string_list_field(text: str, field: str) -> list[str] | None:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*\[(.*?)\]', text, re.DOTALL)
    if not match:
        return None
    values = []
    for item in re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1)):
        try:
            values.append(json.loads(f'"{item}"'))
        except json.JSONDecodeError:
            values.append(item)
    return values


def _salvage_scoring_payload(text: str | None) -> dict | None:
    """Best-effort recovery for truncated scoring JSON payloads."""
    if not text:
        return None

    payload = {
        **_salvage_string_fields(text),
        **_salvage_int_fields(text),
        **_salvage_bool_fields(text),
        **_salvage_list_fields(text),
    }

    if "viral_potential" not in payload and "publishable" not in payload:
        return None
    return payload


def _salvage_string_fields(text: str) -> dict[str, object]:
    fields = (
        "keyword",
        "trend_acceleration",
        "top_insight",
        "best_hook_starter",
        "category",
        "sentiment",
        "why_trending",
        "peak_status",
        "publishability_reason",
        "corrected_keyword",
        "joongyeon_angle",
    )
    return _salvage_fields(text, fields, _extract_json_string_field)


def _salvage_int_fields(text: str) -> dict[str, object]:
    fields = ("volume_last_24h", "viral_potential", "relevance_score", "joongyeon_kick")
    return _salvage_fields(text, fields, _extract_json_int_field)


def _salvage_bool_fields(text: str) -> dict[str, object]:
    return _salvage_fields(text, ("publishable", "safety_flag"), _extract_json_bool_field)


def _salvage_list_fields(text: str) -> dict[str, object]:
    suggested_angles = _extract_json_string_list_field(text, "suggested_angles")
    return {"suggested_angles": suggested_angles} if suggested_angles is not None else {}


def _salvage_fields(text: str, fields: tuple[str, ...], extractor) -> dict[str, object]:
    payload: dict[str, object] = {}
    for field in fields:
        value = extractor(text, field)
        if value is not None:
            payload[field] = value
    return payload


def _topic_boost(keyword: str) -> int:
    """DailyNews 활성 카테고리 기반 viral score boost (+0~+20pt)."""
    global _PACKAGES_PATH_INJECTED
    try:
        if not _PACKAGES_PATH_INJECTED:
            import pathlib
            import sys

            _pkg_path = str(pathlib.Path(__file__).resolve().parents[3] / "packages")
            if _pkg_path not in sys.path:
                sys.path.insert(0, _pkg_path)
            _PACKAGES_PATH_INJECTED = True
        from shared.intelligence import get_score_boost

        return get_score_boost(keyword)
    except ImportError:
        log.warning("shared.intelligence 모듈 없음 — topic boost 비활성 (packages/ 경로 확인 필요)")
        return 0
    except (AttributeError, ValueError, OSError) as e:
        log.warning(f"topic boost 실패 ({keyword}): {e}")
        return 0


# ══════════════════════════════════════════════════════
#  Scoring Prompt
# ══════════════════════════════════════════════════════

SCORING_PROMPT_TEMPLATE = """당신은 소셜 미디어 트렌드 분석 전문가입니다.
현재 시각: {current_time}

키워드: {keyword}
현재 볼륨: {volume}

수집된 실시간 데이터:
{context}

[핵심 분석 원칙]
- "왜 트렌드인지"가 아니라 "왜 지금 이 시점에 폭발했는지" 인과관계를 추론할 것
- 추상적 표현("최근 논란", "화제가 되고 있다") 절대 금지 — 구체적 사건/숫자로 설명
- 컨텍스트에 나온 실제 데이터를 근거로 분석할 것
- 키워드가 문장 조각이거나 의미 불명이면 publishable=false로 판정

다음 JSON 스키마로 정확히 응답:
{{
    "keyword": "{keyword}",
    "publishable": true,
    "publishability_reason": "게시 불가 사유 (publishable=true면 빈 문자열)",
    "corrected_keyword": "오타/약어인 경우 교정된 원본 (정상이면 빈 문자열)",
    "volume_last_24h": 1000,
    "trend_acceleration": "+10%",
    "viral_potential": 85,
    "top_insight": "가장 뜨거운 이슈 1문장",
    "why_trending": "왜 지금 이 트렌드가 뜨는지 원인 1-2문장 추론",
    "peak_status": "상승중|정점|하락중 중 하나",
    "relevance_score": 7,
    "suggested_angles": ["반직관적 앵글", "데이터 기반 앵글", "미래 예측 앵글"],
    "best_hook_starter": "타임라인에서 스크롤 멈추게 하는 첫 문장. 반드시 아래 6가지 패턴 중 하나: 숫자충격('3일 만에 2000억 증발'), 체감환산('월급 250만원 받는 사람한테'), 반전선언('이거 좋은 뉴스라고 생각하면 큰일남'), 내부자시선('이 업계에서 보기에'), 대조병치('그쪽은 축배를 드는데 이쪽은 이력서를 쓴다'), 질문도발('이거 왜 아무도 이상하다고 안 함?'). '화제가 되고 있다' 식 기자체 금지",
    "category": "연예|스포츠|정치|경제|테크|사회|국제|날씨|음식|게임|기타 중 하나",
    "sentiment": "positive|neutral|negative|harmful 중 하나",
    "safety_flag": false,
    "trigger_event": "촉발 사건/발언/발표 (시점 포함)",
    "chain_reaction": "촉발 이후 전개 과정",
    "why_now": "지금 터진 특수한 이유",
    "key_positions": ["찬성측 주장", "반대측 주장"]
}}
- publishable: 이 키워드로 의미 있는 SNS 콘텐츠를 만들 수 있으면 true. 문장 조각·의미불명이면 false
- corrected_keyword: 오타·축약어이면 교정 원본 제시. 정상이면 빈 문자열
- safety_flag=true 조건: 재난/사망/폭력/혐오/자살, 그리고 정치·외교적 갈등(반미/반일/반한) 및 페미니즘 등 특정 이념·성별 갈등 이슈 트렌드."""


# ── 배치 스코어링 프롬프트 (Phase 2: 5개/호출, 비용 ~70% 절감) ──

BATCH_SCORING_PROMPT_TEMPLATE = """당신은 소셜 미디어 트렌드 분석 전문가입니다.
현재 시각: {current_time}
아래 {n}개의 트렌드를 동시에 분석하세요.

트렌드 목록 (JSON):
{trends_json}

[핵심 분석 원칙]
1. "왜 트렌드인지"가 아니라 "왜 지금 이 시점에 폭발했는지" 인과관계를 추론할 것
2. 컨텍스트에 나온 실제 데이터(수치, 발언, 사건)를 근거로 분석할 것
3. 추상적 표현("최근 논란", "화제가 되고 있다") 절대 금지 — 구체적 사건/숫자로 설명
4. X에서 활발히 논의되기 적합한 트렌드만 높은 relevance_score 부여
5. 이미 하락세인 트렌드는 peak_status=하락중으로 표시
6. **게시 가능성(publishable)을 반드시 판단**: 아래 경우 publishable=false 처리
   - 문장 조각 (예: "아주 여리고", "그래서 결국") → 완전한 개념이 아님
   - 의미 불명 키워드 → 컨텍스트로도 뭔지 알 수 없음
   - 오타·약어 키워드 → corrected_keyword에 교정된 원본을 제시 (publishable은 true로 유지하되 교정)

[정보 정확성 원칙 — 필수]
7. **팩트 그라운딩**: why_trending, trigger_event, top_insight에는 반드시 컨텍스트에 실제로 존재하는 사건/수치/발언만 사용할 것
8. **수치 정확성**: 숫자(금액, 인원, 비율)는 컨텍스트에 나온 것만 사용. 확인 불가한 수치는 "약", "추정" 등 한정어 부착
9. **기관/인물 정확성**: 기관명, 인물명은 컨텍스트에 명시적으로 언급된 경우에만 사용. 추론으로 기관명을 만들지 말 것
10. **출처 불명 주장 금지**: "전문가들은", "관계자에 따르면" 등 출처 불명 인용은 0점. 컨텍스트에 실제 출처가 있을 때만 인용

각 트렌드에 대해 반드시 다음 JSON 배열로 응답 (순서와 개수 유지):
[
  {{
    "keyword": "원본 키워드 (변경 금지)",
    "publishable": true,
    "publishability_reason": "게시 불가 사유 (publishable=true면 빈 문자열)",
    "corrected_keyword": "오타/약어인 경우 교정된 원본 (정상이면 빈 문자열)",
    "volume_last_24h": 1000,
    "trend_acceleration": "+10%",
    "viral_potential": 85,
    "top_insight": "핵심 이슈 1문장",
    "why_trending": "왜 지금 이 트렌드가 뜨는지 원인 1-2문장 추론",
    "peak_status": "상승중|정점|하락중 중 하나",
    "relevance_score": 7,
    "suggested_angles": ["앵글1", "앵글2", "앵글3"],
    "best_hook_starter": "타임라인에서 스크롤 멈추게 하는 첫 문장 (6패턴: 숫자충격/체감환산/반전선언/내부자시선/대조병치/질문도발. 기자체 금지)",
    "category": "연예|스포츠|정치|경제|테크|사회|국제|날씨|음식|게임|기타 중 하나",
    "sentiment": "positive|neutral|negative|harmful 중 하나",
    "safety_flag": false,
    "joongyeon_kick": 80,
    "joongyeon_angle": "현상의 역설이나 반전이 담긴 단 한 문장 (없으면 빈 문자열)",
    "trigger_event": "이 트렌드를 촉발한 구체적 사건/발언/발표 (시점 포함, 예: 'OO장관 XX 발언 3시간 전')",
    "chain_reaction": "촉발 사건 이후 전개 과정 (예: '커뮤니티 확산 → 언론 보도 → 반박 성명')",
    "why_now": "과거에도 비슷한 이슈가 있었지만 '지금' 터진 특수한 이유 (시의성)",
    "key_positions": ["찬성/지지 측 핵심 주장", "반대/비판 측 핵심 주장"]
  }}
]
규칙:
- 반드시 JSON 배열만 출력 (설명 금지)
- 배열 길이 = {n}개 (입력 트렌드 수와 동일)
- publishable: 이 키워드로 의미 있는 SNS 콘텐츠를 만들 수 있으면 true. 문장 조각·의미불명이면 false
- corrected_keyword: 오타·축약어(예: "카이로류"→"아카이로 류")면 교정 원본 제시. 정상이면 빈 문자열
- safety_flag=true: 재난/사망/폭력/혐오/자살 및 정치·사회 갈등(반미/반일/반한/페미니즘) 트렌드
- relevance_score: 1~10, X에서 논의하기 적합할수록 높음
- joongyeon_kick: 0~100, 현상의 역설·이면·반전을 뽑을 수 있으면 높음. 단순 사실 전달이면 낮음
- trigger_event/chain_reaction/why_now: 컨텍스트에서 근거를 찾아 구체적으로 작성. 모르면 빈 문자열
- key_positions: 실제 논쟁이 있는 경우만 작성. 논쟁 없으면 빈 배열"""

_JSON_POLICY = LLMPolicy(response_mode="json", task_kind="json_extraction")
# Batch scoring expects a JSON array, so avoid provider-specific object-prefill
# helpers that are tuned for `{...}` payloads.
_JSON_ARRAY_POLICY = LLMPolicy(response_mode="text", task_kind="json_extraction")
_SINGLE_SCORE_MAX_TOKENS = 1200
_SINGLE_SCORE_RETRY_MAX_TOKENS = 1800
_BATCH_SCORE_MAX_TOKENS_PER_ITEM = 900
_BATCH_SCORE_RETRY_MAX_TOKENS_PER_ITEM = 1400


try:
    from .analysis.scoring import (
        _compute_cross_source_confidence,
        _compute_freshness_score,
        _compute_signal_score,
    )
except ImportError:
    from analysis.scoring import (  # noqa: F401
        _compute_cross_source_confidence,
        _compute_freshness_score,
        _compute_signal_score,
    )


def _cached_score_to_trend(keyword: str, context: MultiSourceContext, volume_numeric: int, cached: dict) -> ScoredTrend:
    angles = (
        json.loads(cached.get("suggested_angles", "[]"))
        if isinstance(cached.get("suggested_angles"), str)
        else cached.get("suggested_angles", [])
    )
    return ScoredTrend(
        keyword=keyword,
        rank=0,
        volume_last_24h=volume_numeric,
        trend_acceleration=cached.get("trend_acceleration", "+0%"),
        viral_potential=cached["viral_potential"],
        top_insight=cached.get("top_insight", ""),
        suggested_angles=angles,
        best_hook_starter=cached.get("best_hook_starter", ""),
        context=context,
        sources=[TrendSource.GETDAYTRENDS],
    )


async def _get_cached_scored_trend(
    conn: sqlite3.Connection | None,
    keyword: str,
    context: MultiSourceContext,
    volume_numeric: int,
) -> ScoredTrend | None:
    if conn is None:
        return None
    fingerprint = compute_fingerprint(keyword, volume_numeric)
    cached = await get_cached_score(conn, fingerprint, max_age_hours=18)
    if not cached:
        return None
    log.info(f"  [罹먯떆] '{keyword}' ?ㅼ퐫???ъ궗??({cached['viral_potential']}??")
    return _cached_score_to_trend(keyword, context, volume_numeric, cached)


def _single_score_prompt(keyword: str, volume: str, context: MultiSourceContext) -> str:
    from datetime import datetime as _dt

    return SCORING_PROMPT_TEMPLATE.format(
        keyword=sanitize_keyword(keyword),
        volume=volume,
        context=context.to_combined_text(),
        current_time=_dt.now().strftime("%Y-%m-%d %H:%M (KST)"),
    )


async def _request_single_score(client: LLMClient, prompt: str, attempt: int) -> object:
    max_tokens = _SINGLE_SCORE_MAX_TOKENS if attempt == 0 else _SINGLE_SCORE_RETRY_MAX_TOKENS
    return await client.acreate(
        tier=TaskTier.LIGHTWEIGHT,
        max_tokens=max_tokens,
        policy=_JSON_POLICY,
        messages=[{"role": "user", "content": prompt}],
    )


def _parse_single_score_payload(text: str, keyword: str, attempt: int) -> dict | None:
    parsed = _parse_json(text)
    if parsed:
        return parsed
    parsed = _salvage_scoring_payload(text)
    if parsed:
        log.warning(f"??쇳맜??彛?JSON ?봔?브쑬?ф뤃? ????({attempt + 1}/2): {keyword}")
    return parsed


def _single_score_to_trend(
    parsed: dict,
    keyword: str,
    context: MultiSourceContext,
) -> ScoredTrend:
    raw_category = parsed.get("category", "")
    category = raw_category.split("|")[0].strip() if raw_category else ""
    pub = parsed.get("publishable", True)
    if isinstance(pub, str):
        pub = pub.lower() not in ("false", "0", "no")

    return ScoredTrend(
        keyword=keyword,
        rank=0,
        volume_last_24h=parsed.get("volume_last_24h", 0),
        trend_acceleration=parsed.get("trend_acceleration", "+0%"),
        viral_potential=min(max(parsed.get("viral_potential", 0), 0) + _topic_boost(keyword), 100),
        top_insight=parsed.get("top_insight", ""),
        suggested_angles=parsed.get("suggested_angles", []),
        best_hook_starter=parsed.get("best_hook_starter", ""),
        category=category,
        context=context,
        sources=[TrendSource.GETDAYTRENDS],
        sentiment=parsed.get("sentiment", "neutral"),
        safety_flag=bool(parsed.get("safety_flag", False)),
        why_trending=parsed.get("why_trending", ""),
        peak_status=parsed.get("peak_status", ""),
        relevance_score=min(max(int(parsed.get("relevance_score", 0)), 0), 10),
        publishable=bool(pub),
        publishability_reason=parsed.get("publishability_reason", ""),
        corrected_keyword=parsed.get("corrected_keyword", ""),
    )


async def _score_trend_async(
    keyword: str,
    context: MultiSourceContext,
    volume: str,
    volume_numeric: int,
    client: LLMClient,
    conn: sqlite3.Connection | None = None,
) -> ScoredTrend:
    """단일 트렌드 비동기 스코어링 (캐시 조회 -> LLM 호출, 최대 2회 시도)."""
    cached_trend = await _get_cached_scored_trend(conn, keyword, context, volume_numeric)
    if cached_trend:
        return cached_trend

    prompt = _single_score_prompt(keyword, volume, context)
    for attempt in range(2):
        try:
            response = await _request_single_score(client, prompt, attempt)
            parsed = _parse_single_score_payload(response.text, keyword, attempt)
            if not parsed:
                log.warning(f"스코어링 JSON 파싱 실패 ({attempt + 1}/2): {keyword}")
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                return _default_scored_trend(keyword, context)

            return _single_score_to_trend(parsed, keyword, context)
        except (RuntimeError, ConnectionError, TimeoutError, ValueError) as e:
            log.error(f"스코어링 LLM 실패 ({attempt + 1}/2) ({keyword}): {type(e).__name__}: {e}")
            if attempt == 0:
                await asyncio.sleep(1)
        except Exception as e:
            log.error(f"스코어링 예상외 오류 ({attempt + 1}/2) ({keyword}): {type(e).__name__}: {e}")
            if attempt == 0:
                await asyncio.sleep(1)

    return _default_scored_trend(keyword, context)

# ══════════════════════════════════════════════════════
#  배치 스코어링 (Phase 2: 5개/LLM 호출, 비용 ~70% 절감)
# ══════════════════════════════════════════════════════

_BATCH_SIZE = 5  # 한 번에 스코어링할 트렌드 수


async def _cached_batch_scores(
    batch: list[tuple["RawTrend", "MultiSourceContext"]],
    conn,
    bucket: int,
) -> tuple[list[tuple["RawTrend", "MultiSourceContext"]], dict[str, "ScoredTrend"]]:
    need_llm: list[tuple[RawTrend, MultiSourceContext]] = []
    cached_results: dict[str, ScoredTrend] = {}
    if conn is None:
        return list(batch), cached_results

    for trend, ctx in batch:
        fp = compute_fingerprint(trend.name, trend.volume_numeric, bucket)
        cached = await get_cached_score(conn, fp, max_age_hours=18)
        if not cached:
            need_llm.append((trend, ctx))
            continue

        import json as _json

        angles = (
            _json.loads(cached.get("suggested_angles", "[]"))
            if isinstance(cached.get("suggested_angles"), str)
            else cached.get("suggested_angles", [])
        )
        log.info(f"  [罹먯떆] '{trend.name}' ?ㅼ퐫???ъ궗??({cached['viral_potential']}??")
        cached_results[trend.name] = ScoredTrend(
            keyword=trend.name,
            rank=0,
            volume_last_24h=trend.volume_numeric,
            trend_acceleration=cached.get("trend_acceleration", "+0%"),
            viral_potential=cached["viral_potential"],
            top_insight=cached.get("top_insight", ""),
            suggested_angles=angles,
            best_hook_starter=cached.get("best_hook_starter", ""),
            context=ctx,
            sources=[TrendSource.GETDAYTRENDS],
            sentiment=cached.get("sentiment", "neutral"),
            safety_flag=bool(cached.get("safety_flag", 0)),
            cross_source_confidence=_compute_cross_source_confidence(trend.volume_numeric, ctx),
        )
    return need_llm, cached_results


def _batch_scoring_prompt(need_llm: list[tuple["RawTrend", "MultiSourceContext"]]) -> str:
    from datetime import datetime as _dt

    trends_json = json.dumps(
        [{"keyword": trend.name, "volume": trend.volume, "context": ctx.to_combined_text()} for trend, ctx in need_llm],
        ensure_ascii=False,
    )
    return BATCH_SCORING_PROMPT_TEMPLATE.format(
        n=len(need_llm),
        trends_json=trends_json,
        current_time=_dt.now().strftime("%Y-%m-%d %H:%M (KST)"),
    )


def _normalize_batch_scoring_payload(text: str, expected_count: int) -> list[dict] | None:
    parsed_list = _parse_json_array(text)
    if parsed_list is not None or expected_count != 1:
        return parsed_list

    single_item = _parse_json(text)
    if isinstance(single_item, dict):
        return [single_item]

    repaired = _salvage_scoring_payload(text)
    if repaired:
        log.warning("Recovered truncated single-item batch scoring payload")
        return [repaired]
    return None


async def _request_batch_scoring_list(prompt: str, expected_count: int, client) -> list[dict] | None:
    parsed_list: list[dict] | None = await _score_batch_instructor(prompt, expected_count)
    if parsed_list is not None:
        return parsed_list

    for attempt in range(2):
        parsed_list = await _request_batch_scoring_attempt(prompt, expected_count, client, attempt)
        if parsed_list and len(parsed_list) == expected_count:
            return parsed_list
    return None


async def _request_batch_scoring_attempt(prompt: str, expected_count: int, client, attempt: int) -> list[dict] | None:
    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=_batch_score_max_tokens(attempt, expected_count),
            policy=_JSON_ARRAY_POLICY,
            messages=[{"role": "user", "content": prompt}],
        )
        parsed_list = _normalize_batch_scoring_payload(response.text.strip(), expected_count)
        if not parsed_list or len(parsed_list) != expected_count:
            _log_batch_length_mismatch(parsed_list, expected_count)
        return parsed_list
    except (RuntimeError, ConnectionError, TimeoutError, ValueError) as exc:
        await _handle_batch_scoring_error(exc, attempt, expected=True)
    except Exception as exc:
        await _handle_batch_scoring_error(exc, attempt, expected=False)
    return None


def _batch_score_max_tokens(attempt: int, expected_count: int) -> int:
    per_item = _BATCH_SCORE_MAX_TOKENS_PER_ITEM if attempt == 0 else _BATCH_SCORE_RETRY_MAX_TOKENS_PER_ITEM
    return per_item * expected_count


def _log_batch_length_mismatch(parsed_list: list[dict] | None, expected_count: int) -> None:
    actual_count = len(parsed_list) if parsed_list else 0
    log.warning(f"Batch scoring response length mismatch: {actual_count} vs {expected_count}")


async def _handle_batch_scoring_error(exc: Exception, attempt: int, *, expected: bool) -> None:
    label = "LLM failure" if expected else "unexpected error"
    log.error(f"Batch scoring {label} ({attempt + 1}/2): {type(exc).__name__}: {exc}")
    if attempt == 0:
        await asyncio.sleep(1)


async def _recover_batch_item(trend: RawTrend, ctx: MultiSourceContext, error: Exception, client, conn) -> ScoredTrend:
    safe_keyword = sanitize_keyword(trend.name)
    log.warning(f"Batch scoring item fallback '{safe_keyword}': {type(error).__name__}: {error}")
    try:
        recovered = await _score_trend_async(trend.name, ctx, trend.volume, trend.volume_numeric, client, conn)
        recovered.keyword = safe_keyword
        return recovered
    except Exception as fallback_error:
        log.error(
            f"Batch scoring item fallback failed '{safe_keyword}': "
            f"{type(fallback_error).__name__}: {fallback_error}"
        )
        return _default_scored_trend(safe_keyword, ctx)


async def _volume_velocity_for_batch_item(conn, keyword: str) -> float:
    if conn is None:
        return 0.0
    try:
        try:
            from .db import get_volume_velocity
        except ImportError:
            from db import get_volume_velocity

        return await get_volume_velocity(conn, keyword)
    except (ImportError, sqlite3.Error, ValueError):
        return 0.0


async def _parsed_batch_results(
    need_llm: list[tuple["RawTrend", "MultiSourceContext"]],
    parsed_list: list[dict],
    client,
    conn,
    config: "AppConfig | None",
) -> list["ScoredTrend"]:
    results: list[ScoredTrend] = []
    for (trend, ctx), item in zip(need_llm, parsed_list, strict=False):
        keyword = sanitize_keyword(trend.name)
        vel = await _volume_velocity_for_batch_item(conn, keyword)
        try:
            results.append(_parse_scored_trend_from_dict(item, keyword, trend.volume_numeric, ctx, config, velocity=vel))
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            results.append(await _recover_batch_item(trend, ctx, e, client, conn))
        except Exception as e:
            results.append(await _recover_batch_item(trend, ctx, e, client, conn))
    return results


async def _fallback_batch_scores(
    need_llm: list[tuple["RawTrend", "MultiSourceContext"]],
    client,
    conn,
) -> list["ScoredTrend"]:
    log.warning(f"Batch scoring parse failed; falling back to per-item scoring ({len(need_llm)} items)")
    fallback = await asyncio.gather(
        *[_score_trend_async(t.name, ctx, t.volume, t.volume_numeric, client, conn) for t, ctx in need_llm],
        return_exceptions=True,
    )
    results: list[ScoredTrend] = []
    for (trend, ctx), res in zip(need_llm, fallback, strict=False):
        results.append(_default_scored_trend(trend.name, ctx) if isinstance(res, Exception) else res)
    return results


def _ordered_batch_scores(
    batch: list[tuple["RawTrend", "MultiSourceContext"]],
    cached_results: dict[str, "ScoredTrend"],
    results: list["ScoredTrend"],
) -> list["ScoredTrend"]:
    ordered: list[ScoredTrend] = []
    for trend, ctx in batch:
        if trend.name in cached_results:
            ordered.append(cached_results[trend.name])
        else:
            match = next((r for r in results if r.keyword == sanitize_keyword(trend.name)), None)
            ordered.append(match if match else _default_scored_trend(trend.name, ctx))
    return ordered


async def _batch_score_async(
    batch: list[tuple["RawTrend", "MultiSourceContext"]],
    client,
    conn,
    config: "AppConfig | None" = None,
    bucket: int = 5000,
) -> list["ScoredTrend"]:
    """Score a small trend batch with cache reuse and per-item recovery."""
    need_llm, cached_results = await _cached_batch_scores(batch, conn, bucket)
    results: list[ScoredTrend] = []

    if need_llm:
        prompt = _batch_scoring_prompt(need_llm)
        parsed_list = await _request_batch_scoring_list(prompt, len(need_llm), client)
        if parsed_list:
            results.extend(await _parsed_batch_results(need_llm, parsed_list, client, conn, config))
        else:
            results.extend(await _fallback_batch_scores(need_llm, client, conn))

    return _ordered_batch_scores(batch, cached_results, results)

def _apply_raw_trend_metadata(result: ScoredTrend, trend: RawTrend | None, config: AppConfig) -> None:
    if not trend:
        return
    result.rank = trend.volume_numeric
    result.country = trend.country or config.country


def _has_source_signal(value: str, missing_marker: str) -> bool:
    return bool(value and missing_marker not in value)


def _sources_from_context(context: MultiSourceContext) -> list[TrendSource]:
    sources = [TrendSource.GETDAYTRENDS]
    if _has_source_signal(context.twitter_insight, "미설정"):
        sources.append(TrendSource.TWITTER)
    if _has_source_signal(context.reddit_insight, "없음"):
        sources.append(TrendSource.REDDIT)
    if _has_source_signal(context.news_insight, "없음"):
        sources.append(TrendSource.GOOGLE_NEWS)
    return sources


def _apply_scored_trend_metadata(
    scored: list[ScoredTrend],
    raw_trends: list[RawTrend],
    config: AppConfig,
) -> None:
    trend_map = {t.name: t for t in raw_trends}
    for result in scored:
        _apply_raw_trend_metadata(result, trend_map.get(result.keyword), config)
        context = result.context or MultiSourceContext()
        result.sources = _sources_from_context(context)

def _finalize_scored_trends(scored: list[ScoredTrend]) -> list[ScoredTrend]:
    scored.sort(key=lambda x: x.viral_potential, reverse=True)
    for i, s in enumerate(scored):
        s.rank = i + 1

    safety_count = sum(1 for s in scored if s.safety_flag)
    confidence_low = sum(1 for s in scored if s.cross_source_confidence < 2)
    log.info(
        f"Scoring complete: {len(scored)} trends "
        f"(top score: {scored[0].viral_potential if scored else 0}, "
        f"safety_flag: {safety_count}, low_confidence: {confidence_low})"
    )
    return scored


async def _apply_history_correction(
    scored: list[ScoredTrend],
    config: AppConfig,
    conn: sqlite3.Connection | None,
) -> None:
    if not config.enable_history_correction or conn is None:
        return

    history_multiplier = {
        "new": 1.10,
        "rising": 1.15,
        "stable": 0.90,
        "falling": 0.75,
    }
    try:
        from db import get_trend_history_patterns_batch

        pattern_map = await get_trend_history_patterns_batch(conn, [r.keyword for r in scored], days=7)
    except (ImportError, sqlite3.Error) as exc:
        log.debug(f"Batch history lookup skipped: {type(exc).__name__}: {exc}")
        pattern_map = {}

    for result in scored:
        pattern = pattern_map.get(result.keyword, {"score_trend": "new", "is_recurring": False, "seen_count": 0})
        score_trend = pattern.get("score_trend", "new")
        multiplier = history_multiplier.get(score_trend, 1.0)
        if pattern.get("is_recurring") and pattern.get("seen_count", 0) >= 5:
            multiplier *= 0.8
            log.debug(f"  [Phase3 recurring penalty] '{result.keyword}' x0.8")
        if multiplier != 1.0:
            before = result.viral_potential
            result.viral_potential = min(int(result.viral_potential * multiplier), 100)
            log.debug(
                f"  [Phase3 history] '{result.keyword}' [{score_trend}] "
                f"x{multiplier:.2f}: {before} -> {result.viral_potential}"
            )


async def _apply_emerging_detection(
    scored: list[ScoredTrend],
    config: AppConfig,
    conn: sqlite3.Connection | None,
) -> None:
    if not getattr(config, "enable_emerging_detection", True) or conn is None:
        return

    vel_threshold = getattr(config, "emerging_velocity_threshold", 2.0)
    vol_cap = getattr(config, "emerging_volume_cap", 5000)
    try:
        from db import get_volume_velocity_batch

        keywords = [result.keyword for result in scored]
        vel_map = await get_volume_velocity_batch(conn, keywords)
    except (ImportError, sqlite3.Error, ValueError) as exc:
        log.debug(f"Emerging detection skipped: {type(exc).__name__}: {exc}")
        return

    for result in scored:
        vel = vel_map.get(result.keyword, 0.0)
        result.velocity = vel
        if vel >= vel_threshold and result.volume_last_24h < vol_cap:
            result.is_emerging = True
            bonus = 30
            before = result.viral_potential
            result.viral_potential = min(result.viral_potential + bonus, 100)
            log.info(
                f"  [Phase5 emerging] '{result.keyword}' "
                f"velocity={vel:.1f}x, vol={result.volume_last_24h}, "
                f"+{bonus}: {before} -> {result.viral_potential}"
            )


def _maybe_cluster_trends(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    config: AppConfig,
) -> tuple[list[RawTrend], dict[str, MultiSourceContext], list]:
    if not config.enable_clustering:
        return raw_trends, contexts, []

    return cluster_trends_local(
        raw_trends,
        contexts,
        getattr(config, "jaccard_cluster_threshold", 0.35),
        use_embedding=getattr(config, "enable_embedding_clustering", True),
        embedding_threshold=getattr(config, "embedding_cluster_threshold", 0.75),
    )


def _inject_cluster_hints(contexts: dict[str, MultiSourceContext], clusters: list) -> None:
    cluster_map = {
        cluster.representative: [member for member in cluster.members if member != cluster.representative]
        for cluster in clusters
        if len(cluster.members) > 1
    }
    for rep, related in cluster_map.items():
        ctx = contexts.get(rep, MultiSourceContext())
        related_str = ", ".join(related[:5])
        cluster_hint = (
            f"\n[Related trends cluster]: {related_str}. "
            "Treat these as adjacent search angles for the same broader story."
        )
        contexts[rep] = MultiSourceContext(
            twitter_insight=ctx.twitter_insight,
            reddit_insight=ctx.reddit_insight,
            news_insight=(ctx.news_insight or "") + cluster_hint,
        )
    if cluster_map:
        log.info(f"[cluster-hint] injected related-trend hints for {len(cluster_map)} representative trends")


def _category_reference_texts() -> dict[str, str]:
    return {
        "정치": "국회 대통령 정당 선거 법안 정책 정부 정치 이슈",
        "경제": "주가 환율 금리 GDP 실적 무역 물가 투자",
        "테크": "AI 반도체 스마트폰 앱 서비스 소프트웨어 플랫폼 스타트업",
        "사회": "교육 범죄 사고 환경 복지 인구 노동 사회 문제",
        "스포츠": "축구 야구 농구 올림픽 경기 선수 감독 스포츠",
        "연예": "드라마 영화 아이돌 가수 배우 예능 컴백 엔터테인먼트",
        "국제": "해외 외교 전쟁 미국 중국 일본 정상회담 국제",
        "날씨": "태풍 폭우 폭염 미세먼지 기온 날씨 예보",
        "음식": "맛집 레시피 카페 식당 음식 메뉴 외식",
        "게임": "게임 e스포츠 콘솔 모바일게임 업데이트 출시",
        "기타": "생활 문화 커뮤니티 일반 이슈 기타 트렌드",
    }


def _inject_category_hints(raw_trends: list[RawTrend], contexts: dict[str, MultiSourceContext]) -> None:
    try:
        from shared.embeddings import cosine_similarity as _cos_sim
        from shared.embeddings import embed_texts

        category_refs = _category_reference_texts()
        ref_keys = list(category_refs.keys())
        ref_vectors = embed_texts(list(category_refs.values()), task_type="SEMANTIC_SIMILARITY")
        trend_vectors = embed_texts([trend.name for trend in raw_trends], task_type="SEMANTIC_SIMILARITY") if ref_vectors else []
        if not trend_vectors:
            return

        injected = 0
        for index, trend in enumerate(raw_trends):
            scores = {cat: _cos_sim(trend_vectors[index], ref_vectors[j]) for j, cat in enumerate(ref_keys)}
            best_cat = max(scores, key=scores.get)
            best_score = scores[best_cat]
            if best_score < 0.50:
                continue
            ctx = contexts.get(trend.name, MultiSourceContext())
            cat_hint = f"\n[Category hint from embeddings]: {best_cat} (confidence {best_score:.2f})"
            contexts[trend.name] = MultiSourceContext(
                twitter_insight=ctx.twitter_insight,
                reddit_insight=ctx.reddit_insight,
                news_insight=(ctx.news_insight or "") + cat_hint,
            )
            injected += 1
        log.info(f"[category-hint] injected embedding category hints for {injected}/{len(raw_trends)} trends")
    except (ImportError, RuntimeError, ConnectionError, ValueError) as exc:
        log.debug(f"[category-hint] skipped: {type(exc).__name__}: {exc}")


async def _score_trend_batches(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    config: AppConfig,
    conn,
    client,
) -> list[ScoredTrend]:
    pairs = [(trend, contexts.get(trend.name, MultiSourceContext())) for trend in raw_trends]
    batches = [pairs[index : index + _BATCH_SIZE] for index in range(0, len(pairs), _BATCH_SIZE)]
    bucket = getattr(config, "cache_volume_bucket", 5000)
    log.info(f"  Batch scoring start: {len(raw_trends)} trends across {len(batches)} batches (batch_size={_BATCH_SIZE})")

    batch_results = await asyncio.gather(
        *[_batch_score_async(batch, client, conn, config, bucket) for batch in batches],
        return_exceptions=True,
    )
    scored: list[ScoredTrend] = []
    for batch_result, raw_batch in zip(batch_results, batches, strict=False):
        if isinstance(batch_result, Exception):
            log.error(f"Batch scoring batch exception: {batch_result}")
            scored.extend(_default_scored_trend(trend.name, ctx) for trend, ctx in raw_batch)
        else:
            scored.extend(batch_result)
    return scored


def _apply_joongyeon_kick_floor(scored: list[ScoredTrend], config: AppConfig) -> None:
    kick_threshold = getattr(config, "joongyeon_kick_long_form_threshold", 75)
    for result in scored:
        if result.joongyeon_kick >= kick_threshold and result.viral_potential < config.long_form_min_score:
            result.viral_potential = config.long_form_min_score
            log.debug(
                f"  [Phase4 joongyeon kick] '{result.keyword}' "
                f"kick={result.joongyeon_kick} raised to long-form minimum"
            )


async def _analyze_trends_async(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    config: AppConfig,
    conn: sqlite3.Connection | None = None,
) -> list[ScoredTrend]:
    """Analyze trends asynchronously using clustered context and batch scoring."""
    client = get_client()
    raw_trends, contexts, clusters = _maybe_cluster_trends(raw_trends, contexts, config)
    _inject_cluster_hints(contexts, clusters)
    _inject_category_hints(raw_trends, contexts)

    scored = await _score_trend_batches(raw_trends, contexts, config, conn, client)
    _apply_scored_trend_metadata(scored, raw_trends, config)
    await _apply_history_correction(scored, config, conn)
    _apply_joongyeon_kick_floor(scored, config)
    await _apply_emerging_detection(scored, config, conn)
    return _finalize_scored_trends(scored)

def analyze_trends(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    config: AppConfig,
    conn: sqlite3.Connection | None = None,
) -> list[ScoredTrend]:
    """동기 래퍼. 내부적으로 비동기 병렬 스코어링 실행."""
    return run_async(_analyze_trends_async(raw_trends, contexts, config, conn))

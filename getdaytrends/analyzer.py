"""
getdaytrends v3.0 - Viral Scoring & Trend Analysis
Claude를 활용한 바이럴 포텐셜 스코어링 + 히스토리 패턴 감지 + 트렌드 클러스터링.
async/await 기반 병렬 스코어링 + JSON structured output + 스코어 캐시 + 재시도 지원.
v3.0: 배치 스코어링(5개/호출, 비용 ~70% 절감) + sentiment/safety_flag 분석 추가.
"""

import asyncio
import json
import math
import re
import sqlite3
from pathlib import Path
import sys

# shared.llm 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import AppConfig
from db import compute_fingerprint, get_cached_score
from models import MultiSourceContext, RawTrend, ScoredTrend, TrendCluster, TrendContext, TrendSource
from shared.llm import LLMClient, TaskTier, get_client
from shared.llm.models import LLMPolicy
from utils import run_async, sanitize_keyword

from loguru import logger as log


# ══════════════════════════════════════════════════════
#  JSON Parser (simplified — structured output removes fragility)
# ══════════════════════════════════════════════════════

def _parse_json(text: str | None) -> dict | None:
    """JSON 파싱. response_mode=json 덕분에 단순 loads로 충분."""
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _parse_json_array(text: str | None) -> list | None:
    """JSON 배열 파싱."""
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


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
    "best_hook_starter": "이 트렌드로 트윗을 시작할 최고의 한 문장",
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
    "best_hook_starter": "최고의 훅 한 문장",
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


# ══════════════════════════════════════════════════════
#  v4.0 Helper Functions (Phase 1, 2, 3)
# ══════════════════════════════════════════════════════

def _compute_cross_source_confidence(
    volume_numeric: int,
    context: "MultiSourceContext",
) -> int:
    """
    Phase 1: 멀티소스 교차 검증 점수 (0~4).
    +1 볼륨 있음 / +1 X에서 실제 트윗 확인 / +1 뉴스 확인 / +1 Reddit 확인
    """
    score = 0
    if volume_numeric > 0:
        score += 1
    if context and context.twitter_insight and \
            "없음" not in context.twitter_insight and \
            "오류" not in context.twitter_insight and \
            len(context.twitter_insight) > 20:
        score += 1
    if context and context.news_insight and \
            "없음" not in context.news_insight and \
            len(context.news_insight) > 20:
        score += 1
    if context and context.reddit_insight and \
            "없음" not in context.reddit_insight and \
            "제한" not in context.reddit_insight and \
            len(context.reddit_insight) > 20:
        score += 1
    return score


def _compute_freshness_score(content_age_hours: float, is_new: bool = True) -> float:
    """
    [v6.1] 시간 기반 신선도 점수 (0~20).
    content_age_hours가 0이면 (날짜 미확인) is_new 폴백.
    - 0~1h: 20점 (최신)
    - 1~3h: 20→15점
    - 3~6h: 15→10점
    - 6~12h: 10→5점
    - 12h+: 5→0점
    """
    if content_age_hours <= 0:
        return 20.0 if is_new else 10.0  # 날짜 미확인 → 기존 바이너리 폴백
    if content_age_hours <= 1:
        return 20.0
    if content_age_hours <= 3:
        return 20.0 - (content_age_hours - 1) * 2.5  # 20 → 15
    if content_age_hours <= 6:
        return 15.0 - (content_age_hours - 3) * 1.67  # 15 → 10
    if content_age_hours <= 12:
        return 10.0 - (content_age_hours - 6) * 0.83  # 10 → 5
    return max(5.0 - (content_age_hours - 12) * 0.42, 0)  # 5 → 0 (24h)


def _compute_signal_score(
    volume_numeric: int,
    trend_acceleration: str,
    cross_source_confidence: int,
    is_new: bool = True,
    content_age_hours: float = 0.0,
    velocity: float = 0.0,
) -> float:
    """
    Phase 2: 시그널 기반 보조 점수 (0~100).
    볼륨(30) + 가속도(25) + 소스수(20) + 신선도(15) + 벨로시티(10) [v9.0]
    [v6.1] 신선도: 바이너리 → 시간 감쇠 함수
    [v9.0] velocity: 런 간 볼륨 증가율 기반 최대 10점 추가
    """
    # 볼륨 점수 (로그 정규화, 최대 30점)
    if volume_numeric > 0:
        vol_score = min(math.log10(volume_numeric + 1) / math.log10(10_000_001) * 30, 30)
    else:
        vol_score = 0

    # 가속도 점수 (최대 25점)
    acc_score = 0.0
    m = re.search(r"\+([\d.]+)\s*%?", trend_acceleration or "")
    if m:
        pct = float(m.group(1))
        if pct >= 30:
            acc_score = 25
        elif pct >= 10:
            acc_score = 15
        elif pct >= 3:
            acc_score = 8
        else:
            acc_score = 3
    elif trend_acceleration and trend_acceleration.startswith("-"):
        acc_score = 0
    elif "급상승" in (trend_acceleration or ""):
        acc_score = 25

    # 소스 교차 점수 (최대 20점, 기존 25 → 조정)
    source_score = min(cross_source_confidence * 5.0, 20)

    # [v6.1] 신선도 점수 — 시간 감쇠 (최대 15점, 기존 20 → 조정)
    freshness_score = _compute_freshness_score(content_age_hours, is_new) * 0.75

    # [v9.0] 벨로시티 점수 — 런 간 볼륨 증가율 (최대 10점)
    velocity_score = min(max(velocity, 0.0) * 5.0, 10.0)

    return min(vol_score + acc_score + source_score + freshness_score + velocity_score, 100)


async def _score_trend_async(
    keyword: str,
    context: MultiSourceContext,
    volume: str,
    volume_numeric: int,
    client: LLMClient,
    conn: sqlite3.Connection | None = None,
) -> ScoredTrend:
    """단일 트렌드 비동기 스코어링 (캐시 조회 → LLM 호출, 최대 2회 시도)."""
    # ── 캐시 조회: 카테고리 기반 차등 TTL (C1 최적화) ──
    if conn is not None:
        fingerprint = compute_fingerprint(keyword, volume_numeric)
        cached = await get_cached_score(conn, fingerprint, max_age_hours=18)
        if cached:
            log.info(f"  [캐시] '{keyword}' 스코어 재사용 ({cached['viral_potential']}점)")
            import json as _json
            angles = _json.loads(cached.get("suggested_angles", "[]")) if isinstance(
                cached.get("suggested_angles"), str) else cached.get("suggested_angles", [])
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

    # ── LLM 스코어링 (최대 2회 시도) ──
    from datetime import datetime as _dt
    safe_keyword = sanitize_keyword(keyword)
    prompt = SCORING_PROMPT_TEMPLATE.format(
        keyword=safe_keyword,
        volume=volume,
        context=context.to_combined_text(),
        current_time=_dt.now().strftime("%Y-%m-%d %H:%M (KST)"),
    )

    for attempt in range(2):
        try:
            response = await client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                max_tokens=1000,
                policy=_JSON_POLICY,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _parse_json(response.text)

            if not parsed:
                log.warning(f"스코어링 JSON 파싱 실패 ({attempt + 1}/2): {keyword}")
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                return _default_scored_trend(keyword, context)

            raw_category = parsed.get("category", "")
            # "연예|스포츠|..." 형식 또는 파이프가 포함된 경우 첫 번째 값만 추출
            category = raw_category.split("|")[0].strip() if raw_category else ""

            # [v13.0] publishable 판정
            pub = parsed.get("publishable", True)
            if isinstance(pub, str):
                pub = pub.lower() not in ("false", "0", "no")

            return ScoredTrend(
                keyword=keyword,
                rank=0,
                volume_last_24h=parsed.get("volume_last_24h", 0),
                trend_acceleration=parsed.get("trend_acceleration", "+0%"),
                viral_potential=min(max(parsed.get("viral_potential", 0), 0), 100),
                top_insight=parsed.get("top_insight", ""),
                suggested_angles=parsed.get("suggested_angles", []),
                best_hook_starter=parsed.get("best_hook_starter", ""),
                category=category,
                context=context,
                sources=[TrendSource.GETDAYTRENDS],
                sentiment=parsed.get("sentiment", "neutral"),
                safety_flag=bool(parsed.get("safety_flag", False)),
                # [v8.0] 프롬프트 ① 필드
                why_trending=parsed.get("why_trending", ""),
                peak_status=parsed.get("peak_status", ""),
                relevance_score=min(max(int(parsed.get("relevance_score", 0)), 0), 10),
                # [v13.0] 게시 가능성 게이트
                publishable=bool(pub),
                publishability_reason=parsed.get("publishability_reason", ""),
                corrected_keyword=parsed.get("corrected_keyword", ""),
            )

        except Exception as e:
            log.error(f"스코어링 실패 ({attempt + 1}/2) ({keyword}): {e}")
            if attempt == 0:
                await asyncio.sleep(1)

    return _default_scored_trend(keyword, context)


def _default_scored_trend(keyword: str, context: MultiSourceContext) -> ScoredTrend:
    """스코어링 실패 시 기본값."""
    return ScoredTrend(
        keyword=keyword,
        rank=0,
        context=context,
        sources=[TrendSource.GETDAYTRENDS],
    )


def _parse_scored_trend_from_dict(
    parsed: dict,
    keyword: str,
    volume_numeric: int,
    context: "MultiSourceContext",
    config: "AppConfig | None" = None,
    velocity: float = 0.0,
) -> "ScoredTrend":
    """파싱된 dict → ScoredTrend 변환 (단일·배치 공용).
    Phase 1: cross_source_confidence 계산 + 패널티 적용.
    Phase 2: LLM 점수와 시그널 점수 의 가중 평균.
    Phase 4: joongyeon_kick / joongyeon_angle 파싱.
    [v9.0] velocity: 런 간 볼륨 증가율 신호 점수 반영.
    """
    raw_category = parsed.get("category", "")
    category = raw_category.split("|")[0].strip() if raw_category else ""
    trend_acceleration = parsed.get("trend_acceleration", "+0%")
    llm_viral = min(max(int(parsed.get("viral_potential", 0)), 0), 100)

    # Phase 1: 교차 검증
    confidence = _compute_cross_source_confidence(volume_numeric, context)

    # Phase 2: 하이브리드 스코어링 (벨로시티 포함)
    w_llm = getattr(config, "viral_score_llm_weight", 0.6) if config else 0.6
    w_signal = 1.0 - w_llm
    signal = _compute_signal_score(volume_numeric, trend_acceleration, confidence, velocity=velocity)
    hybrid_viral = int(llm_viral * w_llm + signal * w_signal)

    # Phase 1: confidence 패널티 (저신뢰 트렌드)
    min_conf = getattr(config, "min_cross_source_confidence", 2) if config else 2
    if confidence < min_conf:
        hybrid_viral = int(hybrid_viral * 0.65)
        log.debug(
            f"  [Phase1 패널티] '{keyword}' 교차검증={confidence}/{min_conf} "
            f"→ {llm_viral}점 × 0.65 = {hybrid_viral}점"
        )

    # [v10.0] 구조화된 트렌드 배경 (Deep Why)
    trend_ctx = None
    trigger = parsed.get("trigger_event", "")
    chain = parsed.get("chain_reaction", "")
    why_now = parsed.get("why_now", "")
    positions = parsed.get("key_positions", [])
    if trigger or chain or why_now or positions:
        # 실제 X 반응 요약은 컨텍스트에서 추출
        real_tweets = ""
        if context and context.twitter_insight:
            insight = context.twitter_insight
            if len(insight) > 30 and "오류" not in insight and "없음" not in insight:
                real_tweets = insight[:300]
        trend_ctx = TrendContext(
            trigger_event=trigger,
            chain_reaction=chain,
            why_now=why_now,
            key_positions=positions if isinstance(positions, list) else [],
            real_tweets_summary=real_tweets,
        )

    # [v13.0] 게시 가능성 판정
    publishable = parsed.get("publishable", True)
    # 문자열 "false" 등도 처리
    if isinstance(publishable, str):
        publishable = publishable.lower() not in ("false", "0", "no")
    publishability_reason = parsed.get("publishability_reason", "")
    corrected_keyword = parsed.get("corrected_keyword", "")

    if not publishable:
        log.warning(
            f"  [게시불가] '{keyword}' publishable=false "
            f"(사유: {publishability_reason or '미상'})"
        )
    if corrected_keyword:
        log.info(
            f"  [키워드 교정] '{keyword}' → '{corrected_keyword}'"
        )

    return ScoredTrend(
        keyword=keyword,
        rank=0,
        volume_last_24h=parsed.get("volume_last_24h", volume_numeric),
        trend_acceleration=trend_acceleration,
        viral_potential=min(hybrid_viral, 100),
        top_insight=parsed.get("top_insight", ""),
        suggested_angles=parsed.get("suggested_angles", []),
        best_hook_starter=parsed.get("best_hook_starter", ""),
        category=category,
        context=context,
        sources=[TrendSource.GETDAYTRENDS],
        sentiment=parsed.get("sentiment", "neutral"),
        safety_flag=bool(parsed.get("safety_flag", False)),
        cross_source_confidence=confidence,
        joongyeon_kick=min(max(int(parsed.get("joongyeon_kick", 0)), 0), 100),
        joongyeon_angle=parsed.get("joongyeon_angle", ""),
        # [v8.0] 프롬프트 ① 필드
        why_trending=parsed.get("why_trending", ""),
        peak_status=parsed.get("peak_status", ""),
        relevance_score=min(max(int(parsed.get("relevance_score", 0)), 0), 10),
        # [v10.0] Deep Why 구조화 배경
        trend_context=trend_ctx,
        # [v13.0] 게시 가능성 게이트
        publishable=bool(publishable),
        publishability_reason=publishability_reason,
        corrected_keyword=corrected_keyword,
    )


# ══════════════════════════════════════════════════════
#  배치 스코어링 (Phase 2: 5개/LLM 호출, 비용 ~70% 절감)
# ══════════════════════════════════════════════════════

_BATCH_SIZE = 5  # 한 번에 스코어링할 트렌드 수


# ══════════════════════════════════════════════════════
#  [v9.0] 로컬 Jaccard 클러스터링 (LLM 호출 없음)
#  [v14.0] Gemini Embedding 2 기반 의미적 클러스터링 추가
# ══════════════════════════════════════════════════════

def _jaccard_similarity(a: str, b: str) -> float:
    """형태소 단위 자카드 유사도 (0.0~1.0). 2자 미만 토큰은 제외."""
    tokens_a = {t for t in a.lower().split() if len(t) >= 2}
    tokens_b = {t for t in b.lower().split() if len(t) >= 2}
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _compute_similarity_pairs_embedding(
    names: list[str],
    threshold: float,
) -> list[tuple[int, int]] | None:
    """
    [v14.0] Gemini Embedding 2로 의미적 유사도 계산 후 threshold 이상 쌍 반환.
    실패 시 None 반환 (Jaccard 폴백 트리거).
    """
    try:
        from embeddings import embed_texts, compute_similarity_matrix

        vectors = embed_texts(names)
        if vectors is None or len(vectors) != len(names):
            return None

        sim_matrix = compute_similarity_matrix(vectors)
        pairs = []
        n = len(names)
        for i in range(n):
            for j in range(i + 1, n):
                if sim_matrix[i][j] >= threshold:
                    pairs.append((i, j))
                    log.debug(
                        f"  [임베딩 유사] '{names[i]}' ↔ '{names[j]}' "
                        f"= {sim_matrix[i][j]:.3f} ≥ {threshold}"
                    )
        return pairs

    except Exception as e:
        log.warning(f"[임베딩 클러스터링 실패] {e} → Jaccard 폴백")
        return None


def _merge_clusters(
    raw_trends: list["RawTrend"],
    contexts: dict[str, "MultiSourceContext"],
    groups: dict[int, list[int]],
    names: list[str],
    method: str = "jaccard",
) -> tuple[list["RawTrend"], dict[str, "MultiSourceContext"], list["TrendCluster"]]:
    """Union-Find 그룹 결과 → 대표 선정 + 컨텍스트 병합 (공통 로직)."""
    trend_map = {t.name: t for t in raw_trends}
    clusters: list[TrendCluster] = []
    representatives: list["RawTrend"] = []

    for idxs in groups.values():
        members = [names[i] for i in idxs]
        # 대표 = 볼륨 최대
        rep_name = max(members, key=lambda nm: trend_map[nm].volume_numeric)

        # 컨텍스트 병합
        merged_tw, merged_rd, merged_nw = [], [], []
        for nm in members:
            ctx = contexts.get(nm, MultiSourceContext())
            if ctx.twitter_insight and "오류" not in ctx.twitter_insight:
                merged_tw.append(ctx.twitter_insight)
            if ctx.reddit_insight and "없음" not in ctx.reddit_insight:
                merged_rd.append(ctx.reddit_insight)
            if ctx.news_insight and "없음" not in ctx.news_insight:
                merged_nw.append(ctx.news_insight)

        merged_ctx = MultiSourceContext(
            twitter_insight="\n".join(merged_tw) or contexts.get(rep_name, MultiSourceContext()).twitter_insight,
            reddit_insight="\n".join(merged_rd) or contexts.get(rep_name, MultiSourceContext()).reddit_insight,
            news_insight="\n".join(merged_nw) or contexts.get(rep_name, MultiSourceContext()).news_insight,
        )
        contexts[rep_name] = merged_ctx
        clusters.append(TrendCluster(representative=rep_name, members=members, merged_context=merged_ctx))
        representatives.append(trend_map[rep_name])

    merged_count = sum(len(c.members) - 1 for c in clusters if len(c.members) > 1)
    if merged_count:
        log.info(
            f"[{method} 클러스터링] {len(raw_trends)}개 → {len(representatives)}개 "
            f"(병합 {merged_count}개)"
        )

    return representatives, contexts, clusters


def cluster_trends_local(
    raw_trends: list["RawTrend"],
    contexts: dict[str, "MultiSourceContext"],
    threshold: float = 0.35,
    use_embedding: bool = True,
    embedding_threshold: float = 0.75,
) -> tuple[list["RawTrend"], dict[str, "MultiSourceContext"], list["TrendCluster"]]:
    """
    [v14.0] 하이브리드 의미적 클러스터링.

    1차: Gemini Embedding 2 기반 의미적 유사도 (use_embedding=True)
         → "BTS 컴백" ↔ "방탄소년단 신곡" 같은 의미적 중복 감지 가능
    2차: 임베딩 실패 시 Jaccard 유사도 폴백 (기존 v9.0 방식)

    Args:
        raw_trends: 수집된 트렌드 목록
        contexts: 트렌드별 멀티소스 컨텍스트
        threshold: Jaccard 유사도 임계값 (기본 0.35)
        use_embedding: Gemini Embedding 사용 여부 (기본 True)
        embedding_threshold: 임베딩 코사인 유사도 임계값 (기본 0.75)
    """
    if len(raw_trends) <= 2:
        clusters = [TrendCluster(representative=t.name, members=[t.name]) for t in raw_trends]
        return raw_trends, contexts, clusters

    names = [t.name for t in raw_trends]
    n = len(names)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    # [v14.0] 1차: 임베딩 기반 의미적 유사도 시도
    used_embedding = False
    if use_embedding:
        embedding_pairs = _compute_similarity_pairs_embedding(names, embedding_threshold)
        if embedding_pairs is not None:
            for i, j in embedding_pairs:
                union(i, j)
            used_embedding = True
            log.info(
                f"[임베딩 클러스터링] {len(names)}개 키워드 → "
                f"{len(embedding_pairs)}쌍 유사 감지 (threshold={embedding_threshold})"
            )

    # 2차: 임베딩 실패 시 Jaccard 폴백
    if not used_embedding:
        for i in range(n):
            for j in range(i + 1, n):
                if _jaccard_similarity(names[i], names[j]) >= threshold:
                    union(i, j)

    # 클러스터 그룹핑
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    method = "임베딩" if used_embedding else "Jaccard"
    return _merge_clusters(raw_trends, contexts, groups, names, method)


async def _batch_score_async(
    batch: list[tuple["RawTrend", "MultiSourceContext"]],
    client,
    conn,
    config: "AppConfig | None" = None,
    bucket: int = 5000,
) -> list["ScoredTrend"]:
    """
    트렌드 배치(최대 _BATCH_SIZE개)를 1회 LLM 호출로 스코어링.
    캐시 히트 항목은 LLM 호출에서 제외해 비용 절약.
    실패 시 각 항목을 개별 스코어링으로 폴백.
    """
    # ── 캐시 분리 ──
    need_llm: list[tuple["RawTrend", "MultiSourceContext"]] = []
    cached_results: dict[str, "ScoredTrend"] = {}

    if conn is not None:
        for trend, ctx in batch:
            fp = compute_fingerprint(trend.name, trend.volume_numeric, bucket)
            cached = await get_cached_score(conn, fp, max_age_hours=18)
            if cached:
                import json as _json
                angles = _json.loads(cached.get("suggested_angles", "[]")) \
                    if isinstance(cached.get("suggested_angles"), str) \
                    else cached.get("suggested_angles", [])
                log.info(f"  [캐시] '{trend.name}' 스코어 재사용 ({cached['viral_potential']}점)")
                cached_results[trend.name] = ScoredTrend(
                    keyword=trend.name, rank=0,
                    volume_last_24h=trend.volume_numeric,
                    trend_acceleration=cached.get("trend_acceleration", "+0%"),
                    viral_potential=cached["viral_potential"],
                    top_insight=cached.get("top_insight", ""),
                    suggested_angles=angles,
                    best_hook_starter=cached.get("best_hook_starter", ""),
                    context=ctx, sources=[TrendSource.GETDAYTRENDS],
                    sentiment=cached.get("sentiment", "neutral"),
                    safety_flag=bool(cached.get("safety_flag", 0)),
                    cross_source_confidence=_compute_cross_source_confidence(
                        trend.volume_numeric, ctx
                    ),
                )
            else:
                need_llm.append((trend, ctx))
    else:
        need_llm = list(batch)

    results: list["ScoredTrend"] = []

    if need_llm:
        # ── 배치 LLM 호출 ──
        from datetime import datetime as _dt
        current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")
        trends_json = json.dumps(
            [{"keyword": t.name, "volume": t.volume, "context": ctx.to_combined_text()}
             for t, ctx in need_llm],
            ensure_ascii=False,
        )
        prompt = BATCH_SCORING_PROMPT_TEMPLATE.format(
            n=len(need_llm),
            trends_json=trends_json,
            current_time=current_time,
        )
        parsed_list: list[dict] | None = None
        for attempt in range(2):
            try:
                response = await client.acreate(
                    tier=TaskTier.LIGHTWEIGHT,
                    max_tokens=600 * len(need_llm),   # joongyeon_angle 필드용 토큰 증가
                    policy=_JSON_POLICY,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.text.strip()
                if text.startswith("{"):
                    text = text[1:].lstrip()
                parsed_list = _parse_json_array(text)
                if parsed_list and len(parsed_list) == len(need_llm):
                    break
                log.warning(f"배치 스코어링 응답 길이 불일치: {len(parsed_list) if parsed_list else 0} vs {len(need_llm)}")
                parsed_list = None
            except Exception as e:
                log.error(f"배치 스코어링 실패 ({attempt + 1}/2): {e}")
                if attempt == 0:
                    await asyncio.sleep(1)

        if parsed_list:
            for (trend, ctx), item in zip(need_llm, parsed_list):
                keyword = sanitize_keyword(trend.name)
                # [v9.0 B-1] DB에서 실제 velocity 조회
                vel = 0.0
                if conn is not None:
                    try:
                        from db import get_volume_velocity
                        vel = await get_volume_velocity(conn, keyword)
                    except Exception:
                        pass
                results.append(_parse_scored_trend_from_dict(
                    item, keyword, trend.volume_numeric, ctx, config, velocity=vel
                ))
        else:
            # 배치 실패 → 개별 스코어링 폴백
            log.warning(f"배치 스코어링 실패 → 개별 폴백 ({len(need_llm)}개)")
            fallback = await asyncio.gather(
                *[_score_trend_async(t.name, ctx, t.volume, t.volume_numeric, client, conn)
                  for t, ctx in need_llm],
                return_exceptions=True,
            )
            for (trend, ctx), res in zip(need_llm, fallback):
                if isinstance(res, Exception):
                    results.append(_default_scored_trend(trend.name, ctx))
                else:
                    results.append(res)

    # ── 원래 순서대로 병합 ──
    ordered: list["ScoredTrend"] = []
    for trend, ctx in batch:
        if trend.name in cached_results:
            ordered.append(cached_results[trend.name])
        else:
            match = next((r for r in results if r.keyword == sanitize_keyword(trend.name)), None)
            ordered.append(match if match else _default_scored_trend(trend.name, ctx))
    return ordered


# ══════════════════════════════════════════════════════
#  Clustering
# ══════════════════════════════════════════════════════

CLUSTERING_PROMPT = """다음 트렌드 키워드 목록에서 의미적으로 유사한 키워드를 그루핑해주세요.
각 그룹에서 가장 대표적인 키워드 하나를 representative로 선택하세요.
단독 키워드는 자기 자신만 members에 넣으세요.

키워드 목록:
{keywords}

다음 JSON 배열 스키마로 정확히 응답:
[
  {{"representative": "대표 키워드", "members": ["키워드1", "키워드2"]}},
  {{"representative": "단독 키워드", "members": ["단독 키워드"]}}
]"""


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
            policy=_JSON_POLICY,
            messages=[{"role": "user", "content": prompt}],
        )
        # Clustering returns an array — strip leading { if prefill was applied
        text = response.text.strip()
        if text.startswith("{"):
            # Prefill caused { to be prepended to an array response → strip
            text = text[1:].lstrip()
        parsed = _parse_json_array(text)
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
        if rep not in trend_map:
            valid = [m for m in members if m in trend_map]
            rep = valid[0] if valid else ""
        if not rep:
            continue

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

    filtered = [t for t in raw_trends if t.name in representative_names]

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


# ══════════════════════════════════════════════════════
#  Async Orchestrator
# ══════════════════════════════════════════════════════

async def _analyze_trends_async(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    config: AppConfig,
    conn: sqlite3.Connection | None = None,
) -> list[ScoredTrend]:
    """
    전체 트렌드 비동기 배치 스코어링.
    v3.0: _BATCH_SIZE(5)개씨 묶어 LLM 호출 → 비용 ~70% 절감.
    v4.0: Phase3 히스토리 패턴 보정 + Phase4 중연 킥 기반 장문 조건 연동.
    """
    client = get_client()

    # [v9.0] 클러스터링: enable_llm_clustering=False면 로컬, True면 기존 LLM
    # [v14.0] 로컬 클러스터링에 Gemini Embedding 2 의미적 유사도 추가
    clusters = []
    if config.enable_clustering:
        if getattr(config, "enable_llm_clustering", False):
            raw_trends, contexts, clusters = cluster_trends(raw_trends, contexts, client)
        else:
            threshold = getattr(config, "jaccard_cluster_threshold", 0.35)
            use_emb = getattr(config, "enable_embedding_clustering", True)
            emb_threshold = getattr(config, "embedding_cluster_threshold", 0.75)
            raw_trends, contexts, clusters = cluster_trends_local(
                raw_trends, contexts, threshold,
                use_embedding=use_emb,
                embedding_threshold=emb_threshold,
            )

    # [v14.1] 클러스터 정보를 컨텍스트에 주입 (스코어링 정확도 향상)
    if clusters:
        cluster_map: dict[str, list[str]] = {}
        for c in clusters:
            if len(c.members) > 1:
                cluster_map[c.representative] = [m for m in c.members if m != c.representative]
        for rep, related in cluster_map.items():
            ctx = contexts.get(rep, MultiSourceContext())
            related_str = ", ".join(related[:5])
            cluster_hint = f"\n[관련 트렌드 (의미적 클러스터)]: {related_str} → 이 주제가 여러 검색어로 확산 중"
            # news_insight에 클러스터 힌트 추가
            if ctx.news_insight:
                ctx = MultiSourceContext(
                    twitter_insight=ctx.twitter_insight,
                    reddit_insight=ctx.reddit_insight,
                    news_insight=ctx.news_insight + cluster_hint,
                )
            else:
                ctx = MultiSourceContext(
                    twitter_insight=ctx.twitter_insight,
                    reddit_insight=ctx.reddit_insight,
                    news_insight=cluster_hint,
                )
            contexts[rep] = ctx
        log.info(f"[클러스터 힌트] {len(cluster_map)}개 대표 트렌드에 관련 키워드 정보 주입")

    # [v14.1] 임베딩 기반 카테고리 사전 분류 힌트
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _root = str(_Path(__file__).resolve().parents[1])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from shared.embeddings import embed_texts, cosine_similarity as _cos_sim

        _CATEGORY_REFS = {
            "정치": "국회 대통령 정당 선거 법안 정책",
            "경제": "주가 환율 금리 GDP 실적 무역",
            "테크": "AI 반도체 스마트폰 앱 서비스 소프트웨어",
            "사회": "교육 범죄 사고 환경 복지 인구",
            "스포츠": "축구 야구 농구 올림픽 경기 감독",
            "연예": "드라마 영화 아이돌 가수 배우 컴백",
            "국제": "외교 전쟁 유엔 미국 중국 정상회담",
        }
        ref_texts = list(_CATEGORY_REFS.values())
        ref_keys = list(_CATEGORY_REFS.keys())
        ref_vectors = embed_texts(ref_texts, task_type="SEMANTIC_SIMILARITY")

        if ref_vectors:
            trend_names = [t.name for t in raw_trends]
            trend_vectors = embed_texts(trend_names, task_type="SEMANTIC_SIMILARITY")
            if trend_vectors:
                for i, t in enumerate(raw_trends):
                    scores = {cat: _cos_sim(trend_vectors[i], ref_vectors[j])
                              for j, cat in enumerate(ref_keys)}
                    best_cat = max(scores, key=scores.get)
                    best_score = scores[best_cat]
                    if best_score >= 0.50:  # 최소 신뢰도
                        ctx = contexts.get(t.name, MultiSourceContext())
                        cat_hint = f"\n[카테고리 힌트 (임베딩)]: {best_cat} (신뢰도: {best_score:.2f})"
                        contexts[t.name] = MultiSourceContext(
                            twitter_insight=ctx.twitter_insight,
                            reddit_insight=ctx.reddit_insight,
                            news_insight=(ctx.news_insight or "") + cat_hint,
                        )
                log.info(f"[카테고리 사전분류] {len(raw_trends)}개 트렌드에 임베딩 기반 카테고리 힌트 주입")
    except Exception as _e:
        log.debug(f"[카테고리 사전분류] 사용 불가 (무시): {_e}")

    # 배치 분할 (5개씩)
    pairs = [(t, contexts.get(t.name, MultiSourceContext())) for t in raw_trends]
    batches = [pairs[i:i + _BATCH_SIZE] for i in range(0, len(pairs), _BATCH_SIZE)]
    bucket = getattr(config, "cache_volume_bucket", 5000)

    log.info(f"  배치 스코어링 시작: {len(raw_trends)}개 → {len(batches)}배치 (배치크기={_BATCH_SIZE})")
    batch_results = await asyncio.gather(
        *[_batch_score_async(b, client, conn, config, bucket) for b in batches],
        return_exceptions=True,
    )

    scored: list[ScoredTrend] = []
    for batch, raw_batch in zip(batch_results, batches):
        if isinstance(batch, Exception):
            log.error(f"배치 스코어링 전체 예외: {batch}")
            for trend, ctx in raw_batch:
                scored.append(_default_scored_trend(trend.name, ctx))
            continue
        scored.extend(batch)

    # 소스 정보 보완 및 랜킹 재정렬
    for result in scored:
        trend_map = {t.name: t for t in raw_trends}
        trend = trend_map.get(result.keyword)
        if trend:
            result.rank = trend.volume_numeric
            result.country = trend.country or config.country

        context = result.context or MultiSourceContext()
        sources = [TrendSource.GETDAYTRENDS]
        if context.twitter_insight and "미설정" not in context.twitter_insight:
            sources.append(TrendSource.TWITTER)
        if context.reddit_insight and "없음" not in context.reddit_insight:
            sources.append(TrendSource.REDDIT)
        if context.news_insight and "없음" not in context.news_insight:
            sources.append(TrendSource.GOOGLE_NEWS)
        result.sources = sources

    # Phase 3: 히스토리 패턴 보정 [v9.0] N+1 → 배치 조회
    if config.enable_history_correction and conn is not None:
        _HISTORY_MULTIPLIER = {
            "new":     1.10,
            "rising":  1.15,
            "stable":  0.90,
            "falling": 0.75,
        }
        try:
            from db import get_trend_history_patterns_batch
            pattern_map = await get_trend_history_patterns_batch(
                conn, [r.keyword for r in scored], days=7
            )
        except Exception as _e:
            log.debug(f"배치 히스토리 조회 실패 (무시): {_e}")
            pattern_map = {}

        for result in scored:
            pattern = pattern_map.get(result.keyword, {"score_trend": "new", "is_recurring": False, "seen_count": 0})
            score_trend = pattern.get("score_trend", "new")
            mult = _HISTORY_MULTIPLIER.get(score_trend, 1.0)
            if pattern.get("is_recurring") and pattern.get("seen_count", 0) >= 5:
                mult *= 0.8
                log.debug(f"  [Phase3 반복 패널티] '{result.keyword}' ×0.8 (5회 이상 등장)")
            if mult != 1.0:
                before = result.viral_potential
                result.viral_potential = min(int(result.viral_potential * mult), 100)
                log.debug(
                    f"  [Phase3 히스토리] '{result.keyword}' [{score_trend}] "
                    f"×{mult:.2f} → {before}점 → {result.viral_potential}점"
                )

    # Phase 4: 중연 킥 기반 장문 조건 연동
    kick_threshold = getattr(config, "joongyeon_kick_long_form_threshold", 75)
    for result in scored:
        if result.joongyeon_kick >= kick_threshold and \
                result.viral_potential < config.long_form_min_score:
            result.viral_potential = config.long_form_min_score
            log.debug(
                f"  [Phase4 킥] '{result.keyword}' kick={result.joongyeon_kick} → 장문 미니스코어 우회"
            )

    # Phase 5: [v9.0 C-6] 이머징 트렌드 감지
    if getattr(config, 'enable_emerging_detection', True) and conn is not None:
        vel_threshold = getattr(config, 'emerging_velocity_threshold', 2.0)
        vol_cap = getattr(config, 'emerging_volume_cap', 5000)
        try:
            from db import get_volume_velocity
            for result in scored:
                vel = await get_volume_velocity(conn, result.keyword)
                result.velocity = vel
                if vel >= vel_threshold and result.volume_last_24h < vol_cap:
                    result.is_emerging = True
                    bonus = 30
                    before = result.viral_potential
                    result.viral_potential = min(result.viral_potential + bonus, 100)
                    log.info(
                        f"  [Phase5 이머징] '{result.keyword}' "
                        f"velocity={vel:.1f}x, vol={result.volume_last_24h} "
                        f"→ +{bonus}점 ({before}→{result.viral_potential})"
                    )
        except Exception as _e:
            log.debug(f"이머징 감지 실패 (무시): {_e}")

    scored.sort(key=lambda x: x.viral_potential, reverse=True)
    for i, s in enumerate(scored):
        s.rank = i + 1

    safety_count = sum(1 for s in scored if s.safety_flag)
    confidence_low = sum(1 for s in scored if s.cross_source_confidence < 2)
    log.info(
        f"스코어링 완료: {len(scored)}개 "
        f"(최고 점수: {scored[0].viral_potential if scored else 0}, "
        f"safety_flag: {safety_count}건, "
        f"저신뢰 트렌드: {confidence_low}건)"
    )
    return scored


def analyze_trends(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    config: AppConfig,
    conn: sqlite3.Connection | None = None,
) -> list[ScoredTrend]:
    """동기 래퍼. 내부적으로 비동기 병렬 스코어링 실행."""
    return run_async(_analyze_trends_async(raw_trends, contexts, config, conn))


# ══════════════════════════════════════════════════════
#  Trend Pattern Detection
# ══════════════════════════════════════════════════════

async def detect_trend_patterns(
    conn: sqlite3.Connection, keyword: str, days: int = 7
) -> dict:
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

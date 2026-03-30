"""analysis/parsing.py — JSON 파싱 + ScoredTrend 변환.

analyzer.py에서 추출. JSON 파서, Instructor 배치 스코어링, dict→ScoredTrend 변환.
"""

import json

from loguru import logger as log

from analysis.scoring import _compute_cross_source_confidence, _compute_signal_score
from config import AppConfig
from models import MultiSourceContext, ScoredTrend, TrendContext, TrendSource

# [Phase 1] Instructor 구조화된 출력 (선택 의존성)
try:
    from structured_output import ScoringResponseItem, extract_structured_list

    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False


# ══════════════════════════════════════════════════════
#  JSON Parser
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
#  [Phase 1] Instructor 기반 배치 스코어링
# ══════════════════════════════════════════════════════


async def _score_batch_instructor(
    prompt: str,
    count: int,
) -> list[dict] | None:
    """Instructor로 배치 스코어링 수행. 실패 시 None (기존 경로 폴백)."""
    if not INSTRUCTOR_AVAILABLE:
        return None
    try:
        items = await extract_structured_list(
            prompt,
            ScoringResponseItem,
            tier="lightweight",
            max_tokens=600 * count,
            expected_count=count,
        )
        if items and len(items) == count:
            log.info(f"[Instructor] 배치 스코어링 성공 ({count}개)")
            return [item.model_dump() for item in items]
        return None
    except Exception as e:
        log.debug(f"[Instructor] 배치 스코어링 폴백: {e}")
        return None


# ══════════════════════════════════════════════════════
#  Default / Conversion
# ══════════════════════════════════════════════════════


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

    # [v15.0] Phase A: Niche Bonus — 니치 카테고리에 보너스 점수 부여
    niche_cats = getattr(config, "niche_categories", []) if config else []
    niche_bonus = getattr(config, "niche_bonus_points", 0) if config else 0
    if niche_cats and niche_bonus and category in niche_cats:
        hybrid_viral = min(hybrid_viral + niche_bonus, 100)
        log.debug(f"  [Niche Bonus] '{keyword}' ({category}) +{niche_bonus}점 → {hybrid_viral}점")

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
        log.warning(f"  [게시불가] '{keyword}' publishable=false " f"(사유: {publishability_reason or '미상'})")
    if corrected_keyword:
        log.info(f"  [키워드 교정] '{keyword}' → '{corrected_keyword}'")

    # [v6.0] 출처 신뢰도 & 소스 간 일관성 검증
    source_credibility_val = 0.0
    cross_source_consistent_val = True
    hallucination_flags_val: list[str] = []

    try:
        from fact_checker import (
            check_cross_source_consistency,
            compute_enhanced_confidence,
        )

        # 출처 신뢰도 산출
        news_insight = context.news_insight if context else ""
        _, source_credibility_val = compute_enhanced_confidence(volume_numeric, context, news_insight)

        # 저신뢰 출처 패널티 적용
        cred_threshold = getattr(config, "credibility_penalty_threshold", 0.3) if config else 0.3
        cred_factor = getattr(config, "credibility_penalty_factor", 0.85) if config else 0.85
        enable_cred = getattr(config, "enable_source_credibility", True) if config else True

        if enable_cred and source_credibility_val < cred_threshold and source_credibility_val > 0:
            old_viral = hybrid_viral
            hybrid_viral = int(hybrid_viral * cred_factor)
            log.debug(
                f"  [출처 신뢰도 패널티] '{keyword}' 신뢰도={source_credibility_val:.2f} "
                f"< {cred_threshold} → {old_viral}점 x {cred_factor} = {hybrid_viral}점"
            )

        # 소스 간 일관성 검증
        enable_consistency = getattr(config, "enable_cross_source_consistency", True) if config else True
        if enable_consistency and context:
            temp_trend = ScoredTrend(
                keyword=keyword,
                rank=0,
                context=context,
                sources=[TrendSource.GETDAYTRENDS],
            )
            consistency = check_cross_source_consistency(temp_trend)
            cross_source_consistent_val = consistency["consistent"]
            if not cross_source_consistent_val:
                conflicts = consistency.get("conflicts", [])
                hallucination_flags_val.extend(f"소스 충돌: {c}" for c in conflicts[:3])
                log.warning(f"  [소스 불일치] '{keyword}' 충돌 {len(conflicts)}건: " f"{', '.join(conflicts[:2])}")
    except Exception as _e:
        log.debug(f"[v6.0] 정확성 검증 스킵: {_e}")

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
        # [v6.0] 정보 정확성
        source_credibility=source_credibility_val,
        cross_source_consistent=cross_source_consistent_val,
        hallucination_flags=hallucination_flags_val,
    )

"""JSON parsing and ScoredTrend conversion helpers for analyzer."""

import json
import re

from loguru import logger as log

try:
    from .scoring import _compute_cross_source_confidence, _compute_signal_score
    from ..config import AppConfig
    from ..models import MultiSourceContext, ScoredTrend, TrendContext, TrendSource
except ImportError:
    from analysis.scoring import _compute_cross_source_confidence, _compute_signal_score
    from config import AppConfig
    from models import MultiSourceContext, ScoredTrend, TrendContext, TrendSource

try:
    try:
        from ..structured_output import ScoringResponseItem, extract_structured_list
    except ImportError:
        from structured_output import ScoringResponseItem, extract_structured_list

    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False


def _json_candidates(text: str, opening: str, closing: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    candidates = [stripped]
    fence_match = re.match(r"^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$", stripped, re.IGNORECASE)
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    start = stripped.find(opening)
    end = stripped.rfind(closing)
    if start != -1 and end != -1 and start < end:
        candidates.append(stripped[start : end + 1])

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _parse_json(text: str | None) -> dict | None:
    """Parse a JSON object, tolerating fenced or prefixed payloads."""
    if not text:
        return None

    last_error: json.JSONDecodeError | None = None
    for candidate in _json_candidates(text, "{", "}"):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed

    preview = text[:200].replace("\n", "\\n")
    log.warning(f"[_parse_json] JSON parse failed: {last_error} | preview: {preview}")
    return None


def _parse_json_array(text: str | None) -> list | None:
    """Parse a JSON array, including wrapped list payloads."""
    if not text:
        return None

    for candidate in _json_candidates(text, "[", "]"):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("items", "results", "data", "trends"):
                value = parsed.get(key)
                if isinstance(value, list):
                    return value
    return None


async def _score_batch_instructor(prompt: str, count: int) -> list[dict] | None:
    """Use Instructor structured output when available; otherwise return None."""
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
            log.info(f"[Instructor] Batch scoring succeeded ({count} items)")
            return [item.model_dump() for item in items]
        return None
    except Exception as exc:
        log.debug(f"[Instructor] Batch scoring fallback: {exc}")
        return None


def _default_scored_trend(keyword: str, context: MultiSourceContext) -> ScoredTrend:
    """Return a zero-score fallback trend."""
    return ScoredTrend(
        keyword=keyword,
        rank=0,
        context=context,
        sources=[TrendSource.GETDAYTRENDS],
    )


def _coerce_nullable_int(value, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _coerce_nullable_str(value, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _compute_hybrid_viral(
    config: "AppConfig | None",
    llm_viral: int,
    volume_numeric: int,
    trend_acceleration: str,
    confidence: int,
    velocity: float,
    keyword: str,
    category: str,
) -> int:
    """Blend model score with signal score and apply category/confidence adjustments."""
    weight = getattr(config, "viral_score_llm_weight", 0.6) if config else 0.6
    signal = _compute_signal_score(volume_numeric, trend_acceleration, confidence, velocity=velocity)
    hybrid = int(llm_viral * weight + signal * (1.0 - weight))

    min_conf = getattr(config, "min_cross_source_confidence", 2) if config else 2
    if confidence < min_conf:
        hybrid = int(hybrid * 0.65)
        log.debug(
            f"[Phase1 penalty] '{keyword}' confidence {confidence}/{min_conf} -> viral {hybrid}"
        )

    niche_categories = getattr(config, "niche_categories", []) if config else []
    niche_bonus = getattr(config, "niche_bonus_points", 0) if config else 0
    if niche_categories and niche_bonus and category in niche_categories:
        hybrid = min(hybrid + niche_bonus, 100)
        log.debug(f"[Niche bonus] '{keyword}' ({category}) +{niche_bonus} -> {hybrid}")

    return hybrid


def _build_trend_context(parsed: dict, context: "MultiSourceContext") -> "TrendContext | None":
    """Build structured trend context when deep-why fields are present."""
    trigger = parsed.get("trigger_event", "")
    chain = parsed.get("chain_reaction", "")
    why_now = parsed.get("why_now", "")
    positions = parsed.get("key_positions", [])
    if not (trigger or chain or why_now or positions):
        return None

    real_tweets = ""
    if context and context.twitter_insight:
        insight = context.twitter_insight
        if len(insight) > 30 and "오류" not in insight and "없음" not in insight:
            real_tweets = insight[:300]

    return TrendContext(
        trigger_event=trigger,
        chain_reaction=chain,
        why_now=why_now,
        key_positions=positions if isinstance(positions, list) else [],
        real_tweets_summary=real_tweets,
    )


def _parse_publishability(parsed: dict, keyword: str) -> tuple[bool, str, str]:
    """Return publishability decision plus reason and corrected keyword."""
    publishable = parsed.get("publishable", True)
    if isinstance(publishable, str):
        publishable = publishable.lower() not in ("false", "0", "no")

    reason = parsed.get("publishability_reason", "")
    corrected = parsed.get("corrected_keyword", "")

    if not publishable:
        log.warning(f"[Publishability] '{keyword}' blocked: {reason or 'unspecified'}")
    if corrected:
        log.info(f"[Keyword correction] '{keyword}' -> '{corrected}'")

    return bool(publishable), reason, corrected


def _apply_credibility_check(
    config: "AppConfig | None",
    context: "MultiSourceContext",
    keyword: str,
    hybrid_viral: int,
) -> tuple[int, float, bool, list[str]]:
    """Apply credibility penalty and cross-source consistency checks."""
    credibility = 0.0
    consistent = True
    flags: list[str] = []

    try:
        try:
            from ..fact_checker import check_cross_source_consistency, compute_enhanced_confidence
        except ImportError:
            from fact_checker import check_cross_source_consistency, compute_enhanced_confidence

        news_insight = context.news_insight if context else ""
        _, credibility = compute_enhanced_confidence(hybrid_viral, context, news_insight)

        threshold = getattr(config, "credibility_penalty_threshold", 0.3) if config else 0.3
        penalty_factor = getattr(config, "credibility_penalty_factor", 0.85) if config else 0.85
        enable_credibility = getattr(config, "enable_source_credibility", True) if config else True
        if enable_credibility and 0 < credibility < threshold:
            hybrid_viral = int(hybrid_viral * penalty_factor)
            log.debug(
                f"[Credibility penalty] '{keyword}' credibility {credibility:.2f} < {threshold} -> {hybrid_viral}"
            )

        enable_consistency = getattr(config, "enable_cross_source_consistency", True) if config else True
        if enable_consistency and context:
            temp = ScoredTrend(keyword=keyword, rank=0, context=context, sources=[TrendSource.GETDAYTRENDS])
            result = check_cross_source_consistency(temp)
            consistent = result["consistent"]
            if not consistent:
                conflicts = result.get("conflicts", [])
                flags.extend(f"cross-source conflict: {item}" for item in conflicts[:3])
                log.warning(f"[Cross-source mismatch] '{keyword}' conflicts={len(conflicts)}")
    except Exception as exc:
        log.debug(f"[Credibility check] skipped: {exc}")

    return hybrid_viral, credibility, consistent, flags


def _parse_scored_trend_from_dict(
    parsed: dict,
    keyword: str,
    volume_numeric: int,
    context: "MultiSourceContext",
    config: "AppConfig | None" = None,
    velocity: float = 0.0,
) -> "ScoredTrend":
    """Convert parsed LLM output into a ScoredTrend."""
    raw_category = parsed.get("category", "")
    category = raw_category.split("|")[0].strip() if raw_category else ""
    trend_acceleration = _coerce_nullable_str(parsed.get("trend_acceleration"), "+0%")
    llm_viral = min(max(_coerce_nullable_int(parsed.get("viral_potential"), 0), 0), 100)
    volume_last_24h = _coerce_nullable_int(parsed.get("volume_last_24h"), volume_numeric)
    suggested_angles = parsed.get("suggested_angles") or []

    confidence = _compute_cross_source_confidence(volume_numeric, context)
    hybrid_viral = _compute_hybrid_viral(
        config,
        llm_viral,
        volume_numeric,
        trend_acceleration,
        confidence,
        velocity,
        keyword,
        category,
    )
    trend_context = _build_trend_context(parsed, context)
    publishable, publishability_reason, corrected_keyword = _parse_publishability(parsed, keyword)
    hybrid_viral, source_credibility, cross_source_consistent, hallucination_flags = _apply_credibility_check(
        config,
        context,
        keyword,
        hybrid_viral,
    )

    return ScoredTrend(
        keyword=keyword,
        rank=0,
        volume_last_24h=volume_last_24h,
        trend_acceleration=trend_acceleration,
        viral_potential=min(hybrid_viral, 100),
        top_insight=_coerce_nullable_str(parsed.get("top_insight"), ""),
        suggested_angles=suggested_angles,
        best_hook_starter=_coerce_nullable_str(parsed.get("best_hook_starter"), ""),
        category=category,
        context=context,
        sources=[TrendSource.GETDAYTRENDS],
        sentiment=_coerce_nullable_str(parsed.get("sentiment"), "neutral"),
        safety_flag=bool(parsed.get("safety_flag", False)),
        cross_source_confidence=confidence,
        joongyeon_kick=min(max(_coerce_nullable_int(parsed.get("joongyeon_kick"), 0), 0), 100),
        joongyeon_angle=_coerce_nullable_str(parsed.get("joongyeon_angle"), ""),
        why_trending=_coerce_nullable_str(parsed.get("why_trending"), ""),
        peak_status=_coerce_nullable_str(parsed.get("peak_status"), ""),
        relevance_score=min(max(_coerce_nullable_int(parsed.get("relevance_score"), 0), 0), 10),
        trend_context=trend_context,
        publishable=bool(publishable),
        publishability_reason=publishability_reason,
        corrected_keyword=corrected_keyword,
        source_credibility=source_credibility,
        cross_source_consistent=cross_source_consistent,
        hallucination_flags=hallucination_flags,
    )

"""
getdaytrends — Content QA & Regeneration
콘텐츠 QA 감사 + 재생성 로직.
generator.py에서 분리됨.
"""

import asyncio
import re

from loguru import logger as log
from shared.llm import LLMClient
from shared.llm.models import LLMPolicy

from config import AppConfig
from models import GeneratedTweet, ScoredTrend, TweetBatch
from multilang import (
    _BLOG_REQUIRED_HEADINGS,
    _GENERIC_ENTITY_ALLOWLIST,
    _QA_CLICHE_PATTERNS,
    _THREADS_BAIT_PATTERNS,
    _build_allowed_fact_corpus,
    _extract_candidate_entities,
    _first_nonempty_lines,
)

_JSON_POLICY = LLMPolicy(response_mode="json")


def _audit_content_group(
    group_name: str,
    items: list[GeneratedTweet],
    trend: ScoredTrend,
    config: AppConfig,
) -> dict:
    combined = "\n".join(item.content for item in items if item.content)
    combined_lower = combined.lower()
    leading_lines = _first_nonempty_lines(combined, limit=3)
    lead_text = " ".join(leading_lines)
    issues: list[str] = []

    hook = 16
    if any(phrase in lead_text for phrase in _QA_CLICHE_PATTERNS):
        hook = max(0, hook - 6)
        issues.append("첫 문장이 기사체/상투구에 가까움")
    if not re.search(r"\d|왜|무엇|핵심|신호|질문", lead_text):
        hook = max(0, hook - 3)

    tone = 15
    matched_cliches = [phrase for phrase in _QA_CLICHE_PATTERNS if phrase in combined]
    if matched_cliches:
        tone = max(0, tone - min(15, 5 * len(matched_cliches)))
        issues.append(f"상투구 감지: {', '.join(matched_cliches[:3])}")

    # [Phase 2] Kiwipiepy 형태소 기반 AI어투 심층 탐지
    try:
        from korean_nlp import compute_quality_score, detect_ai_voice

        ai_flags = detect_ai_voice(combined)
        if ai_flags:
            # 기존 상투구와 중복되지 않는 새로운 AI어투만 추가 감점
            new_flags = [f for f in ai_flags if not any(c in f for c in matched_cliches)]
            if new_flags:
                tone = max(0, tone - min(10, 3 * len(new_flags)))
                issues.append(f"AI어투(형태소): {', '.join(new_flags[:2])}")
        # 품질 점수가 낮으면 추가 감점
        avg_quality = sum(compute_quality_score(item.content) for item in items if item.content) / max(len(items), 1)
        if avg_quality < 0.5:
            tone = max(0, tone - 3)
            issues.append(f"Kiwipiepy 품질 점수 낮음: {avg_quality:.2f}")
    except ImportError:
        pass  # Kiwipiepy 미설치 시 기존 동작 유지

    allowed_corpus = _build_allowed_fact_corpus(trend)
    allowed_lower = allowed_corpus.lower()
    allowed_entities = {
        entity.casefold()
        for entity in _extract_candidate_entities(allowed_corpus)
        if entity.casefold() not in _GENERIC_ENTITY_ALLOWLIST
    }
    content_entities = {
        entity.casefold()
        for entity in _extract_candidate_entities(combined)
        if entity.casefold() not in _GENERIC_ENTITY_ALLOWLIST
    }
    unknown_entities = sorted(content_entities - allowed_entities)
    allowed_percentages = set(re.findall(r"\d+(?:\.\d+)?%", allowed_corpus))
    unknown_percentages = sorted(set(re.findall(r"\d+(?:\.\d+)?%", combined)) - allowed_percentages)

    fact = 15
    fact_violation = False
    if unknown_entities:
        fact = max(0, fact - min(10, 4 * len(unknown_entities[:2])))
        fact_violation = True
        issues.append(f"컨텍스트 밖 고유명사 추정: {', '.join(unknown_entities[:2])}")
    if unknown_percentages:
        fact = max(0, fact - min(8, 3 * len(unknown_percentages[:2])))
        fact_violation = True
        issues.append(f"컨텍스트 밖 수치 추정: {', '.join(unknown_percentages[:2])}")
    if not allowed_lower.strip():
        fact = min(fact, 10)

    # [v6.0] 강화된 팩트 체크 — 출처 불명 인용 감지
    _UNVERIFIED_QUOTE_PATTERNS = [
        "전문가들은",
        "관계자에 따르면",
        "업계 관계자",
        "한 관계자는",
        "내부 소식통",
        "익명의 관계자",
        "소식통에 따르면",
        "전문가는 분석",
    ]
    matched_unverified = [p for p in _UNVERIFIED_QUOTE_PATTERNS if p in combined]
    if matched_unverified:
        fact = max(0, fact - min(10, 5 * len(matched_unverified)))
        fact_violation = True
        issues.append(f"출처 불명 인용 감지: {', '.join(matched_unverified[:2])}")

    # [v6.0] 숫자 일관성 검증 — 같은 대상에 대한 모순된 수치
    content_numbers = re.findall(r"(\d{1,3}(?:[,.]?\d{3})*(?:\.\d+)?)\s*(만|억|조|%)", combined)
    if len(content_numbers) >= 2:
        # 같은 단위의 숫자가 크게 다르면 경고
        by_unit: dict[str, list[float]] = {}
        for num_str, unit in content_numbers:
            try:
                val = float(num_str.replace(",", ""))
                by_unit.setdefault(unit, []).append(val)
            except ValueError:
                pass
        for unit, vals in by_unit.items():
            if len(vals) >= 2:
                ratio = max(vals) / max(min(vals), 0.01)
                if ratio > 100:  # 100배 이상 차이
                    fact = max(0, fact - 3)
                    issues.append(f"수치 불일치 의심: 같은 단위({unit})에서 {ratio:.0f}배 차이")

    kick = 12
    ending = combined.splitlines()[-1] if combined.splitlines() else combined
    if any(phrase in ending for phrase in ("귀추가 주목된다", "마무리하며", "결론적으로")):
        kick = 4
        issues.append("마무리가 상투적임")

    angle = 12
    regulation = 10
    algorithm = 10

    if group_name == "tweets":
        if any(len(item.content) > 280 for item in items):
            regulation = min(regulation, 6)
            algorithm = min(algorithm, 6)
            issues.append("280자 초과 트윗 존재")
    elif group_name == "threads_posts":
        if "#" in combined:
            regulation = 0
            issues.append("해시태그 사용")
        matched_bait = [phrase for phrase in _THREADS_BAIT_PATTERNS if phrase in combined]
        if matched_bait:
            regulation = max(0, regulation - 6)
            issues.append(f"참여 유도 문구 감지: {', '.join(matched_bait[:2])}")
        if any(len(item.content) > 500 for item in items):
            algorithm = max(0, algorithm - 4)
            issues.append("500자 초과 Threads 포스트 존재")
    elif group_name == "long_posts":
        if len(leading_lines) < 2:
            hook = max(0, hook - 4)
            issues.append("첫 3줄 안의 핵심 주장 구조가 약함")
        if not re.search(r"\n", combined):
            angle = max(0, angle - 4)
    elif group_name == "blog_posts":
        missing_headings = [heading for heading in _BLOG_REQUIRED_HEADINGS if heading not in combined]
        if missing_headings:
            angle = max(0, angle - min(12, 3 * len(missing_headings)))
            issues.append(f"필수 섹션 누락: {', '.join(missing_headings)}")
        if "## 핵심 정리" in combined and not re.search(r"(?m)^[\-\*\u2022]\s+", combined):
            angle = max(0, angle - 4)
            issues.append("핵심 정리 불릿 부족")

    total = hook + fact + tone + kick + angle + regulation + algorithm
    threshold = config.get_quality_threshold(group_name)
    failed = total < threshold or regulation <= 3 or fact_violation
    reason = issues[0] if issues else "통과"
    worst = min(
        {
            "hook": hook,
            "fact": fact,
            "tone": tone,
            "kick": kick,
            "angle": angle,
            "regulation": regulation,
            "algorithm": algorithm,
        }.items(),
        key=lambda item: item[1],
    )[0]
    return {
        "hook": hook,
        "fact": fact,
        "tone": tone,
        "kick": kick,
        "angle": angle,
        "regulation": regulation,
        "algorithm": algorithm,
        "total": total,
        "avg_score": total,
        "threshold": threshold,
        "fact_violation": fact_violation,
        "failed": failed,
        "worst": worst,
        "reason": reason,
        "issues": issues,
    }


async def audit_generated_content(
    batch: "TweetBatch",
    trend: "ScoredTrend",
    config: "AppConfig",
    client: "LLMClient",
) -> dict | None:
    """포맷별 규칙 기반 QA. 실패한 그룹만 재생성할 수 있도록 상세 결과를 반환."""
    if not batch:
        return None

    group_map = {
        "tweets": list(getattr(batch, "tweets", []) or []),
        "threads_posts": list(getattr(batch, "threads_posts", []) or []),
        "long_posts": list(getattr(batch, "long_posts", []) or []),
        "blog_posts": list(getattr(batch, "blog_posts", []) or []),
    }
    present_groups = {name: items for name, items in group_map.items() if items}
    if not present_groups:
        return None

    group_results: dict[str, dict] = {}
    failed_groups: list[str] = []
    for group_name, items in present_groups.items():
        result = _audit_content_group(group_name, items, trend, config)
        group_results[group_name] = result
        if result["failed"]:
            failed_groups.append(group_name)
        log.info(
            f"  [QA:{group_name}] '{trend.keyword}' → {result['total']}/{result['threshold']} "
            f"(F:{result['fact']} T:{result['tone']} R:{result['regulation']})"
        )

    summary_total = round(sum(r["total"] for r in group_results.values()) / len(group_results))
    summary_regulation = min(r["regulation"] for r in group_results.values())
    primary_result = group_results.get("tweets") or next(iter(group_results.values()))
    summary_reason = (
        " | ".join(f"{group}: {result['reason']}" for group, result in group_results.items() if result["failed"])
        or "통과"
    )
    summary_worst = min(group_results.items(), key=lambda item: item[1]["total"])[0]

    summary = {
        **primary_result,
        "total": summary_total,
        "avg_score": summary_total,
        "regulation": summary_regulation,
        "reason": summary_reason,
        "worst": summary_worst,
        "failed_groups": failed_groups,
        "group_results": group_results,
    }
    return summary


async def regenerate_content_groups(
    batch: "TweetBatch",
    trend: "ScoredTrend",
    config: "AppConfig",
    client: "LLMClient",
    groups: list[str],
    recent_tweets: list[str] | None = None,
) -> "TweetBatch":
    """실패한 콘텐츠 그룹만 1회 재생성해 기존 배치에 반영한다."""
    if not groups:
        return batch

    # Import lazily to avoid circular imports while generator.py re-exports
    # these helpers from content_qa.py for backward compatibility.
    from generator import (
        _select_generation_tier,
        generate_blog_async,
        generate_long_form_async,
        generate_threads_content_async,
        generate_tweets_async,
    )

    regen_tasks: dict[str, asyncio.Task] = {}
    if "tweets" in groups:
        regen_tasks["tweets"] = asyncio.create_task(generate_tweets_async(trend, config, client, recent_tweets))
    if "threads_posts" in groups:
        regen_tasks["threads_posts"] = asyncio.create_task(generate_threads_content_async(trend, config, client))
    if "long_posts" in groups and config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        regen_tasks["long_posts"] = asyncio.create_task(
            generate_long_form_async(trend, config, client, tier=_select_generation_tier(trend, config))
        )
    if (
        "blog_posts" in groups
        and "naver_blog" in getattr(config, "target_platforms", [])
        and trend.viral_potential >= getattr(config, "blog_min_score", 70)
    ):
        regen_tasks["blog_posts"] = asyncio.create_task(generate_blog_async(trend, config, client))

    if not regen_tasks:
        return batch

    results = await asyncio.gather(*regen_tasks.values(), return_exceptions=True)
    for group_name, result in zip(regen_tasks.keys(), results, strict=False):
        if isinstance(result, Exception):
            log.warning(f"  [QA 재생성 실패] '{trend.keyword}' {group_name}: {result}")
            continue
        if group_name == "tweets":
            if result and getattr(result, "tweets", None):
                batch.tweets = result.tweets
        elif result is not None:
            setattr(batch, group_name, result)
    return batch


# ══════════════════════════════════════════════════════
#  v15.0 Phase B: Named Persona Rotation
#  → generation/persona.py로 추출됨
# ══════════════════════════════════════════════════════

from generation.persona import _CATEGORY_PERSONA_MAP, _round_robin_counter, select_persona  # noqa: F401

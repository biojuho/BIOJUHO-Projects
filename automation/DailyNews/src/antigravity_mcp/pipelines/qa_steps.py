from __future__ import annotations

import logging
import re
from typing import Any

from antigravity_mcp.integrations.fact_check_adapter import FactCheckAdapter
from antigravity_mcp.integrations.llm import is_meta_response
from antigravity_mcp.integrations.llm_prompts import get_category_contract
from antigravity_mcp.pipelines.assembly_context import ReportAssemblyContext

logger = logging.getLogger(__name__)


def _has_generic_cta(text: str) -> bool:
    generic_terms = ("검토", "고려", "관찰", "주목", "모니터링")
    if not any(term in text for term in generic_terms):
        return False
    return not bool(re.search(r"(오늘|이번|주|개월|30일|48시간|까지)", text))


def _collect_evidence_quality_warnings(parser_meta: dict[str, Any]) -> list[str]:
    if parser_meta.get("format") != "v2":
        return []
    evidence = parser_meta.get("evidence", {})
    warnings: list[str] = []
    missing_line_count = int(evidence.get("missing_line_count", 0) or 0)
    if missing_line_count:
        warnings.append(f"Evidence tags missing on {missing_line_count} analytic line(s).")
    line_count = int(evidence.get("line_count", 0) or 0)
    background_line_count = int(evidence.get("background_line_count", 0) or 0)
    if line_count and background_line_count > max(1, line_count // 2):
        warnings.append("Too many [Background] claims in base LLM analysis.")
    article_ref_count = int(evidence.get("article_ref_count", 0) or 0)
    if line_count and article_ref_count == 0:
        warnings.append("Base LLM analysis does not cite any direct article tags.")
    return warnings


def _quality_review_warnings(ctx: ReportAssemblyContext, draft_text: str, parser_meta: dict) -> list[str]:
    warnings: list[str] = []
    if _has_generic_cta("\n".join(ctx.insights) + "\n" + draft_text):
        warnings.append("Generic CTA detected without timeframe.")
    if any("..." in insight for insight in ctx.insights):
        warnings.append("Truncated insight text detected.")
    warnings.extend(_collect_evidence_quality_warnings(parser_meta))
    return warnings


_EVIDENCE_TAG_PATTERN = re.compile(r"\[(?:A\d+|Inference:[^\]]+|Background|Insufficient evidence)\]")


def _check_category_contract_for_content(category: str, summary_lines: list[str], insights: list[str]) -> list[str]:
    contract = get_category_contract(category)
    violations: list[str] = []

    min_summary = int(contract.get("min_summary_lines", 2))
    if len(summary_lines) < min_summary:
        violations.append(
            f"Category contract: {category} requires {min_summary} summary lines, got {len(summary_lines)}."
        )

    min_insights = int(contract.get("min_insights", 1))
    if len(insights) < min_insights:
        violations.append(
            f"Category contract: {category} requires {min_insights} insights, got {len(insights)}."
        )

    min_citations = int(contract.get("min_source_citations", 1))
    combined = "\n".join(summary_lines + insights)
    citation_count = len(_EVIDENCE_TAG_PATTERN.findall(combined))
    if citation_count < min_citations:
        violations.append(
            f"Category contract: {category} requires {min_citations} source citations, got {citation_count}."
        )

    if contract.get("required_data_anchors"):
        has_data = bool(re.search(r"\d+\.?\d*%?", combined))
        if not has_data:
            violations.append(
                f"Category contract: {category} requires data anchors (numbers/percentages)."
            )

    return violations


def _check_category_contract(ctx: ReportAssemblyContext) -> list[str]:
    return _check_category_contract_for_content(ctx.category, ctx.summary_lines, ctx.insights)


def _detect_semantic_overlap(
    ctx: ReportAssemblyContext, *, similarity_threshold: float = 0.75,
) -> dict[str, Any]:
    try:
        recent_drafts = ctx.state_store.get_recent_drafts(ctx.category, days=7, channel="x")
    except Exception as exc:
        logger.debug("Semantic overlap check failed: %s", exc)
        return {}

    if not recent_drafts:
        return {}

    current_draft = "\n".join(
        draft.content for draft in ctx.channel_drafts
        if draft.channel == "x" and draft.content
    )
    if not current_draft:
        return {}

    past_texts = [p["content"] for p in recent_drafts if p.get("content")]
    if not past_texts:
        return {}

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 3),
            max_features=3000,
            sublinear_tf=True,
        )
        all_texts = past_texts + [current_draft]
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        sim_scores = sklearn_cosine(tfidf_matrix[-1:], tfidf_matrix[:-1]).flatten()

        max_similarity = float(sim_scores.max()) if len(sim_scores) > 0 else 0.0
        overlapping_indices = [i for i, score in enumerate(sim_scores) if score >= similarity_threshold]

        logger.debug(
            "TF-IDF overlap for %s: max=%.3f, overlapping=%d/%d",
            ctx.category, max_similarity, len(overlapping_indices), len(past_texts),
        )
    except ImportError:
        logger.debug("sklearn not available, falling back to bigram Jaccard")

        def _bigrams(text: str) -> set[str]:
            cleaned = re.sub(r"\s+", "", text.lower())
            return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)} if len(cleaned) >= 2 else set()

        current_bg = _bigrams(current_draft)
        if not current_bg:
            return {}

        sim_scores_list: list[float] = []
        for past_text in past_texts:
            past_bg = _bigrams(past_text)
            if not past_bg:
                sim_scores_list.append(0.0)
                continue
            intersection = current_bg & past_bg
            union = current_bg | past_bg
            sim_scores_list.append(len(intersection) / len(union) if union else 0.0)

        max_similarity = max(sim_scores_list) if sim_scores_list else 0.0
        overlapping_indices = [i for i, score in enumerate(sim_scores_list) if score >= similarity_threshold]

    result: dict[str, Any] = {
        "max_similarity": round(max_similarity, 3),
        "overlapping_count": len(overlapping_indices),
        "threshold": similarity_threshold,
    }
    if overlapping_indices:
        result["overlapping_drafts"] = [past_texts[i][:300] for i in overlapping_indices[:3]]
    return result


async def _run_fact_check(ctx: ReportAssemblyContext, draft_text: str, review_warnings: list[str]) -> None:
    try:
        adapter = FactCheckAdapter()
        if not adapter.is_available():
            return
        result = await adapter.check_report(
            summary_lines=ctx.summary_lines,
            insights=ctx.insights,
            drafts_text=draft_text,
            source_articles=[
                {"title": item.title, "description": item.summary[:200], "source_name": item.source_name}
                for item in ctx.items
            ],
        )
        ctx.fact_check_score = result.get("fact_check_score", 0.0)
        ctx.analysis_meta["fact_check"] = result
        if not result.get("passed", True):
            review_warnings.extend(result.get("issues", [])[:3])
    except Exception as exc:
        logger.debug("Final fact-check skipped for %s: %s", ctx.category, exc)


async def _auto_heal_once(
    ctx: ReportAssemblyContext,
    violations: list[str],
) -> bool:
    if not violations:
        return False

    llm = getattr(ctx, "_llm_adapter", None)
    if llm is None or not hasattr(llm, "build_report_payload"):
        return False

    try:
        payload, heal_warnings = await llm.build_report_payload(
            category=ctx.category,
            items=ctx.items,
            window_name=ctx.window_name,
            quality_feedback={
                "recurring_warnings": violations[:5],
                "improvement_suggestions": violations[:5],
            },
        )
        if heal_warnings:
            ctx.analysis_meta["auto_heal_warnings"] = list(heal_warnings)
        if payload.parse_meta.get("used_fallback"):
            ctx.analysis_meta["auto_heal"] = {
                "applied": False,
                "reason": payload.parse_meta.get("reason", "parser_fallback"),
            }
            return False

        candidate_summary = list(getattr(payload, "summary_lines", None) or [])
        candidate_insights = list(getattr(payload, "insights", None) or [])
        if not candidate_summary or not candidate_insights:
            ctx.analysis_meta["auto_heal"] = {"applied": False, "reason": "empty_payload"}
            return False

        if is_meta_response("\n".join(candidate_summary + candidate_insights), check_line_count=False):
            ctx.analysis_meta["auto_heal"] = {"applied": False, "reason": "meta_response"}
            return False

        re_violations = _check_category_contract_for_content(ctx.category, candidate_summary, candidate_insights)
        if len(re_violations) >= len(violations):
            ctx.analysis_meta["auto_heal"] = {
                "applied": False,
                "reason": "no_improvement",
                "remaining_violations": re_violations,
            }
            return False

        ctx.summary_lines = candidate_summary
        ctx.insights = candidate_insights
        if getattr(payload, "channel_drafts", None):
            ctx.channel_drafts = list(payload.channel_drafts)
        ctx.analysis_meta["parser"] = getattr(payload, "parse_meta", {}) or ctx.analysis_meta.get("parser", {})
        brief_body = str(ctx.analysis_meta["parser"].get("brief_body", "") or "").strip()
        if brief_body:
            ctx.analysis_meta["brief_body"] = brief_body
        ctx.analysis_meta["auto_heal"] = {
            "applied": True,
            "attempt": 1,
            "remaining_violations": re_violations,
        }
        logger.info(
            "Auto-heal improved %s from %d to %d violations",
            ctx.category,
            len(violations),
            len(re_violations),
        )
        return not re_violations
    except Exception as exc:
        logger.warning("Auto-heal failed for %s: %s", ctx.category, exc)
        ctx.analysis_meta["auto_heal"] = {"applied": False, "error": str(exc)[:120]}
        return False


async def finalize_quality(ctx: ReportAssemblyContext) -> None:
    draft_text = "\n".join(draft.content for draft in ctx.channel_drafts if draft.content)
    parser_meta = ctx.analysis_meta.get("parser", {})

    review_warnings = _quality_review_warnings(ctx, draft_text, parser_meta)
    await _run_fact_check(ctx, draft_text, review_warnings)

    contract_violations = _check_category_contract(ctx)
    if contract_violations:
        healed = await _auto_heal_once(ctx, contract_violations)
        if healed:
            ctx.warnings.append(f"[Quality] Auto-heal succeeded for {ctx.category}")
            contract_violations = []
        else:
            review_warnings.extend(contract_violations)
            ctx.analysis_meta["contract_violations"] = contract_violations
        parser_meta = ctx.analysis_meta.get("parser", parser_meta)

    overlap = _detect_semantic_overlap(ctx)
    if overlap:
        ctx.analysis_meta["semantic_overlap"] = overlap
        if overlap.get("overlapping_count", 0) > 0:
            review_warnings.append(
                f"Semantic overlap detected: {overlap['overlapping_count']} past draft(s) "
                f"with similarity >= {overlap['threshold']} (max={overlap['max_similarity']})."
            )

    has_fallback_draft = any(draft.channel == "x" and draft.is_fallback for draft in ctx.channel_drafts)
    insight_error = ctx.analysis_meta.get("insight_generator", {}).get("error", "")

    if parser_meta.get("used_fallback") or has_fallback_draft or (insight_error and not ctx.summary_lines):
        ctx.quality_state = "fallback"
    elif overlap.get("overlapping_count", 0) > 0:
        ctx.quality_state = "needs_differentiation"
    elif review_warnings or (ctx.fact_check_score and ctx.fact_check_score < 0.45):
        ctx.quality_state = "needs_review"
    else:
        ctx.quality_state = "ok"

    ctx.analysis_meta["quality_review"] = {
        "warnings": review_warnings,
        "evidence": parser_meta.get("evidence", {}),
    }
    if ctx.detail_level != "standard":
        ctx.analysis_meta["quality_review"]["detail_level"] = ctx.detail_level
    if review_warnings:
        ctx.warnings.extend(f"[Quality] {warning}" for warning in review_warnings)

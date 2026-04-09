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
    generic_terms = ("검토", "고려", "관심", "주목", "모니터링")
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
    """CTA, 잘린 인사이트, 증거 품질 경고 수집."""
    warnings: list[str] = []
    if _has_generic_cta("\n".join(ctx.insights) + "\n" + draft_text):
        warnings.append("Generic CTA detected without timeframe.")
    if any("..." in insight for insight in ctx.insights):
        warnings.append("Truncated insight text detected.")
    warnings.extend(_collect_evidence_quality_warnings(parser_meta))
    return warnings


_EVIDENCE_TAG_PATTERN = re.compile(r"\[(?:A\d+|Inference:[^\]]+|Background|Insufficient evidence)\]")


def _check_category_contract(ctx: ReportAssemblyContext) -> list[str]:
    """Enforce structural quality minimums defined in _CATEGORY_CONTRACTS.

    Returns a list of violation messages. An empty list means the report
    meets all category-specific quality requirements.
    """
    contract = get_category_contract(ctx.category)
    violations: list[str] = []

    min_summary = int(contract.get("min_summary_lines", 2))
    if len(ctx.summary_lines) < min_summary:
        violations.append(
            f"Category contract: {ctx.category} requires {min_summary} summary lines, got {len(ctx.summary_lines)}."
        )

    min_insights = int(contract.get("min_insights", 1))
    if len(ctx.insights) < min_insights:
        violations.append(
            f"Category contract: {ctx.category} requires {min_insights} insights, got {len(ctx.insights)}."
        )

    min_citations = int(contract.get("min_source_citations", 1))
    combined = "\n".join(ctx.summary_lines + ctx.insights)
    citation_count = len(_EVIDENCE_TAG_PATTERN.findall(combined))
    if citation_count < min_citations:
        violations.append(
            f"Category contract: {ctx.category} requires {min_citations} source citations, got {citation_count}."
        )

    if contract.get("required_data_anchors"):
        has_data = bool(re.search(r"\d+\.?\d*%?", combined))
        if not has_data:
            violations.append(
                f"Category contract: {ctx.category} requires data anchors (numbers/percentages)."
            )

    return violations


def _detect_semantic_overlap(
    ctx: ReportAssemblyContext, *, similarity_threshold: float = 0.75,
) -> dict[str, Any]:
    """최근 드래프트와 현재 드래프트 간 시맨틱 유사도 검사.

    1차: scikit-learn TF-IDF + 코사인 유사도 (문맥 기반, API 비용 0)
    2차 fallback: bi-gram 기반 Jaccard (sklearn 미설치 환경 대비)

    Returns:
        overlap metadata dict with max_similarity, overlapping_count, threshold
    """
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

    # ── TF-IDF 코사인 유사도 (1차 시도) ──
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

        # 한/영 혼합 텍스트를 위해 char_wb analyzer + (1,3)-gram 사용
        vectorizer = TfidfVectorizer(
            analyzer="char_wb",       # 단어 경계 기반 character n-gram
            ngram_range=(2, 3),       # bigram~trigram — 한국어 형태소 분리 없이 문맥 포착
            max_features=3000,        # 메모리 절약
            sublinear_tf=True,        # TF 스무딩 — 빈도 편향 방지
        )
        all_texts = past_texts + [current_draft]
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        # 현재 드래프트(마지막) vs 과거 드래프트(나머지)의 코사인 유사도
        sim_scores = sklearn_cosine(tfidf_matrix[-1:], tfidf_matrix[:-1]).flatten()

        max_similarity = float(sim_scores.max()) if len(sim_scores) > 0 else 0.0
        overlapping_indices = [i for i, s in enumerate(sim_scores) if s >= similarity_threshold]

        logger.debug(
            "TF-IDF overlap for %s: max=%.3f, overlapping=%d/%d",
            ctx.category, max_similarity, len(overlapping_indices), len(past_texts),
        )

    except ImportError:
        # ── Fallback: bi-gram Jaccard (sklearn 미설치 환경) ──
        logger.debug("sklearn not available, falling back to bigram Jaccard")

        def _bigrams(text: str) -> set[str]:
            """공백 제거 후 문자 bi-gram 집합 생성."""
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
        overlapping_indices = [i for i, s in enumerate(sim_scores_list) if s >= similarity_threshold]

    # ── 결과 조립 ──
    result: dict[str, Any] = {
        "max_similarity": round(max_similarity, 3),
        "overlapping_count": len(overlapping_indices),
        "threshold": similarity_threshold,
    }
    if overlapping_indices:
        result["overlapping_drafts"] = [
            past_texts[i][:300] for i in overlapping_indices[:3]
        ]
    return result


async def _run_fact_check(ctx: ReportAssemblyContext, draft_text: str, review_warnings: list[str]) -> None:
    """팩트 체크 실행 — 실패 시 무시, 결과를 ctx에 인플레이스 기록."""
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
    """품질 미달 시 LLM에 1회 자동 교정 요청.

    감점 사유를 명시한 짧은 교정 프롬프트로 재생성을 시도한다.
    성공(violations 해소) 시 True, 실패 시 False 반환.
    교정에 실패하더라도 파이프라인을 절대 중단하지 않는다.
    """
    if not violations:
        return False
    llm = getattr(ctx, "_llm_adapter", None)
    if llm is None or not hasattr(llm, "generate_text"):
        return False

    # 감점 사유를 한 줄씩 정리
    deduction_summary = "\n".join(f"- {v}" for v in violations[:5])
    heal_prompt = (
        "CRITICAL: This is a FRESH, STANDALONE request. You have NO previous conversation history.\n"
        "Do NOT say '죄송합니다', '이전 대화 없음', or ask for clarification.\n"
        f"The {ctx.category} brief has these quality issues:\n"
        f"{deduction_summary}\n\n"
        "Rewrite the brief DIRECTLY fixing only the listed issues. "
        "Keep Summary/Insights/Brief/Draft structure. Use ONLY the article context above."
    )

    try:
        corrected_text = await llm.generate_text(
            prompt=heal_prompt,
            max_tokens=1200,
            temperature=0.15,
            cache_scope=f"heal:{ctx.category}:{ctx.window_name}",
        )
        if not corrected_text or len(corrected_text.strip()) < 50:
            logger.info("Auto-heal returned empty/short response for %s", ctx.category)
            return False

        # 메타응답 감지 — "죄송합니다 / 이전 기록 없음" 류를 ctx에 주입하지 않음
        if is_meta_response(corrected_text, check_line_count=False):
            logger.warning("Auto-heal returned meta-response for %s; discarding", ctx.category)
            ctx.analysis_meta["auto_heal"] = {"applied": False, "reason": "meta_response"}
            return False

        # 교정된 텍스트에서 핵심 지표만 재검증
        lines = [ln.strip() for ln in corrected_text.split("\n") if ln.strip()]
        healed_summary = [ln for ln in lines if not ln.startswith("#") and len(ln) > 10][:5]
        healed_insights = [ln for ln in lines if "insight" in ln.lower() or "시사점" in ln or "의미" in ln][:3]

        # 교정 결과가 기존보다 나으면 ctx에 반영
        if len(healed_summary) >= 2 or len(healed_insights) >= 1:
            if len(healed_summary) > len(ctx.summary_lines):
                ctx.summary_lines = healed_summary
            if len(healed_insights) > len(ctx.insights):
                ctx.insights = healed_insights
            ctx.analysis_meta["auto_heal"] = {"applied": True, "attempt": 1}
            logger.info("Auto-heal succeeded for %s — re-checking contract", ctx.category)

            # 교정 후 계약 재검증
            re_violations = _check_category_contract(ctx)
            if not re_violations:
                return True  # 교정 성공!
            logger.info("Auto-heal partial: %d violations remain for %s", len(re_violations), ctx.category)
            return False

        return False
    except Exception as exc:
        logger.warning("Auto-heal failed for %s: %s", ctx.category, exc)
        ctx.analysis_meta["auto_heal"] = {"applied": False, "error": str(exc)[:120]}
        return False


async def finalize_quality(ctx: ReportAssemblyContext) -> None:
    draft_text = "\n".join(draft.content for draft in ctx.channel_drafts if draft.content)
    parser_meta = ctx.analysis_meta.get("parser", {})

    review_warnings = _quality_review_warnings(ctx, draft_text, parser_meta)
    await _run_fact_check(ctx, draft_text, review_warnings)

    # ── Category contract enforcement ──
    contract_violations = _check_category_contract(ctx)

    # ── 자가 치유: 계약 위반이 있으면 LLM 재시도 1회 ──
    if contract_violations:
        healed = await _auto_heal_once(ctx, contract_violations)
        if healed:
            # 교정 성공 — 위반 목록 비우고 경고만 기록
            ctx.warnings.append(f"[Quality] Auto-heal succeeded for {ctx.category}")
            contract_violations = []
        else:
            # 교정 실패 — 원래대로 위반 기록
            review_warnings.extend(contract_violations)
            ctx.analysis_meta["contract_violations"] = contract_violations

    # ── Semantic overlap detection ──
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

    ctx.analysis_meta["quality_review"] = {"warnings": review_warnings, "evidence": parser_meta.get("evidence", {})}
    # Record detail_level in quality meta for audit trail
    if ctx.detail_level != "standard":
        ctx.analysis_meta["quality_review"]["detail_level"] = ctx.detail_level
    if review_warnings:
        ctx.warnings.extend(f"[Quality] {warning}" for warning in review_warnings)


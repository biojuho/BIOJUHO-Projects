from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from antigravity_mcp.domain.models import ContentItem

_PROMPT_VERSION_RAW = os.getenv("PROMPT_VERSION", "").strip().lower()
_BRIEF_STYLE_RAW = os.getenv("BRIEF_STYLE", "").strip().lower()


def resolve_brief_style() -> str:
    if _BRIEF_STYLE_RAW in {"concise", "brief", "short", "legacy", "v1"}:
        return "concise"
    if _BRIEF_STYLE_RAW in {"detailed", "longform", "deep", "v2"}:
        return "detailed"
    if _PROMPT_VERSION_RAW in {"v2", "v2-deep", "v2-multi"}:
        return "detailed"
    return "concise"


PROMPT_VERSION = _PROMPT_VERSION_RAW or ("v2" if resolve_brief_style() == "detailed" else "v1")

_CATEGORY_CONTRACTS = {
    "economy": {
        "audiences": ["Investor", "Business operator"],
        "x_length": "500-750 characters",
        "tone": "practical, data-driven, mobile-friendly",
        # Structural quality requirements
        "min_summary_lines": 3,
        "min_insights": 2,
        "min_source_citations": 2,
        "required_data_anchors": True,
        "counterpoint_required": True,
    },
    "tech": {
        "audiences": ["Founder/PM", "Developer/Engineer"],
        "x_length": "700-1000 characters",
        "tone": "sharp, builder-oriented, decision-useful",
        "min_summary_lines": 3,
        "min_insights": 2,
        "min_source_citations": 2,
        "required_data_anchors": True,
        "counterpoint_required": True,
    },
    "default": {
        "audiences": ["Operator", "Investor"],
        "x_length": "600-900 characters",
        "tone": "concise, non-generic, execution-oriented",
        "min_summary_lines": 2,
        "min_insights": 1,
        "min_source_citations": 1,
        "required_data_anchors": False,
        "counterpoint_required": False,
    },
}


def get_category_contract(category: str) -> dict[str, Any]:
    if category.startswith("Economy_") or category == "Crypto":
        return _CATEGORY_CONTRACTS["economy"]
    if category == "Tech" or category.startswith("AI_"):
        return _CATEGORY_CONTRACTS["tech"]
    return _CATEGORY_CONTRACTS["default"]


def resolve_prompt_mode(window_name: str, item_count: int) -> str:
    if resolve_brief_style() == "concise":
        return "v1-brief"
    if PROMPT_VERSION in ("v2-deep", "v2-multi"):
        return PROMPT_VERSION
    if PROMPT_VERSION == "v2":
        if item_count <= 2:
            return "v2-deep"
        return "v2-multi" if window_name in ("evening",) else "v2-deep"
    if PROMPT_VERSION in ("v1", "v1-brief"):
        return "v1-brief"
    return PROMPT_VERSION


def _build_quality_feedback_block(quality_feedback: dict) -> str:
    """과거 품질 히스토리를 '3줄 금지 규칙'으로 압축.

    토큰 다이어트: 과거 경고를 전부 나열하지 않고,
    빈도·심각도 순으로 분석해서 딱 3줄의 금지 규칙만 생성한다.
    이 3줄이 System Prompt에 주입되어 반복 실수를 예방한다.
    """
    if not quality_feedback:
        return ""
    recurring = quality_feedback.get("recurring_warnings", [])

    # 메타응답 루프 방지: 최근 경고에 meta_response가 있으면 피드백 블록 자체를 비활성화
    # (quality_feedback이 "이전 리포트 수정 요청"으로 오해되는 피드백 루프 차단)
    meta_loop = any("meta_response" in w for w in recurring)
    if meta_loop:
        return ""
    suggestions = quality_feedback.get("improvement_suggestions", [])
    if not recurring and not suggestions:
        return ""

    # ── Step 1: 패턴별 빈도 카운트 (동일 유형 그룹핑) ──
    pattern_map: dict[str, int] = {}
    pattern_rules: dict[str, str] = {
        "draft_fallback": "Draft Post 섹션을 반드시 포함할 것 (누락 금지)",
        "generic": "모호한 동사(모니터링, 검토, 고려) 대신 구체적 액션+기한을 쓸 것",
        "evidence": "모든 분석 문장 끝에 증거 태그([A1], [Inference:...]) 필수",
        "truncat": "인사이트를 중간에 자르지 말고 완전한 문장으로 쓸 것",
        "citation": "출처 인용을 최소 2개 이상 포함할 것",
        "data": "수치/퍼센트 등 데이터 앵커를 반드시 포함할 것",
    }

    for w in recurring:
        w_lower = w.lower()
        matched = False
        for key in pattern_rules:
            if key in w_lower:
                pattern_map[key] = pattern_map.get(key, 0) + 1
                matched = True
                break
        if not matched:
            pattern_map[f"other:{w[:60]}"] = pattern_map.get(f"other:{w[:60]}", 0) + 1
            pattern_rules[f"other:{w[:60]}"] = w[:80]

    # ── Step 2: 빈도 순 정렬 → 상위 3개만 추출 ──
    sorted_patterns = sorted(pattern_map.items(), key=lambda x: x[1], reverse=True)
    top_3_keys = [k for k, _ in sorted_patterns[:3]]

    if not top_3_keys:
        return ""

    # ── Step 3: 정확히 3줄의 금지 규칙 생성 ──
    rules: list[str] = []
    for key in top_3_keys:
        rules.append(f"🚫 {pattern_rules[key]}")

    # 3줄 미만이면 suggestions에서 보충
    for s in suggestions:
        if len(rules) >= 3:
            break
        rules.append(f"🚫 {s[:80]}")

    # 정확히 3줄로 패딩 (부족 시 기본 규칙 추가)
    defaults = [
        "🚫 뻔한 결론 금지 — 독자가 이미 아는 내용을 반복하지 말 것",
        "🚫 감정적 과장 금지 — 팩트 기반 서술만 허용",
        "🚫 불필요한 배경 설명 금지 — 핵심만 간결하게",
    ]
    while len(rules) < 3:
        rules.append(defaults[len(rules) % len(defaults)])

    return (
        "\n## 품질 개선 가이드라인 (새 리포트 작성 시 적용할 규칙 — 기존 리포트 수정 요청 아님)\n"
        "아래 규칙은 과거 반복된 품질 문제를 방지하기 위한 가이드입니다. "
        "지금 제공된 기사들을 바탕으로 완전히 새로운 브리프를 작성하세요.\n"
        + "\n".join(rules[:3])
        + "\n"
    )


def _build_semantic_overlap_block(past_drafts: list[str]) -> str:
    """Build a differentiation directive from past draft texts.

    When semantic overlap is detected, this block instructs the LLM to
    find a genuinely new angle instead of repeating known conclusions.
    """
    if not past_drafts:
        return ""
    lines = ["\n## Differentiation Required (content overlap detected)"]
    lines.append("The following drafts were recently published for this category.")
    lines.append("You MUST NOT repeat the same framing, conclusions, or key phrases.")
    lines.append("Instead, find a NEW angle, different ripple effects, or a contrarian take.\n")
    for i, draft in enumerate(past_drafts[:3], 1):
        preview = draft[:250].replace("\n", " ").strip()
        lines.append(f"Previously published #{i}: {preview}")
    return "\n".join(lines) + "\n"


def build_report_prompt(
    *,
    category: str,
    items: list[ContentItem],
    window_name: str,
    quality_feedback: dict | None = None,
    overlapping_drafts: list[str] | None = None,
) -> tuple[str, str, str]:
    contract = get_category_contract(category)
    mode = resolve_prompt_mode(window_name, len(items))
    audiences = ", ".join(contract["audiences"])
    x_length = str(contract["x_length"])
    tone = str(contract["tone"])
    article_lines = "\n".join(
        f"### [A{i}] [{item.source_name}] {item.title}\n{item.summary}\nLink: {item.link}\n"
        for i, item in enumerate(items[:12], 1)
    )
    user_prompt = (
        f"Category: {category}\n"
        f"Time window: {window_name}\n"
        f"Reader contract: {audiences}\n\n"
        f"Articles:\n{article_lines}\n"
    )
    # Inject quality feedback and semantic overlap directives
    user_prompt += _build_quality_feedback_block(quality_feedback or {})
    user_prompt += _build_semantic_overlap_block(overlapping_drafts or [])
    if mode == "v1-brief":
        system_prompt = f"""
CRITICAL: This is a FRESH, STANDALONE request. You have NO previous conversation history with the user.
Do NOT say "죄송합니다", "이전 대화 없음", or ask for clarification.
Generate the brief DIRECTLY using ONLY the articles provided in the user message.

You are a newsroom editor writing a compact Korean briefing for {audiences}.

Write the actual output in Korean.
Your job is to produce a short editor note that is fast to scan on mobile, not a long-form essay.

Output sections in this exact order:
Summary
Insights
Brief
Draft

Rules:
- Summary must contain exactly 3 bullet lines.
- Each summary line must be one short sentence with concrete nouns, timing, and actors when available.
- Insights must contain exactly 2 bullet lines.
- Each insight line should explain why the story matters in plain language using no more than 2 short sentences.
- Brief must be the main reader-facing briefing body in Korean.
- Start Brief with: "오늘의 핫 이슈: {category}. ..." as a one-line opener.
- Then write 3 to 5 short sections using markdown headings like "## [emoji] short title".
- Each section should naturally flow as fact -> background -> implication across 2 to 3 short paragraphs.
- Do not write explicit labels such as "핵심 사실:", "배경/디테일:", or "전망/의미:".
- Use exactly one emoji per section heading.
- Keep the tone crisp and editorial, like a sharp morning briefing note.
- Draft must be one short X/Threads-ready post in 3 to 5 short lines, roughly 180 to 260 characters total.
- For Draft: Use natural line breaks, engaging hooks, and a professional yet conversational tone suitable for social media distribution.
- No spammy hashtags, no hook formulas, no rhetorical padding, no bold headings.
- Do not output separate sections like Signal, Pattern, Ripple Effects, Counterpoint, or Action Items.
- Use only the article set. If evidence is thin, say so briefly instead of filling space.
""".strip()
        user_prompt += (
            "Return a short briefing only.\n"
            "Format example:\n"
            "Summary\n"
            "- ...\n"
            "- ...\n"
            "- ...\n"
            "Insights\n"
            "- ...\n"
            "- ...\n"
            "Brief\n"
            "오늘의 핫 이슈: Category. ...\n"
            "## 📌 short title\n"
            "첫 문단은 사실 요약.\n"
            "둘째 문단은 배경 설명.\n"
            "셋째 문단은 의미나 전망.\n"
            "Draft\n"
            "...\n"
        )
    elif mode == "v2-multi":
        user_prompt += (
            "Use only the article set unless a statement is explicitly marked [Background]. "
            "If evidence is insufficient, say so directly instead of inventing support.\n\n"
            "Evidence tag contract:\n"
            "- End each analytic line in Signal / Pattern / Ripple Effects / Counterpoint / Action Items with exactly one tag.\n"
            "- Allowed tags: [A1], [A2], [Inference:A1+A2], [Background], [Insufficient evidence]\n"
            "- Prefer direct article tags like [A1] when possible.\n"
            "- Use [Inference:A1+A2] only for synthesis across multiple articles.\n"
            "- Draft Post must not include evidence tags.\n"
        )
        system_prompt = f"""
CRITICAL: This is a FRESH, STANDALONE request. You have NO previous conversation history with the user.
Do NOT say "죄송합니다", "이전 대화 없음", or ask for clarification.
Generate the brief DIRECTLY using ONLY the articles provided in the user message.

You are a senior intelligence analyst writing for {audiences}.

Your job is NOT to summarize headlines.
Your job is to identify the 3 most important signals and explain what the reader should do next.

Tone: {tone}
X draft length target: {x_length}

Output sections in this exact order:
### Signal
### Pattern
### Ripple Effects
### Counterpoint
### Action Items
### Draft Post

Rules:
- Pattern and Ripple must be grounded in the attached article set.
- Do not introduce new companies, dates, valuations, or benchmark numbers unless tagged [Background].
- Action items must name one audience from this set only: {audiences}
- No more than 2 audience types in the final output.
- Every analytic bullet or sentence in Signal / Pattern / Ripple Effects / Counterpoint / Action Items must end with exactly one evidence tag.
- Draft Post must be clean reader-facing prose designed for X/Threads and Naver Blog.
- For Draft Post: Use engaging hooks, natural spacing, and conversational tone to drive organic inbound traffic. Avoid evidence tags here.
""".strip()
    else:
        user_prompt += (
            "Use only the article set unless a statement is explicitly marked [Background]. "
            "If evidence is insufficient, say so directly instead of inventing support.\n\n"
            "Evidence tag contract:\n"
            "- End each analytic line in Signal / Pattern / Ripple Effects / Counterpoint / Action Items with exactly one tag.\n"
            "- Allowed tags: [A1], [A2], [Inference:A1+A2], [Background], [Insufficient evidence]\n"
            "- Prefer direct article tags like [A1] when possible.\n"
            "- Use [Inference:A1+A2] only for synthesis across multiple articles.\n"
            "- Draft Post must not include evidence tags.\n"
        )
        system_prompt = f"""
You are a senior intelligence analyst writing for {audiences}.

Your job is NOT to summarize what happened.
Your job is to surface one dominant signal, connect it to a broader pattern, and tell the reader what to do next.

Tone: {tone}
X draft length target: {x_length}

Output sections in this exact order:
### Signal
### Pattern
### Ripple Effects
### Counterpoint
### Action Items
### Draft Post

Rules:
- Every non-obvious claim must be grounded in the article set or tagged [Background].
- Counterpoint must directly challenge the Signal section; filler caveats are not acceptable.
- Action items must include an explicit timeframe and concrete target.
- No more than 2 audience types in the final output.
- Every analytic bullet or sentence in Signal / Pattern / Ripple Effects / Counterpoint / Action Items must end with exactly one evidence tag.
- Draft Post must be clean reader-facing prose designed for X/Threads and Naver Blog.
- For Draft Post: Use engaging hooks, natural spacing, and conversational tone to drive organic inbound traffic. Avoid evidence tags here.
""".strip()
    return mode, system_prompt, user_prompt


__all__ = [
    "build_report_prompt",
    "get_category_contract",
    "resolve_brief_style",
    "resolve_prompt_mode",
    "PROMPT_VERSION",
    "_build_quality_feedback_block",
    "_build_semantic_overlap_block",
]

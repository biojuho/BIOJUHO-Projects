from __future__ import annotations

import os
from typing import TYPE_CHECKING

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
    },
    "tech": {
        "audiences": ["Founder/PM", "Developer/Engineer"],
        "x_length": "700-1000 characters",
        "tone": "sharp, builder-oriented, decision-useful",
    },
    "default": {
        "audiences": ["Operator", "Investor"],
        "x_length": "600-900 characters",
        "tone": "concise, non-generic, execution-oriented",
    },
}


def get_category_contract(category: str) -> dict[str, str | list[str]]:
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


def build_report_prompt(*, category: str, items: list[ContentItem], window_name: str) -> tuple[str, str, str]:
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
    if mode == "v1-brief":
        system_prompt = f"""
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
- Draft must be one short X-ready post in 3 to 5 short lines, roughly 180 to 260 characters total.
- No hashtags, no emojis, no hook formulas, no rhetorical padding, no bold headings.
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
- Draft Post must be clean reader-facing prose with no evidence tags.
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
- Draft Post must be clean reader-facing prose with no evidence tags.
""".strip()
    return mode, system_prompt, user_prompt

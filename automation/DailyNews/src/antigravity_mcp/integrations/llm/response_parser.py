from __future__ import annotations

import logging
import re
from typing import Any

from antigravity_mcp.domain.models import ChannelDraft, ContentItem, GeneratedPayload
from antigravity_mcp.integrations.llm.draft_generators import DraftGenerator
from antigravity_mcp.integrations.llm_prompts import resolve_prompt_mode

logger = logging.getLogger(__name__)

# P0: Meta-response detection patterns
_META_RESPONSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"죄송(하지만|합니다|해요)", re.I),
    re.compile(r"이전\s*(대화|리포트|기록|내용).*(없|없음|확인\s*불가)", re.I),
    re.compile(r"(기록|대화\s*이력|이력).*(남아있지|없|없습니다)", re.I),
    re.compile(r"(다음\s*중\s*하나|어느\s*쪽).*(원하시|알려주시면)", re.I),
    re.compile(r"(붙여넣어|공유해|알려주시면)\s*(주시면|주면)\s*(즉시|바로|처리)", re.I),
    re.compile(r"^(I'm sorry|I don't have|I cannot|As an AI)", re.I | re.MULTILINE),
)

_MIN_CONTENT_LINES = 3

def is_meta_response(text: str, *, check_line_count: bool = True) -> bool:
    for pattern in _META_RESPONSE_PATTERNS:
        if pattern.search(text):
            return True
    if not check_line_count:
        return False
    content_lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    return len(content_lines) < _MIN_CONTENT_LINES


_SECTION_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "signal": (re.compile(r"^(top\s+)?signal\b"),),
    "pattern": (re.compile(r"^pattern\b"),),
    "ripple": (re.compile(r"^ripple(\s+effects?)?\b"),),
    "counterpoint": (re.compile(r"^counterpoint\b"),),
    "action": (re.compile(r"^action(\s+items?)?\b"),),
    "draft": (re.compile(r"^(draft(\s+post)?)\b"),),
}

_EVIDENCE_TAG_RE = re.compile(r"\[(?:A\d+|Inference:[A\d+\s]+|Background|Insufficient evidence)\]")
_ARTICLE_TAG_RE = re.compile(r"\[A\d+\]")
_INFERENCE_TAG_RE = re.compile(r"\[Inference:[^\]]+\]")
_BACKGROUND_TAG_RE = re.compile(r"\[Background\]")


def has_evidence_tag(text: str) -> bool:
    return bool(_EVIDENCE_TAG_RE.search(text))


def collect_evidence_stats(lines: list[str]) -> dict[str, Any]:
    tagged_lines = [line for line in lines if has_evidence_tag(line)]
    missing_lines = [line for line in lines if line.strip() and not has_evidence_tag(line)]
    article_refs = sorted(set(_ARTICLE_TAG_RE.findall("\n".join(lines))))
    inference_refs = _INFERENCE_TAG_RE.findall("\n".join(lines))
    background_refs = _BACKGROUND_TAG_RE.findall("\n".join(lines))
    return {
        "line_count": len(lines),
        "tagged_line_count": len(tagged_lines),
        "missing_line_count": len(missing_lines),
        "missing_lines_preview": missing_lines[:5],
        "article_ref_count": len(article_refs),
        "article_refs": article_refs,
        "inference_count": len(inference_refs),
        "background_line_count": len(background_refs),
    }


class ResponseParser:
    """Parses LLM outputs into structured domain models."""

    def __init__(self, draft_generator: DraftGenerator) -> None:
        self.draft_gen = draft_generator

    def parse_response(
        self,
        *,
        category: str,
        text: str,
        items: list[ContentItem],
        window_name: str,
        generation_mode: str,
    ) -> tuple[GeneratedPayload, list[str]]:
        if generation_mode.startswith("v2"):
            payload, warnings = self._parse_v2_response(
                category=category,
                text=text,
                items=items,
                window_name=window_name,
                generation_mode=generation_mode,
            )
            if payload.parse_meta.get("used_fallback") and self._looks_like_v1_response(text):
                return self._parse_v1_response(
                    category=category,
                    text=text,
                    items=items,
                    window_name=window_name,
                    generation_mode=generation_mode,
                )
            return payload, warnings
        return self._parse_v1_response(
            category=category,
            text=text,
            items=items,
            window_name=window_name,
            generation_mode=generation_mode,
        )

    def _looks_like_v1_response(self, text: str) -> bool:
        lowered_lines = {line.strip().lower().rstrip(":") for line in text.splitlines() if line.strip()}
        return {"summary", "insights", "draft"}.issubset(lowered_lines)

    def _normalize_header(self, line: str) -> str:
        header = line.strip()
        header = re.sub(r"^[#>\-\s]+", "", header)
        header = header.replace("📌", "").replace("🔗", "").replace("🌊", "")
        header = header.replace("⚡", "").replace("✅", "").replace("📰", "")
        header = header.replace("**", "").replace("__", "")
        header = re.sub(r"\s+", " ", header)
        return header.strip().lower()

    def _detect_section(self, line: str) -> str | None:
        header_line = self._normalize_header(line)
        for section_name, patterns in _SECTION_PATTERNS.items():
            if any(pattern.match(header_line) for pattern in patterns):
                return section_name
        return None

    def _parse_v1_response(
        self,
        *,
        category: str,
        text: str,
        items: list[ContentItem],
        window_name: str,
        generation_mode: str,
    ) -> tuple[GeneratedPayload, list[str]]:
        summary_lines: list[str] = []
        insights: list[str] = []
        brief_lines: list[str] = []
        draft_lines: list[str] = []
        warnings: list[str] = []
        current = "summary"
        insight_limit = 2 if generation_mode == "v1-brief" else 3

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower().rstrip(":")
            if lowered == "summary":
                current = "summary"
                continue
            if lowered == "insights":
                current = "insights"
                continue
            if lowered == "brief":
                current = "brief"
                continue
            if lowered == "draft":
                current = "draft"
                continue
            if current == "summary":
                clean = line.removeprefix("- ").strip()
                summary_lines.append(clean)
            elif current == "insights":
                clean = line.removeprefix("- ").strip()
                insights.append(clean)
            elif current == "brief":
                brief_lines.append(line)
            else:
                draft_lines.append(line)

        if not summary_lines or not insights:
            warnings.append(f"parse_fallback:{category}:{window_name}")
            return self.draft_gen.fallback_report(
                category=category,
                items=items,
                window_name=window_name,
                generation_mode=generation_mode,
                reason="v1_parse_failure",
            ), warnings

        # P0: 파서 레벨 메타응답 감지 — 섹션 안에 거절 응답이 들어온 경우
        parsed_text = " ".join(summary_lines + insights)
        if is_meta_response(parsed_text, check_line_count=False):
            warnings.append(f"meta_response_in_sections:{category}:{window_name}")
            logger.warning("Meta-response detected inside parsed sections for %s/%s", category, window_name)
            return self.draft_gen.fallback_report(
                category=category,
                items=items,
                window_name=window_name,
                generation_mode=generation_mode,
                reason="meta_response_in_sections",
            ), warnings

        x_fallback = not draft_lines
        brief_body = "\n".join(brief_lines).strip()
        payload = GeneratedPayload(
            summary_lines=summary_lines[:3],
            insights=insights[:insight_limit],
            channel_drafts=[
                ChannelDraft(
                    channel="x",
                    status="draft",
                    content="\n".join(draft_lines)
                    if draft_lines
                    else self.draft_gen.build_x_draft(category, summary_lines, items),
                    source="fallback" if x_fallback else "llm",
                    is_fallback=x_fallback,
                ),
                ChannelDraft(
                    channel="canva",
                    status="draft",
                    content=self.draft_gen.build_canva_draft(category, items),
                    source="fallback",
                    is_fallback=True,
                ),
            ],
            generation_mode=generation_mode,
            parse_meta={
                "used_fallback": False,
                "format": "v1",
                "missing_sections": ["draft"] if x_fallback else [],
                "sections_found": {
                    "summary": len(summary_lines),
                    "insights": len(insights),
                    "brief": len(brief_lines),
                    "draft": len(draft_lines),
                },
                "brief_body": brief_body,
            },
            quality_state="fallback" if x_fallback else "ok",
        )
        if x_fallback:
            warnings.append(f"draft_fallback:{category}:{window_name}")
        return payload, warnings

    def _parse_v2_response(
        self,
        *,
        category: str,
        text: str,
        items: list[ContentItem],
        window_name: str,
        generation_mode: str | None = None,
    ) -> tuple[GeneratedPayload, list[str]] | tuple[list[str], list[str], list[ChannelDraft]]:
        legacy_mode = generation_mode is None
        generation_mode = generation_mode or resolve_prompt_mode(window_name, len(items))
        sections: dict[str, list[str]] = {
            "signal": [],
            "pattern": [],
            "ripple": [],
            "counterpoint": [],
            "action": [],
            "draft": [],
        }
        current = "signal"
        warnings: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            detected = self._detect_section(line)
            if detected is not None:
                current = detected
                continue
            clean = re.sub(r"^[-*\d\.\)\s]+", "", line).strip()
            if clean:
                sections[current].append(clean)

        summary_lines = sections["signal"][:3]
        insights = (sections["pattern"] + sections["ripple"] + sections["counterpoint"] + sections["action"])[:10]
        draft_lines = sections["draft"]
        missing_sections = [
            name for name in ("signal", "pattern", "ripple", "counterpoint", "action") if not sections[name]
        ]
        sections_found = {key: len(value) for key, value in sections.items() if value}

        if not summary_lines or not insights:
            warnings.append(f"parse_fallback:{category}:{window_name}")
            payload = self.draft_gen.fallback_report(
                category=category,
                items=items,
                window_name=window_name,
                generation_mode=generation_mode,
                reason="v2_parse_failure",
                missing_sections=missing_sections,
                sections_found=sections_found,
            )
            if legacy_mode:
                return payload.summary_lines, payload.insights, payload.channel_drafts
            return payload, warnings

        # P0: 파서 레벨 메타응답 감지 (v2)
        parsed_text_v2 = " ".join(summary_lines + insights)
        if is_meta_response(parsed_text_v2, check_line_count=False):
            warnings.append(f"meta_response_in_sections:{category}:{window_name}")
            logger.warning("Meta-response detected inside v2 parsed sections for %s/%s", category, window_name)
            payload = self.draft_gen.fallback_report(
                category=category,
                items=items,
                window_name=window_name,
                generation_mode=generation_mode,
                reason="meta_response_in_sections",
            )
            if legacy_mode:
                return payload.summary_lines, payload.insights, payload.channel_drafts
            return payload, warnings

        x_fallback = not draft_lines
        payload = GeneratedPayload(
            summary_lines=summary_lines,
            insights=insights,
            channel_drafts=[
                ChannelDraft(
                    channel="x",
                    status="draft",
                    content="\n".join(draft_lines)
                    if draft_lines
                    else self.draft_gen.build_x_draft(category, summary_lines, items),
                    source="fallback" if x_fallback else "llm",
                    is_fallback=x_fallback,
                ),
                ChannelDraft(
                    channel="canva",
                    status="draft",
                    content=self.draft_gen.build_canva_draft(category, items),
                    source="fallback",
                    is_fallback=True,
                ),
            ],
            generation_mode=generation_mode,
            parse_meta={
                "used_fallback": False,
                "format": "v2",
                "missing_sections": missing_sections,
                "sections_found": sections_found,
                "evidence": collect_evidence_stats(summary_lines + insights),
            },
            quality_state="fallback" if x_fallback else "ok",
        )
        if x_fallback:
            warnings.append(f"draft_fallback:{category}:{window_name}")
        if legacy_mode:
            return payload.summary_lines, payload.insights, payload.channel_drafts
        return payload, warnings

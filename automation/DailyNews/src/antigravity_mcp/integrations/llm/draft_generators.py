from __future__ import annotations

from collections import Counter
from typing import Any

from antigravity_mcp.domain.models import ChannelDraft, ContentItem, GeneratedPayload


class DraftGenerator:
    """Generates fallback reports and social media platform drafts."""

    def fallback_report(
        self,
        *,
        category: str,
        items: list[ContentItem],
        window_name: str,
        generation_mode: str,
        reason: str,
        missing_sections: list[str] | None = None,
        sections_found: dict[str, int] | None = None,
    ) -> GeneratedPayload:
        top_titles = [item.title for item in items[:3]]
        source_counts = Counter(item.source_name for item in items)
        summary_lines = [
            f"{category} {window_name} brief covers {len(items)} curated items.",
            f"Top signals: {'; '.join(top_titles) if top_titles else 'No titles available.'}",
            f"Most active sources: {', '.join(f'{source} ({count})' for source, count in source_counts.most_common(3))}.",
        ]
        insights = [
            f"{category} coverage is clustering around {items[0].title}."
            if items
            else f"{category} coverage is limited.",
            f"Operators should review {min(len(items), 3)} candidate stories before publishing.",
            "External distribution remains manual until approval is granted.",
        ]
        return GeneratedPayload(
            summary_lines=summary_lines,
            insights=insights,
            channel_drafts=[
                ChannelDraft(
                    channel="x",
                    status="draft",
                    content=self.build_x_draft(category, summary_lines, items),
                    source="fallback",
                    is_fallback=True,
                ),
                ChannelDraft(
                    channel="canva",
                    status="draft",
                    content=self.build_canva_draft(category, items),
                    source="fallback",
                    is_fallback=True,
                ),
            ],
            generation_mode=generation_mode,
            parse_meta={
                "used_fallback": True,
                "format": "fallback",
                "reason": reason,
                "missing_sections": missing_sections or [],
                "sections_found": sections_found or {},
            },
            quality_state="fallback",
        )

    def build_canva_draft(self, category: str, items: list[ContentItem]) -> str:
        lead = items[0].title if items else category
        return (
            f"Create a square hero card for {category} with the lead headline '{lead}' "
            "and highlight the top three briefing points. "
            "If a NotebookLM infographic is available, use it as the primary visual asset."
        )

    def build_x_draft(self, category: str, summary_lines: list[str], items: list[ContentItem]) -> str:
        lead = items[0].title if items else f"{category} update"
        second_line = summary_lines[1] if len(summary_lines) > 1 else "Editorial review pending."
        return (
            f"{category} brief\n\n"
            f"{lead}\n"
            f"- {summary_lines[0]}\n"
            f"- {second_line}\n\n"
            "Draft only. Manual approval required before publishing."
        )

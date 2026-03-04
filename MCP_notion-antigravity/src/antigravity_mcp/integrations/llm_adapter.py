from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ChannelDraft, ContentItem

# shared.llm 모듈
_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_ROOT))
from shared.llm import TaskTier, get_client as _get_llm_client


class LLMAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()
        try:
            self._llm_client = _get_llm_client()
        except Exception:
            self._llm_client = None

    async def build_report_payload(
        self,
        *,
        category: str,
        items: list[ContentItem],
        window_name: str,
    ) -> tuple[tuple[list[str], list[str], list[ChannelDraft]], list[str]]:
        warnings: list[str] = []
        if not items:
            return ([], [], []), ["No content items were available."]
        if self._llm_client is None:
            warnings.append("LLM unavailable; using deterministic fallback summary.")
            return self._fallback_report(category=category, items=items, window_name=window_name), warnings

        prompt = self._build_prompt(category=category, items=items, window_name=window_name)
        try:
            response = await self._llm_client.acreate(
                tier=TaskTier.MEDIUM,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.text or ""
            return self._parse_response(category=category, text=text, items=items, window_name=window_name), warnings
        except Exception as exc:
            warnings.append(f"LLM failed ({type(exc).__name__}); using fallback summary.")
            return self._fallback_report(category=category, items=items, window_name=window_name), warnings

    def _build_prompt(self, *, category: str, items: list[ContentItem], window_name: str) -> str:
        article_lines = "\n".join(
            f"- {item.title} | {item.summary[:280]} | {item.link}"
            for item in items[:8]
        )
        return (
            "You are preparing a concise content briefing for an internal newsroom.\n"
            "Return plain text with sections titled Summary, Insights, and Draft.\n"
            "Each summary line should be a single sentence. Each insight should be concrete.\n"
            f"Category: {category}\n"
            f"Window: {window_name}\n"
            f"Articles:\n{article_lines}"
        )

    def _parse_response(
        self,
        *,
        category: str,
        text: str,
        items: list[ContentItem],
        window_name: str,
    ) -> tuple[list[str], list[str], list[ChannelDraft]]:
        summary_lines: list[str] = []
        insights: list[str] = []
        draft_lines: list[str] = []
        current = "summary"
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
            if lowered == "draft":
                current = "draft"
                continue
            line = line.removeprefix("- ").strip()
            if current == "summary":
                summary_lines.append(line)
            elif current == "insights":
                insights.append(line)
            else:
                draft_lines.append(line)
        if not summary_lines or not insights:
            return self._fallback_report(category=category, items=items, window_name=window_name)
        drafts = [
            ChannelDraft(
                channel="x",
                status="draft",
                content="\n".join(draft_lines) if draft_lines else self._build_x_draft(category, summary_lines, items),
            )
        ]
        return summary_lines[:3], insights[:3], drafts

    def _fallback_report(
        self,
        *,
        category: str,
        items: list[ContentItem],
        window_name: str,
    ) -> tuple[list[str], list[str], list[ChannelDraft]]:
        top_titles = [item.title for item in items[:3]]
        source_counts = Counter(item.source_name for item in items)
        summary_lines = [
            f"{category} {window_name} brief covers {len(items)} curated items.",
            f"Top signals: {'; '.join(top_titles) if top_titles else 'No titles available.'}",
            f"Most active sources: {', '.join(f'{source} ({count})' for source, count in source_counts.most_common(3))}.",
        ]
        insights = [
            f"{category} coverage is clustering around {items[0].title}." if items else f"{category} coverage is limited.",
            f"Operators should review {min(len(items), 3)} candidate stories before publishing.",
            "External distribution remains manual until approval is granted.",
        ]
        drafts = [
            ChannelDraft(
                channel="x",
                status="draft",
                content=self._build_x_draft(category, summary_lines, items),
            ),
            ChannelDraft(
                channel="canva",
                status="draft",
                content=f"Create a hero card for {category} using the lead headline '{items[0].title if items else category}'.",
            ),
        ]
        return summary_lines, insights, drafts

    def _build_x_draft(self, category: str, summary_lines: list[str], items: list[ContentItem]) -> str:
        lead = items[0].title if items else f"{category} update"
        return (
            f"{category} brief\n\n"
            f"{lead}\n"
            f"- {summary_lines[0]}\n"
            f"- {summary_lines[1] if len(summary_lines) > 1 else 'Editorial review pending.'}\n\n"
            "Draft only. Manual approval required before publishing."
        )

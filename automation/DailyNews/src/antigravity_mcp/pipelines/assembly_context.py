from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from antigravity_mcp.domain.models import ChannelDraft, ContentItem
from antigravity_mcp.integrations.llm_prompts import resolve_brief_style
from antigravity_mcp.state.store import PipelineStateStore

def _is_concise_brief() -> bool:
    return resolve_brief_style() == "concise"


def _normalize_brief_body(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for prefix in ("핵심 사실:", "배경/디테일:", "전망/의미:"):
            if line.startswith(prefix):
                line = line[len(prefix) :].strip()
                break
        lines.append(line)
    return "\n".join(lines).strip()


@dataclass(slots=True)
class ReportAssemblyContext:
    category: str
    items: list[ContentItem]
    window_name: str
    window_start: str
    window_end: str
    state_store: PipelineStateStore
    report_id: str
    generation_mode: str
    fingerprint: str
    source_links: list[str]
    enriched_items: list[ContentItem]
    summary_lines: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    channel_drafts: list[ChannelDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notebooklm_metadata: dict[str, Any] = field(default_factory=dict)
    fact_check_score: float = 0.0
    quality_state: str = "ok"
    detail_level: str = "standard"  # "minimal" | "standard" | "full" — from TokenBudget
    analysis_meta: dict[str, Any] = field(default_factory=dict)
    _llm_adapter: Any = field(default=None, repr=False)  # Auto-heal용 LLM 참조


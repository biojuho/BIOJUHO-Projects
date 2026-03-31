from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class PageSummary:
    id: str
    title: str
    url: str
    last_edited_time: str = ""
    object_type: str = "page"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ContentItem:
    source_name: str
    category: str
    title: str
    link: str
    published_at: str = ""
    summary: str = ""
    full_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChannelDraft:
    channel: str
    status: str
    content: str
    external_url: str = ""
    source: str = "llm"
    is_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GeneratedPayload:
    summary_lines: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    channel_drafts: list[ChannelDraft] = field(default_factory=list)
    generation_mode: str = ""
    parse_meta: dict[str, Any] = field(default_factory=dict)
    quality_state: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["channel_drafts"] = [draft.to_dict() for draft in self.channel_drafts]
        return data

    def as_legacy_tuple(self) -> tuple[list[str], list[str], list[ChannelDraft]]:
        return self.summary_lines, self.insights, self.channel_drafts

    def __iter__(self):
        return iter(self.as_legacy_tuple())

    def __getitem__(self, index: int):
        return self.as_legacy_tuple()[index]


@dataclass(slots=True)
class ContentReport:
    report_id: str
    category: str
    window_name: str
    window_start: str
    window_end: str
    summary_lines: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    channel_drafts: list[ChannelDraft] = field(default_factory=list)
    notion_page_id: str = ""
    asset_status: str = "draft"
    approval_state: str = "manual"
    source_links: list[str] = field(default_factory=list)
    status: str = "draft"
    fingerprint: str = ""
    created_at: str = ""
    updated_at: str = ""
    notebooklm_metadata: dict[str, Any] = field(default_factory=dict)
    fact_check_score: float = 0.0
    generation_mode: str = ""
    quality_state: str = "ok"
    analysis_meta: dict[str, Any] = field(default_factory=dict)

    def has_notion_sync(self) -> bool:
        return bool(str(self.notion_page_id or "").strip())

    @property
    def delivery_state(self) -> str:
        """Expose an explicit operational label without breaking stored status values."""
        if self.has_notion_sync():
            return "notion_synced"
        raw_status = str(self.status or "draft").strip()
        return raw_status or "draft"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["channel_drafts"] = [draft.to_dict() for draft in self.channel_drafts]
        return data


@dataclass(slots=True)
class PipelineRun:
    run_id: str
    job_name: str
    status: str
    started_at: str
    finished_at: str = ""
    processed_count: int = 0
    published_count: int = 0
    error_text: str = ""
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FactFragment:
    """Inductive reasoning Step 1: extracted fact fragment with 'why?' question."""

    fact_id: str
    report_id: str
    fact_text: str
    why_question: str
    category: str
    source_title: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Hypothesis:
    """Inductive reasoning Step 2/3: hypothesis with falsification status."""

    hypothesis_id: str
    hypothesis_text: str
    based_on_facts: list[str] = field(default_factory=list)
    related_pattern: str = ""
    status: str = "pending"  # pending → survived → falsified
    counter_evidence: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DigestEntry:
    """Digest queue entry — summarises multiple reports into one digest."""

    digest_id: str
    report_ids: list[str] = field(default_factory=list)
    summary_text: str = ""
    serial_number: str = ""  # "0001_260327"
    status: str = "pending"  # pending → generated → pinned
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChannelDraft:
    channel: str
    status: str
    content: str
    external_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

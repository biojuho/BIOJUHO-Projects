"""
BioLinker data models.

The project uses these shared Pydantic models across routers, services, and
tests so request and response shapes stay consistent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class FitGrade(str, Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class RFPDocument(BaseModel):
    """Structured representation of a funding notice."""

    id: str | None = None
    title: str = Field(..., description="Notice title")
    source: str = Field(..., description="Notice source, such as KDDF or NTIS")
    deadline: datetime | None = Field(None, description="Notice deadline")
    budget_range: str | None = Field(None, description="Funding range")
    min_trl: int | None = Field(None, description="Minimum TRL")
    max_trl: int | None = Field(None, description="Maximum TRL")
    body_text: str = Field(..., description="Full notice body")
    keywords: list[str] = Field(default_factory=list, description="Extracted keywords")
    eligibility: list[str] = Field(default_factory=list, description="Eligibility requirements")
    required_docs: list[str] = Field(default_factory=list, description="Required submission documents")
    url: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class UserProfile(BaseModel):
    """Technology profile used during RFP analysis."""

    company_name: str = Field(..., description="Company name")
    tech_keywords: list[str] = Field(..., description="Technology keywords")
    tech_description: str = Field(..., description="Technology summary")
    company_size: str | None = Field(None, description="Company size")
    established_year: int | None = Field(None, description="Established year")
    current_trl: str | None = Field(None, description="Current technology readiness level")


class AnalysisResult(BaseModel):
    """RFP fit analysis result."""

    fit_score: int = Field(..., ge=0, le=100, description="Fit score from 0 to 100")
    fit_grade: FitGrade = Field(..., description="Fit grade")
    match_summary: list[str] = Field(..., description="Primary reasons for the match")
    required_docs: list[str] = Field(default_factory=list, description="Required documents")
    risk_flags: list[str] = Field(default_factory=list, description="Risk flags")
    recommended_actions: list[str] = Field(default_factory=list, description="Recommended actions")
    analyzed_at: datetime = Field(default_factory=datetime.now)


class AnalyzeRequest(BaseModel):
    """Analyze a notice against a technology profile."""

    rfp_text: str = Field(..., description="Raw notice text")
    rfp_url: str | None = Field(None, description="Source URL")
    user_profile: UserProfile


class AnalyzeResponse(BaseModel):
    """Structured analyze response payload."""

    rfp: RFPDocument
    result: AnalysisResult


class Paper(BaseModel):
    """Uploaded research paper metadata."""

    id: str = Field(..., description="Paper identifier")
    title: str = Field(..., description="Paper title")
    abstract: str | None = Field(None, description="Paper abstract")
    cid: str = Field(..., description="IPFS CID")
    ipfs_url: str = Field(..., description="IPFS gateway URL")
    uploaded_at: datetime = Field(default_factory=datetime.now)
    reward_claimed: bool = Field(False, description="Whether the reward has been claimed")


class VCFirm(BaseModel):
    """VC firm profile used for investor matching."""

    id: str = Field(..., description="VC identifier")
    name: str = Field(..., description="Firm name")
    country: str = Field("KR", description="Country code")
    website: str | None = Field(None, description="Website URL")
    investment_thesis: str = Field(..., description="Investment thesis")
    preferred_stages: list[str] = Field(default_factory=list, description="Preferred stages")
    portfolio_keywords: list[str] = Field(default_factory=list, description="Portfolio keywords")
    contact_email: str | None = Field(None, description="Contact email")


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobType(str, Enum):
    NOTICE_COLLECTION = "notice_collection"
    PAPER_INDEX = "paper_index"
    PAPER_MATCH = "paper_match"
    PROPOSAL_GENERATION = "proposal_generation"


class JobEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: JobStatus
    progress: int = Field(..., ge=0, le=100)
    message: str = Field(..., min_length=1)


class JobSnapshot(BaseModel):
    id: str
    type: JobType
    status: JobStatus
    progress: int = Field(..., ge=0, le=100)
    message: str = Field(..., min_length=1)
    storage: Literal["memory", "redis"] = "memory"
    partial: bool = Field(True, description="False when this snapshot is a terminal stream frame.")
    result: Any | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    events: list[JobEvent] = Field(default_factory=list)


class JobAcceptedResponse(BaseModel):
    job: JobSnapshot


class PaperIndexJobRequest(BaseModel):
    paper_id: str = Field(..., min_length=1)


class PaperMatchJobRequest(BaseModel):
    paper_id: str = Field(..., min_length=1)
    limit: int = Field(5, ge=1, le=20)
    target_trl: int | None = Field(None, ge=0, le=9)
    enrich: bool = False


class ProposalGenerationJobRequest(BaseModel):
    paper_id: str = Field(..., min_length=1)
    rfp_id: str = Field(..., min_length=1)

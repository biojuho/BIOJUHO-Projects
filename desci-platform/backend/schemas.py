from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator

SENSITIVE_TERMS = [
    "patient", "subject", "ssn", "passport", "resident id", "주민등록", "환자"
]


def check_sensitive(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return value
    lowered = value.lower()
    if any(term in lowered for term in SENSITIVE_TERMS):
        raise ValueError(
            f"{field_name} contains sensitive personal data. Remove identifiers before saving."
        )
    return value


class ProgramBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    regulatory_context: Optional[str] = None
    status: str = "active"

    _check_description = validator("description", allow_reuse=True)(
        lambda v: check_sensitive(v, "description")
    )
    _check_reg_context = validator("regulatory_context", allow_reuse=True)(
        lambda v: check_sensitive(v, "regulatory_context")
    )


class ProgramCreate(ProgramBase):
    pass


class ProgramRead(ProgramBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class WorkstreamBase(BaseModel):
    name: str
    type: str
    status: str = "active"


class WorkstreamCreate(WorkstreamBase):
    pass


class WorkstreamRead(WorkstreamBase):
    id: int
    program_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    regulatory_basis: str
    status: str = "todo"
    assignee_agent: Optional[str] = None

    _check_description = validator("description", allow_reuse=True)(
        lambda v: check_sensitive(v, "description")
    )
    _check_regulatory_basis = validator("regulatory_basis", allow_reuse=True)(
        lambda v: check_sensitive(v, "regulatory_basis")
    )


class TaskCreate(TaskBase):
    pass


class TaskRead(TaskBase):
    id: int
    workstream_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class DeliverableBase(BaseModel):
    title: str
    content: Optional[str] = None
    version: str = "v0.1"
    status: str = "draft"

    _check_content = validator("content", allow_reuse=True)(
        lambda v: check_sensitive(v, "content")
    )


class DeliverableCreate(DeliverableBase):
    pass


class DeliverableRead(DeliverableBase):
    id: int
    task_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class ApprovalCreate(BaseModel):
    status: str
    reviewer: str
    notes: Optional[str] = None

    _check_notes = validator("notes", allow_reuse=True)(
        lambda v: check_sensitive(v, "notes")
    )


class ApprovalRead(ApprovalCreate):
    id: int
    deliverable_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class AuditLogRead(BaseModel):
    id: int
    actor_type: str
    actor_name: str
    action: str
    resource_type: str
    resource_id: Optional[int]
    rationale: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class OrchestrationRequest(BaseModel):
    request_text: str


class AgentResponseSchema(BaseModel):
    agent: str
    summary: str
    assumptions: List[str]
    evidence_refs: List[str]
    risks: List[str]
    open_questions: List[str]
    next_actions: List[str]


class DecisionRecordSchema(BaseModel):
    context: str
    decision: str
    rationale: str
    alternatives_considered: str
    consequences: str
    owner: str
    date: str


class OrchestrationResponse(BaseModel):
    run_id: int
    summary: str
    agent_responses: List[AgentResponseSchema]
    decision_record: DecisionRecordSchema

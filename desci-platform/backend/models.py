from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship
from database import Base


class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    regulatory_context = Column(Text, nullable=True)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workstreams = relationship("Workstream", back_populates="program", cascade="all, delete")


class Workstream(Base):
    __tablename__ = "workstreams"

    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    name = Column(String(200), nullable=False)
    type = Column(String(100), nullable=False)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    program = relationship("Program", back_populates="workstreams")
    tasks = relationship("Task", back_populates="workstream", cascade="all, delete")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    workstream_id = Column(Integer, ForeignKey("workstreams.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    regulatory_basis = Column(Text, nullable=False)
    status = Column(String(50), default="todo", nullable=False)
    assignee_agent = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workstream = relationship("Workstream", back_populates="tasks")
    deliverables = relationship("Deliverable", back_populates="task", cascade="all, delete")


class Deliverable(Base):
    __tablename__ = "deliverables"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    version = Column(String(20), default="v0.1", nullable=False)
    status = Column(String(30), default="draft", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="deliverables")
    approvals = relationship("Approval", back_populates="deliverable", cascade="all, delete")


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, index=True)
    deliverable_id = Column(Integer, ForeignKey("deliverables.id"), nullable=False)
    status = Column(String(30), nullable=False)
    reviewer = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    deliverable = relationship("Deliverable", back_populates="approvals")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_type = Column(String(50), nullable=False)
    actor_name = Column(String(200), nullable=False)
    action = Column(String(200), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(Integer, nullable=True)
    rationale = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OrchestrationRun(Base):
    __tablename__ = "orchestration_runs"

    id = Column(Integer, primary_key=True, index=True)
    request_text = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    agent_responses = relationship("AgentResponse", back_populates="orchestration", cascade="all, delete")
    decision_record = relationship("DecisionRecord", back_populates="orchestration", uselist=False, cascade="all, delete")


class AgentResponse(Base):
    __tablename__ = "agent_responses"

    id = Column(Integer, primary_key=True, index=True)
    orchestration_id = Column(Integer, ForeignKey("orchestration_runs.id"), nullable=False)
    agent = Column(String(100), nullable=False)
    summary = Column(Text, nullable=False)
    assumptions = Column(JSON, nullable=False)
    evidence_refs = Column(JSON, nullable=False)
    risks = Column(JSON, nullable=False)
    open_questions = Column(JSON, nullable=False)
    next_actions = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    orchestration = relationship("OrchestrationRun", back_populates="agent_responses")


class DecisionRecord(Base):
    __tablename__ = "decision_records"

    id = Column(Integer, primary_key=True, index=True)
    orchestration_id = Column(Integer, ForeignKey("orchestration_runs.id"), nullable=False)
    context = Column(Text, nullable=False)
    decision = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    alternatives_considered = Column(Text, nullable=True)
    consequences = Column(Text, nullable=True)
    owner = Column(String(200), nullable=False)
    date = Column(String(30), nullable=False)

    orchestration = relationship("OrchestrationRun", back_populates="decision_record")

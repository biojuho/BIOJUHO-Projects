from sqlalchemy.orm import Session
from models import Program, Workstream, Task, Deliverable, Approval, AuditLog
from schemas import ProgramCreate, WorkstreamCreate, TaskCreate, DeliverableCreate, ApprovalCreate


def create_program(db: Session, data: ProgramCreate) -> Program:
    program = Program(**data.dict())
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


def list_programs(db: Session):
    return db.query(Program).all()


def create_workstream(db: Session, program_id: int, data: WorkstreamCreate) -> Workstream:
    workstream = Workstream(program_id=program_id, **data.dict())
    db.add(workstream)
    db.commit()
    db.refresh(workstream)
    return workstream


def list_workstreams(db: Session, program_id: int):
    return db.query(Workstream).filter(Workstream.program_id == program_id).all()


def create_task(db: Session, workstream_id: int, data: TaskCreate) -> Task:
    task = Task(workstream_id=workstream_id, **data.dict())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, workstream_id: int):
    return db.query(Task).filter(Task.workstream_id == workstream_id).all()


def create_deliverable(db: Session, task_id: int, data: DeliverableCreate) -> Deliverable:
    deliverable = Deliverable(task_id=task_id, **data.dict())
    db.add(deliverable)
    db.commit()
    db.refresh(deliverable)
    return deliverable


def create_approval(db: Session, deliverable_id: int, data: ApprovalCreate) -> Approval:
    approval = Approval(deliverable_id=deliverable_id, **data.dict())
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


def list_audit_logs(db: Session):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).all()


def create_audit_log(
    db: Session,
    actor_type: str,
    actor_name: str,
    action: str,
    resource_type: str,
    resource_id: int | None,
    rationale: str | None = None,
):
    log = AuditLog(
        actor_type=actor_type,
        actor_name=actor_name,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        rationale=rationale,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

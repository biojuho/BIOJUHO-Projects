from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
import crud
import schemas

router = APIRouter(prefix="/tasks", tags=["deliverables"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{task_id}/deliverables", response_model=schemas.DeliverableRead)
def create_deliverable(
    task_id: int, payload: schemas.DeliverableCreate, db: Session = Depends(get_db)
):
    deliverable = crud.create_deliverable(db, task_id, payload)
    crud.create_audit_log(
        db,
        actor_type="user",
        actor_name="pm",
        action="create_deliverable",
        resource_type="deliverable",
        resource_id=deliverable.id,
        rationale="산출물 버전 등록",
    )
    return deliverable


@router.post(
    "/{task_id}/deliverables/{deliverable_id}/approvals",
    response_model=schemas.ApprovalRead,
)
def create_approval(
    task_id: int,
    deliverable_id: int,
    payload: schemas.ApprovalCreate,
    db: Session = Depends(get_db),
):
    approval = crud.create_approval(db, deliverable_id, payload)
    crud.create_audit_log(
        db,
        actor_type="user",
        actor_name="reviewer",
        action="create_approval",
        resource_type="approval",
        resource_id=approval.id,
        rationale="산출물 승인 흐름 기록",
    )
    return approval

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
import crud
import schemas

router = APIRouter(prefix="/workstreams", tags=["tasks"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{workstream_id}/tasks", response_model=schemas.TaskRead)
def create_task(
    workstream_id: int, payload: schemas.TaskCreate, db: Session = Depends(get_db)
):
    task = crud.create_task(db, workstream_id, payload)
    crud.create_audit_log(
        db,
        actor_type="user",
        actor_name="pm",
        action="create_task",
        resource_type="task",
        resource_id=task.id,
        rationale="규제 근거 기반 태스크 생성",
    )
    return task


@router.get("/{workstream_id}/tasks", response_model=list[schemas.TaskRead])
def list_tasks(workstream_id: int, db: Session = Depends(get_db)):
    return crud.list_tasks(db, workstream_id)

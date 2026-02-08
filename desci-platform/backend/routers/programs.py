from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
import crud
import schemas

router = APIRouter(prefix="/programs", tags=["programs"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=schemas.ProgramRead)
def create_program(payload: schemas.ProgramCreate, db: Session = Depends(get_db)):
    program = crud.create_program(db, payload)
    crud.create_audit_log(
        db,
        actor_type="user",
        actor_name="pm",
        action="create_program",
        resource_type="program",
        resource_id=program.id,
        rationale="프로그램 신규 등록",
    )
    return program


@router.get("", response_model=list[schemas.ProgramRead])
def list_programs(db: Session = Depends(get_db)):
    return crud.list_programs(db)


@router.post("/{program_id}/workstreams", response_model=schemas.WorkstreamRead)
def create_workstream(
    program_id: int, payload: schemas.WorkstreamCreate, db: Session = Depends(get_db)
):
    workstream = crud.create_workstream(db, program_id, payload)
    crud.create_audit_log(
        db,
        actor_type="user",
        actor_name="pm",
        action="create_workstream",
        resource_type="workstream",
        resource_id=workstream.id,
        rationale="워크스트림 신규 등록",
    )
    return workstream


@router.get("/{program_id}/workstreams", response_model=list[schemas.WorkstreamRead])
def list_workstreams(program_id: int, db: Session = Depends(get_db)):
    return crud.list_workstreams(db, program_id)

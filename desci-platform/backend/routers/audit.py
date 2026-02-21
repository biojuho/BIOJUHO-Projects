from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
import crud
import schemas

router = APIRouter(prefix="/audit-logs", tags=["audit"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=list[schemas.AuditLogRead])
def list_audit_logs(db: Session = Depends(get_db)):
    return crud.list_audit_logs(db)

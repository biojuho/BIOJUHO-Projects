# ruff: noqa: B008  # FastAPI's Depends() in defaults is the canonical injection pattern
import uuid
from datetime import UTC, datetime

import models
import schemas
from auth import get_current_user
from dependencies import get_db
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/users/", response_model=schemas.User)
def create_user(
    user: schemas.UserCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    db_user = models.User(
        id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        role=user.role,
        name=user.name,
        organization=user.organization,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

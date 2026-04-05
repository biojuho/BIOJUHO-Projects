from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from dependencies import get_db
import models
import schemas
import uuid
import json
from datetime import UTC, datetime, timedelta
from auth import get_current_user
from services.chain_simulator import get_chain



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

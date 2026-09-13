from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from decimal import Decimal

from ...db import get_db
from ...models.models import RoomCredit

router = APIRouter()


class RoomCreditCreate(BaseModel):
    room_number: str
    enabled: bool = True
    credit_limit: float = 0  # topall (0 = sense límit)


class RoomCreditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    room_number: str
    enabled: bool
    credit_limit: float
    current_balance: float


@router.get("", response_model=List[RoomCreditOut])
def list_room_credits(db: Session = Depends(get_db)):
    """Llista els límits de crèdit per habitació."""
    return db.query(RoomCredit).order_by(RoomCredit.room_number).all()


@router.post("", response_model=RoomCreditOut, status_code=status.HTTP_201_CREATED)
def upsert_room_credit(payload: RoomCreditCreate, db: Session = Depends(get_db)):
    """Crea o actualitza el límit de crèdit d'una habitació (idempotent)."""
    rc = (
        db.query(RoomCredit)
        .filter(RoomCredit.room_number == payload.room_number)
        .first()
    )
    if rc:
        rc.enabled = payload.enabled
        rc.credit_limit = Decimal(str(payload.credit_limit))
    else:
        rc = RoomCredit(
            room_number=payload.room_number,
            enabled=payload.enabled,
            credit_limit=Decimal(str(payload.credit_limit)),
            current_balance=Decimal("0"),
        )
        db.add(rc)
    db.commit()
    db.refresh(rc)
    return rc

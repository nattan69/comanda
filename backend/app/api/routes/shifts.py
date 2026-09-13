from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ...db import get_db
from ...models.models import Shift
from ...schemas.schemas import ShiftOpen, ShiftClose, ShiftOut
from ...services.shift_service import open_shift, preview_shift, close_shift

router = APIRouter()


@router.post("/open", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
def login_shift(payload: ShiftOpen, db: Session = Depends(get_db)):
    """Login del cambrer dins un centre: obre un torn nou."""
    try:
        return open_shift(db, payload.staff_id, payload.center_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{shift_id}/x")
def shift_x_report(shift_id: UUID, db: Session = Depends(get_db)):
    """Informe X personal: què duu fet el cambrer al torn (sense tancar)."""
    try:
        return preview_shift(db, shift_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{shift_id}/close", response_model=ShiftOut)
def logout_shift(shift_id: UUID, payload: ShiftClose, db: Session = Depends(get_db)):
    """Logout: tanca el torn i calcula la liquidació personal."""
    try:
        return close_shift(db, shift_id, payload.cash_declared)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[ShiftOut])
def list_shifts(db: Session = Depends(get_db)):
    """Llista els torns (més recents primer)."""
    return db.query(Shift).order_by(Shift.opened_at.desc()).all()

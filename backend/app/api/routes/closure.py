"""
Router del tancament del dia del TPV.

- `POST /closure/run`  — executa (idempotent) el tancament per a una data.
- `GET  /closure`      — llista els tancaments.
- `GET  /closure/{id}` — detall d'un tancament.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import date

from ...db import get_db
from ...models.models import DayClosure
from ...schemas.schemas import DayClosureOut, DayClosureRunRequest
from ...services.closure_service import run_day_closure

router = APIRouter()


@router.post("/run", response_model=DayClosureOut)
def run_closure(payload: DayClosureRunRequest, db: Session = Depends(get_db)):
    """Executa (idempotent) el tancament del dia i el retorna."""
    closure_date = payload.closure_date or date.today()
    return run_day_closure(db, closure_date)


@router.get("", response_model=List[DayClosureOut])
def list_closures(db: Session = Depends(get_db)):
    """Llista els tancaments (del més recent al més antic)."""
    return (
        db.query(DayClosure)
        .order_by(DayClosure.closure_date.desc())
        .all()
    )


@router.get("/{closure_id}", response_model=DayClosureOut)
def get_closure(closure_id: UUID, db: Session = Depends(get_db)):
    """Detall d'un tancament."""
    closure = db.get(DayClosure, closure_id)
    if not closure:
        raise HTTPException(status_code=404, detail="Tancament no trobat")
    return closure

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
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


@router.get("/panell")
def panell_cambrers(center_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    """PANELL DE CAMBRERS (decisió Tomeu 14/09/2026).

    Retorna els cambrers LOGUEATS (torn obert) al centre indicat, amb:
      · el seu torn i centre
      · quantes taules té obertes
      · el SALDO PENDENT de cobrar de les seves taules
    És el frame que va a dalt del cos: qui està de servei i quant es deu.
    """
    from ...models.models import Order, Table, Staff, Center

    torns = db.query(Shift).filter(Shift.status == "open")
    if center_id:
        torns = torns.filter(Shift.center_id == center_id)
    torns = torns.all()

    # comandes obertes indexades per cambrer
    obertes = (
        db.query(Order)
        .filter(Order.status.notin_(["paid", "cancelled", "closed"]))
        .all()
    )
    per_staff: dict = {}
    for o in obertes:
        if not o.staff_id:
            continue
        per_staff.setdefault(o.staff_id, {"comandes": [], "taules": set()})
        per_staff[o.staff_id]["comandes"].append(Decimal(str(o.total_amount or 0)))
        if o.table_id:
            per_staff[o.staff_id]["taules"].add(o.table_id)

    resultat = []
    for torn in torns:
        staff = db.get(Staff, torn.staff_id)
        centre = db.get(Center, torn.center_id) if torn.center_id else None
        info = per_staff.get(torn.staff_id, {"comandes": [], "taules": set()})
        resultat.append({
            "shift_id": str(torn.id),
            "staff_id": str(torn.staff_id),
            "staff_name": staff.full_name if staff else "—",
            "center_id": str(torn.center_id) if torn.center_id else None,
            "center_name": centre.name if centre else None,
            "opened_at": str(torn.opened_at) if torn.opened_at else None,
            "taules_obertes": len(info["taules"]),
            "comandes_obertes": len(info["comandes"]),
            "saldo_pendent": float(sum(info["comandes"], Decimal("0"))),
        })
    return resultat

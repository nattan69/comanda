from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from uuid import UUID

from ...db import get_db
from ...models.models import Shift, Center
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
        return close_shift(
            db, shift_id,
            payload.cash_declared,
            payload.errors,
            payload.observations,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/obert")
def el_meu_torn(staff_id: UUID, db: Session = Depends(get_db)):
    """El torn obert d'un cambrer (o null).

    L'usa la Comandera per saber a quin torn i centre està abans de carregar el
    pla de sala, i la derivació del torn de les comandes noves.
    """
    from ...services.shift_service import torn_obert_de

    shift = torn_obert_de(db, staff_id)
    if not shift:
        return None
    centre = db.get(Center, shift.center_id) if shift.center_id else None
    return {
        "id": str(shift.id),
        "staff_id": str(shift.staff_id),
        "center_id": str(shift.center_id) if shift.center_id else None,
        "center_name": centre.name if centre else None,
        "status": shift.status,
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else None,
    }


@router.get("", response_model=List[ShiftOut])
def list_shifts(db: Session = Depends(get_db)):
    """Llista els torns (més recents primer)."""
    return db.query(Shift).order_by(Shift.opened_at.desc()).all()


# ============================================================
# DOCUMENTS IMPRIMIBLES DE LA LIQUIDACIÓ (decisió Tomeu 18/09/2026)
# ============================================================
# Són DOS documents SEPARATS, per imprimir-los i signar-los, per ficar dins el
# sobre amb els doblers i els justificants (nuls, invitacions, crèdits...).
# `?format=text` (per veure'l o imprimir pel navegador) o `escpos` (impressora
# tèrmica, bytes crus).

@router.get("/{shift_id}/liquidacio")
def liquidacio_cambrer(shift_id: UUID, format: str = "text", db: Session = Depends(get_db)):
    """FULL DE LIQUIDACIÓ DEL CAMBRER — el que firma i va dins el sobre."""
    from ...services.liquidacio_service import (
        build_liquidacio_cambrer, render_liquidacio_cambrer_text, render_escpos,
    )

    try:
        doc = build_liquidacio_cambrer(db, shift_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    text = render_liquidacio_cambrer_text(doc)
    if format == "escpos":
        return Response(content=render_escpos(text), media_type="application/octet-stream")
    return PlainTextResponse(text)


@router.get("/{shift_id}/moviments")
def full_moviments_cambrer(shift_id: UUID, format: str = "text", db: Session = Depends(get_db)):
    """FULL DE MOVIMENTS DEL TORN — els justificants línia a línia."""
    from ...services.liquidacio_service import (
        build_full_moviments_cambrer, render_full_moviments_cambrer_text, render_escpos,
    )

    try:
        doc = build_full_moviments_cambrer(db, shift_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    text = render_full_moviments_cambrer_text(doc)
    if format == "escpos":
        return Response(content=render_escpos(text), media_type="application/octet-stream")
    return PlainTextResponse(text)


@router.get("/liquidacio/centre")
def liquidacio_centre(
    data: Optional[str] = None,
    format: str = "text",
    db: Session = Depends(get_db),
):
    """FULL DE LIQUIDACIÓ DELS CAMBRERS DEL CENTRE — per a l'ENCARREGAT.

    És el paper que repassa i firma amb la Z. `data` en format ISO (per defecte
    avui).
    """
    from datetime import date as _date

    from ...services.liquidacio_service import (
        build_liquidacio_centre, render_liquidacio_centre_text, render_escpos,
    )

    try:
        dia = _date.fromisoformat(data) if data else _date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Data invàlida (format ISO: AAAA-MM-DD)")

    doc = build_liquidacio_centre(db, dia)
    text = render_liquidacio_centre_text(doc)
    if format == "escpos":
        return Response(content=render_escpos(text), media_type="application/octet-stream")
    return PlainTextResponse(text)


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

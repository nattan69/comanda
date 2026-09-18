"""
Router del tancament del dia del TPV.

- `POST /closure/run`  — executa (idempotent) el tancament per a una data.
- `GET  /closure`      — llista els tancaments.
- `GET  /closure/{id}` — detall d'un tancament.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import date

from ...db import get_db
from ...models.models import DayClosure
from ...schemas.schemas import DayClosureOut, DayClosureRunRequest
from ...services.closure_service import run_day_closure, preview_day_closure

router = APIRouter()


@router.post("/x")
def preview_closure(payload: Optional[DayClosureRunRequest] = None, db: Session = Depends(get_db)):
    """Informe X (pre-tancament): lectura del dia, sense tancar res.

    Es pot emetre tantes vegades com calgui. NO tanca comandes ni crea cap
    tancament definitiu. El body és opcional (per defecte: avui).
    """
    closure_date = (payload.closure_date if payload else None) or date.today()
    return preview_day_closure(db, closure_date)


@router.post("/run", response_model=DayClosureOut)
def run_closure(payload: Optional[DayClosureRunRequest] = None, db: Session = Depends(get_db)):
    """Executa (idempotent) el tancament del dia (la Z) i el retorna.

    El body és opcional (per defecte: avui).
    """
    closure_date = (payload.closure_date if payload else None) or date.today()
    return run_day_closure(db, closure_date)


@router.get("", response_model=List[DayClosureOut])
def list_closures(db: Session = Depends(get_db)):
    """Llista els tancaments (del més recent al més antic)."""
    return (
        db.query(DayClosure)
        .order_by(DayClosure.closure_date.desc())
        .all()
    )


# ============================================================
# IMPRESSIÓ DE LA Z (impressora tèrmica de tiquets — decisió 18/09/2026)
# ============================================================
# La Z s'imprimeix a la MATEIXA tèrmica de 80 mm que els tiquets. L'endpoint
# torna els bytes crus ESC/POS (per enviar-los a la impressora) o el text pla
# (per veure'l o imprimir-lo pel navegador si no hi ha tèrmica).
#
# La Z inclou la LIQUIDACIÓ DE TOTS ELS CAMBRERS perquè l'encarregat la
# repassi i la firmi abans d'arxivar-la.

@router.get("/{closure_date}/x-ticket")
def x_ticket(
    closure_date: date,
    format: str = "text",
    db: Session = Depends(get_db),
):
    """TIQUET DE LA X (80 mm) amb la liquidació dels cambrers inclosa.

    La X NO tanca res: es pot treure tantes vegades com calgui. Serveix perquè
    l'encarregat repassi les liquidacions dels cambrers ABANS de fer la Z.
    """
    from ...services.liquidacio_service import render_x_text, render_escpos
    from ...services.closure_service import preview_day_closure

    previa = preview_day_closure(db, closure_date)
    text = render_x_text(closure_date, previa.get("summary") or {})
    if format == "escpos":
        return Response(content=render_escpos(text), media_type="application/octet-stream")
    return PlainTextResponse(text)


@router.get("/{closure_date}/z-ticket")
def z_ticket(
    closure_date: date,
    format: str = "text",
    db: Session = Depends(get_db),
):
    """TIQUET DE LA Z (80 mm) amb la liquidació dels cambrers inclosa.

    Si la Z d'aquella data encara no existeix, es calcula la prèvia (X) i
    s'imprimeix igualment — així l'encarregat la pot repassar ABANS de tancar.
    """
    from ...services.liquidacio_service import render_z_text, render_escpos
    from ...services.closure_service import preview_day_closure

    closure = (
        db.query(DayClosure)
        .filter(DayClosure.closure_date == closure_date)
        .first()
    )
    font = closure if closure is not None else preview_day_closure(db, closure_date)
    if closure is None:
        # La prèvia porta {report_type, closure_date, summary}: l'adaptam.
        class _Prev:
            pass
        _p = _Prev()
        _p.summary = font.get("summary") or {}
        _p.closure_date = closure_date
        font = _p

    text = render_z_text(font)
    if format == "escpos":
        return Response(content=render_escpos(text), media_type="application/octet-stream")
    return PlainTextResponse(text)


@router.get("/{closure_id}", response_model=DayClosureOut)
def get_closure(closure_id: UUID, db: Session = Depends(get_db)):
    """Detall d'un tancament."""
    closure = db.get(DayClosure, closure_id)
    if not closure:
        raise HTTPException(status_code=404, detail="Tancament no trobat")
    return closure

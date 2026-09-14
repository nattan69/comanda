from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ...db import get_db
from ...models.models import Area, Table
from ...schemas.schemas import AreaCreate, AreaOut, TableCreate, TableUpdate, TableOut

router = APIRouter()


# ============================================================
# ÁREAS
# ============================================================
@router.get("/areas", response_model=List[AreaOut])
def list_areas(center_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    """Àrees de la sala. Si s'indica `center_id`, només les d'aqueix centre.

    La DISPOSICIÓ del pla de sala és PER CENTRE/DEPARTAMENT (decisió Tomeu
    14/09/2026): cada punt de venda té les seves àrees i les seves taules.
    """
    q = db.query(Area)
    if center_id:
        q = q.filter(Area.center_id == center_id)
    arees = q.order_by(Area.name).all()
    # comptador de taules per zona (per la pantalla de gestió de zones)
    comptes = dict(
        db.query(Table.area_id, func.count(Table.id))
        .group_by(Table.area_id)
        .all()
    )
    sortida = []
    for a in arees:
        d = AreaOut.model_validate(a)
        d.table_count = int(comptes.get(a.id, 0))
        sortida.append(d)
    return sortida


@router.post("/areas", response_model=AreaOut, status_code=status.HTTP_201_CREATED)
def create_area(payload: AreaCreate, db: Session = Depends(get_db)):
    area = Area(**payload.model_dump())
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


# ============================================================
# MESAS
# ============================================================
def _amb_saldo(db: Session, taules: list) -> list:
    """Afegeix a cada taula el saldo pendent de cobrar de la seva comanda oberta.

    El pla de sala ha de reflectir el que es deu (decisió Tomeu 14/09/2026):
    així el cambrer veu d'un cop d'ull quines taules queden per cobrar i quant.
    Es calcula en una SOLA consulta agregada (no N+1).
    """
    from ...models.models import Order, OrderItem

    obertes = (
        db.query(Order)
        .filter(Order.status.notin_(["paid", "cancelled", "closed"]))
        .all()
    )
    per_taula = {}
    for o in obertes:
        if not o.table_id:
            continue
        total = Decimal(str(o.total_amount or 0))
        descompte = Decimal(str(o.discount_amount or 0))
        pagat = Decimal("0")
        # La comanda no guarda 'paid_amount' propi: ho derivam del que ja està pagat.
        # Si el pagament parcial crea files de pagament, es podria sumar aquí;
        # de moment, si l'estat és 'paid' sortiria de la llista d'obertes.
        pendent = total - descompte - pagat
        if pendent < 0:
            pendent = Decimal("0")
        per_taula[o.table_id] = {
            "order_id": o.id,
            "total": total,
            "paid": pagat,
            "pending": pendent,
        }

    resultat = []
    for t in taules:
        info = per_taula.get(t.id)
        d = TableOut.model_validate(t).model_dump()
        if info:
            d["open_order_id"] = info["order_id"]
            d["pending_amount"] = float(info["pending"])
            d["paid_amount"] = float(info["paid"])
        resultat.append(d)
    return resultat


class AreaUpdate(BaseModel):
    """Actualització parcial d'una àrea."""
    name: Optional[str] = None
    center_id: Optional[UUID] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    surcharge_percent: Optional[float] = None


@router.patch("/areas/{area_id}", response_model=AreaOut)
def update_area(area_id: UUID, payload: AreaUpdate, db: Session = Depends(get_db)):
    """Modifica una àrea (nom, CENTRE al qual pertany, posició, recàrrec).

    Serveix per ASSIGNAR una àrea a un centre/departament — imprescindible perquè
    el pla de sala és per centre (decisió Tomeu 14/09/2026).
    """
    area = db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=404, detail="Àrea no trobada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(area, k, v)
    db.commit()
    db.refresh(area)
    return area


@router.delete("/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_area(area_id: UUID, db: Session = Depends(get_db)):
    """Esborra una zona. NO deixa taules òrfenes: si en té, es rebutja.

    Per a un restaurant, esborrar una zona amb taules dins seria perdre el pla
    de sala per accident (decisió Tomeu 15/09/2026).
    """
    area = db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=404, detail="Àrea no trobada")
    n = db.query(Table).filter(Table.area_id == area_id).count()
    if n:
        raise HTTPException(
            status_code=409,
            detail=f"La zona «{area.name}» té {n} taula(es). Mou-les a una altra zona o esborra-les abans.",
        )
    db.delete(area)
    db.commit()


@router.get("", response_model=List[TableOut])
def list_tables(center_id: Optional[UUID] = None, area_id: Optional[UUID] = None,
                db: Session = Depends(get_db)):
    """Pla de sala: taules amb posició, forma, estat i SALDO PENDENT de cobrar.

    ⚠️ Es filtra PER CENTRE (decisió Tomeu 14/09/2026): cada punt de venda té
    la seva pròpia distribució de taules. Sense el filtre, tots els centres
    veien les mateixes taules i canviar de centre donava error (530).
    """
    q = db.query(Table)
    if center_id:
        q = q.filter(Table.center_id == center_id)
    if area_id:
        q = q.filter(Table.area_id == area_id)
    taules = q.order_by(Table.number).all()
    return _amb_saldo(db, taules)


@router.post("", response_model=TableOut, status_code=status.HTTP_201_CREATED)
def create_table(payload: TableCreate, db: Session = Depends(get_db)):
    table = Table(**payload.model_dump())
    db.add(table)
    db.commit()
    db.refresh(table)
    return table


@router.get("/{table_id}", response_model=TableOut)
def get_table(table_id: UUID, db: Session = Depends(get_db)):
    table = db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    return _amb_saldo(db, [table])[0]


@router.get("/{table_id}/compte")
def get_compte_de_taula(table_id: UUID, db: Session = Depends(get_db)):
    """COMPTE COMPLET d'una taula: TOTES les comandes obertes (no només una).

    Per què: quan es reparteixen línies a una altra comanda per fer TIQUETS
    SEPARATS (compartir el compte), a la taula hi ha MÉS D'UNA comanda oberta.
    L'endpoint /comanda retornava només la més recent i les altres desapareixien
    de la vista (catch 15/09/2026, reportat per Tomeu).

    Retorna: { table_id, open, total_pendent, comandes: [ {id, comanda_number,
              total, pendent, lines[], payments[]} ] }
    """
    from ...models.models import Order, OrderItem, MenuItem, Payment

    ordres = (
        db.query(Order)
        .filter(Order.table_id == table_id, Order.status.notin_(["paid", "cancelled", "closed"]))
        .order_by(Order.comanda_number, Order.created_at)
        .all()
    )
    if not ordres:
        return {"table_id": str(table_id), "open": False, "total_pendent": 0.0, "comandes": []}

    def _linies(order):
        out = []
        for it in db.query(OrderItem).filter(OrderItem.order_id == order.id).all():
            art = db.get(MenuItem, it.menu_item_id) if it.menu_item_id else None
            out.append({
                "id": str(it.id),
                "menu_item_id": str(it.menu_item_id) if it.menu_item_id else None,
                "name": it.name_snapshot or (art.name if art else "—"),
                "quantity": float(it.quantity),
                "unit_price": float(it.price_snapshot or 0),
                "amount": float((it.price_snapshot or 0) * it.quantity),
                "vat_rate": float(art.vat_rate) if art and art.vat_rate is not None else None,
                "status": it.status,
                "modifications": it.modifications or [],
                "comanda_number": it.comanda_number,
            })
        return out

    comandes = []
    total_pendent = 0.0
    for o in ordres:
        pagat = sum(float(p.amount or 0) for p in db.query(Payment).filter(Payment.order_id == o.id).all())
        pend = float(o.total_amount or 0) - pagat
        total_pendent += pend
        comandes.append({
            "id": str(o.id),
            "comanda_number": o.comanda_number,
            "status": o.status,
            "total": float(o.total_amount or 0),
            "paid_amount": pagat,
            "pending_amount": pend,
            "lines": _linies(o),
        })
    return {"table_id": str(table_id), "open": True, "total_pendent": total_pendent, "comandes": comandes}


@router.get("/{table_id}/comanda")
def get_comanda_de_taula(table_id: UUID, db: Session = Depends(get_db)):
    """Desglossament de la comanda oberta d'una taula (per al modal de fitxa).

    Retorna: capçalera (id, estat, total, pendent) + línies (article, qty, preu,
    import) + pagaments fets. És el que el modal del pla de sala mostra en fer
    DOBLE CLIC (decisió Tomeu 14/09/2026).
    """
    from ...models.models import Order, OrderItem, MenuItem, Payment

    order = (
        db.query(Order)
        .filter(Order.table_id == table_id, Order.status.notin_(["paid", "cancelled", "closed"]))
        .order_by(Order.created_at.desc())
        .first()
    )
    if not order:
        return {"table_id": str(table_id), "open": False, "lines": [], "payments": []}

    linies = []
    for it in db.query(OrderItem).filter(OrderItem.order_id == order.id).all():
        # Els camps REALS del model són name_snapshot / price_snapshot
        # (congelats en el moment de la comanda — no canvien si després es
        # modifica el preu de la carta). L'article viu només per a l'IVA.
        art = db.get(MenuItem, it.menu_item_id) if it.menu_item_id else None
        preu = Decimal(str(it.price_snapshot if it.price_snapshot is not None else (art.price if art else 0)))
        qty = int(it.quantity or 0)
        linies.append({
            "id": str(it.id),
            "menu_item_id": str(it.menu_item_id) if it.menu_item_id else None,
            "name": it.name_snapshot or (art.name if art else "Article"),
            "vat_rate": float(it.vat_rate) if it.vat_rate is not None
                        else (float(art.vat_rate) if art and art.vat_rate is not None else None),
            "quantity": qty,
            "unit_price": float(preu),
            "amount": float(preu * qty),
            "status": it.status,
            "modifications": it.modifications,
        })

    pagaments = []
    try:
        for pg in db.query(Payment).filter(Payment.order_id == order.id).all():
            pagaments.append({
                "id": str(pg.id),
                "method": pg.method,
                "amount": float(pg.amount or 0),
                "created_at": str(pg.created_at) if pg.created_at else None,
            })
    except Exception:
        pagaments = []

    total = Decimal(str(order.total_amount or 0))
    descompte = Decimal(str(order.discount_amount or 0))
    pagat = sum(Decimal(str(p["amount"])) for p in pagaments)

    return {
        "table_id": str(table_id),
        "open": True,
        "order_id": str(order.id),
        "status": order.status,
        "total_amount": float(total),
        "discount_amount": float(descompte),
        "paid_amount": float(pagat),
        "pending_amount": float(max(total - descompte - pagat, Decimal("0"))),
        "lines": linies,
        "payments": pagaments,
    }


@router.patch("/{table_id}", response_model=TableOut)
def update_table(table_id: UUID, payload: TableUpdate, db: Session = Depends(get_db)):
    table = db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(table, key, value)
    db.commit()
    db.refresh(table)
    return table


@router.delete("/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_table(table_id: UUID, db: Session = Depends(get_db)):
    table = db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    db.delete(table)
    db.commit()

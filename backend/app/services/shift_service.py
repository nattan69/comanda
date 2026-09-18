"""
Servei de torns (shift) del cambrer.

Cicle: login (obrir torn) → treball → X personal (opcional) → liquidació
personal → logout (tancar torn). Cada torn és d'UN cambrer dins UN centre.

LIQUIDACIÓ PERSONAL (decisió Tomeu 18/09/2026)
----------------------------------------------
El cambrer NO surt sense quadrar si duu moviments. El modal de logout li demana:

  · EFECTIU ENTREGAT — el que posa a caixa
  · ERRORS           — diferències que assumeix com a seves

I el sistema li dona **PER BONS** els totals que ja certifica Jornada
(targetes i crèdits a habitació), perquè no els hagi de sumar a mà. Aquests
surten al modal en lectura, amb l'etiqueta «per bons (Jornada)».

Els mètodes que NO són venda real (invitacions i nuls) queden FORA de l'efectiu
i la targeta esperats, i es llisten a part perquè la Z en pugui donar compte
(decisió Tomeu 14/09/2026).
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..models.models import Order, Payment, Shift, Void, Staff, Center

#: Mètodes que NO són «venda real» — ALINEAT amb closure_service. Nuls i
#: invitacions queden fora de l'efectiu/targeta esperats i de la venda.
NON_SALE_METHODS = {"house", "anul", "null"}

#: Estats de comanda que compten com a OBERTA (compte encara per cobrar).
OPEN_STATUSES = ("open", "sent_to_kitchen", "served", "pending_payment")


def _obertes(db: Session, shift: Shift):
    """Comandes del torn que encara no estan cobrades ni cancel·lades."""
    return (
        db.query(Order)
        .filter(
            Order.shift_id == shift.id,
            Order.status.notin_(["paid", "cancelled", "closed"]),
        )
        .all()
    )


def _shift_summary(db: Session, shift: Shift) -> dict:
    """Resum de les vendes i pagaments del torn (sense tancar res).

    L'efectiu i la targeta esperats surten NOMÉS de la venda real: invitacions
    i nuls no hi entren (es llisten a part).
    """
    orders = (
        db.query(Order)
        .filter(Order.shift_id == shift.id, Order.status == "paid")
        .all()
    )
    order_ids = [o.id for o in orders]

    payments = (
        db.query(Payment).filter(Payment.order_id.in_(order_ids)).all()
        if order_ids else []
    )

    # Comandes amb algun pagament de mètode «no venda» (invitació/nul).
    non_sale_ids = {
        p.order_id for p in payments
        if (p.method or "").strip().lower() in NON_SALE_METHODS
    }
    declarable = [o for o in orders if o.id not in non_sale_ids]
    non_sale_orders = [o for o in orders if o.id in non_sale_ids]

    total_sales = sum((Decimal(str(o.total_amount or 0)) for o in declarable), Decimal("0"))
    non_sale_total = sum((Decimal(str(o.total_amount or 0)) for o in non_sale_orders), Decimal("0"))

    payments_by_method: dict[str, str] = {}
    for p in payments:
        method = (p.method or "other").strip().lower() or "other"
        if method in NON_SALE_METHODS or p.status != "completed":
            continue
        payments_by_method[method] = str(
            Decimal(payments_by_method.get(method, "0")) + Decimal(str(p.amount or 0))
        )

    voids = db.query(Void).filter(Void.order_id.in_(order_ids)).all() if order_ids else []
    voids_total = sum((Decimal(str(v.amount or 0)) for v in voids), Decimal("0"))

    cash_expected = Decimal(payments_by_method.get("cash", "0"))
    card_total = Decimal(payments_by_method.get("card", "0"))
    room_total = Decimal(payments_by_method.get("room_charge", "0"))

    obertes = _obertes(db, shift)
    obertes_total = sum((Decimal(str(o.total_amount or 0)) for o in obertes), Decimal("0"))

    return {
        "gross_sales": str(total_sales),
        "orders_count": len(declarable),
        "payments_by_method": payments_by_method,
        "non_sale": {"total": str(non_sale_total), "orders": len(non_sale_orders)},
        "house": {"total": str(non_sale_total), "orders": len(non_sale_orders)},
        "voids": {"count": len(voids), "total": str(voids_total)},
        "cash_expected": str(cash_expected),
        "card_total": str(card_total),
        "room_charge_total": str(room_total),
        #: Totals que es donen PER BONS (els certifica Jornada): el cambrer no
        #: els ha de sumar a mà al modal de liquidació.
        "per_bons": {
            "targeta_credit": str(card_total),
            "carrec_habitacio": str(room_total),
            "total": str(card_total + room_total),
        },
        #: Taules encara obertes: el cambrer les ha de saber abans de sortir.
        "obertes": {
            "count": len(obertes),
            "total": str(obertes_total),
            "items": [
                {
                    "order_id": str(o.id),
                    "comanda_number": int(getattr(o, "comanda_number", 1) or 1),
                    "total": str(o.total_amount or 0),
                    "status": o.status,
                }
                for o in obertes
            ],
        },
    }


def open_shift(db: Session, staff_id, center_id) -> Shift:
    """Login: obre un torn per al cambrer dins el centre.

    La invariància «un sol torn obert per cambrer» la garanteix un índex únic
    parcial a la BD (`uq_shifts_open_per_staff`), no el codi. Si hi ha
    concurrència (doble clic, PDA + mòbil, reintents), el segon INSERT topa amb
    la constraint i es retorna l'error net en lloc de duplicar el torn.
    """
    shift = Shift(staff_id=staff_id, center_id=center_id, status="open")
    db.add(shift)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("El cambrer ja té un torn obert (ha de fer logout abans).")
    db.refresh(shift)
    return shift


def torn_obert_de(db: Session, staff_id) -> Shift | None:
    """El torn obert d'un cambrer (o None). L'usa la derivació del torn."""
    return (
        db.query(Shift)
        .filter(Shift.staff_id == staff_id, Shift.status == "open")
        .order_by(Shift.opened_at.desc())
        .first()
    )


def preview_shift(db: Session, shift_id) -> dict:
    """Informe X personal: què duu fet el cambrer al seu torn (sense tancar).

    Aquest és el resum que veu el cambrer al MODAL DE LIQUIDACIÓ abans de
    tancar el torn.
    """
    shift = db.get(Shift, shift_id)
    if not shift:
        raise ValueError("Torn no trobat.")
    staff = db.get(Staff, shift.staff_id)
    centre = db.get(Center, shift.center_id) if shift.center_id else None
    return {
        "report_type": "X-shift",
        "shift_id": str(shift.id),
        "staff_id": str(shift.staff_id),
        "staff_name": staff.full_name if staff else None,
        "center_id": str(shift.center_id) if shift.center_id else None,
        "center_name": centre.name if centre else None,
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else None,
        "status": shift.status,
        "summary": _shift_summary(db, shift),
    }


def close_shift(
    db: Session,
    shift_id,
    cash_declared=None,
    errors=None,
    observations=None,
) -> Shift:
    """Logout: tanca el torn i calcula la liquidació personal.

    Paràmetres de la liquidació (decisió Tomeu 18/09/2026):
      · `cash_declared` — efectiu que el cambrer ENTREGA a caixa.
      · `errors`        — import de les diferències que assumeix com a seves
                          (canvi donat malament, arrodoniments...).
      · `observations`  — nota lliure del cambrer.

    El desquadre es dona en dues xifres, que és el que de debò importa:
      · `desquadre`          = entregat − esperat  (negatiu = falta diners)
      · `desquadre_pendent`  = desquadre + errors  (0 = tot justificat)
    """
    shift = db.get(Shift, shift_id)
    if not shift:
        raise ValueError("Torn no trobat.")
    if shift.status == "closed":
        raise ValueError("El torn ja està tancat.")

    summary = _shift_summary(db, shift)

    cash_expected = Decimal(summary["cash_expected"])
    card_total = Decimal(summary["card_total"])
    cash_decl = Decimal(str(cash_declared)) if cash_declared is not None else None
    errors_dec = Decimal(str(errors)) if errors is not None else Decimal("0")

    desquadre = (cash_decl - cash_expected) if cash_decl is not None else None
    desquadre_pendent = (desquadre + errors_dec) if desquadre is not None else None

    shift.status = "closed"
    shift.closed_at = datetime.now(timezone.utc)
    shift.cash_declared = cash_decl
    shift.card_total = card_total
    shift.liquidation = {
        **summary,
        "cash_declared": str(cash_decl) if cash_decl is not None else None,
        "errors": str(errors_dec),
        "observations": (observations or "").strip() or None,
        "desquadre": str(desquadre) if desquadre is not None else None,
        "desquadre_pendent": str(desquadre_pendent) if desquadre_pendent is not None else None,
        # Compat: la clau que ja existia al resum.
        "discrepancy": str(desquadre) if desquadre is not None else None,
        "closed_at": shift.closed_at.isoformat(),
    }
    db.commit()
    db.refresh(shift)
    return shift

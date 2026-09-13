"""
Servei de torns (shift) del cambrer.

Cicle: login (obrir torn) → treball → X personal (opcional) → liquidació
personal → logout (tancar torn). Cada torn és d'UN cambrer dins UN departament.
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from ..models.models import Order, Payment, Shift, Void

NON_SALE_METHODS = {"house"}


def _shift_summary(db: Session, shift: Shift) -> dict:
    """Resum de les vendes i pagaments del torn (sense tancar res)."""
    orders = (
        db.query(Order)
        .filter(Order.shift_id == shift.id, Order.status == "paid")
        .all()
    )
    order_ids = [o.id for o in orders]

    # Pagaments del torn
    payments = []
    if order_ids:
        payments = db.query(Payment).filter(Payment.order_id.in_(order_ids)).all()

    house_ids = {p.order_id for p in payments if p.method == "house"}
    declarable = [o for o in orders if o.id not in house_ids]
    house_orders = [o for o in orders if o.id in house_ids]

    total_sales = sum((Decimal(str(o.total_amount or 0)) for o in declarable), Decimal("0"))
    house_total = sum((Decimal(str(o.total_amount or 0)) for o in house_orders), Decimal("0"))

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

    return {
        "gross_sales": str(total_sales),
        "orders_count": len(declarable),
        "payments_by_method": payments_by_method,
        "house": {"total": str(house_total), "orders": len(house_orders)},
        "voids": {"count": len(voids), "total": str(voids_total)},
        "cash_expected": str(cash_expected),
        "card_total": str(card_total),
    }


def open_shift(db: Session, staff_id, center_id) -> Shift:
    """Login: obre un torn per al cambrer dins el centre."""
    existing = (
        db.query(Shift)
        .filter(Shift.staff_id == staff_id, Shift.status == "open")
        .first()
    )
    if existing:
        raise ValueError("El cambrer ja té un torn obert (ha de fer logout abans).")
    shift = Shift(staff_id=staff_id, center_id=center_id, status="open")
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


def preview_shift(db: Session, shift_id) -> dict:
    """Informe X personal: què duu fet el cambrer al seu torn (sense tancar)."""
    shift = db.get(Shift, shift_id)
    if not shift:
        raise ValueError("Torn no trobat.")
    return {
        "report_type": "X-shift",
        "shift_id": str(shift.id),
        "staff_id": str(shift.staff_id),
        "center_id": str(shift.center_id),
        "status": shift.status,
        "summary": _shift_summary(db, shift),
    }


def close_shift(db: Session, shift_id, cash_declared=None) -> Shift:
    """Logout: tanca el torn i calcula la liquidació personal.

    `cash_declared` és l'efectiu que el cambrer declara entregar. Si no es
    passa, la liquidació és "cega" (el cambrer no ha vist la X) i el sistema
    quadra l'efectiu esperat contra el declarat.
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
    discrepancy = (cash_expected - cash_decl) if cash_decl is not None else None

    shift.status = "closed"
    shift.closed_at = datetime.now(timezone.utc)
    shift.cash_declared = cash_decl
    shift.card_total = card_total
    shift.liquidation = {
        **summary,
        "cash_declared": str(cash_decl) if cash_decl is not None else None,
        "discrepancy": str(discrepancy) if discrepancy is not None else None,
    }
    db.commit()
    db.refresh(shift)
    return shift

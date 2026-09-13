"""
Servei de tancament del dia del TPV (informe Z).

Calcula la "Z" completa del dia: vendes brutes, descomptes, pagaments per
mètode (efectiu, targeta, bizum, càrrecs a habitació), càrrecs a habitacions,
anul·lacions autoritzades per un cap, i el desglossament d'IVA.

Les INVITACIONS (`house`) NO formen part de la venda: es llisten A PART (clau
`house`), fora del total i del desglossament d'IVA, per no declarar-ne l'IVA.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from ..models.models import DayClosure, Order, OrderItem, Payment, Void
from .ticket_service import next_ticket_number

# Mètodes de pagament que són "venda real" (declarables). `house` (invitació) va a part.
NON_SALE_METHODS = {"house"}


def _day_bounds(closure_date: date) -> tuple[datetime, datetime]:
    """Principi i final (exclusiu) del dia en hora local (naive, com els camps)."""
    start = datetime.combine(closure_date, time.min)
    end = start + timedelta(days=1)
    return start, end


def run_day_closure(db: Session, closure_date: date) -> DayClosure:
    """Executa (idempotent) el tancament del dia (la Z) i el retorna."""
    existing = (
        db.query(DayClosure)
        .filter(DayClosure.closure_date == closure_date)
        .first()
    )
    if existing:
        return existing

    start, end = _day_bounds(closure_date)

    # --- Ventes del dia (comandes tancades) ---
    orders = (
        db.query(Order)
        .filter(
            Order.status == "paid",
            Order.closed_at.isnot(None),
            Order.closed_at >= start,
            Order.closed_at < end,
        )
        .all()
    )

    # Identificar les comandes d'invitació (pagades amb `house`) — NO són venda.
    house_order_ids = {
        p.order_id
        for p in db.query(Payment).filter(
            Payment.method == "house",
            Payment.status == "completed",
            Payment.paid_at >= start,
            Payment.paid_at < end,
        ).all()
    }

    declarable_orders = [o for o in orders if o.id not in house_order_ids]
    house_orders = [o for o in orders if o.id in house_order_ids]

    total_sales = sum((Decimal(str(o.total_amount or 0)) for o in declarable_orders), Decimal("0"))
    house_total = sum((Decimal(str(o.total_amount or 0)) for o in house_orders), Decimal("0"))
    discounts_total = sum((Decimal(str(o.discount_amount or 0)) for o in declarable_orders), Decimal("0"))
    orders_count = len(declarable_orders)

    orders_by_type: dict[str, int] = {}
    for o in declarable_orders:
        t = (o.order_type or "dine_in").strip() or "dine_in"
        orders_by_type[t] = orders_by_type.get(t, 0) + 1

    # --- Pagaments del dia per mètode (SENSE house, que va a part) ---
    payments = (
        db.query(Payment)
        .filter(
            Payment.status == "completed",
            Payment.paid_at.isnot(None),
            Payment.paid_at >= start,
            Payment.paid_at < end,
        )
        .all()
    )
    payments_by_method: dict[str, str] = {}
    for p in payments:
        method = (p.method or "other").strip().lower() or "other"
        if method in NON_SALE_METHODS:
            continue  # house es llista a part
        payments_by_method[method] = str(
            Decimal(payments_by_method.get(method, "0")) + Decimal(str(p.amount or 0))
        )

    # --- Càrrecs a habitacions (room charges) ---
    room_charges: dict[str, dict] = {}
    for o in declarable_orders:
        if o.room_number:
            rn = o.room_number.strip()
            entry = room_charges.setdefault(rn, {"room_number": rn, "total": Decimal("0"), "orders": 0})
            entry["total"] += Decimal(str(o.total_amount or 0))
            entry["orders"] += 1
    room_charges_list = [
        {"room_number": r["room_number"], "total": str(r["total"]), "orders": r["orders"]}
        for r in room_charges.values()
    ]
    room_charges_total = sum((Decimal(r["total"]) for r in room_charges_list), Decimal("0"))

    # --- Anul·lacions autoritzades (voids) ---
    voids = (
        db.query(Void)
        .filter(Void.authorized_at >= start, Void.authorized_at < end)
        .all()
    )
    voids_list = [
        {
            "order_id": str(v.order_id),
            "amount": str(v.amount),
            "reason": v.reason or "",
            "authorized_by_id": str(v.authorized_by_id) if v.authorized_by_id else None,
            "authorized_at": v.authorized_at.isoformat() if v.authorized_at else None,
        }
        for v in voids
    ]
    voids_total = sum((Decimal(v["amount"]) for v in voids_list), Decimal("0"))

    # --- Desglossament d'IVA per tipus (només vendes declarables) ---
    order_ids = [o.id for o in declarable_orders]
    vat_map: dict[str, Decimal] = {}
    base_map: dict[str, Decimal] = {}
    if order_ids:
        items = db.query(OrderItem).filter(OrderItem.order_id.in_(order_ids)).all()
        for it in items:
            rate = str(Decimal(str(it.vat_rate or 0)))
            base = Decimal(str(it.price_snapshot or 0)) * Decimal(str(it.quantity or 0))
            base_map[rate] = base_map.get(rate, Decimal("0")) + base
            vat_map[rate] = vat_map.get(rate, Decimal("0")) + (base * Decimal(str(it.vat_rate or 0)) / Decimal("100"))
    vat_breakdown = [
        {
            "rate": rate,
            "base": str(base_map.get(rate, Decimal("0"))),
            "tax": str(vat_map.get(rate, Decimal("0"))),
        }
        for rate in sorted(base_map.keys(), key=lambda r: Decimal(r))
    ]

    # --- Tancament forçat de comandes obertes (queden pendents de cobrament) ---
    open_orders = (
        db.query(Order)
        .filter(Order.status.in_(["open", "sent_to_kitchen", "served"]))
        .all()
    )
    pending_charges = []
    for o in open_orders:
        o.status = "pending_payment"
        o.closed_at = datetime.now()
        pending_charges.append({
            "order_id": str(o.id),
            "total": str(o.total_amount or 0),
            "ticket_code": o.ticket_code or "",
        })
    pending_total = sum((Decimal(p["total"]) for p in pending_charges), Decimal("0"))

    # Seqüència anual de la Z (independent de la dels tiquets).
    _, z_code = next_ticket_number(db, "Z")

    closure = DayClosure(
        closure_date=closure_date,
        status="completed",
        total_sales=total_sales,
        orders_count=orders_count,
        summary={
            "z_number": z_code,
            "gross_sales": str(total_sales),
            "discounts_total": str(discounts_total),
            "net_sales": str(total_sales - discounts_total),
            "payments_by_method": payments_by_method,
            "payments_total": str(sum(Decimal(v) for v in payments_by_method.values())),
            "orders_by_type": orders_by_type,
            "house": {
                "total": str(house_total),
                "orders": len(house_orders),
            },
            "room_charges": room_charges_list,
            "room_charges_total": str(room_charges_total),
            "voids": {
                "count": len(voids_list),
                "total": str(voids_total),
                "items": voids_list,
            },
            "pending_charges": {
                "count": len(pending_charges),
                "total": str(pending_total),
                "items": pending_charges,
            },
            "vat_breakdown": vat_breakdown,
        },
        external_id=f"comanda-cierre-{closure_date.isoformat()}",
        emitted_to_pms=False,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(closure)
    db.commit()
    db.refresh(closure)
    return closure

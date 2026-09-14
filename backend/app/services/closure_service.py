"""
Servei de tancament del dia del TPV (informes X i Z).

- **Informe X (pre-tancament)**: lectura del que hi ha fins al moment. Es pot
  emetre TANTES VEGADES com calgui, sense tancar res.
- **Informe Z (tancament)**: definitiu, una vegada per dia (idempotent). Tanca
  les comandes obertes forçosament i crea la fila `DayClosure`.

Tots dos comparteixen el càlcul (`_compute_summary`). La diferència: la Z tanca
les comandes obertes i persisteix; la X només les llista com a obertes.

Les INVITACIONS (`house`) NO formen part de la venda: es llisten A PART (clau
`house`), fora del total i del desglossament d'IVA, per no declarar-ne l'IVA.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from ..models.models import DayClosure, Order, OrderItem, Payment, Void
from .ticket_service import next_ticket_number
from .pms_adapter import get_pms_adapter
from .comanda_client import envia_cierre_a_compta

# Mètodes que NO són "venda real" (no es declaren, queden fora del total i de
# l'IVA): les INVITACIONS (`house`) i els NULS (`anul`). Tots dos es llisten
# A PART perquè la Z en pugui donar compte sense contaminar la venda.
NON_SALE_METHODS = {"house", "anul", "null"}
OPEN_STATUSES = ["open", "sent_to_kitchen", "served"]


def _day_bounds(closure_date: date) -> tuple[datetime, datetime]:
    """Principi i final (exclusiu) del dia en hora local (naive, com els camps)."""
    start = datetime.combine(closure_date, time.min)
    end = start + timedelta(days=1)
    return start, end


def _compute_summary(db: Session, closure_date: date, close_open: bool) -> dict:
    """Calcula el resum del dia. Si `close_open`, tanca les comandes obertes."""
    start, end = _day_bounds(closure_date)

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

    house_order_ids = {
        p.order_id
        for p in db.query(Payment).filter(
            Payment.method.in_(list(NON_SALE_METHODS)),
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
            continue
        payments_by_method[method] = str(
            Decimal(payments_by_method.get(method, "0")) + Decimal(str(p.amount or 0))
        )

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
            "ticket_code": v.ticket_code or "",
            "authorized_at": v.authorized_at.isoformat() if v.authorized_at else None,
        }
        for v in voids
    ]
    voids_total = sum((Decimal(v["amount"]) for v in voids_list), Decimal("0"))

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

    summary: dict = {
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
        "vat_breakdown": vat_breakdown,
    }

    # Comandes obertes: la X les llista, la Z les tanca forçosament.
    open_orders = (
        db.query(Order).filter(Order.status.in_(OPEN_STATUSES)).all()
    )
    if close_open:
        pending_charges = []
        for o in open_orders:
            o.status = "pending_payment"
            o.closed_at = datetime.now()
            pending_charges.append({
                "order_id": str(o.id),
                "total": str(o.total_amount or 0),
                "ticket_code": o.ticket_code or "",
            })
        summary["pending_charges"] = {
            "count": len(pending_charges),
            "total": str(sum((Decimal(p["total"]) for p in pending_charges), Decimal("0"))),
            "items": pending_charges,
        }
    else:
        summary["open_orders"] = {
            "count": len(open_orders),
            "items": [
                {
                    "order_id": str(o.id),
                    "total": str(o.total_amount or 0),
                    "status": o.status,
                    "ticket_code": o.ticket_code or "",
                }
                for o in open_orders
            ],
        }

    return summary


def preview_day_closure(db: Session, closure_date: date) -> dict:
    """Informe X (pre-tancament): lectura del dia, sense tancar res.

    Es pot emetre tantes vegades com calgui. NO tanca comandes ni crea
    `DayClosure`; les comandes obertes surten llistades a `open_orders`.
    """
    summary = _compute_summary(db, closure_date, close_open=False)
    return {"report_type": "X", "closure_date": closure_date.isoformat(), "summary": summary}


def run_day_closure(db: Session, closure_date: date) -> DayClosure:
    """Informe Z (tancament): definitiu i idempotent (una Z per dia)."""
    existing = (
        db.query(DayClosure)
        .filter(DayClosure.closure_date == closure_date)
        .first()
    )
    if existing:
        return existing

    summary = _compute_summary(db, closure_date, close_open=True)

    # Seqüència anual de la Z (independent de la dels tiquets).
    _, z_code = next_ticket_number(db, "Z")

    closure = DayClosure(
        closure_date=closure_date,
        status="completed",
        total_sales=Decimal(summary["gross_sales"]),
        orders_count=summary["orders_by_type"] and sum(summary["orders_by_type"].values()) or 0,
        summary={"z_number": z_code, **summary},
        external_id=f"comanda-cierre-{closure_date.isoformat()}",
        emitted_to_pms=False,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(closure)
    db.flush()

    # Volcat cap al PMS (Estada): el Night Audit quadra la caixa del bar/restaurant.
    # Si el PMS no respon, la Z es tanca igualment i el volcat es pot reintentar.
    adapter = get_pms_adapter()
    if adapter:
        try:
            pms_result = adapter.post_day_closure(
                external_id=closure.external_id,
                closure_date=closure_date,
                summary=closure.summary,
            )
        except Exception as exc:  # no volem que el tancament falli pel volcat
            pms_result = {"success": False, "error": "pms_exception", "message": str(exc)}
        closure.pms_response = pms_result
        if pms_result.get("success"):
            closure.emitted_to_pms = True
            closure.emitted_at = datetime.now(timezone.utc)

    # Volcat cap a Compta (assentament de CONTROL del tancament de caixa).
    try:
        compta_result = envia_cierre_a_compta(
            external_id=closure.external_id,
            date_str=closure_date.isoformat(),
            concept=f"Tancament de caixa TPV {closure_date.isoformat()}",
            summary=closure.summary,
        )
    except Exception as exc:  # el tancament no falla pel volcat comptable
        compta_result = {"ok": False, "error": str(exc)}
    closure.compta_response = compta_result
    if compta_result.get("ok"):
        closure.emitted_to_compta = True

    db.commit()
    db.refresh(closure)
    return closure

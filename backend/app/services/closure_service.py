"""
Servei de tancament del dia del TPV.

Calcula les ventes del dia (comandes tancades) i els pagaments per mètode
(efectiu, targeta, bizum...), i ho registra en una fila `DayClosure` idempotent
per data de negoci. És el volcat diari que Estada (PMS) consumirà per al
quadrament de caixa del seu night audit.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from ..models.models import DayClosure, Order, Payment


def _day_bounds(closure_date: date) -> tuple[datetime, datetime]:
    """Principi i final (exclusiu) del dia en hora local (naive, com els camps)."""
    start = datetime.combine(closure_date, time.min)
    end = start + timedelta(days=1)
    return start, end


def run_day_closure(db: Session, closure_date: date) -> DayClosure:
    """Executa (idempotent) el tancament del dia i el retorna.

    - Ventes = comandes `paid` tancades el dia (suma de `total_amount`).
    - Pagaments per mètode = `Payment` `completed` amb `paid_at` el dia.
    """
    # Idempotència: una fila per data de negoci.
    existing = (
        db.query(DayClosure)
        .filter(DayClosure.closure_date == closure_date)
        .first()
    )
    if existing:
        return existing

    start, end = _day_bounds(closure_date)

    # Ventes del dia (comandes tancades).
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
    total_sales = sum((Decimal(str(o.total_amount or 0)) for o in orders), Decimal("0"))
    orders_count = len(orders)

    orders_by_type: dict[str, int] = {}
    for o in orders:
        t = (o.order_type or "dine_in").strip() or "dine_in"
        orders_by_type[t] = orders_by_type.get(t, 0) + 1

    # Pagaments del dia, agrupats per mètode.
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
        payments_by_method[method] = str(
            Decimal(payments_by_method.get(method, "0")) + Decimal(str(p.amount or 0))
        )

    closure = DayClosure(
        closure_date=closure_date,
        status="completed",
        total_sales=total_sales,
        orders_count=orders_count,
        summary={
            "payments_by_method": payments_by_method,
            "payments_total": str(
                sum(Decimal(v) for v in payments_by_method.values())
            ),
            "orders_by_type": orders_by_type,
        },
        external_id=f"comanda-cierre-{closure_date.isoformat()}",
        emitted_to_pms=False,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(closure)
    db.commit()
    db.refresh(closure)
    return closure

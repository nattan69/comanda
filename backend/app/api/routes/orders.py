from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from ...db import get_db
from ...models.models import Order, OrderItem, MenuItem, Void
from ...schemas.schemas import OrderCreate, OrderOut, OrderItemCreate, OrderItemOut, VoidCreate, VoidOut
from ...services.ticket_service import next_ticket_number

router = APIRouter()


def _recalc_total(order: Order, db: Session) -> None:
    """Recalcula el total de la comanda a partir dels seus items."""
    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    total = Decimal("0")
    for it in items:
        price = Decimal(str(it.price_snapshot or 0))
        total += price * it.quantity
    order.total_amount = total - Decimal(str(order.discount_amount or 0))


@router.get("", response_model=List[OrderOut])
def list_orders(db: Session = Depends(get_db)):
    return db.query(Order).order_by(Order.opened_at.desc()).all()


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    order = Order(
        table_id=payload.table_id,
        staff_id=payload.staff_id,
        order_type=payload.order_type,
        notes=payload.notes,
    )
    # Tiquet de comanda (numeració per tipus COM).
    _, order.ticket_code = next_ticket_number(db, "COM")
    db.add(order)
    db.flush()  # para obtener order.id

    for item_data in payload.items:
        # Snapshot de nombre y precio desde el menú si no se pasan explícitos
        name_snapshot = item_data.name_snapshot
        price_snapshot = item_data.price_snapshot
        vat_rate = item_data.vat_rate
        if item_data.menu_item_id and (name_snapshot is None or price_snapshot is None):
            mi = db.get(MenuItem, item_data.menu_item_id)
            if mi:
                name_snapshot = name_snapshot or mi.name
                price_snapshot = price_snapshot if price_snapshot is not None else mi.price
                vat_rate = vat_rate if vat_rate is not None else mi.vat_rate

        item = OrderItem(
            order_id=order.id,
            menu_item_id=item_data.menu_item_id,
            name_snapshot=name_snapshot,
            price_snapshot=price_snapshot,
            quantity=item_data.quantity,
            vat_rate=vat_rate,
            modifications=item_data.modifications,
            seat_number=item_data.seat_number,
        )
        db.add(item)

    db.flush()
    _recalc_total(order, db)
    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: UUID, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Comanda no encontrada")
    return order


@router.post("/{order_id}/items", response_model=OrderItemOut, status_code=status.HTTP_201_CREATED)
def add_item(order_id: UUID, payload: OrderItemCreate, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Comanda no encontrada")

    name_snapshot = payload.name_snapshot
    price_snapshot = payload.price_snapshot
    vat_rate = payload.vat_rate
    if payload.menu_item_id and (name_snapshot is None or price_snapshot is None):
        mi = db.get(MenuItem, payload.menu_item_id)
        if mi:
            name_snapshot = name_snapshot or mi.name
            price_snapshot = price_snapshot if price_snapshot is not None else mi.price
            vat_rate = vat_rate if vat_rate is not None else mi.vat_rate

    item = OrderItem(
        order_id=order_id,
        menu_item_id=payload.menu_item_id,
        name_snapshot=name_snapshot,
        price_snapshot=price_snapshot,
        quantity=payload.quantity,
        vat_rate=vat_rate,
        modifications=payload.modifications,
        seat_number=payload.seat_number,
    )
    db.add(item)
    db.flush()
    _recalc_total(order, db)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_order_status(order_id: UUID, status_value: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Comanda no encontrada")
    order.status = status_value
    db.commit()
    db.refresh(order)
    return order


@router.post("/{order_id}/void", response_model=VoidOut, status_code=status.HTTP_201_CREATED)
def void_order(order_id: UUID, payload: VoidCreate, db: Session = Depends(get_db)):
    """Anul·la una comanda (o part), autoritzada per un cap/manager.

    Registra l'anul·lació amb qui l'ha autoritzada i el motiu, perquè surti al
    tancament del dia (la Z) com a línia a part. Si s'anul·la l'import total,
    la comanda passa a `cancelled`.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Comanda no encontrada")

    void = Void(
        order_id=order_id,
        amount=Decimal(str(payload.amount)),
        reason=payload.reason,
        authorized_by_id=payload.authorized_by_id,
    )
    # Tiquet d'anul·lació (numeració per tipus NUL).
    _, void.ticket_code = next_ticket_number(db, "NUL")
    db.add(void)

    # Si s'anul·la el total (o més), la comanda queda cancel·lada.
    if Decimal(str(payload.amount)) >= Decimal(str(order.total_amount or 0)):
        order.status = "cancelled"
        order.closed_at = datetime.now()

    db.commit()
    db.refresh(void)
    return void

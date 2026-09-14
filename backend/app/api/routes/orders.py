from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel, Field
from datetime import datetime

from ...db import get_db
from ...models.models import Order, OrderItem, MenuItem, Void, Payment, RoomCredit, Center
from ...schemas.schemas import (
    OrderCreate,
    OrderOut,
    OrderItemCreate,
    OrderItemOut,
    VoidCreate,
    VoidOut,
    PaymentRequest,
    PaymentOut,
)
from ...services.ticket_service import next_ticket_number
from ...services.receipt_service import (
    build_service_slip,
    render_service_slip_text,
    render_service_slip_escpos,
)
from ...services.receipt_service import (
    build_receipt,
    build_payment_receipt,
    build_void_receipt,
    render_receipt_text,
    render_receipt_escpos,
)
from ...services.pms_adapter import get_pms_adapter
from ...realtime import emit_sync

router = APIRouter()


def _recalc_total(order: Order, db: Session) -> None:
    """Recalcula el total de la comanda a partir dels seus items.

    ⚠️ EXCLOU les línies anul·lades (status='cancelled') — si no, anul·lar un
    article no faria baixar el compte. Fix 14/09/2026.
    """
    items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id, OrderItem.status != "cancelled")
        .all()
    )
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
    # === COMANDA SUCCESSIVA (decisió Tomeu 14/09/2026) ===
    # Si la taula ja té un compte obert (una comanda sense pagar), aquesta nova
    # comanda és una RONDA MÉS: el número s'incrementa (2, 3...) i el seu import
    # se suma al saldo anterior del compte. El tiquet de servei ho mostrarà.
    ronda = 1
    if payload.table_id:
        darrera = (
            db.query(Order)
            .filter(
                Order.table_id == payload.table_id,
                Order.status.notin_(["paid", "cancelled", "closed"]),
            )
            .order_by(Order.comanda_number.desc())
            .first()
        )
        if darrera:
            # === POLÍTICA DE TAULES OBERTES (decisió Tomeu 14/09/2026) ===
            # Si el centre NO permet taules obertes, no es pot acumular una
            # ronda nova sobre un compte sense pagar: cal cobrar la primera.
            centre = db.get(Center, payload.center_id or darrera.center_id) if (payload.center_id or darrera.center_id) else None
            if centre is not None and not bool(getattr(centre, "allows_open_tables", True)):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Aquest punt de venda no permet taules obertes: "
                        "cal cobrar les consumicions de la taula abans de fer-ne més."
                    ),
                )
            ronda = int(getattr(darrera, "comanda_number", 1) or 1) + 1

    order = Order(
        table_id=payload.table_id,
        staff_id=payload.staff_id,
        shift_id=payload.shift_id,
        center_id=payload.center_id,
        order_type=payload.order_type,
        notes=payload.notes,
        comanda_number=ronda,
    )
    # Tiquet de comanda (seqüència única TICKET, compartida per tots els tipus).
    _, order.ticket_code = next_ticket_number(db, "TICKET")
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
            comanda_number=ronda,
        )
        db.add(item)

    db.flush()
    _recalc_total(order, db)
    db.commit()
    db.refresh(order)
    emit_sync("order.created", {
        "order_id": str(order.id),
        "ticket_code": order.ticket_code,
        "table_id": str(order.table_id) if order.table_id else None,
        "center_id": str(order.center_id) if order.center_id else None,
        "total_amount": str(order.total_amount or 0),
    })
    return order


@router.get("/room-info")
def get_room_info(
    room_number: str,
    db: Session = Depends(get_db),
):
    """Consulta el règim + nom del titular d'una habitació (proxy cap al PMS).

    El frontend crida aquest endpoint (no Estada directament) perquè la clau
    PMS no ha de sortir mai del backend. Retorna room_found, guest_name
    (titular de la reserva), meal_plan, credit_type/limit i folio_balance.
    """
    adapter = get_pms_adapter()
    if not adapter:
        raise HTTPException(status_code=501, detail="PMS no configurat")
    return adapter.verify_room(room_number)


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
    # Tiquet d'anul·lació (seqüència única TICKET, compartida per tots els tipus).
    _, void.ticket_code = next_ticket_number(db, "TICKET")
    db.add(void)

    # Si s'anul·la el total (o més), la comanda queda cancel·lada.
    if Decimal(str(payload.amount)) >= Decimal(str(order.total_amount or 0)):
        order.status = "cancelled"
        order.closed_at = datetime.now()

    db.commit()
    db.refresh(void)
    return void


@router.get("/{order_id}/ticket")
def get_ticket(
    order_id: UUID,
    format: str = "json",
    payment_id: Optional[UUID] = None,
    copy: bool = False,
    db: Session = Depends(get_db),
):
    """Retorna el tiquet de la comanda (capçalera + línies agrupades + total).

    Si es passa `payment_id`, retorna el tiquet de pagament (amb el mètode,
    habitació/convidat/motiu i requadre de signatura si cal).
    Si `copy=true`, el tiquet surt marcat com a «CÒPIA» (reimpressió).
    `format=json` retorna el tiquet estructurat; `format=text` el renderitza en
    text pla per a impressora tèrmica de 80 mm.
    """
    try:
        receipt = (
            build_payment_receipt(db, payment_id)
            if payment_id
            else build_receipt(db, order_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if copy:
        receipt["mark"] = "copy"

    if format == "text":
        return PlainTextResponse(render_receipt_text(receipt))
    if format == "escpos":
        return Response(content=render_receipt_escpos(receipt), media_type="application/octet-stream")
    return receipt


@router.get("/{order_id}/void/{void_id}/ticket")
def get_void_ticket(
    order_id: UUID,
    void_id: UUID,
    format: str = "json",
    db: Session = Depends(get_db),
):
    """Retorna el tiquet d'anul·lació (l'original marcat «ANUL·LAT» + motiu)."""
    try:
        receipt = build_void_receipt(db, void_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if format == "text":
        return PlainTextResponse(render_receipt_text(receipt))
    if format == "escpos":
        return Response(content=render_receipt_escpos(receipt), media_type="application/octet-stream")
    return receipt


@router.post("/{order_id}/pay", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def pay_order(order_id: UUID, payload: PaymentRequest, db: Session = Depends(get_db)):
    """Registra un pagament de la comanda i, si cobreix el total, la tanca.

    Mètodes: `cash` (efectiu), `card` (targeta/SoftPOS), `bizum`, `split`,
    `room_charge` (càrrec a habitació) i `house` (invitació). Les invitacions
    tenen seqüència de tiquet pròpia (`INV`), la resta comparteixen `TICKET`.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Comanda no trobada")

    method = (payload.method or "").strip().lower()
    if method not in ("cash", "card", "bizum", "split", "room_charge", "house"):
        raise HTTPException(status_code=400, detail="Mètode de pagament invàlid")

    # Validació del càrrec a habitació (habilitació + topall)
    pms_result = None
    if method == "room_charge":
        if not payload.room_number:
            raise HTTPException(status_code=400, detail="Cal indicar el número d'habitació")

        # Si hi ha PMS configurat (Estada), el càrrec es posta al foli del client.
        # El PMS valida guest + règim + línia de crèdit i és la font de veritat.
        adapter = get_pms_adapter()
        if adapter:
            pms_result = adapter.post_room_charge(
                external_id=f"comanda-pay-{uuid4()}",
                room_number=payload.room_number,
                amount=Decimal(str(payload.amount)),
                items=[
                    {
                        "name": it.name_snapshot or "Article",
                        "qty": it.quantity,
                        "price": str(it.price_snapshot or 0),
                        "tax_rate": str(it.vat_rate or 0),
                    }
                    for it in order.items
                ],
                guest_name=payload.guest_name,
                staff_id=str(order.staff_id) if order.staff_id else None,
            )
            if not pms_result.get("success"):
                raise HTTPException(
                    status_code=400,
                    detail=pms_result.get("message")
                    or pms_result.get("error")
                    or "El PMS ha rebutjat el càrrec",
                )
        else:
            # Sense PMS: validació local (còpia RoomCredit)
            rc = (
                db.query(RoomCredit)
                .filter(RoomCredit.room_number == payload.room_number)
                .first()
            )
            if rc and not rc.enabled:
                raise HTTPException(status_code=400, detail="Habitació sense crèdit habilitat")
            if rc and Decimal(str(rc.credit_limit or 0)) > 0:
                new_balance = Decimal(str(rc.current_balance or 0)) + Decimal(str(payload.amount))
                if new_balance > Decimal(str(rc.credit_limit)):
                    raise HTTPException(status_code=400, detail="Habitació topada (supera el límit de crèdit)")

    seq = "INV" if method == "house" else "TICKET"
    _, ticket_code = next_ticket_number(db, seq)

    payment = Payment(
        order_id=order_id,
        method=method,
        amount=Decimal(str(payload.amount)),
        status="completed",
        ticket_code=ticket_code,
        guest_name=payload.guest_name,
        room_number=payload.room_number,
        invited_by=payload.invited_by,
        reason=payload.reason,
        card_reference=payload.card_reference,
        pms_posted=bool(pms_result and pms_result.get("success")),
        pms_response=pms_result,
    )
    db.add(payment)

    # Tancar la comanda si el pagament (o la suma dels pagaments) cobreix el total.
    paid_total = (
        db.query(func.sum(Payment.amount))
        .filter(Payment.order_id == order_id, Payment.status == "completed")
        .scalar()
    )
    paid_total = Decimal(str(paid_total or 0)) + Decimal(str(payload.amount))
    if paid_total >= Decimal(str(order.total_amount or 0)):
        order.status = "paid"
        order.closed_at = datetime.now()

    # Actualitzar el crèdit acumulat de l'habitació (només sense PMS local)
    if method == "room_charge" and pms_result is None:
        rc = (
            db.query(RoomCredit)
            .filter(RoomCredit.room_number == payload.room_number)
            .first()
        )
        if rc:
            rc.current_balance = Decimal(str(rc.current_balance or 0)) + Decimal(str(payload.amount))

    db.commit()
    db.refresh(payment)
    emit_sync("order.paid", {
        "order_id": str(order.id),
        "payment_id": str(payment.id),
        "method": method,
        "ticket_code": payment.ticket_code,
        "amount": str(payment.amount or 0),
    })
    return payment


# ============================================================
# CRUD DE LÍNIES (Modal de taula del pla de sala — decisió Tomeu 14/09/2026)
# ============================================================

class OrderItemPatch(BaseModel):
    """Modificació d'una línia de comanda: només la quantitat."""
    quantity: int = Field(..., ge=1, description="Nova quantitat (mínim 1)")


@router.patch("/{order_id}/items/{item_id}", response_model=OrderItemOut)
def update_item(order_id: UUID, item_id: UUID, payload: OrderItemPatch, db: Session = Depends(get_db)):
    """Modifica la quantitat d'una línia de la comanda (pla de sala).

    Recalcula el total de la comanda. No permet editar línies ja anul·lades.
    """
    item = db.get(OrderItem, item_id)
    if not item or item.order_id != order_id:
        raise HTTPException(status_code=404, detail="Línia no trobada en aquesta comanda")
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Comanda no encontrada")
    if item.status == "cancelled":
        raise HTTPException(status_code=409, detail="Aquesta línia ja està anul·lada")
    if order.status in ("paid", "cancelled", "closed"):
        raise HTTPException(status_code=409, detail="La comanda ja està tancada — no es pot modificar")

    item.quantity = payload.quantity
    db.flush()
    _recalc_total(order, db)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{order_id}/items/{item_id}/void", response_model=OrderItemOut)
def void_item(order_id: UUID, item_id: UUID, db: Session = Depends(get_db)):
    """Anul·la UNA línia de la comanda (pla de sala).

    La línia queda amb status='cancelled' (traça conservada, com mana la
    política comptable: mai esborrar) i el total de la comanda es recalcula.
    """
    item = db.get(OrderItem, item_id)
    if not item or item.order_id != order_id:
        raise HTTPException(status_code=404, detail="Línia no trobada en aquesta comanda")
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Comanda no encontrada")
    if order.status in ("paid", "cancelled", "closed"):
        raise HTTPException(status_code=409, detail="La comanda ja està tancada — no es pot anul·lar línies")

    item.status = "cancelled"
    db.flush()
    _recalc_total(order, db)
    db.commit()
    db.refresh(item)
    return item


# ============================================================
# TIQUET DE SERVEI (per portar a taula) — decisió Tomeu 14/09/2026
# ============================================================

@router.get("/{order_id}/tiquet-servei")
def tiquet_servei(order_id: UUID, format: str = "text", inclou_anterior: bool = True,
                  db: Session = Depends(get_db)):
    """Tiquet de SERVEI: sense dades fiscals, per portar a la taula.

    Conté: departament · nº de comanda (ronda) · saldo anterior · desglossament
    de la comanda actual · cambrer · import de la comanda.
    `format=escpos` retorna els bytes per a la impressora tèrmica.
    """
    try:
        slip = build_service_slip(db, order_id, inclou_anterior=inclou_anterior)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if format == "escpos":
        return Response(content=render_service_slip_escpos(slip), media_type="application/octet-stream")
    return PlainTextResponse(render_service_slip_text(slip))


# ============================================================
# DIVIDIR LA COMANDA (moure línies a una altra comanda) — decisió Tomeu 14/09/2026
# ============================================================

class MouLiniesPayload(BaseModel):
    """Mou línies seleccionades d'una comanda a una ALTRA (per tiquets separats)."""
    line_ids: List[UUID] = Field(..., min_length=1, description="Línies a moure")
    #: Comanda de destí. Si no s'indica, se'n crea una de nova per a la taula.
    desti_order_id: Optional[UUID] = Field(None, description="Comanda de destí (opcional)")
    #: Si es crea una comanda nova, se li pot canviar el nom/etiqueta de taula.
    nota: Optional[str] = None


@router.post("/{order_id}/moure-linies", response_model=OrderOut)
def moure_linies(order_id: UUID, payload: MouLiniesPayload, db: Session = Depends(get_db)):
    """Mou línies d'una comanda a una altra per fer TIQUETS SEPARATS.

    Cas d'ús (Tomeu 14/09/2026): en pagar, poder separar les consumicions en
    tiquets diferents — per exemple una part per a una persona i una altra per
    a una altra, i cobrar-les per separat.

    Si no s'indica `desti_order_id`, es crea una comanda NOVA a la mateixa taula
    (marcada com a divisió) i s'hi mouen les línies. Les dues comandes quadren:
    el total de les línies és el mateix, només canvien de capçalera.
    """
    origen = db.get(Order, order_id)
    if not origen:
        raise HTTPException(status_code=404, detail="Comanda origen no trobada")
    if origen.status in ("paid", "cancelled", "closed"):
        raise HTTPException(status_code=409, detail="La comanda origen ja està tancada")

    linies = (
        db.query(OrderItem)
        .filter(OrderItem.id.in_(payload.line_ids), OrderItem.order_id == order_id)
        .all()
    )
    if not linies:
        raise HTTPException(status_code=404, detail="Cap de les línies indicades és a la comanda origen")

    # destinació: la indicada o una de nova (divisió del compte)
    if payload.desti_order_id:
        desti = db.get(Order, payload.desti_order_id)
        if not desti:
            raise HTTPException(status_code=404, detail="Comanda destí no trobada")
        if desti.status in ("paid", "cancelled", "closed"):
            raise HTTPException(status_code=409, detail="La comanda destí ja està tancada")
    else:
        desti = Order(
            table_id=origen.table_id,
            staff_id=origen.staff_id,
            shift_id=origen.shift_id,
            center_id=origen.center_id,
            order_type=origen.order_type,
            notes=payload.nota or f"Divisió de {origen.ticket_code or 'comanda'}",
            #: mateixa ronda que l'origen: és una divisió del MATEIX compte
            comanda_number=int(getattr(origen, "comanda_number", 1) or 1),
        )
        _, desti.ticket_code = next_ticket_number(db, "TICKET")
        db.add(desti)
        db.flush()

    for l in linies:
        l.order_id = desti.id

    db.flush()
    _recalc_total(origen, db)
    _recalc_total(desti, db)
    db.commit()
    db.refresh(desti)
    return desti

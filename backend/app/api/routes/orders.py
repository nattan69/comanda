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
from ...models.models import Order, OrderItem, MenuItem, Void, Payment, RoomCredit, Center, Table, Staff
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
    # === L'ESDEVENIMENT DE COMANDA PORTA ELS ARTICLES ===
    # El KDS de cuina ha de saber QUÈ ha de preparar, no només que hi ha una
    # comanda. S'hi envien les línies (nom, quantitat, modificacions) perquè
    # la pantalla de cuina les pugui llistar i les pugui imprimir (decisió
    # Tomeu 14/09/2026).
    linies_esdeveniment = [
        {
            "id": str(it.id),
            "name": it.name_snapshot or "Article",
            "quantity": it.quantity,
            "modifications": it.modifications,
            "status": it.status,
            "comanda_number": int(getattr(it, "comanda_number", 1) or 1),
        }
        for it in db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        if it.status != "cancelled"
    ]
    taula = db.get(Table, order.table_id) if order.table_id else None
    centre = db.get(Center, order.center_id) if order.center_id else None
    cambrer = db.get(Staff, order.staff_id) if order.staff_id else None
    emit_sync("order.created", {
        "order_id": str(order.id),
        "ticket_code": order.ticket_code,
        "table_id": str(order.table_id) if order.table_id else None,
        "table_number": taula.number if taula else None,
        "center_id": str(order.center_id) if order.center_id else None,
        "center_name": centre.name if centre else None,
        "staff_name": cambrer.full_name if cambrer else None,
        "total_amount": str(order.total_amount or 0),
        "comanda_number": int(getattr(order, "comanda_number", 1) or 1),
        #: les línies que la cuina ha de preparar
        "items": linies_esdeveniment,
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

    # Els 5 tipus de pagament del TPV (decisió Tomeu 14/09/2026):
    #   cash        → Efectiu
    #   room_charge → Crèdit (càrrec a habitació)
    #   card        → Targeta de crèdit
    #   house       → Invitació
    #   anul        → Nul (s'anul·la la consumició; no genera cobrament ni IVA)
    # (bizum i split es mantenen per compatibilitat amb el que ja hi havia)
    method = (payload.method or "").strip().lower()
    if method not in ("cash", "card", "bizum", "split", "room_charge", "house", "anul", "null"):
        raise HTTPException(status_code=400, detail="Mètode de pagament invàlid")

    # === NUL ===
    # «Nul» és un mètode PROPI (no és una invitació): la consumició no es cobra
    # ni es declara, però la Z els ha de poder distingir. Tots dos queden fora
    # de la comptabilitat (ni ingrés ni IVA), però amb traça separada.
    if method == "null":
        method = "anul"
    if method == "anul" and not payload.reason:
        payload.reason = "Nul (anul·lació de consumició)" 

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

    # Seqüència de tiquet: INV per a invitacions, TICKET per a la resta.
    # Els NULS comparteixen la sèrie TICKET (el seu tiquet queda marcat amb el
    # motiu i el mètode `anul`, que els distingeix a la Z sense necessitat
    # d'una sèrie pròpia).
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


# ============================================================
# ENVIAR A CUINA — els plats de menjar per preparar
# (decisió Tomeu 14/09/2026)
# ============================================================

class EnviarCuinaPayload(BaseModel):
    """Enviament a cuina: quines línies i a quin centre de producció."""
    #: Línies a enviar. Si no s'indica, s'envien totes les pendents.
    line_ids: Optional[List[UUID]] = None
    #: Imprimir el tiquet de cuina a la impressora tèrmica del departament.
    imprimir: bool = True


def build_kitchen_ticket(db: Session, order_id, line_ids: Optional[list] = None) -> dict:
    """Tiquet de CUINA: el que la cuina ha de preparar, sense imports ni fiscalitat.

    Només hi ha d'anar el que es prepara: article, quantitat i modificacions
    («sense ceba», «poc fet»...). Els preus NO hi surten — a la cuina no els
    calen i així el paper és més llegible de lluny.
    """
    order = db.get(Order, order_id)
    if not order:
        raise ValueError("Comanda no trobada.")
    taula = db.get(Table, order.table_id) if order.table_id else None
    centre = db.get(Center, order.center_id) if order.center_id else None
    cambrer = db.get(Staff, order.staff_id) if order.staff_id else None

    q = db.query(OrderItem).filter(OrderItem.order_id == order_id)
    if line_ids:
        q = q.filter(OrderItem.id.in_(line_ids))
    items = [it for it in q.all() if it.status != "cancelled"]

    return {
        "type": "cuina",
        "order_id": str(order.id),
        "ticket_code": order.ticket_code or "",
        "comanda_number": int(getattr(order, "comanda_number", 1) or 1),
        "table_number": taula.number if taula else None,
        "center_name": centre.name if centre else None,
        "staff_name": cambrer.full_name if cambrer else None,
        "issued_at": (order.opened_at or datetime.now(timezone.utc)).isoformat(),
        "lines": [
            {
                "name": it.name_snapshot or "Article",
                "quantity": it.quantity,
                "modifications": it.modifications,
            }
            for it in items
        ],
    }


def render_kitchen_ticket_text(t: dict) -> str:
    """Text pla (80 mm) del tiquet de CUINA — lletra gran, sense imports."""
    out = []
    sep = "=" * LINE_WIDTH_K
    out.append(_center_k("*** CUINA ***", gran=True))
    if t.get("center_name"):
        out.append(_center_k(str(t["center_name"]).upper()))
    out.append(sep)
    if t.get("table_number") is not None:
        out.append(f"TAULA: {t['table_number']}")
    out.append(f"Comanda nº: {t.get('comanda_number', 1)}")
    if t.get("ticket_code"):
        out.append(f"Tiquet: {t['ticket_code']}")
    if t.get("staff_name"):
        out.append(f"Cambrer: {t['staff_name']}")
    try:
        from datetime import datetime as _dt
        _q = _dt.fromisoformat(str(t["issued_at"]).replace("Z", "+00:00")).astimezone()
        out.append(f"Hora: {_q.strftime('%H:%M:%S')}  ({_q.strftime('%d/%m/%Y')})")
    except Exception:
        pass
    out.append(sep)
    for l in t.get("lines", []):
        out.append(f"  {l['quantity']} x  {l['name']}")
        for mod in (l.get("modifications") or []):
            out.append(f"        >> {mod}")
    out.append(sep)
    out.append(_center_k("a preparar"))
    return "\n".join(out) + "\n"


LINE_WIDTH_K = 42


def _center_k(text: str, gran: bool = False) -> str:
    """Centra una línia per a impressora de 80 mm (42 columnes)."""
    t = str(text)
    if gran:
        t = t.center(LINE_WIDTH_K)
    return t.center(LINE_WIDTH_K)


async def _imprimir_cuina(t: dict) -> None:
    """Envia el tiquet de cuina a la impressora del departament (si n'hi ha)."""
    # La impressió real va per LAN (raw 9100) des del dispositiu de cuina,
    # no pel núvol — arquitectura Conceptes. Aquí només deixem el ganxo.
    return None


@router.post("/{order_id}/enviar-cuina")
def enviar_cuina(order_id: UUID, payload: EnviarCuinaPayload, db: Session = Depends(get_db)):
    """Envia la comanda a CUINA: marca les línies com a enviades i avisa el KDS.

    És el que fa el botó «Enviar a cuina» de la Comandera i del TPV: les línies
    passen a `sent` i el KDS de la cuina rep l'esdeveniment amb els plats a
    preparar. Opcionalment s'imprimeix el tiquet de cuina a la impressora
    tèrmica del departament (decisió Tomeu 14/09/2026).
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Comanda no trobada")
    if order.status in ("paid", "cancelled", "closed"):
        raise HTTPException(status_code=409, detail="La comanda ja està tancada")

    q = db.query(OrderItem).filter(OrderItem.order_id == order_id)
    if payload.line_ids:
        q = q.filter(OrderItem.id.in_(payload.line_ids))
    items = [it for it in q.all() if it.status != "cancelled"]
    if not items:
        raise HTTPException(status_code=404, detail="Cap línia per enviar a cuina")

    for it in items:
        if it.status in ("pending", None):
            it.status = "sent"

    if order.status in ("open", None):
        order.status = "sent_to_kitchen"

    db.commit()

    try:
        ticket = build_kitchen_ticket(db, order_id, [it.id for it in items])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Avisa el KDS en viu (amb els plats)
    emit_sync("order.sent_to_kitchen", {
        "order_id": str(order.id),
        "ticket_code": order.ticket_code,
        "table_number": ticket.get("table_number"),
        "center_id": str(order.center_id) if order.center_id else None,
        "comanda_number": ticket.get("comanda_number"),
        "items": ticket["lines"],
    })

    return {"ok": True, "enviat": len(items), "ticket": ticket,
            "text": render_kitchen_ticket_text(ticket)}


@router.get("/{order_id}/tiquet-cuina")
def tiquet_cuina(order_id: UUID, format: str = "text", db: Session = Depends(get_db)):
    """Tiquet de CUINA (text o escpos): què ha de preparar la cuina, sense imports."""
    try:
        t = build_kitchen_ticket(db, order_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if format == "escpos":
        return Response(content=_escpos_kitchen(render_kitchen_ticket_text(t)),
                        media_type="application/octet-stream")
    return PlainTextResponse(render_kitchen_ticket_text(t))


def _escpos_kitchen(text: str) -> bytes:
    """Bytes ESC/POS del tiquet de cuina (lletra gran, tall de paper)."""
    out = bytearray()
    out += b"\x1b@"      # init
    out += b"\x1b!\x10"  # doble alçada (més llegible de lluny a la cuina)
    for linia in text.split("\n"):
        try:
            out += linia.encode("cp858", errors="replace") + b"\n"
        except Exception:
            out += linia.encode("latin-1", errors="replace") + b"\n"
    out += b"\x1b!\x00"  # tornem a mida normal
    out += b"\n\n\n"
    out += b"\x1dV\x00"  # tall
    return bytes(out)

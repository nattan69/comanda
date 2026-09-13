"""
Servei de tiquets (rebuts) del TPV.

Genera el tiquet d'una comanda o d'un pagament: capçalera (dades fiscals de
l'establiment + centre/departament), línies agrupades per producte, total amb
IVA inclòs, i — per als pagaments — la part de pagament (mètode, habitació,
convidat, motiu) amb requadre de signatura quan cal. També el renderitza en
text pla per a impressora tèrmica de 80 mm.

Els preus de carta són amb IVA inclòs. El desglossament d'IVA per tipus es fa
al tancament del dia (la Z), no al tiquet individual.
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from ..models.models import Center, Establishment, Order, Payment, Staff, Table

# Amplada de la impressora tèrmica (80 mm ≈ 42 caràcters).
LINE_WIDTH = 42

# Mètodes que requereixen signatura al tiquet.
SIGNATURE_METHODS = {"room_charge", "house"}


def _build_lines(order: Order) -> list:
    """Línies agrupades per producte + preu unitari (quantitat × preu)."""
    lines: dict = {}
    for it in order.items:
        if it.status == "cancelled":
            continue
        name = it.name_snapshot or "Producte"
        unit_price = Decimal(str(it.price_snapshot or 0))
        key = (name, str(unit_price))
        if key not in lines:
            lines[key] = {
                "name": name,
                "quantity": 0,
                "unit_price": str(unit_price),
                "total": Decimal("0"),
            }
        lines[key]["quantity"] += it.quantity
        lines[key]["total"] += unit_price * it.quantity
    lines_list = sorted(lines.values(), key=lambda l: l["name"])
    for l in lines_list:
        l["total"] = str(l["total"])
    return lines_list


def _build_header(db: Session, order: Order) -> dict:
    center = db.get(Center, order.center_id) if order.center_id else None
    establishment = (
        db.get(Establishment, center.establishment_id) if center and center.establishment_id else None
    )
    staff = db.get(Staff, order.staff_id) if order.staff_id else None
    table = db.get(Table, order.table_id) if order.table_id else None
    issued_at = order.closed_at or datetime.now(timezone.utc)

    return {
        "establishment": {
            "name": establishment.name,
            "legal_name": establishment.legal_name,
            "nif": establishment.nif,
            "category": establishment.category,
            "address": establishment.address,
            "city": establishment.city,
            "postal_code": establishment.postal_code,
        }
        if establishment
        else None,
        "center": {"name": center.name} if center else None,
        "issued_at": issued_at.isoformat(),
        "staff_name": staff.full_name if staff else None,
        "table_number": table.number if table else None,
    }


def build_receipt(db: Session, order_id) -> dict:
    """Tiquet d'una comanda (capçalera + línies + total)."""
    order = db.get(Order, order_id)
    if not order:
        raise ValueError("Comanda no trobada.")

    lines_list = _build_lines(order)
    total = sum((Decimal(l["total"]) for l in lines_list), Decimal("0"))

    return {
        "ticket_code": order.ticket_code or "",
        "order_id": str(order.id),
        "type": "comanda",
        "header": _build_header(db, order),
        "lines": lines_list,
        "total": str(total),  # IVA inclòs
        "payment": None,
    }


def build_payment_receipt(db: Session, payment_id) -> dict:
    """Tiquet d'un pagament (comanda + mètode de pagament + signatura si cal)."""
    payment = db.get(Payment, payment_id)
    if not payment:
        raise ValueError("Pagament no trobat.")

    receipt = build_receipt(db, payment.order_id)
    receipt["type"] = payment.method
    receipt["payment"] = {
        "method": payment.method,
        "amount": str(payment.amount),
        "ticket_code": payment.ticket_code or "",
        "guest_name": payment.guest_name,       # room_charge
        "room_number": payment.room_number,     # room_charge
        "invited_by": payment.invited_by,       # house
        "reason": payment.reason,               # house
        "signature_required": payment.method in SIGNATURE_METHODS,
    }
    return receipt


def _center(text: str) -> str:
    return text.center(LINE_WIDTH).rstrip()


def _money(value: str) -> str:
    """Formata un import amb coma decimal i 2 decimals."""
    return f"{Decimal(value):.2f}".replace(".", ",")


def _signature_box() -> str:
    """Requadre de signatura per a room charge i invitacions."""
    sep = "-" * LINE_WIDTH
    return "\n".join(
        [
            "",
            "  Signatura: ..............................",
            "  (Firma del client)",
            "",
        ]
    )


def render_receipt_text(receipt: dict) -> str:
    """Renderitza el tiquet en text pla (80 mm) per a impressió."""
    h = receipt.get("header") or {}
    est = h.get("establishment") or {}
    center = h.get("center") or {}
    payment = receipt.get("payment") or {}

    out = []
    sep = "-" * LINE_WIDTH

    # Capçalera: dades fiscals + centre/departament
    if est:
        if est.get("name"):
            out.append(_center(str(est["name"]).upper()))
        if est.get("legal_name"):
            out.append(_center(str(est["legal_name"])))
        if est.get("category"):
            out.append(_center(str(est["category"])))
        if est.get("nif"):
            out.append(_center(f"NIF: {est['nif']}"))
        addr = " ".join(x for x in [est.get("address"), est.get("postal_code"), est.get("city")] if x)
        if addr:
            out.append(_center(addr))
    if center and center.get("name"):
        out.append(_center(f'Centre: {center["name"]}'))
    out.append(sep)

    # Identificació del tiquet
    code = (payment.get("ticket_code") or receipt.get("ticket_code") or "")
    if code:
        out.append(_center(f"Tiquet: {code}"))
    if h.get("issued_at"):
        out.append(_center(f"Data: {h['issued_at'][:19].replace('T', ' ')}"))
    if h.get("staff_name"):
        out.append(_center(f"Cambrer: {h['staff_name']}"))
    if h.get("table_number") is not None:
        out.append(_center(f"Taula: {h['table_number']}"))
    out.append(sep)

    # Línies agrupades per producte
    for l in receipt.get("lines", []):
        qty = l["quantity"]
        up = _money(l["unit_price"])
        tot = _money(l["total"])
        left = f"{qty} x {l['name']}"
        right = f"{up}  {tot}"
        pad = LINE_WIDTH - len(left) - len(right)
        if pad < 1:
            pad = 1
        out.append(f"{left}{'.' * pad}{right}")

    out.append(sep)
    out.append(_center(f"TOTAL (IVA inclòs)   {_money(receipt.get('total', '0'))} €"))

    # Part de pagament (si n'hi ha)
    if payment:
        out.append(sep)
        method = payment.get("method")
        amount = _money(payment.get("amount", "0"))
        if method == "cash":
            out.append(_center(f"PAGAT EN EFECTIU: {amount} €"))
        elif method == "card":
            out.append(_center(f"PAGAT AMB TARGETA: {amount} €"))
        elif method == "bizum":
            out.append(_center(f"PAGAT AMB BIZUM: {amount} €"))
        elif method == "room_charge":
            room = payment.get("room_number") or "-"
            guest = payment.get("guest_name") or "-"
            out.append(_center(f"CÀRREC A HABITACIÓ {room}"))
            out.append(_center(f"Client: {guest}"))
            out.append(_center(f"Import: {amount} €"))
        elif method == "house":
            invited = payment.get("invited_by") or "-"
            reason = payment.get("reason") or "-"
            out.append(_center(f"INVITACIÓ (compte casa)"))
            out.append(_center(f"Convidat per: {invited}"))
            out.append(_center(f"Motiu: {reason}"))
            out.append(_center(f"Import: {amount} €"))
        if payment.get("signature_required"):
            out.append(_signature_box())

    out.append(sep)
    out.append(_center("Gràcies per la seva visita"))

    return "\n".join(out)

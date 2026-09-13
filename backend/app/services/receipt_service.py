"""
Servei de tiquets (rebuts) del TPV.

Genera el tiquet d'una comanda: capçalera (dades fiscals de l'establiment +
centre/departament), línies agrupades per producte (quantitat × preu = total)
i total amb IVA inclòs. També el renderitza en text pla per a impressora
tèrmica de 80 mm.

Els preus de carta són amb IVA inclòs (com és habitual en hostaleria). El
desglossament d'IVA per tipus es fa al tancament del dia (la Z), no al tiquet
individual.
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from ..models.models import Center, Establishment, Order, Staff, Table

# Amplada de la impressora tèrmica (80 mm ≈ 42 caràcters).
LINE_WIDTH = 42


def build_receipt(db: Session, order_id) -> dict:
    """Construeix el tiquet estructurat d'una comanda."""
    order = db.get(Order, order_id)
    if not order:
        raise ValueError("Comanda no trobada.")

    center = db.get(Center, order.center_id) if order.center_id else None
    establishment = (
        db.get(Establishment, center.establishment_id) if center and center.establishment_id else None
    )
    staff = db.get(Staff, order.staff_id) if order.staff_id else None
    table = db.get(Table, order.table_id) if order.table_id else None

    # Línies agrupades per producte + preu unitari.
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
    total = sum((l["total"] for l in lines_list), Decimal("0"))

    issued_at = order.closed_at or datetime.now(timezone.utc)

    return {
        "ticket_code": order.ticket_code or "",
        "order_id": str(order.id),
        "type": "comanda",
        "header": {
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
        },
        "lines": [
            {"name": l["name"], "quantity": l["quantity"], "unit_price": l["unit_price"], "total": str(l["total"])}
            for l in lines_list
        ],
        "total": str(total),  # IVA inclòs
    }


def _center(text: str) -> str:
    return text.center(LINE_WIDTH).rstrip()


def _money(value: str) -> str:
    """Formata un import amb coma decimal i 2 decimals."""
    return f"{Decimal(value):.2f}".replace(".", ",")


def render_receipt_text(receipt: dict) -> str:
    """Renderitza el tiquet en text pla (80 mm) per a impressió."""
    h = receipt.get("header") or {}
    est = h.get("establishment") or {}
    center = h.get("center") or {}

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
    if receipt.get("ticket_code"):
        out.append(_center(f"Tiquet: {receipt['ticket_code']}"))
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
    out.append(sep)
    out.append(_center("Gràcies per la seva visita"))

    return "\n".join(out)

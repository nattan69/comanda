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

from ..models.models import Center, Establishment, Order, Payment, Staff, Table, Void

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
        # La clau inclou la RONDA (comanda_number): el tiquet de servei ha de
        # poder mostrar només el que s'ha demanat ARA (decisió Tomeu 14/09/2026).
        ronda = int(getattr(it, "comanda_number", 1) or 1)
        key = (name, str(unit_price), ronda)
        if key not in lines:
            lines[key] = {
                "name": name,
                "quantity": 0,
                "unit_price": str(unit_price),
                "total": Decimal("0"),
                "comanda_number": ronda,
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


def build_void_receipt(db: Session, void_id) -> dict:
    """Tiquet d'anul·lació: el tiquet original marcat «ANUL·LAT» + motiu.

    Es genera per adjuntar amb l'original (que queda barrat en diagonal) quan
    un cap autoritza una anul·lació.
    """
    void = db.get(Void, void_id)
    if not void:
        raise ValueError("Anul·lació no trobada.")

    receipt = build_receipt(db, void.order_id)
    receipt["type"] = "void"
    receipt["mark"] = "void"
    receipt["void"] = {
        "ticket_code": void.ticket_code or "",
        "amount": str(void.amount),
        "reason": void.reason or "",
        "authorized_by_id": str(void.authorized_by_id) if void.authorized_by_id else None,
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

    # DATA I HORA d'emissió (decisió Tomeu 14/09/2026): tots els tiquets en duen,
    # tant en imprimir com en cobrar. Es formata en hora local del servei.
    if h.get("issued_at"):
        try:
            from datetime import datetime as _dt
            _iso = str(h["issued_at"])
            _quan = _dt.fromisoformat(_iso.replace("Z", "+00:00"))
            _local = _quan.astimezone()
            out.append(_center(_local.strftime("%d/%m/%Y  %H:%M:%S")))
        except Exception:
            out.append(_center(str(h["issued_at"])))
    out.append(sep)

    # Marca ben visible (anul·lat / còpia)
    mark = receipt.get("mark")
    if mark == "void":
        out.append(_center("*** ANUL·LAT ***"))
        out.append("")
    elif mark == "copy":
        out.append(_center("*** CÒPIA ***"))
        out.append("")

    # Identificació del tiquet
    code = (payment.get("ticket_code") or receipt.get("ticket_code") or "")
    if code:
        out.append(_center(f"Tiquet: {code}"))
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

    # Informació de l'anul·lació (si n'hi ha)
    void_info = receipt.get("void")
    if void_info:
        out.append(sep)
        out.append(_center(f"ANUL·LACIÓ: {_money(void_info.get('amount', '0'))} €"))
        out.append(_center(f"Motiu: {void_info.get('reason') or '-'}"))

    out.append(sep)
    out.append(_center("Gràcies per la seva visita"))

    return "\n".join(out)


# ============================================================
# ESC/POS — impressió real per a impressora tèrmica
# ============================================================

def _encode_escpos(text: str) -> bytes:
    """Codifica una línia per a ESC/POS.

    Les impressores tèrmiques no entenen UTF-8 pels accents: es fa servir
    CP858 (CP850 + símbol €), que cobreix els caràcters catalans (à, è, í, ò,
    ú, ç, l·l) i l'euro. Els caràcters que no hi caben es substitueixen.
    """
    return text.encode("cp858", errors="replace")


def render_receipt_escpos(receipt: dict) -> bytes:
    """Genera els bytes ESC/POS del tiquet per a impressora tèrmica de 80 mm.

    Aplica negreta a les línies importants (total, marca ANUL·LAT/CÒPIA),
    codifica en CP858 i tanca amb un tall de paper automàtic.
    """
    text = render_receipt_text(receipt)
    out = bytearray()
    out += b"\x1b@"  # ESC @ → inicialitza la impressora

    for line in text.split("\n"):
        stripped = line.strip()
        is_bold = (
            stripped.startswith("TOTAL")
            or "ANUL·LAT" in stripped
            or "CÒPIA" in stripped
        )
        out += b"\x1b\x45\x01" if is_bold else b"\x1b\x45\x00"  # ESC E n → negreta
        out += _encode_escpos(line)
        out += b"\n"

    out += b"\x1b\x45\x00"        # negreta OFF
    out += b"\n" * 4               # feed final (espai abans del tall)
    out += b"\x1d\x56\x42\x00"    # GS V → tall parcial de paper
    return bytes(out)


# ============================================================
# TIQUET DE SERVEI (per portar a taula) — decisió Tomeu 14/09/2026
# ============================================================
# NO porta dades fiscals (ni NIF, ni raó social, ni desglossament d'IVA):
# només és el paper que el cambrer duu a la taula per confirmar la comanda.
# Conté: nom del departament · nº de comanda (ronda) · SALDO ANTERIOR ·
# desglossament de la comanda actual · cambrer · import de la comanda.

def build_service_slip(db: Session, order_id, inclou_anterior: bool = True) -> dict:
    """Tiquet de servei de la comanda actual d'una taula.

    Si `inclou_anterior` i la taula ja tenia consumicions d'una ronda anterior
    sense pagar, s'hi afegeix el SALDO ANTERIOR i el total acumulat.
    """
    order = db.get(Order, order_id)
    if not order:
        raise ValueError("Comanda no trobada.")

    center = db.get(Center, order.center_id) if order.center_id else None
    staff = db.get(Staff, order.staff_id) if order.staff_id else None
    table = db.get(Table, order.table_id) if order.table_id else None

    # línies NOMÉS d'aquesta ronda
    ronda = int(getattr(order, "comanda_number", 1) or 1)
    linies = [
        l for l in _build_lines(order)
        if int(l.get("comanda_number") or ronda) == ronda
    ]
    importe = sum((Decimal(str(l["total"])) for l in linies), Decimal("0"))

    # saldo anterior: les rondes anteriors del MATEIX compte de taula
    saldo_anterior = Decimal("0")
    comandes_anteriors = 0
    if inclou_anterior and order.table_id:
        anteriors = (
            db.query(Order)
            .filter(
                Order.table_id == order.table_id,
                Order.id != order.id,
                Order.status.notin_(["paid", "cancelled", "closed"]),
            )
            .all()
        )
        for o in anteriors:
            if int(getattr(o, "comanda_number", 1) or 1) < ronda:
                saldo_anterior += Decimal(str(o.total_amount or 0))
                comandes_anteriors += 1

    return {
        "type": "servei",
        "comanda_number": ronda,
        "table_number": table.number if table else None,
        "center": {"name": center.name} if center else None,
        "staff_name": staff.full_name if staff else None,
        "issued_at": (order.opened_at or datetime.now(timezone.utc)).isoformat(),
        "lines": linies,
        "importe_comanda": float(importe),
        "saldo_anterior": float(saldo_anterior),
        "comandes_anteriors": comandes_anteriors,
        "total_acumulat": float(importe + saldo_anterior),
    }


def render_service_slip_text(slip: dict) -> str:
    """Text pla (80 mm) del tiquet de SERVEI — sense dades fiscals."""
    out = []
    sep = "-" * LINE_WIDTH
    center = slip.get("center") or {}

    if center.get("name"):
        out.append(_center(str(center["name"]).upper()))
    out.append(_center("*** COMANDA (sense valor fiscal) ***"))
    out.append(sep)

    out.append(f"Comanda nº: {slip.get('comanda_number', 1)}")
    if slip.get("table_number") is not None:
        out.append(f"Taula: {slip['table_number']}")
    if slip.get("staff_name"):
        out.append(f"Cambrer: {slip['staff_name']}")
    if slip.get("issued_at"):
        try:
            from datetime import datetime as _dt
            _q = _dt.fromisoformat(str(slip["issued_at"]).replace("Z", "+00:00")).astimezone()
            out.append(f"Data: {_q.strftime('%d/%m/%Y %H:%M:%S')}")
        except Exception:
            out.append(f"Data: {slip['issued_at']}")
    out.append(sep)

    # SALDO ANTERIOR (les rondes que ja hi havia a la taula)
    if slip.get("saldo_anterior"):
        out.append(f"Saldo anterior ({slip.get('comandes_anteriors', 0)} com.):")
        out.append(f"{'':>{LINE_WIDTH - 12}}{slip['saldo_anterior']:>10.2f} EUR")
        out.append(sep)

    out.append("COMANDAT ARA:")
    for l in slip.get("lines", []):
        nom = str(l.get("name") or "")
        qty = l.get("quantity", 1)
        import_linia = Decimal(str(l.get("total") or 0))
        capcalera = f"{qty} x {nom}"
        out.append(capcalera if len(capcalera) <= LINE_WIDTH - 12 else capcalera[:LINE_WIDTH - 12])
        out.append(f"{'':>{LINE_WIDTH - 12}}{import_linia:>10.2f} EUR")
    out.append(sep)

    out.append(f"{'IMPORT COMANDA:':<{LINE_WIDTH - 12}}{slip['importe_comanda']:>10.2f} EUR")
    if slip.get("saldo_anterior"):
        out.append(f"{'TOTAL A LA TAULA:':<{LINE_WIDTH - 12}}{slip['total_acumulat']:>10.2f} EUR")
    out.append(sep)
    out.append(_center("Sense valor fiscal — porteu-lo a taula"))
    return "\n".join(out) + "\n"


def render_service_slip_escpos(slip: dict) -> bytes:
    """Bytes ESC/POS del tiquet de servei (per a la impressora del departament)."""
    return _escpos_from_text(render_service_slip_text(slip))


def _escpos_from_text(text: str) -> bytes:
    """Emboleall ESC/POS mínim: init + text + tall."""
    out = bytearray()
    out += b"\x1b@"          # init
    for linia in text.split("\n"):
        out += _encode_escpos(linia) + b"\n"
    out += b"\n\n\n"
    out += b"\x1dV\x00"      # tall de paper
    return bytes(out)

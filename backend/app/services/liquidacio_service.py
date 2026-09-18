"""
DOCUMENTS DE LIQUIDACIÓ DEL CAMBRER — paper imprimible (decisió Tomeu 18/09/2026).

Sort que el cambrer tanca el torn i li demana el paper per ficar DINS EL SOBRE
amb els doblers i els justificants. Per això són DOS DOCUMENTS SEPARATS, tots
dos amb requadre de signatura:

  1. **LIQUIDACIÓ DEL CAMBRER** (`build_liquidacio_cambrer`)
     El full que signa el cambrer: efectiu esperat, efectiu entregat, errors
     que assumeix, desquadre, i el desglossament del que va dins el sobre
     (efectiu, nuls, invitacions, crèdits, targetes).

  2. **FULL DE MOVIMENTS** (`build_full_moviments_cambrer`)
     Justificants línia a línia: cada tiquet de venda amb el seu mètode, i
     cada NUL / INVITACIÓ / CRÈDIT amb la seva referència i motiu — perquè
     l'encarregat pugui comprovar el que hi ha al sobre.

  3. **Z / LIQUIDACIÓ DEL CENTRE** (`build_liquidacio_centre`)
     El full que repassa i firma l'ENCARREGAT: la liquidació de TOTS els
     cambrers del centre, amb els torns oberts remarcats.

IMPORTANT (per què no es fa servir el tiquet genèric): aquests fulls porten
línies de signatura, i el renderitzador de tiquets posa en NEGRETA qualsevol
línia que comenci per "TOTAL" — se'n menjaria els punts de signatura. Aquí es
fan servir les mateixes primitives (_center, _money, _encode_escpos) però amb
el seu propi renderitzador.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models.models import Center, Establishment, Payment, Shift, Staff, Void, Order

LINE_WIDTH = 48

#: Mètodes que NO són venda real: van al sobre com a justificants, no a caixa.
NON_SALE_METHODS = {"house", "anul", "null"}

#: Etiquetes de mètode per al paper.
ETIQUETES = {
    "cash": "Efectiu",
    "card": "Targeta",
    "room_charge": "Crèdit habitació",
    "bizum": "Bizum",
    "house": "Invitació",
    "anul": "NUL",
    "split": "Pagament dividit",
}


def _money(value) -> str:
    """Import amb coma decimal i 2 decimals (format del país)."""
    try:
        return f"{Decimal(str(value or 0)):.2f}".replace(".", ",")
    except Exception:
        return "0,00"


def _euros(value) -> str:
    return f"{_money(value)} EUR"


def _center(text: str) -> str:
    return text.center(LINE_WIDTH).rstrip()


def _dues(esq: str, dre: str) -> str:
    """Línia amb text a l'esquerra i import a la dreta (amplada 80 mm)."""
    espai = max(1, LINE_WIDTH - len(esq) - len(dre))
    return f"{esq}{' ' * espai}{dre}"


def _talla(text: str, ample: int) -> str:
    """Retalla un text a l'amplada indicada (per a columnes de la tèrmica)."""
    t = (text or "").strip()
    return t if len(t) <= ample else t[: ample - 1] + "."


def _linia(ch: str = "-") -> str:
    return ch * LINE_WIDTH


def _requadre_signatura(qui: str, etiqueta: str) -> list:
    """Requadre de signatura imprès (el full es firma i va dins el sobre).

    ⚠️ TOTES les línies han de capir dins l'amplada de la tèrmica (48 caràcters
    a 80 mm). Les línies de punts es calculen, no es posen a mà: si es posen a
    mà, se surt de la ratlla i la impressora les talla (catch 18/09/2026).
    """
    def _punts(etiqueta_text: str, ample: int = LINE_WIDTH) -> str:
        """Etiqueta + punts per omplir fins a l'amplada de la tèrmica."""
        return etiqueta_text + "." * max(3, ample - len(etiqueta_text))

    return [
        "",
        _linia("."),
        f"  {etiqueta}",
        "",
        _punts("  Nom i llinatges: "),
        "",
        _punts("  Signatura: "),
        "",
        # Data i hora: les dues caselles han de cabre dins la ratlla.
        _punts("  Data: ", 30) + "Hora: ......",
        "",
        f"  ({qui})" if qui else "",
        "",
    ]


# ============================================================
# 1. LIQUIDACIÓ DEL CAMBRER (el full que firma el cambrer)
# ============================================================
def build_liquidacio_cambrer(db: Session, shift_id) -> dict:
    """Construeix el full de liquidació d'un torn de cambrer.

    Porta el resum del torn, l'efectiu esperat/entregat, els errors que el
    cambrer assumeix, el desquadre, i el desglossament del que va al sobre
    (doblers, nuls, invitacions, crèdits, targetes).
    """
    shift = db.get(Shift, shift_id)
    if not shift:
        raise ValueError("Torn no trobat.")

    staff = db.get(Staff, shift.staff_id)
    centre = db.get(Center, shift.center_id) if shift.center_id else None
    est = None
    if centre and getattr(centre, "establishment_id", None):
        est = db.get(Establishment, centre.establishment_id)

    liq = shift.liquidation or {}

    # Moviments del torn: els tiquets amb el seu mètode (els justificants del sobre)
    comandes = (
        db.query(Order)
        .filter(Order.shift_id == shift.id, Order.status == "paid")
        .order_by(Order.closed_at.asc())
        .all()
    )
    moviments = []
    for o in comandes:
        pagaments = db.query(Payment).filter(Payment.order_id == o.id).all()
        metodes = [(p.method or "").strip().lower() for p in pagaments]
        principal = metodes[0] if metodes else ""
        moviments.append({
            "ticket_code": o.ticket_code or "",
            "hora": o.closed_at.strftime("%H:%M") if o.closed_at else "",
            "taula": None,
            "import": str(o.total_amount or 0),
            "metode": principal,
            "etiqueta": ETIQUETES.get(principal, principal or "—"),
            "es_venda": principal not in NON_SALE_METHODS,
            "room_number": o.room_number,
            "motiu": next((p.reason for p in pagaments if p.reason), None) or o.notes,
        })

    nuls = [m for m in moviments if m["metode"] in ("anul", "null")]
    invitacions = [m for m in moviments if m["metode"] == "house"]
    credits = [m for m in moviments if m["metode"] == "room_charge"]
    targetes = [m for m in moviments if m["metode"] == "card"]
    efectiu = [m for m in moviments if m["metode"] == "cash"]

    def _suma(rows) -> Decimal:
        return sum((Decimal(str(r["import"] or 0)) for r in rows), Decimal("0"))

    per_bons = liq.get("per_bons") or {}
    obertes = (liq.get("obertes") or {})

    return {
        "document": "liquidacio-cambrer",
        "shift_id": str(shift.id),
        "establiment": {
            "name": est.name if est else None,
            "legal_name": est.legal_name if est else None,
            "nif": est.nif if est else None,
        },
        "centre": centre.name if centre else None,
        "cambrer": staff.full_name if staff else "—",
        "obert": shift.opened_at.isoformat() if shift.opened_at else None,
        "tancat": shift.closed_at.isoformat() if shift.closed_at else None,
        "obert_hora": shift.opened_at.strftime("%H:%M") if shift.opened_at else "",
        "tancat_hora": shift.closed_at.strftime("%H:%M") if shift.closed_at else "",
        "venda": liq.get("gross_sales", "0"),
        "comandes_count": liq.get("orders_count", 0),
        "efectiu_esperat": liq.get("cash_expected", "0"),
        "efectiu_entregat": liq.get("cash_declared"),
        "efectiu_declarat": str(_suma(efectiu)),
        "errors": liq.get("errors", "0"),
        "desquadre": liq.get("desquadre"),
        "desquadre_pendent": liq.get("desquadre_pendent"),
        "observacions": liq.get("observations"),
        # === DESGLOSSAMENT DEL SOBRE ===
        "sobre": {
            "doblers": {
                "count": len(efectiu),
                "total": str(_suma(efectiu)),
                "items": efectiu,
            },
            "nuls": {"count": len(nuls), "total": str(_suma(nuls)), "items": nuls},
            "invitacions": {
                "count": len(invitacions),
                "total": str(_suma(invitacions)),
                "items": invitacions,
            },
            "credits": {"count": len(credits), "total": str(_suma(credits)), "items": credits},
            "targetes": {"count": len(targetes), "total": str(_suma(targetes)), "items": targetes},
        },
        # PER BONS: els certifica Jornada; no es compten a mà
        "per_bons": {
            "targeta_credit": per_bons.get("targeta_credit", "0"),
            "carrec_habitacio": per_bons.get("carrec_habitacio", "0"),
            "total": per_bons.get("total", "0"),
        },
        "obertes": obertes,
        "moviments": moviments,
    }


def render_liquidacio_cambrer_text(doc: dict) -> str:
    """Full de liquidació del cambrer en text pla (80 mm), amb signatura."""
    o = []
    est = doc.get("establiment") or {}
    o.append(_center(est.get("name") or "—"))
    if est.get("nif"):
        o.append(_center(f"NIF {est['nif']}"))
    o.append(_center(f"Punt de venda: {doc.get('centre') or '—'}"))
    o.append(_linia("="))
    o.append(_center("LIQUIDACIO DEL CAMBRER"))
    o.append(_linia("="))
    o.append(f"Cambrer : {doc.get('cambrer')}")
    o.append(f"Torn    : {doc.get('obert_hora')} -> {doc.get('tancat_hora')}")
    o.append(f"Data    : {_data_llegible(doc.get('tancat') or doc.get('obert'))}")
    o.append(_linia())

    o.append(_center("RESUM DEL TORN"))
    o.append(_dues("Venda del torn", _euros(doc.get("venda"))))
    o.append(_dues("Comandes", str(doc.get("comandes_count", 0))))
    if doc.get("per_bons"):
        o.append(_dues("Targetes (per bons)", _euros(doc["per_bons"].get("targeta_credit"))))
        o.append(_dues("Credits habitacio (per bons)", _euros(doc["per_bons"].get("carrec_habitacio"))))
    o.append(_linia())

    o.append(_center("CAIXA"))
    o.append(_dues("Efectiu esperat", _euros(doc.get("efectiu_esperat"))))
    o.append(_dues("Efectiu ENTREGAT", _euros(doc.get("efectiu_entregat"))))
    o.append(_dues("Errors assumits", _euros(doc.get("errors"))))
    o.append(_dues("Desquadre", _euros(doc.get("desquadre"))))
    o.append(_dues("DESQUADRE PENDENT", _euros(doc.get("desquadre_pendent"))))
    o.append(_linia())

    s = doc.get("sobre") or {}
    o.append(_center("CONTINGUT DEL SOBRE"))
    for clau, nom in (
        ("doblers", "Doblers (efectiu)"),
        ("nuls", "Nuls"),
        ("invitacions", "Invitacions"),
        ("credits", "Credits habitacio"),
        ("targetes", "Targetes"),
    ):
        bloc = s.get(clau) or {}
        o.append(_dues(f"{nom} ({bloc.get('count', 0)})", _euros(bloc.get("total"))))
    o.append(_linia())

    # Detall dels justificants no-venda (els que acompanyen el sobre)
    for clau, nom in (("nuls", "NULS"), ("invitacions", "INVITACIONS"),
                      ("credits", "CREDITS A HABITACIO")):
        bloc = s.get(clau) or {}
        if not bloc.get("items"):
            continue
        o.append(_center(nom))
        for m in bloc["items"]:
            ref = m.get("ticket_code") or "-"
            o.append(_dues(f"{ref} {m.get('hora') or ''}", _euros(m.get("import"))))
            if m.get("motiu"):
                o.append(f"   motiu: {m['motiu']}")
            if m.get("room_number"):
                o.append(f"   habitacio: {m['room_number']}")
        o.append(_linia())

    if doc.get("observacions"):
        o.append(f"Observacions: {doc['observacions']}")
        o.append(_linia())

    ob = doc.get("obertes") or {}
    if (ob.get("count") or 0) > 0:
        o.append(_center("*** ATENCIO: COMANDES SENSE COBRAR ***"))
        o.append(f"  {ob.get('count')} comanda(es) obertes per {_euros(ob.get('total'))}")
        for it in (ob.get("items") or []):
            o.append(f"   - comanda {it.get('comanda_number')}: {_euros(it.get('total'))}")
        o.append(_linia())

    o += _requadre_signatura(doc.get("cambrer") or "", "Firma del cambrer (conforme)")
    return "\n".join(o)


# ============================================================
# 2. FULL DE MOVIMENTS (els justificants, línia a línia)
# ============================================================
def build_full_moviments_cambrer(db: Session, shift_id) -> dict:
    """Full de moviments del torn: cada tiquet amb el seu mètode.

    És el paper que acompanya els justificants dins el sobre (nuls,
    invitacions, crèdits, targetes) perquè l'encarregat ho comprovi tot.
    """
    doc = build_liquidacio_cambrer(db, shift_id)
    return {
        "document": "full-moviments-cambrer",
        "shift_id": doc["shift_id"],
        "establiment": doc["establiment"],
        "centre": doc["centre"],
        "cambrer": doc["cambrer"],
        "data": doc.get("tancat") or doc.get("obert"),
        "moviments": doc["moviments"],
        "sobre": doc["sobre"],
        "per_bons": doc["per_bons"],
        "obertes": doc["obertes"],
    }


def render_full_moviments_cambrer_text(doc: dict) -> str:
    """Full de moviments en text pla (80 mm)."""
    o = []
    est = doc.get("establiment") or {}
    o.append(_center(est.get("name") or "—"))
    o.append(_center(f"Punt de venda: {doc.get('centre') or '—'}"))
    o.append(_linia("="))
    o.append(_center("FULL DE MOVIMENTS DEL TORN"))
    o.append(_linia("="))
    o.append(f"Cambrer : {doc.get('cambrer')}")
    o.append(f"Data    : {_data_llegible(doc.get('data'))}")
    o.append(_linia())
    o.append(_dues("Tiquet   Hora", "Import    Metode"))
    o.append(_linia())

    for m in doc.get("moviments") or []:
        ref = (m.get("ticket_code") or "-")[:12]
        hora = (m.get("hora") or "")[:5]
        etq = (m.get("etiqueta") or "")[:14]
        o.append(f"{ref:<12} {hora:<5} {_money(m.get('import')):>8}  {etq}")
        extra = []
        if m.get("room_number"):
            extra.append(f"habitacio {m['room_number']}")
        if m.get("motiu"):
            extra.append(m["motiu"])
        if extra:
            o.append(f"    ({'; '.join(extra)})")

    if not (doc.get("moviments") or []):
        o.append(_center("(sense moviments)"))

    o.append(_linia())
    o.append(_center("TOTALITZAT PER METODE"))
    for clau, nom in (
        ("doblers", "Efectiu"),
        ("targetes", "Targetes"),
        ("credits", "Credits habitacio"),
        ("invitacions", "Invitacions"),
        ("nuls", "Nuls"),
    ):
        bloc = (doc.get("sobre") or {}).get(clau) or {}
        o.append(_dues(f"{nom} ({bloc.get('count', 0)})", _euros(bloc.get("total"))))
    o.append(_linia())
    o += _requadre_signatura(doc.get("cambrer") or "", "Firma del cambrer (conforme)")
    return "\n".join(o)


# ============================================================
# 3. LIQUIDACIÓ DEL CENTRE (el full que firma l'ENCARREGAT)
# ============================================================
def build_liquidacio_centre(db: Session, closure_date: date) -> dict:
    """Full de liquidació de TOTS els cambrers del centre per a l'encarregat.

    És el document que repassa i firma l'encarregat amb la Z. Inclou els torns
    oberts (els que fan que la caixa no quadri).
    """
    from .closure_service import _liquidacions_de_cambrers

    dades = _liquidacions_de_cambrers(db, closure_date)
    est = db.query(Establishment).first()
    centres = db.query(Center).all()
    return {
        "document": "liquidacio-centre",
        "data": closure_date.isoformat(),
        "establiment": {
            "name": est.name if est else None,
            "legal_name": est.legal_name if est else None,
            "nif": est.nif if est else None,
        },
        "centres": [c.name for c in centres],
        **dades,
    }


def render_liquidacio_centre_text(doc: dict) -> str:
    """Full de liquidació del centre en text pla, amb signatura de l'encarregat."""
    o = []
    est = doc.get("establiment") or {}
    o.append(_center(est.get("name") or "—"))
    if est.get("nif"):
        o.append(_center(f"NIF {est['nif']}"))
    o.append(_center(f"Data de negoci: {_data_llegible(doc.get('data'))}"))
    o.append(_linia("="))
    o.append(_center("LIQUIDACIO DELS CAMBRERS"))
    o.append(_linia("="))
    o.append("Cambrer            E. esperat  Entregat  Pendent  Per bons")
    o.append(_linia())

    for c in doc.get("cambrers") or []:
        nom = _talla(c.get("staff_name") or "-", 18)
        o.append(
            f"{nom:<18} {_money(c.get('efectiu_esperat')):>9} "
            f"{_money(c.get('efectiu_entregat')):>9} "
            f"{_money(c.get('desquadre_pendent')):>8} "
            f"{_money((c.get('per_bons') or {}).get('total')):>9}"
        )
        if c.get("observacions"):
            o.append(f"    ({c['observacions']})")

    if not (doc.get("cambrers") or []):
        o.append(_center("(cap torn tancat)"))

    o.append(_linia())
    o.append(_dues("TOTAL EFECTIU ESPERAT", _euros(doc.get("total_efectiu_esperat"))))
    o.append(_dues("TOTAL EFECTIU ENTREGAT", _euros(doc.get("total_efectiu_entregat"))))
    o.append(_dues("TOTAL ERRORS", _euros(doc.get("total_errors"))))
    o.append(_dues("TOTAL DESQUADRE PENDENT", _euros(doc.get("total_desquadre_pendent"))))
    o.append(_linia())

    if (doc.get("count_oberts") or 0) > 0:
        o.append(_center("*** TORNS SENSE TANCAR ***"))
        o.append(f"  {doc.get('count_oberts')} cambrer(s), "
                 f"{_euros(doc.get('total_obert_efectiu_esperat'))} d'efectiu sense entregar")
        for t in doc.get("torns_oberts") or []:
            o.append(f"   - {t.get('staff_name')} ({_euros(t.get('efectiu_esperat'))})")
        o.append(_linia())

    o += _requadre_signatura("", "Firma de l'encarregat (revisat i conforme)")
    return "\n".join(o)


def _data_llegible(iso) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        return str(iso)[:10]


# ============================================================
# 4. LA Z — el TIQUET de tancament, amb les liquidacions a sota
# ============================================================
# Va a la MATEIXA impressora tèrmica de tiquets que tot lo demás (80 mm,
# ESC/POS). Per això totes les línies van dins els 48 caràcters d'amplada i
# sense caràcters estranys: el renderitzador els codifica en CP858.
#
# Ordre del tiquet: capçalera fiscal → resum de caixa del dia → desglossament
# per mètodes i famílies → NULS i INVITACIONS detallats → **LIQUIDACIÓ DE TOTS
# ELS CAMBRERS** (perquè l'encarregat la repassi i la firmi) → Z número i
# signatura.

# ============================================================
# 5. LA X — el TIQUET de pre-tancament (es pot treure tantes vegades com calgui)
# ============================================================
# Mateixa impressora tèrmica de 80 mm. La diferència amb la Z:
#   · NO tanca res: és una LECTURA. Es pot treure totes les vegades que calgui.
#   · Porta els TORNS ENCARA OBERTS com a avís (la Z ja els hauria de tenir
#     tancats o marcats).
# Serveix perquè l'encarregat repassi les liquidacions dels cambrers ABANS de
# fer el tancament definitiu (decisió Tomeu 18/09/2026).

def render_x_text(closure_date, summary: dict) -> str:
    """La X en text pla (80 mm), amb les liquidacions dels cambrers incloses."""
    s = summary or {}
    o = []

    o.append(_linia("="))
    o.append(_center("INFORME X - PRE-TANCAMENT"))
    o.append(_center("(NO tanca el dia)"))
    o.append(_linia("="))
    o.append(f"Data de negoci : {_data_llegible(closure_date)}")

    # --- VENDA DEL DIA ---
    o.append(_linia())
    o.append(_center("RESUM DEL DIA"))
    o.append(_dues("Venda bruta", _euros(s.get("gross_sales"))))
    o.append(_dues("Descomptes", _euros(s.get("discounts_total"))))
    o.append(_dues("Venda neta", _euros(s.get("net_sales"))))
    o.append(_dues("Comandes", str(sum((s.get("orders_by_type") or {}).values()))))

    # --- TOTALS PER METODE ---
    tm = s.get("totals_per_metode") or {}
    if tm:
        o.append(_linia())
        o.append(_center("TOTALS PER METODE"))
        for clau, nom in (
            ("efectiu", "Efectiu"),
            ("targeta_credit", "Targeta credit"),
            ("carrec_habitacio", "Carrec habitacio"),
            ("bizum", "Bizum"),
            ("invitacions", "Invitacions"),
            ("nuls", "Nuls"),
        ):
            o.append(_dues(nom, _euros(tm.get(clau))))

    # --- FAMILIES ---
    fam = s.get("by_family") or {}
    if fam:
        o.append(_linia())
        o.append(_center("TOTAL PER FAMILIES"))
        o.append(_dues("Begudes", _euros(fam.get("begudes"))))
        o.append(_dues("Menjars", _euros(fam.get("menjars"))))
        o.append(_dues("Varis", _euros(fam.get("varis"))))
        o.append(_dues("TOTAL", _euros(s.get("by_family_total"))))

    # --- NULS (nº tiquet + import) ---
    nuls = s.get("nuls") or {}
    if nuls.get("count"):
        o.append(_linia())
        o.append(_center("NULS"))
        for n in (nuls.get("items") or []):
            o.append(_dues(n.get("ticket_code") or "-", _euros(n.get("amount"))))
        o.append(_dues(f"TOTAL NULS ({nuls.get('count')})", _euros(nuls.get("total"))))

    # --- INVITACIONS ---
    h = s.get("house") or {}
    if h.get("orders"):
        o.append(_linia())
        o.append(_center("INVITACIONS"))
        o.append(_dues(f"{h.get('orders')} invitacio(ns)", _euros(h.get("total"))))

    # --- COMANDES SENSE COBRAR (a la X és el més important: encara són obertes) ---
    pend = s.get("open_orders") or s.get("pending_charges") or {}
    if pend.get("count"):
        o.append(_linia())
        o.append(_center("*** COMANDES SENSE COBRAR ***"))
        o.append(_dues(f"{pend.get('count')} comanda(es)", _euros(pend.get("total"))))
        for it in (pend.get("items") or []):
            o.append(f"   {(it.get('ticket_code') or it.get('order_id') or '')[:20]}"
                     f"  {_euros(it.get('total'))}")

    # === LIQUIDACIÓ DE TOTS ELS CAMBRERS (el que repassa l'encarregat) ===
    o += _bloc_liquidacions_cambrers(s)

    o += _requadre_signatura("", "Firma de l'encarregat (revisat i conforme)")
    return "\n".join(o)


def _bloc_liquidacions_cambrers(s: dict) -> list:
    """Bloc compartit (X i Z): la taula de liquidacions dels cambrers + avisos."""
    o = []
    lc = s.get("liquidacions_cambrers") or {}
    o.append(_linia("="))
    o.append(_center("LIQUIDACIO DELS CAMBRERS"))
    o.append(_linia("="))
    if not lc.get("count"):
        o.append(_center("(cap torn tancat)"))
    else:
        o.append("Cambrer            Esperat Entregat Pendent")
        o.append(_linia())
        for c in lc.get("cambrers") or []:
            nom = _talla(c.get("staff_name") or "-", 18)
            o.append(
                f"{nom:<18} {_money(c.get('efectiu_esperat')):>7} "
                f"{_money(c.get('efectiu_entregat')):>8} "
                f"{_money(c.get('desquadre_pendent')):>7}"
            )
            if c.get("observacions"):
                o.append(f"   ({_talla(c['observacions'], 42)})")
        o.append(_linia())
        o.append(_dues("TOTAL ESPERAT", _euros(lc.get("total_efectiu_esperat"))))
        o.append(_dues("TOTAL ENTREGAT", _euros(lc.get("total_efectiu_entregat"))))
        o.append(_dues("TOTAL ERRORS", _euros(lc.get("total_errors"))))
        o.append(_dues("TOTAL PENDENT", _euros(lc.get("total_desquadre_pendent"))))

    if lc.get("count_oberts"):
        o.append(_linia())
        o.append(_center("*** TORNS SENSE TANCAR ***"))
        o.append(f"  {lc.get('count_oberts')} cambrer(s) - "
                 f"{_euros(lc.get('total_obert_efectiu_esperat'))} sense entregar")
        for t in (lc.get("torns_oberts") or []):
            o.append(f"   - {_talla(t.get('staff_name') or '', 40)}")
    return o


def render_z_text(closure) -> str:
    """La Z en text pla (80 mm) amb les liquidacions dels cambrers incloses."""
    s = (closure.summary or {}) if hasattr(closure, "summary") else (closure or {})
    s = s or {}
    z_number = s.get("z_number") or ""
    o = []

    o.append(_linia("="))
    o.append(_center("TANCAMENT DE CAIXA - Z"))
    if z_number:
        o.append(_center(z_number))
    o.append(_linia("="))
    o.append(f"Data de negoci : {_data_llegible(getattr(closure, 'closure_date', None) or s.get('closure_date'))}")

    # --- VENDA DEL DIA ---
    o.append(_linia())
    o.append(_center("RESUM DEL DIA"))
    o.append(_dues("Venda bruta", _euros(s.get("gross_sales"))))
    o.append(_dues("Descomptes", _euros(s.get("discounts_total"))))
    o.append(_dues("Venda neta", _euros(s.get("net_sales"))))
    o.append(_dues("Comandes", str(sum((s.get("orders_by_type") or {}).values()))))

    # --- TOTALS PER METODE ---
    tm = s.get("totals_per_metode") or {}
    if tm:
        o.append(_linia())
        o.append(_center("TOTALS PER METODE"))
        for clau, nom in (
            ("efectiu", "Efectiu"),
            ("targeta_credit", "Targeta credit"),
            ("carrec_habitacio", "Carrec habitacio"),
            ("bizum", "Bizum"),
            ("invitacions", "Invitacions"),
            ("nuls", "Nuls"),
        ):
            o.append(_dues(nom, _euros(tm.get(clau))))

    # --- FAMILIES ---
    fam = s.get("by_family") or {}
    if fam:
        o.append(_linia())
        o.append(_center("TOTAL PER FAMILIES"))
        o.append(_dues("Begudes", _euros(fam.get("begudes"))))
        o.append(_dues("Menjars", _euros(fam.get("menjars"))))
        o.append(_dues("Varis", _euros(fam.get("varis"))))
        o.append(_dues("TOTAL", _euros(s.get("by_family_total"))))

    # --- IVA ---
    if s.get("vat_breakdown"):
        o.append(_linia())
        o.append(_center("DESGLOSSAMENT IVA"))
        for v in s["vat_breakdown"]:
            o.append(_dues(f"Base {v.get('rate')}%", _euros(v.get("base"))))
            o.append(_dues(f"  Quota {v.get('rate')}%", _euros(v.get("tax"))))

    # --- NULS (nº tiquet + import) ---
    nuls = s.get("nuls") or {}
    if nuls.get("count"):
        o.append(_linia())
        o.append(_center("NULS"))
        for n in (nuls.get("items") or []):
            o.append(_dues(n.get("ticket_code") or "-", _euros(n.get("amount"))))
        o.append(_dues(f"TOTAL NULS ({nuls.get('count')})", _euros(nuls.get("total"))))

    # --- INVITACIONS ---
    h = s.get("house") or {}
    if h.get("orders"):
        o.append(_linia())
        o.append(_center("INVITACIONS"))
        o.append(_dues(f"{h.get('orders')} invitacio(ns)", _euros(h.get("total"))))

    # --- ANUL·LACIONS ---
    v = s.get("voids") or {}
    if v.get("count"):
        o.append(_linia())
        o.append(_center("ANUL·LACIONS"))
        for it in (v.get("items") or []):
            o.append(_dues(it.get("ticket_code") or "-", _euros(it.get("amount"))))
        o.append(_dues(f"TOTAL ({v.get('count')})", _euros(v.get("total"))))

    # --- COMANDES SENSE COBRAR ---
    pend = s.get("pending_charges") or s.get("open_orders") or {}
    if pend.get("count"):
        o.append(_linia())
        o.append(_center("*** COMANDES SENSE COBRAR ***"))
        o.append(_dues(f"{pend.get('count')} comanda(es)", _euros(pend.get("total"))))

    # === LIQUIDACIÓ DE TOTS ELS CAMBRERS (el que repassa l'encarregat) ===
    o += _bloc_liquidacions_cambrers(s)

    o += _requadre_signatura("", "Firma de l'encarregat (revisat i conforme)")
    return "\n".join(o)


def _escpos_from_text(text: str) -> bytes:
    """Emboleall ESC/POS: init + text + tall (renderitzador PROPI).

    No es fa servir el genèric de tiquets perquè aquest posa en negreta qualsevol
    línia que comenci per "TOTAL" — i aquí n'hi ha que són línies de signatura.
    """
    from .receipt_service import _encode_escpos

    out = bytearray()
    out += b"\x1b@"          # init
    for linia in text.split("\n"):
        out += _encode_escpos(linia) + b"\n"
    out += b"\n\n\n"
    out += b"\x1d\x56\x00"   # tall de paper
    return bytes(out)


def render_escpos(text: str) -> bytes:
    """Bytes ESC/POS d'un full (per a la impressora de xarxa/USB)."""
    return _escpos_from_text(text)

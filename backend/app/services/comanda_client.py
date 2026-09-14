# Enviament del tancament de caixa del TPV (Comanda) → Compta (hub comptable).
# Mateix patró que Estada (services/compta_client.py): Compta és l'hub; Comanda
# EMET el tancament de caixa diari (Z) i no guarda comptabilitat pròpia.
# Idempotent per external_id ("comanda-cierre-<data>"): Compta no duplica.
# API key: COMPTA_KEY_COMANDA (X-API-Key) → endpoint /api/v1/intake/comanda.
#
# Mapping PGC (ratificat contra el PGC real):
#   cash → 570 (caixa)          card → 5730 (pont TPV)       bizum → 5720 (banc)
#   room_charge → 5730 (pont TPV: el TPV va fer el cobrament, Estada el reconcilia
#                        al foli del client via 4300 — el 5730 es neteja al consolidat)
#   ingressos → 7020 (ventes/restauració del TPV)
#   IVA repercutit → 4771
# NOTA: `house` (invitacions) NO es comptabilitza (fora de la Z, no es declara IVA).
import logging
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)

_METHOD_ACCOUNT = {
    "cash": "570",                   # caixa (euros)
    "efectiu": "570",
    "efectivo": "570",
    "card": "5730",                  # pont TPV (targeta)
    "targeta": "5730",
    "tarjeta": "5730",
    "bizum": "5720",                 # banc (transferència)
    "room_charge": "5730",           # pont TPV (el cobrament va via l'habitació)
    "room_charge_extra": "5730",
}


def envia_cierre_a_compta(
    *,
    external_id: str,
    date_str: str,
    concept: str,
    summary: dict,
) -> dict:
    """Envia el tancament de caixa diari (Z) a Compta com a assentament de CONTROL.

    Assentament EQUILIBRAT amb el compte pont (5730) SALDAT dins el mateix
    assentament:
    - DEURE: cobraments per mètode — cash→570 (caixa), card/room_charge→5730
      (pont), bizum→5720 (banc).
    - SALDAMENT del pont: card→5720 (banc) i room_charge→4300 (client), amb la
      contrapartida al 5730 perquè quedi a zero.
    - HAVER: ingressos 7020 + IVA repercutit 4771.
    El `house` queda fora (no es declara).
    """
    from ..config import settings

    url = settings.COMPTA_URL
    key = settings.COMPTA_KEY_COMANDA

    payments = summary.get("payments_by_method") or {}
    net_sales = Decimal(str(summary.get("net_sales") or 0))
    vat_total = Decimal("0")
    for v in summary.get("vat_breakdown") or []:
        vat_total += Decimal(str(v.get("tax") or 0))

    lines = []

    # 1) Deure: cobraments per mètode (house exclòs).
    card_total = Decimal("0")
    room_total = Decimal("0")
    for method, amount in payments.items():
        m = (method or "").strip().lower()
        if m in ("house", "invitacio", "invitación"):
            continue  # house no es declara
        amt = Decimal(str(amount or 0))
        if amt <= 0:
            continue
        if m in ("card", "targeta", "tarjeta"):
            card_total += amt
        elif m in ("room_charge", "room_charge_extra"):
            room_total += amt
        lines.append({
            "account": _METHOD_ACCOUNT.get(m, "5730"),
            "debit": str(amt),
            "credit": "0",
            "concept": f"Cobraments {m}",
        })

    # 2) Saldament del pont 5730: targetes → banc (5720), room_charge → client (4300).
    if card_total > 0:
        lines.append({"account": "5720", "debit": str(card_total), "credit": "0", "concept": "Liquidació targetes (pont → banc)"})
        lines.append({"account": "5730", "debit": "0", "credit": str(card_total), "concept": "Saldament pont TPV (targetes)"})
    if room_total > 0:
        lines.append({"account": "4300", "debit": str(room_total), "credit": "0", "concept": "Càrrec a habitació (pont → client)"})
        lines.append({"account": "5730", "debit": "0", "credit": str(room_total), "concept": "Saldament pont TPV (room charge)"})

    # 3) Haver: ingressos (base) + IVA repercutit.
    if net_sales > 0:
        lines.append({"account": "7020", "debit": "0", "credit": str(net_sales), "concept": "Ingressos TPV (base)"})
    if vat_total > 0:
        lines.append({"account": "4771", "debit": "0", "credit": str(vat_total), "concept": "IVA repercutit"})

    # 4) Ajust per arrodoniments (si cal), a un compte dedicat — MAI al pont 5730,
    # que ha de quedar saldat.
    debit_total = sum(Decimal(l["debit"]) for l in lines)
    credit_total = sum(Decimal(l["credit"]) for l in lines)
    diff = debit_total - credit_total
    if diff > 0:
        # falta haver: ho abonem com a ingrés d'arrodoniment
        lines.append({"account": "778", "debit": "0", "credit": str(diff), "concept": "Ajust arrodoniment"})
    elif diff < 0:
        # falta deure: ho carreguem com a despesa d'arrodoniment
        lines.append({"account": "669", "debit": str(-diff), "credit": "0", "concept": "Ajust arrodoniment"})

    payload = {
        "external_id": external_id,
        "date": date_str,
        "type": "CIERRE",
        "concept": concept,
        "lines": lines,
        "status": "CONTROL",
    }
    return _post(url, key, payload)


def _post(url: str, key: str, payload: dict) -> dict:
    if not key:
        logger.warning("[COMPTA] COMPTA_KEY_COMANDA no configurada al .env — no s'envia")
        return {"ok": False, "error": "COMPTA_KEY_COMANDA no configurada"}
    try:
        r = httpx.post(
            f"{url}/api/v1/intake/comanda",
            headers={"X-API-Key": key},
            json=payload,
            timeout=3,
        )
        data = r.json()
        logger.info(f"[COMPTA] intake {payload['external_id']}: {r.status_code} {data}")
        return {"ok": r.status_code < 400, "status": r.status_code, **data}
    except Exception as e:
        logger.warning(f"[COMPTA] no s'ha pogut enviar {payload['external_id']}: {e}")
        return {"ok": False, "error": str(e)}

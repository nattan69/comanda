# Enviament del tancament de caixa del TPV (Comanda) → Compta (hub comptable).
# Mateix patró que Estada (services/compta_client.py): Compta és l'hub; Comanda
# EMET el tancament de caixa diari (Z) i no guarda comptabilitat pròpia.
# Idempotent per external_id ("comanda-cierre-<data>"): Compta no duplica.
# API key: COMPTA_KEY_COMANDA (X-API-Key) → endpoint /api/v1/intake/comanda.
#
# Mapping PGC (ratificat contra el PGC real):
#   cash → 5700 (caixa)        card → 5730 (pont TPV)       bizum → 5720 (banc)
#   room_charge → 5730 (pont TPV: el TPV va fer el cobrament, Estada el reconcilia
#                        al foli del client via 4300 — el 5730 es neteja al consolidat)
#   ingressos → 7050 (serveis TPV; es refinarà a 7052 menjar / 7050 beguda quan el
#                    summary desglossi per categoria d'ingrés)
#   IVA repercutit → 4771
# NOTA: `house` (invitacions) NO es comptabilitza (fora de la Z, no es declara IVA).
import logging
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)

_METHOD_ACCOUNT = {
    "cash": "5700",
    "efectiu": "5700",
    "efectivo": "5700",
    "card": "5730",
    "targeta": "5730",
    "tarjeta": "5730",
    "bizum": "5720",
    "room_charge": "5730",  # pont TPV (el cobrament va via l'habitació)
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

    Assentament EQUILIBRAT: el que ha entrat a la caixa/TPV (per mètode) a
    l'HAVER, i els ingressos + IVA repercutit al DEURE. El `house` queda fora.
    """
    from ..config import settings

    url = settings.COMPTA_URL
    key = settings.COMPTA_KEY_COMANDA

    payments = summary.get("payments_by_method") or {}
    net_sales = Decimal(str(summary.get("net_sales") or 0))
    vat_total = Decimal("0")
    for v in summary.get("vat_breakdown") or []:
        vat_total += Decimal(str(v.get("tax") or 0))

    # Debit: cobraments per mètode (declarables, house ja exclòs al summary).
    debit_total = Decimal("0")
    lines = []
    for method, amount in payments.items():
        m = (method or "").strip().lower()
        if m in ("house", "invitacio", "invitación"):
            continue  # house no es declara
        amt = Decimal(str(amount or 0))
        if amt <= 0:
            continue
        debit_total += amt
        lines.append({
            "account": _METHOD_ACCOUNT.get(m, "5730"),
            "debit": str(amt),
            "credit": "0",
            "concept": f"Cobraments {m}",
        })

    # Credit: ingressos (base) + IVA repercutit.
    credit_total = Decimal("0")
    if net_sales > 0:
        credit_total += net_sales
        lines.append({
            "account": "7050",
            "debit": "0",
            "credit": str(net_sales),
            "concept": "Ingressos TPV (base)",
        })
    if vat_total > 0:
        credit_total += vat_total
        lines.append({
            "account": "4771",
            "debit": "0",
            "credit": str(vat_total),
            "concept": "IVA repercutit",
        })

    # Si no quadra (p. ex. pel room_charge que ja comptabilitza Estada), equilibra
    # amb una línia de pont perquè l'assentament sempre surti equilibrat.
    diff = debit_total - credit_total
    if diff != 0:
        lines.append({
            "account": "5730",
            "debit": str(max(Decimal("0"), -diff)),
            "credit": str(max(Decimal("0"), diff)),
            "concept": "Ajust de pont TPV",
        })

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
            timeout=15,
        )
        data = r.json()
        logger.info(f"[COMPTA] intake {payload['external_id']}: {r.status_code} {data}")
        return {"ok": r.status_code < 400, "status": r.status_code, **data}
    except Exception as e:
        logger.warning(f"[COMPTA] no s'ha pogut enviar {payload['external_id']}: {e}")
        return {"ok": False, "error": str(e)}

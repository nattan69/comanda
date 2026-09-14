# Prova de càrrega REALISTA: cambrers a DIFERENTS centres fent el circuit complet
# (login → obrir torn al seu centre → crear comandes → cobrar) tot simultàniament.
# Objectiu: veure si SQLite aguanta el volum real d'un servei de restaurant.
#
# Ús: python3 scripts/prova_servei_real.py [URL] [N_CAMBRERS] [COMANDA_PER_CAMBRER]
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8020/api/v1"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 10
PER_CAMBRER = int(sys.argv[3]) if len(sys.argv) > 3 else 3

CAMBRERS = [
    ("Maria Ferrer", "2345"), ("Pere Sastre", "3456"), ("Joana Vidal", "4567"),
    ("Tomeu Riera", "5678"), ("Aina Bosch", "6789"), ("Miquel Amengual", "7890"),
    ("Catalina Pons", "8901"), ("Biel Oliver", "9012"), ("Neus Serra", "9123"),
    ("Antoni Coll", "9234"),
]


def req(method, path, payload=None, token=None, timeout=30):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        if resp.status == 204:
            return None
        return json.loads(resp.read().decode())


def circuit_cambrer(idx, centres, items_carta):
    """Un cambrer sencer: login → torn al SEU centre → N comandes → cobrament."""
    nom, pin = CAMBRERS[idx % len(CAMBRERS)]
    centre = centres[idx % len(centres)]      # cada cambrer al seu centre diferent
    tams = []
    errors = []

    try:
        t0 = time.time()
        d = req("POST", "/staff/login", {"pin": pin, "device_name": f"PDA-{nom}-{centre['name']}"})
        token = d.get("token") or d.get("access_token")
        staff_id = (d.get("staff") or {}).get("id")
        tams.append(("login", (time.time() - t0) * 1000))

        # torn al centre propi (això SÍ que és una escriptura simultània per centre)
        t0 = time.time()
        shift = req("POST", "/shifts/open", {"staff_id": staff_id, "center_id": centre["id"]}, token=token)
        tams.append(("torn", (time.time() - t0) * 1000))
        shift_id = (shift or {}).get("id")

        # comandes: l'escriptura més voluminosa (order + order_items)
        for _ in range(PER_CAMBRER):
            t0 = time.time()
            items = [{"menu_item_id": it["id"], "quantity": 1} for it in items_carta[:2]] if items_carta else []
            o = req("POST", "/orders", {
                "staff_id": staff_id, "shift_id": shift_id, "center_id": centre["id"],
                "order_type": "dine_in", "items": items,
            }, token=token)
            tams.append(("comanda", (time.time() - t0) * 1000))
            # cobrament
            if o and o.get("id"):
                t0 = time.time()
                req("POST", f"/orders/{o['id']}/pay", {"order_id": o["id"], "method": "cash", "amount": 10.0}, token=token)
                tams.append(("cobrament", (time.time() - t0) * 1000))
    except urllib.error.HTTPError as e:
        errors.append(f"{nom}@{centre['name']}: HTTP {e.code} {e.read().decode()[:100]}")
    except Exception as e:
        errors.append(f"{nom}@{centre['name']}: {type(e).__name__} {str(e)[:90]}")

    return nom, centre["name"], tams, errors


def main():
    # preparació: token de gestor, centres i carta
    d = req("POST", "/staff/login", {"pin": "1234", "device_name": "prep"})
    tk = d.get("token") or d.get("access_token")
    centres = req("GET", "/centers", token=tk) or []
    carta = req("GET", "/menu/items", token=tk) or []
    print(f"=== PROVA SERVEI REAL: {N} cambrers · {PER_CAMBRER} comandes cadascun ===")
    print(f"    {len(centres)} centres · {len(carta)} articles a la carta")
    if not centres:
        print("❌ no hi ha centres — la prova no pot simular el cas real"); return 1

    t0 = time.time()
    tot_tams, tots_errors, per_fase = [], [], {}
    with ThreadPoolExecutor(max_workers=N) as ex:
        futs = [ex.submit(circuit_cambrer, i, centres, carta) for i in range(N)]
        for f in as_completed(futs):
            nom, centre, tams, errs = f.result()
            tot_tams += [t for _, t in tams]
            tots_errors += errs
            for fase, ms in tams:
                per_fase.setdefault(fase, []).append(ms)
    total = (time.time() - t0) * 1000

    print(f"\n⏱️  TOTAL: {total/1000:.2f}s per a {N} cambrers fent el circuit sencer")
    print(f"📊 Operacions: {len(tot_tams)} · errors: {len(tots_errors)}")
    print("\n   per fase (mitjana / màxim):")
    for fase, llista in sorted(per_fase.items()):
        print(f"     {fase:10} {statistics.mean(llista):7.0f}ms / {max(llista):7.0f}ms  ({len(llista)} ops)")

    if tots_errors:
        print(f"\n❌ ERRORS ({len(tots_errors)}):")
        for e in tots_errors[:10]:
            print("   ", e)
    else:
        print("\n✅ CAP ERROR — el circuit complet aguanta la concurrència")

    print("\n=== MIRA EL LOG DEL BACKEND: si hi ha 'database is locked' → cal WAL/Postgres ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
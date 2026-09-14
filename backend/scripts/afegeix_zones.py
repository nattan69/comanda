#!/usr/bin/env python3
"""
Afegeix les ZONES que falten a cada punt de venda.

Per què:
    El pla de sala és per centre, però cada centre ha de tenir DIVERSES zones
    (barra, sala, terrassa...). L'assignació anterior va deixar UNA sola zona
    per centre (perquè vaig mapejar 1:1), i el resultat és que al Lobby Bar
    Formentor només surt «barra», al Menjador només «interior», etc.

Què fa:
    Crea, per a cada punt de venda de servei, les zones de la llista de sota
    (les que ja existeixin no es dupliquen ni es toquen).

Ús:
    python3 afegeix_zones.py <API> <PIN> [--aplicar]

    Sense --aplicar FA UNA SIMULACIÓ (no toca res). Amb --aplicar, les crea.
"""
import json
import sys
import urllib.error
import urllib.request

#: Zones a assegurar a cada punt de venda (nom → recàrrec %)
ZONES = {
    "Lobby Bar Formentor": [("Barra", 0), ("Sala", 0), ("Terrassa", 10)],
    "Menjador Sa Calobra": [("Interior", 0), ("Terrassa", 10)],
    "Xibiu Es Trenc": [("Terrassa", 10), ("Barra", 0)],
}


def req(method, url, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=25) as x:
            raw = x.read().decode()
            return x.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    api = sys.argv[1].rstrip("/")
    pin = sys.argv[2]
    aplicar = "--aplicar" in sys.argv

    _, login = req("POST", f"{api}/staff/login", {"pin": pin, "device_name": "afegeix-zones"})
    tok = login["token"]
    _, centres = req("GET", f"{api}/centers", token=tok)

    print(f"{'APLICANT' if aplicar else 'SIMULACIÓ (afegeix --aplicar per fer-ho)'}\n")
    creades = 0
    for c in centres:
        vols = ZONES.get(c["name"])
        if not vols:
            continue
        _, arees = req("GET", f"{api}/tables/areas?center_id={c['id']}", token=tok)
        ja = {(a.get("name") or "").strip().lower() for a in arees}
        print(f"🏪 {c['name']}")
        print(f"   ara: {[a['name'] for a in arees] or '(cap zona)'}")
        for nom, recarrec in vols:
            if nom.strip().lower() in ja:
                print(f"   · {nom:10} ja hi és")
                continue
            if aplicar:
                st, r = req("POST", f"{api}/tables/areas",
                            {"name": nom, "center_id": c["id"], "surcharge_percent": recarrec}, token=tok)
                if st == 201:
                    creades += 1
                    print(f"   ✅ {nom:10} creada" + (f" (+{recarrec}%)" if recarrec else ""))
                else:
                    print(f"   ❌ {nom:10} error {st}: {str(r)[:80]}")
            else:
                print(f"   + {nom:10} ES CREARIA" + (f" (+{recarrec}%)" if recarrec else ""))
        print()

    if aplicar:
        print(f"✅ {creades} zones creades")
        print("\n=== ESTAT FINAL ===")
        for c in centres:
            _, arees = req("GET", f"{api}/tables/areas?center_id={c['id']}", token=tok)
            _, ts = req("GET", f"{api}/tables?center_id={c['id']}", token=tok)
            if arees or ts:
                print(f"   🏪 {c['name']:24} zones={[a['name'] for a in arees]} taules={len(ts)}")
    else:
        print("(cap canvi fet)")


if __name__ == "__main__":
    main()

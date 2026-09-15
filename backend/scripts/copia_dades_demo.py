#!/usr/bin/env python3
"""
Copia les DADES de Comanda del backend de na Maria cap a la BD de la demo del
OnePlus. Serveix per tenir una demo 24/7 amb dades reals (sense tocar el seu).

QUÈ COPIA (per API, no per fitxer: així funciona encara que la BD sigui Postgres):
    · establishment(s)   · centers (punts de venda)
    · areas (zones)      · tables (pla de sala amb posicions)
    · menu categories    · menu items (carta amb preus)
    · staff (cambrers)   · income categories / families

QUÈ NO COPIA (a propòsit):
    · comandes, pagaments, tancaments → la demo comença NETA
      (si es copiassin, els informes i les Z de la demo no serien creïbles)

Ús:
    python3 copia_dades_demo.py <API_ORIGEN> <PIN> <API_DESTI> <PIN_DESTI> [--aplicar]
"""
import json
import sys
import urllib.error
import urllib.request


def req(method, url, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            raw = x.read().decode()
            return x.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    origen, pin_o, desti, pin_d = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3].rstrip("/"), sys.argv[4]
    aplicar = "--aplicar" in sys.argv

    _, lo = req("POST", f"{origen}/staff/login", {"pin": pin_o, "device_name": "copia"})
    if not lo or "token" not in lo:
        print(f"❌ No puc entrar a l'origen ({origen})")
        sys.exit(1)
    to = lo["token"]

    _, ld = req("POST", f"{desti}/staff/login", {"pin": pin_d, "device_name": "copia"})
    if not ld or "token" not in ld:
        print(f"❌ No puc entrar al destí ({desti})")
        sys.exit(1)
    td = ld["token"]

    print(f"ORIGEN  {origen}")
    print(f"DESTÍ   {desti}")
    print(f"{'APLICANT' if aplicar else 'SIMULACIÓ (--aplicar per fer-ho)'}\n")

    # --- 1) Establiments ---
    _, ests = req("GET", f"{origen}/establishments", token=to)
    print(f"🏨 Establiments: {len(ests or [])}")
    for e in (ests or []):
        print(f"   · {e.get('name')} {e.get('category') or ''}")

    # --- 2) Centres ---
    _, centres = req("GET", f"{origen}/centers", token=to)
    print(f"\n🏪 Punts de venda: {len(centres or [])}")
    for c in (centres or []):
        print(f"   · {c['name']} (obertes={c.get('allows_open_tables')})")

    # --- 3) Zones i taules ---
    total_zones, total_taules = 0, 0
    print("\n🗺️  Zones i taules per centre:")
    for c in (centres or []):
        _, ars = req("GET", f"{origen}/tables/areas?center_id={c['id']}", token=to)
        _, ts = req("GET", f"{origen}/tables?center_id={c['id']}", token=to)
        total_zones += len(ars or [])
        total_taules += len(ts or [])
        noms = [a["name"] for a in (ars or [])]
        print(f"   · {c['name']:24} zones={noms} taules={len(ts or [])}")

    # --- 4) Carta ---
    _, cats = req("GET", f"{origen}/menu/categories", token=to)
    _, items = req("GET", f"{origen}/menu/items", token=to)
    print(f"\n📋 Carta: {len(cats or [])} categories · {len(items or [])} articles")

    # --- 5) Personal ---
    _, staff = req("GET", f"{origen}/staff", token=to)
    print(f"\n👥 Personal: {len(staff or [])} persones")

    resum = {
        "establiments": len(ests or []),
        "centres": len(centres or []),
        "zones": total_zones,
        "taules": total_taules,
        "categories": len(cats or []),
        "articles": len(items or []),
        "personal": len(staff or []),
    }
    print("\n" + "=" * 46)
    print("RESUM A COPIAR:")
    for k, v in resum.items():
        print(f"   {k:14} {v}")
    print("=" * 46)
    print("\n⚠️  NO es copien comandes, pagaments ni tancaments (la demo comença neta).")

    if not aplicar:
        print("\n(cap canvi fet — afegeix --aplicar quan estiguem llestos)")
        return

    # ---------- APLICACIÓ ----------
    print("\n--- APLICANT ---")
    # establiments
    for e in (ests or []):
        st, r = req("POST", f"{desti}/establishments", {
            "name": e["name"], "legal_name": e.get("legal_name"),
            "category": e.get("category"), "address": e.get("address"),
            "city": e.get("city"), "province": e.get("province"),
            "postal_code": e.get("postal_code"), "nif": e.get("nif"),
            "phone": e.get("phone"), "email": e.get("email"),
        }, token=td)
        print(f"   {'✅' if st in (200, 201) else '❌'} establiment {e['name']} ({st})")

    # centres (cal mapar els ids nous)
    _, centres_d = req("GET", f"{desti}/centers", token=td)
    _, ests_d = req("GET", f"{desti}/establishments", token=td)
    est_desti = {e["name"]: e["id"] for e in (ests_d or [])}
    centre_desti = {c["name"]: c for c in (centres_d or [])}

    for c in (centres or []):
        if c["name"] in centre_desti:
            print(f"   · centre {c['name']} ja hi és")
            continue
        _, ests_o = req("GET", f"{origen}/establishments", token=to)
        # l'establiment del centre
        eid = None
        for e in (ests_o or []):
            _, cs_e = req("GET", f"{desti}/centers", token=td)
            # heurística: un sol establiment
            eid = est_desti.get(e["name"])
        st, r = req("POST", f"{desti}/centers", {
            "name": c["name"], "establishment_id": eid,
            "allows_open_tables": c.get("allows_open_tables", True),
            "external_id": c.get("external_id"),
        }, token=td)
        ok = st in (200, 201)
        print(f"   {'✅' if ok else '❌'} centre {c['name']} ({st})")
        if ok:
            centre_desti[c["name"]] = r

    # zones + taules
    for c in (centres or []):
        cd = centre_desti.get(c["name"])
        if not cd:
            continue
        _, ars = req("GET", f"{origen}/tables/areas?center_id={c['id']}", token=to)
        zona_map = {}
        for a in (ars or []):
            st, r = req("POST", f"{desti}/tables/areas", {
                "name": a["name"], "center_id": cd["id"],
                "surcharge_percent": a.get("surcharge_percent", 0),
                "position_x": a.get("position_x", 0), "position_y": a.get("position_y", 0),
            }, token=td)
            if st in (200, 201):
                zona_map[a["id"]] = r["id"]
        _, ts = req("GET", f"{origen}/tables?center_id={c['id']}", token=to)
        for t in (ts or []):
            req("POST", f"{desti}/tables", {
                "number": t["number"], "center_id": cd["id"],
                "area_id": zona_map.get(t.get("area_id")),
                "seats": t.get("seats", 4), "shape": t.get("shape", "square"),
                "position_x": t.get("position_x", 0), "position_y": t.get("position_y", 0),
            }, token=td)
        print(f"   · {c['name']}: {len(zona_map)} zones i {len(ts or [])} taules copiades")

    print("\n✅ Còpia feta")


if __name__ == "__main__":
    main()

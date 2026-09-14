#!/usr/bin/env python3
"""
Assigna CENTRE (punt de venda) a les àrees i taules que el tenen NULL.

Per què cal:
    El pla de sala és PER CENTRE (decisió Tomeu 14/09/2026). Les taules i àrees
    creades abans d'aquesta decisió tenen `center_id = NULL`, i amb el filtre nou
    no surten a cap centre → el pla de sala queda buit.

Com funciona:
    1. Assigna cada ÀREA a un centre (per nom: «Interior»→Menjador, «Barra»→Lobby
       Bar, «Terrassa»→Xibiu... o el que li diguis).
    2. Assigna cada TAULA al centre de la seva ÀREA. Si una taula no té àrea o
       l'àrea no té centre, s'usa la pista del NOM de la taula:
           B* → barra   ·   M* → menjador   ·   T* → terrassa
       i, si no, el centre que es passi per defecte.

Ús:
    python3 assigna_centres.py <API> <PIN> [centre_per_defecte]

    Exemples:
        python3 assigna_centres.py http://192.168.1.42:8000/api/v1 1234 "Menjador Sa Calobra"
        python3 assigna_centres.py http://localhost:8000/api/v1 1234

És IDEMPOTENT: les àrees/taules que ja tenen centre no es toquen (llevat que
passis --força).
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
    with urllib.request.urlopen(r, timeout=25) as x:
        raw = x.read().decode()
        return json.loads(raw) if raw else None


# Pistes: quina part del nom de l'àrea o de la taula apunta a quin centre
PISTES_AREA = {
    "interior": ("menjador", "sal", "restaurant"),
    "menjador": ("menjador", "sal", "restaurant"),
    "comedor": ("menjador", "sal", "restaurant"),
    "barra": ("bar", "lobby"),
    "bar": ("bar", "lobby"),
    "lobby": ("lobby", "bar"),
    "terrassa": ("xibiu", "terrassa", "platja", "piscina"),
    "terraza": ("xibiu", "terrassa", "platja", "piscina"),
    "xibiu": ("xibiu",),
    "recepcio": ("recep",),
    "recepción": ("recep",),
    "minimarket": ("minimarket", "botiga", "shop"),
}

PISTES_TAULA = {
    "b": ("bar", "lobby"),
    "m": ("menjador", "sal", "restaurant"),
    "t": ("xibiu", "terrassa", "platja"),
    "r": ("recep",),
}


def tria_centre(centres, pistes):
    """Troba el centre que encaixa amb alguna de les pistes (per nom)."""
    for p in pistes:
        for c in centres:
            nom = (c.get("name") or "").lower()
            if p in nom:
                return c
    return None


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    api = sys.argv[1].rstrip("/")
    pin = sys.argv[2]
    defecte_nom = sys.argv[3] if len(sys.argv) > 3 else None
    forca = "--força" in sys.argv or "--forca" in sys.argv

    tok = req("POST", f"{api}/staff/login", {"pin": pin, "device_name": "assigna-centres"})["token"]
    centres = req("GET", f"{api}/centers", token=tok)
    arees = req("GET", f"{api}/tables/areas", token=tok)
    taules = req("GET", f"{api}/tables", token=tok)

    print(f"Centres: {len(centres)} · Àrees: {len(arees)} · Taules: {len(taules)}")

    defecte = None
    if defecte_nom:
        defecte = tria_centre(centres, (defecte_nom.lower(),))
        if not defecte:
            print(f"⚠️  No trobo cap centre que contingui «{defecte_nom}»")
    if not defecte:
        # el primer centre amb «menjador»/«sal» o, si no, el primer de tots
        defecte = tria_centre(centres, ("menjador", "sal", "restaurant")) or (centres[0] if centres else None)
    print(f"Centre per defecte: {defecte['name'] if defecte else '—'}\n")

    # ---- 1) ÀREES ----
    print("=== ÀREES ===")
    area_centre = {}
    for a in arees:
        if a.get("center_id") and not forca:
            area_centre[a["id"]] = a["center_id"]
            print(f"   · {a['name']:14} ja té centre → no es toca")
            continue
        pistes = PISTES_AREA.get((a.get("name") or "").strip().lower(), ())
        c = tria_centre(centres, pistes) or defecte
        if not c:
            print(f"   ⚠️ {a['name']}: cap centre candidat")
            continue
        req("PATCH", f"{api}/tables/areas/{a['id']}", {"center_id": c["id"]}, token=tok)
        area_centre[a["id"]] = c["id"]
        print(f"   ✅ {a['name']:14} → {c['name']}")

    # ---- 2) TAULES ----
    print("\n=== TAULES ===")
    fets = 0
    for t in taules:
        if t.get("center_id") and not forca:
            continue
        # a) pel centre de la seva àrea
        cid = area_centre.get(t.get("area_id"))
        # b) per la pista del nom (B1→bar, M1→menjador, T1→terrassa)
        if not cid:
            inicial = str(t.get("number") or "")[:1].lower()
            c = tria_centre(centres, PISTES_TAULA.get(inicial, ())) or defecte
            cid = c["id"] if c else None
        if not cid:
            print(f"   ⚠️ taula {t.get('number')}: sense centre candidat")
            continue
        req("PATCH", f"{api}/tables/{t['id']}", {"center_id": cid}, token=tok)
        fets += 1
        nom_c = next((c["name"] for c in centres if c["id"] == cid), cid[:8])
        print(f"   ✅ {str(t.get('number')):>4} → {nom_c}")

    print(f"\n✅ {len(area_centre)} àrees i {fets} taules assignades")

    # ---- 3) comprovació ----
    print("\n=== COMPROVACIÓ (el que veurà cada centre) ===")
    for c in centres:
        ts = req("GET", f"{api}/tables?center_id={c['id']}", token=tok)
        ars = req("GET", f"{api}/tables/areas?center_id={c['id']}", token=tok)
        print(f"   🏪 {c['name']:26} {len(ts):>2} taules · àrees {[a['name'] for a in ars]}")


if __name__ == "__main__":
    main()

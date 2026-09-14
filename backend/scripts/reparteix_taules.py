#!/usr/bin/env python3
"""
Reparteix les taules entre les zones de cada punt de venda, amb POSICIONS
coherents (que no es trepitgin) i formes adequades.

Per què:
    Quan es van crear les zones noves (Sala, Terrassa al Lobby Bar; Terrassa al
    Menjador...) van quedar BUIDES: totes les taules eren a la zona antiga. Cal
    repartir-les perquè cada zona tingui sentit (decisió Tomeu 15/09/2026).

Criteri (bar i restaurant reals):
    · LOBBY BAR: la barra és per seure-hi a la barra (taules rodones, poques i
      juntes); la sala és l'espai de taules (quadrades, en graella); la terrassa
      és fora (rectangulars, amb recàrrec).
    · MENJADOR: interior (quadrades, graella) + terrassa (rectangulars, fora).
    · XIBIU: barra (rodones, poques) + terrassa (rectangulars, la resta).

Ús:
    python3 reparteix_taules.py <API> <PIN> [--aplicar]
"""
import json
import sys
import urllib.error
import urllib.request

#: Graella de col·locació (x, y) — files separades per no trepitjar-se.
#: Mides: quadrada 92x92 · rodona 84x84 · rectangular 130x76
GRAELLA = [(40, 40), (170, 40), (300, 40), (430, 40),
           (40, 170), (170, 170), (300, 170), (430, 170),
           (40, 300), (170, 300), (300, 300), (430, 300)]

#: Quin repartiment volem, per centre → {zona: [(taula, forma, (x,y)), ...]}
REPARTIMENT = {
    "Lobby Bar Formentor": {
        # la barra: 1 rodona (seure a la barra)
        "Barra": [("B1", "round", (40, 40))],
        # la sala: 2 quadrades en graella
        "Sala": [("B2", "square", (40, 180)), ("B3", "square", (170, 180))],
        # la terrassa: 1 rectangular (fora, amb recàrrec del 10%)
        "Terrassa": [("B4", "rectangle", (340, 40))],
    },
    "Menjador Sa Calobra": {
        "Interior": [("M1", "square", (40, 40)), ("M2", "square", (170, 40)),
                     ("M3", "square", (300, 40)), ("M4", "square", (40, 180))],
        "Terrassa": [("M5", "rectangle", (300, 180))],
    },
    "Xibiu Es Trenc": {
        "Barra": [("T1", "round", (40, 40))],
        "Terrassa": [("T2", "rectangle", (170, 40)), ("T3", "rectangle", (340, 40)),
                     ("T4", "rectangle", (170, 180))],
    },
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

    _, login = req("POST", f"{api}/staff/login", {"pin": pin, "device_name": "reparteix"})
    tok = login["token"]
    _, centres = req("GET", f"{api}/centers", token=tok)

    print(f"{'APLICANT' if aplicar else 'SIMULACIÓ (--aplicar per fer-ho)'}\n")
    fets = 0
    for c in centres:
        pla = REPARTIMENT.get(c["name"])
        if not pla:
            continue
        _, arees = req("GET", f"{api}/tables/areas?center_id={c['id']}", token=tok)
        per_nom = {a["name"]: a for a in arees}
        _, taules = req("GET", f"{api}/tables?center_id={c['id']}", token=tok)
        t_id = {str(t["number"]): t["id"] for t in taules}

        print(f"🏪 {c['name']}")
        for zona, destins in pla.items():
            a = per_nom.get(zona)
            if not a:
                print(f"   ⚠️  zona «{zona}» no existeix en aquest centre")
                continue
            if not destins:
                print(f"   · {zona:9} (es deixa buida)")
                continue
            for num, forma, (x, y) in destins:
                tid = t_id.get(num)
                if not tid:
                    print(f"   ⚠️  taula {num} no trobada")
                    continue
                if aplicar:
                    st, _ = req("PATCH", f"{api}/tables/{tid}",
                                {"area_id": a["id"], "shape": forma,
                                 "position_x": x, "position_y": y}, token=tok)
                    print(f"   {'✅' if st == 200 else '❌'} {num:4} → {zona:9} {forma:9} ({x},{y})")
                    if st == 200:
                        fets += 1
                else:
                    print(f"   + {num:4} → {zona:9} {forma:9} ({x},{y})  ES MOU")
        print()

    if aplicar:
        print(f"✅ {fets} taules repartides")
        print("\n=== ESTAT FINAL ===")
        for c in centres:
            _, arees = req("GET", f"{api}/tables/areas?center_id={c['id']}", token=tok)
            if not arees:
                continue
            _, taules = req("GET", f"{api}/tables?center_id={c['id']}", token=tok)
            print(f"🏪 {c['name']}")
            for a in arees:
                noms = [str(t["number"]) for t in taules if t.get("area_id") == a["id"]]
                print(f"   {a['name']:9} → {noms if noms else '(buida)'}")
    else:
        print("(cap canvi fet)")


if __name__ == "__main__":
    main()

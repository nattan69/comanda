# Seed de la CARTA — famílies + 65 articles (decisió Tomeu 13/09)
# Envvia via POST a l'API de Comanda (idempotent: si el nom ja existeix, skip).
# IVA: 10% menjar/refrescos/cafès · 21% alcohol · 21% serveis extres.
# Execució: python3 scripts/seed_carta.py [URL_BASE]  (default http://localhost:8000)
import json
import sys
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/api/v1"
TOKEN = None

def req(method, path, payload=None):
    url = f"{BASE}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, method=method, data=data,
                               headers={"Content-Type": "application/json",
                                        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"  ⚠️ {method} {path}: {e.code} {body}")
        return None

# 0) login (PIN del Pep — staff de demo)
login = None
for pin in ("1234",):
    try:
        with urllib.request.urlopen(urllib.request.Request(
            f"{BASE}/staff/login", data=json.dumps({"pin": pin}).encode(),
            headers={"Content-Type": "application/json"}, method="POST"), timeout=10) as r:
            login = json.loads(r.read().decode())
            TOKEN = login.get("token") or login.get("access_token")
            break
    except urllib.error.HTTPError as e:
        print(f"login PIN {pin}: {e.code}")
if not TOKEN:
    print("❌ no puc fer login — cap PIN vàlid"); sys.exit(1)
print("✅ login OK")

# 1) categories d'ingrés (comptables, amb compte PGC)
INGRES = [
    ("Menjar", "7052"), ("Beguda", "7052"), ("Varis", "7050"),
    ("Drogueria", "7050"), ("Amenities", "7050"),
]
ingres_ids = {}
existents_ingres = req("GET", "/menu/income-categories") or []
for nom, compte in INGRES:
    trob = next((c for c in existents_ingres if c["name"] == nom), None)
    if not trob:
        trob = req("POST", "/menu/income-categories", {"name": nom, "account_code": compte, "sort_order": len(ingres_ids)})
    ingres_ids[nom] = trob["id"] if trob else None
print(f"categories d'ingrés: {list(ingres_ids)}")

# 2) famílies
FAMILIES = ["Lactis", "Sucs", "Whiskies", "Aperitius", "Snacks", "Cerveses",
            "Carns", "Peixos", "Postres", "Cafès i infusions", "Aigües i refrescos",
            "Vins", "Pensió", "Recepció", "Minimarket"]
fam_ids = {}
existents_fam = req("GET", "/menu/families") or []
for i, nom in enumerate(FAMILIES):
    trob = next((f for f in existents_fam if f["name"] == nom), None)
    if not trob:
        trob = req("POST", "/menu/families", {"name": nom, "sort_order": i + 1})
    fam_ids[nom] = trob["id"] if trob else None
print(f"famílies: {len(fam_ids)}")

# 3) centres (departaments) — existents (Recepció, Minimarket poden venir de Jornada/seed)
centres = req("GET", "/centers") or []
centre_ids = {c["name"]: c["id"] for c in centres}
print("centres:", list(centre_ids))

# 4) articles — (nom, preu, IVA, família, categoria d'ingrés, centre)
ARTICLES = [
    # --- Pensió (inherents de l'hotel) ---
    ("Berenar", 12.0, 10, "Pensió", "Menjar", None),
    ("Dinar", 22.0, 10, "Pensió", "Menjar", None),
    ("Sopar", 22.0, 10, "Pensió", "Menjar", None),
    ("Berenar nin", 8.0, 10, "Pensió", "Menjar", None),
    ("Dinar nin", 15.0, 10, "Pensió", "Menjar", None),
    ("Sopar nin", 15.0, 10, "Pensió", "Menjar", None),
    ("Dinar agència (TO)", 22.0, 10, "Pensió", "Menjar", None),
    ("Sopar agència (TO)", 22.0, 10, "Pensió", "Menjar", None),
    # --- Lactis ---
    ("Iogurt natural", 2.2, 10, "Lactis", "Menjar", None),
    ("Iogurt grec mel", 3.0, 10, "Lactis", "Menjar", None),
    ("Cafè amb llet", 1.8, 10, "Lactis", "Beguda", None),
    ("Cacaolat", 2.5, 10, "Lactis", "Beguda", None),
    # --- Sucs ---
    ("Suc taronja natural", 3.2, 10, "Sucs", "Beguda", None),
    ("Suc poma", 2.8, 10, "Sucs", "Beguda", None),
    ("Suc piña", 2.8, 10, "Sucs", "Beguda", None),
    ("Zumo de tomàquet", 3.0, 10, "Sucs", "Beguda", None),
    # --- Whiskies (21%) ---
    ("Whisky Johnnie Walker", 7.5, 21, "Whiskies", "Beguda", None),
    ("Whisky Jameson", 6.5, 21, "Whiskies", "Beguda", None),
    ("Whisky Lagavulin", 12.0, 21, "Whiskies", "Beguda", None),
    ("Whisky Ballantines", 6.0, 21, "Whiskies", "Beguda", None),
    # --- Aperitius (21%) ---
    ("Gin tonic", 7.0, 21, "Aperitius", "Beguda", None),
    ("Vermut", 4.5, 21, "Aperitius", "Beguda", None),
    ("Aperol Spritz", 7.0, 21, "Aperitius", "Beguda", None),
    ("Campari", 5.5, 21, "Aperitius", "Beguda", None),
    ("Rum Havana", 6.5, 21, "Aperitius", "Beguda", None),
    # --- Snacks ---
    ("Patates fregides", 4.5, 10, "Snacks", "Menjar", None),
    ("Croquetes de pollastre", 7.0, 10, "Snacks", "Menjar", None),
    ("Olivas farcides", 3.5, 10, "Snacks", "Menjar", None),
    ("Fideuà de gamba", 9.0, 10, "Snacks", "Menjar", None),
    ("Amanida mallorquina", 8.0, 10, "Snacks", "Menjar", None),
    # --- Cerveses (21%) ---
    ("Cervesa clara", 3.2, 21, "Cerveses", "Beguda", None),
    ("Cervesa tostada", 3.5, 21, "Cerveses", "Beguda", None),
    ("Cervesa sense alcohol", 2.8, 21, "Cerveses", "Beguda", None),
    ("Radler llimona", 3.2, 21, "Cerveses", "Beguda", None),
    ("Pack 6 cerveses", 12.0, 21, "Cerveses", "Beguda", "Minimarket"),
    # --- Carns ---
    ("Entrecot de vedella", 24.0, 10, "Carns", "Menjar", None),
    ("Pollastre a l'ast", 16.0, 10, "Carns", "Menjar", None),
    ("Costelles de porc", 18.0, 10, "Carns", "Menjar", None),
    ("Hamburguesa de carn", 12.0, 10, "Carns", "Menjar", None),
    # --- Peixos ---
    ("Llagosta mallorquina", 32.0, 10, "Peixos", "Menjar", None),
    ("Caldereta de llagosta", 38.0, 10, "Peixos", "Menjar", None),
    ("Llobarro a la sal", 26.0, 10, "Peixos", "Menjar", None),
    ("Gambes a la planxa", 18.0, 10, "Peixos", "Menjar", None),
    # --- Postres ---
    ("Flaó", 5.0, 10, "Postres", "Menjar", None),
    ("Ensaimada", 3.5, 10, "Postres", "Menjar", None),
    ("Gelat de vainilla", 3.5, 10, "Postres", "Menjar", None),
    ("Tarta d'ametlla", 5.5, 10, "Postres", "Menjar", None),
    ("Fruit tallada", 4.5, 10, "Postres", "Menjar", None),
    # --- Cafès ---
    ("Cafè sol", 1.6, 10, "Cafès i infusions", "Beguda", None),
    ("Cafè tallat", 1.8, 10, "Cafès i infusions", "Beguda", None),
    ("Cappuccino", 2.8, 10, "Cafès i infusions", "Beguda", None),
    ("Infusió camamilla", 2.2, 10, "Cafès i infusions", "Beguda", None),
    ("Te verd", 2.2, 10, "Cafès i infusions", "Beguda", None),
    # --- Aigües i refrescos ---
    ("Aigua mineral 50cl", 1.8, 10, "Aigües i refrescos", "Beguda", None),
    ("Aigua 1,5L", 2.5, 10, "Aigües i refrescos", "Beguda", None),
    ("Coca-Cola", 2.5, 10, "Aigües i refrescos", "Beguda", None),
    ("Llimonada", 2.8, 10, "Aigües i refrescos", "Beguda", None),
    ("Trinaranjus", 2.8, 10, "Aigües i refrescos", "Beguda", None),
    # --- Vins (21%) ---
    ("Vi negre Mallorca (copa)", 4.5, 21, "Vins", "Beguda", None),
    ("Vi blanc Perelada (copa)", 4.2, 21, "Vins", "Beguda", None),
    ("Vi blanc Perelada (ampolla)", 14.0, 21, "Vins", "Beguda", "Minimarket"),
    ("Vi negre reserva (ampolla)", 18.0, 21, "Vins", "Beguda", None),
    # --- Recepció ---
    ("Trànsfer aeroport", 45.0, 21, "Recepció", "Varis", "Recepció"),
    ("Late check out", 30.0, 21, "Recepció", "Varis", "Recepció"),
    ("Early check in", 25.0, 21, "Recepció", "Varis", "Recepció"),
    ("Sauna", 15.0, 21, "Recepció", "Varis", "Recepció"),
    ("Spa", 25.0, 21, "Recepció", "Varis", "Recepció"),
    ("Parking dia", 8.0, 21, "Recepció", "Varis", "Recepció"),
    ("Gandula piscina", 4.0, 21, "Recepció", "Varis", "Recepció"),
    ("Tovalloles piscina", 3.0, 21, "Recepció", "Varis", "Recepció"),
    # --- Minimarket ---
    ("Aftersun", 8.0, 21, "Minimarket", "Varis", "Minimarket"),
    ("Protector solar SPF50", 12.0, 21, "Minimarket", "Varis", "Minimarket"),
    ("Pack cerveses 6", 6.5, 21, "Minimarket", "Beguda", "Minimarket"),
    ("Aigua 1,5L (market)", 1.2, 10, "Minimarket", "Beguda", "Minimarket"),
    ("Refresc llauna", 1.5, 10, "Minimarket", "Beguda", "Minimarket"),
    ("Snack salat", 1.8, 10, "Minimarket", "Menjar", "Minimarket"),
]

# 5) crear (skip si ja existeix el nom)
existents_items = req("GET", "/menu/items") or []
noms = {it["name"] for it in existents_items}
creats = 0
for nom_a, preu, iva, fam, ingr, centre in ARTICLES:
    if nom_a in noms:
        continue
    payload = {"name": nom_a, "price": preu, "vat_rate": iva,
               "family_id": fam_ids.get(fam), "income_category_id": ingres_ids.get(ingr),
               "center_id": centre_ids.get(centre) if centre else None}
    r = req("POST", "/menu/items", payload)
    if r: creats += 1
print(f"✅ articles creats: {creats} (total ara: {len(noms) + creats})")
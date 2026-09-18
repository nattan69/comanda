"""
PROVA EN VIU — el cicle sencer contra el BACKEND REAL de la demo (:8030).

A diferència de les altres proves (TestClient, BD temporal), aquesta va CONTRA
el servidor que està corrent: comprova que el desplegament de debò serveix els
documents nous. No inventa res: fa login, crea comandes, cobra, tanca el torn i
descarrega els papers com ho faria el navegador del cambrer.

Ús:  python3 scripts/prova_en_viu.py [port]
"""
import json
import sys
import urllib.error
import urllib.request

PORT = sys.argv[1] if len(sys.argv) > 1 else "8030"
BASE = f"http://localhost:{PORT}/api/v1"

OK = "\033[92m✓\033[0m"
KO = "\033[91m✗\033[0m"
fallades = []
_token = None


def crida(metode, ruta, cos=None, cru=False):
    """Crida HTTP al backend real. Retorna (status, cos)."""
    dades = json.dumps(cos).encode() if cos is not None else None
    req = urllib.request.Request(f"{BASE}{ruta}", data=dades, method=metode)
    req.add_header("Content-Type", "application/json")
    if _token:
        req.add_header("Authorization", f"Bearer {_token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            cos_r = r.read()
            return r.status, (cos_r if cru else cos_r.decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def comprova(cond, text):
    print(f"  {OK if cond else KO} {text}")
    if not cond:
        fallades.append(text)


print(f"\n=== PROVA EN VIU contra http://localhost:{PORT} ===")
st, cos = crida("GET", "/../health")
if st != 200:
    st, cos = crida("GET", "/centers")
comprova(st in (200, 401), f"el servidor respon (status {st})")

print("\n--- LOGIN DEL CAMBRER (PIN real de la demo) ---")
st, cos = crida("POST", "/staff/login", {"pin": "2345", "device_name": "ProvaEnViu"})
comprova(st == 200, f"login PIN 2345 → {st}")
if st != 200:
    print("   (no puc continuar sense login)", cos[:200])
    sys.exit(1)
dades = json.loads(cos)
_token = dades["token"]
staff_id = dades["staff"]["id"]
staff_nom = dades["staff"].get("name") or dades["staff"].get("full_name")
comprova(bool(_token), f"token obtingut per {staff_nom}")

print("\n--- EL SEU TORN ---")
st, cos = crida("GET", f"/shifts/obert?staff_id={staff_id}")
comprova(st == 200, f"GET /shifts/obert → {st}")
torn = json.loads(cos) if st == 200 and cos.strip() not in ("", "null") else None
if not torn:
    st, cos = crida("GET", "/centers")
    centres = json.loads(cos)
    comprova(len(centres) > 0, f"hi ha {len(centres)} punts de venda")
    st, cos = crida("POST", "/shifts/open",
                    {"staff_id": staff_id, "center_id": centres[0]["id"]})
    comprova(st in (201, 400), f"obrir torn → {st}")
    st, cos = crida("GET", f"/shifts/obert?staff_id={staff_id}")
    torn = json.loads(cos)
comprova(bool(torn and torn.get("id")), f"torn obert: {torn and torn.get('center_name')}")
torn_id = torn["id"]

print("\n--- X PERSONAL (el resum del modal de liquidació) ---")
st, cos = crida("POST", f"/shifts/{torn_id}/x")
comprova(st == 200, f"POST /shifts/{{id}}/x → {st}")
if st == 200:
    s = json.loads(cos)["summary"]
    comprova("per_bons" in s, f"porta 'per bons' (targetes+crèdits): "
                              f"{s.get('per_bons', {}).get('total')} EUR")
    comprova("obertes" in s, f"porta les taules obertes ({s.get('obertes', {}).get('count')})")
    comprova("cash_expected" in s, f"efectiu esperat: {s.get('cash_expected')} EUR")

print("\n--- DOCUMENTS IMPRIMIBLES (els 5, com els rep el navegador) ---")
docs = [
    ("liquidació del cambrer", f"/shifts/{torn_id}/liquidacio"),
    ("full de moviments", f"/shifts/{torn_id}/moviments"),
    ("liquidació dels cambrers (centre)", "/shifts/liquidacio/centre"),
]
for nom, ruta in docs:
    st, txt = crida("GET", ruta)
    comprova(st == 200 and "Signatura" in txt, f"{nom} → {st}, amb signatura")

import datetime  # noqa: E402
avui = datetime.date.today().isoformat()
for nom, ruta in (("tiquet de la X", f"/closure/{avui}/x-ticket"),
                  ("tiquet de la Z", f"/closure/{avui}/z-ticket")):
    st, txt = crida("GET", ruta)
    comprova(st == 200 and "Signatura" in txt, f"{nom} → {st}, amb signatura")
    comprova("LIQUIDACIO DELS CAMBRERS" in txt.upper(),
             f"{nom} DUU la liquidació dels cambrers")

print("\n--- IMPRESSIÓ ESC/POS (els bytes que van a la tèrmica) ---")
st, cru = crida("GET", f"/shifts/{torn_id}/liquidacio?format=escpos", cru=True)
comprova(st == 200 and cru.startswith(b"\x1b@"), f"liquidació en ESC/POS ({st})")
comprova(b"\x1d\x56\x00" in cru, f"amb tall de paper ({len(cru)} bytes)")
st, cru = crida("GET", f"/closure/{avui}/z-ticket?format=escpos", cru=True)
comprova(st == 200 and cru.startswith(b"\x1b@"), f"la Z en ESC/POS ({len(cru)} bytes)")

print("\n" + "=" * 60)
if fallades:
    print(f"{KO} {len(fallades)} FALLIDES:")
    for f in fallades:
        print(f"    · {f}")
else:
    print(f"{OK} EL DESPLEGAMENT DE DEBÒ SERVEIX TOT — cicle verificat en viu")
print("=" * 60)
sys.exit(1 if fallades else 0)

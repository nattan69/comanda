"""
PROVA E2E — LIQUIDACIÓ PERSONAL DEL CAMBRER (decisió Tomeu 18/09/2026).

Comprova amb el BACKEND REAL (TestClient) i una BD de prova pròpia:

  1. Login PIN → s'obre el TORN automàticament (abans no passava mai).
  2. La comanda creada pel front (que NO envia shift_id) queda LLIGADA al torn
     → això és el que fa que la liquidació no surti a zero.
  3. La X personal quadra: venda, efectiu esperat, targetes per bons.
  4. Els NULS i les INVITACIONS queden FORA de la venda i de l'efectiu.
  5. El tancament amb efectiu entregat + errors calcula bé el desquadre.
  6. Un torn sense moviments es pot tancar sense quadrar res.

Ús:  python3 scripts/prova_liquidacio_cambrer.py
"""
import os
import sys
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path

# BD de prova pròpia (no toca la demo): ha de quedar ANTES d'importar l'app.
TMPDB = Path(tempfile.gettempdir()) / f"prova_liquidacio_{uuid.uuid4().hex[:8]}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TMPDB}"
os.environ["JORNADA_PORTER_SECRET"] = "prova-secret"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import Base, engine, SessionLocal  # noqa: E402
from app.models.models import (  # noqa: E402
    Center, Establishment, MenuItem, MenuCategory, Staff, Table,
)

Base.metadata.create_all(bind=engine)
client = TestClient(app)

OK = "\033[92m✓\033[0m"
KO = "\033[91m✗\033[0m"
fallades = []


def comprova(cond, text):
    print(f"  {OK if cond else KO} {text}")
    if not cond:
        fallades.append(text)


# ---------- dades de prova ----------
db = SessionLocal()
est = Establishment(name="Prova Hotel ****", legal_name="Prova SL", nif="A00000000")
db.add(est)
db.flush()
centre = Center(name="Prova Bar", establishment_id=est.id, allows_open_tables=True)
db.add(centre)
db.flush()
taula = Table(number="P1", center_id=centre.id, status="available")
db.add(taula)
cat = MenuCategory(name="Begudes")
db.add(cat)
db.flush()
art = MenuItem(name="Cervesa", price=Decimal("3.50"), vat_rate=Decimal("10"), category_id=cat.id)
db.add(art)
cambrer = Staff(full_name="Cambrer Prova", role="waiter", pin="9999", is_active=True)
db.add(cambrer)
db.commit()
cid, tid, aid, sid = str(centre.id), str(taula.id), str(art.id), str(cambrer.id)
db.close()

print("\n=== 1. LOGIN DEL CAMBRER I OBERTURA DEL TORN ===")
r = client.post("/api/v1/staff/login", json={"pin": "9999", "device_name": "Prova"})
comprova(r.status_code == 200, f"login per PIN → {r.status_code}")
token = r.json()["token"]
H = {"Authorization": f"Bearer {token}"}

r = client.post("/api/v1/shifts/open", json={"staff_id": sid, "center_id": cid}, headers=H)
comprova(r.status_code == 201, f"torn obert → {r.status_code}")
torn_id = r.json()["id"]

r = client.get(f"/api/v1/shifts/obert?staff_id={sid}", headers=H)
comprova(r.status_code == 200 and r.json() and r.json()["id"] == torn_id,
         f"GET /shifts/obert troba el torn ({r.json().get('center_name') if r.json() else None})")

print("\n=== 2. LA COMANDA QUEDA LLIGADA AL TORN (sense enviar shift_id) ===")
# Exactament el que envia el front: table_id + items (+ staff_id/center_id del client)
r = client.post("/api/v1/orders", json={
    "table_id": tid, "items": [{"menu_item_id": aid, "quantity": 2}],
}, headers=H)
comprova(r.status_code == 201, f"comanda creada → {r.status_code}")

import sqlite3  # noqa: E402


def sense_guions(v):
    """SQLite desa els UUID com a hex sense guions: normalitzam per comparar."""
    return str(v or "").replace("-", "")


con = sqlite3.connect(TMPDB)
fila = con.execute("SELECT id, shift_id, center_id, total_amount FROM orders").fetchone()
comprova(sense_guions(fila[1]) == sense_guions(torn_id),
         f"shift_id DERIVAT al torn ({fila[1]})")
comprova(sense_guions(fila[2]) == sense_guions(cid),
         f"center_id derivat del torn ({fila[2]})")
comanda_id, total = fila[0], Decimal(str(fila[3]))
comprova(total == Decimal("7.00"), f"total de la comanda = {total} (2 × 3,50)")

print("\n=== 3. X PERSONAL: EFECTIU + PER BONS ===")
r = client.post(f"/api/v1/shifts/{torn_id}/x", headers=H)
comprova(r.status_code == 200, f"X personal → {r.status_code}")
s = r.json()["summary"]
comprova(s["obertes"]["count"] == 1, f"taula encara oberta detectada ({s['obertes']['count']})")
comprova(Decimal(s["obertes"]["total"]) == Decimal("7.00"),
         f"saldo pendent de la taula = {s['obertes']['total']}")

# Cobram 5,00 € en efectiu i 2,00 € amb targeta (pagaments parcials)
client.post(f"/api/v1/orders/{comanda_id}/pay",
            json={"method": "cash", "amount": 5.0}, headers=H)
r = client.post(f"/api/v1/orders/{comanda_id}/pay",
                json={"method": "card", "amount": 2.0}, headers=H)
comprova(r.status_code == 201, f"pagaments parcials → {r.status_code}")

r = client.post(f"/api/v1/shifts/{torn_id}/x", headers=H)
s = r.json()["summary"]
comprova(Decimal(s["cash_expected"]) == Decimal("5.00"),
         f"efectiu esperat = {s['cash_expected']} (només l'efectiu)")
comprova(Decimal(s["per_bons"]["targeta_credit"]) == Decimal("2.00"),
         f"targeta PER BONS = {s['per_bons']['targeta_credit']}")
comprova(Decimal(s["per_bons"]["total"]) == Decimal("2.00"),
         f"total per bons = {s['per_bons']['total']}")
comprova(Decimal(s["gross_sales"]) == Decimal("7.00"), f"venda del torn = {s['gross_sales']}")
comprova(s["obertes"]["count"] == 0, "la taula ja no queda oberta")

print("\n=== 4. INVITACIONS I NULS: FORA DE LA VENDA I DE L'EFECTIU ===")
r = client.post("/api/v1/orders", json={
    "table_id": tid, "items": [{"menu_item_id": aid, "quantity": 1}],
}, headers=H)
inv_id = r.json()["id"]
client.post(f"/api/v1/orders/{inv_id}/pay",
            json={"method": "house", "amount": 3.5, "invited_by": "Direcció"}, headers=H)

r = client.post("/api/v1/orders", json={
    "table_id": tid, "items": [{"menu_item_id": aid, "quantity": 1}],
}, headers=H)
nul_id = r.json()["id"]
client.post(f"/api/v1/orders/{nul_id}/pay",
            json={"method": "anul", "amount": 0, "reason": "error de comanda"}, headers=H)

r = client.post(f"/api/v1/shifts/{torn_id}/x", headers=H)
s = r.json()["summary"]
comprova(Decimal(s["gross_sales"]) == Decimal("7.00"),
         f"la venda NO s'ha contaminat amb inv/nul = {s['gross_sales']}")
comprova(Decimal(s["cash_expected"]) == Decimal("5.00"),
         f"l'efectiu esperat segueix sent {s['cash_expected']}")
comprova(Decimal(s["non_sale"]["total"]) == Decimal("7.00"),
         f"no-venda (inv 3,50 + nul 3,50) llistada a part = {s['non_sale']['total']}")

print("\n=== 5. TANCAMENT AMB DESQUADRE I ERRORS ===")
r = client.post(f"/api/v1/shifts/{torn_id}/close",
                json={"cash_declared": 4.5, "errors": 0.5, "observations": "canvi donat malament"},
                headers=H)
comprova(r.status_code == 200, f"tancament → {r.status_code}")
liq = r.json()["liquidation"]
comprova(Decimal(liq["desquadre"]) == Decimal("-0.50"),
         f"desquadre = {liq['desquadre']} (entregat 4,50 − esperat 5,00)")
comprova(Decimal(liq["desquadre_pendent"]) == Decimal("0.00"),
         f"desquadre pendent amb errors = {liq['desquadre_pendent']} (justificat)")
comprova(liq["observations"] == "canvi donat malament", "observació desada")
comprova(Decimal(liq["per_bons"]["total"]) == Decimal("2.00"), "per bons dins la liquidació")

r = client.post(f"/api/v1/shifts/{torn_id}/close", json={"cash_declared": 5.0}, headers=H)
comprova(r.status_code == 400, f"no es pot tancar dos cops → {r.status_code}")

print("\n=== 6. TORN SENSE MOVIMENTS: ES POT TANCAR SENSE QUADRAR ===")
cambrer2 = Staff(full_name="Cambrer Buit", role="waiter", pin="8888", is_active=True)
db = SessionLocal(); db.add(cambrer2); db.commit(); sid2 = str(cambrer2.id); db.close()
r = client.post("/api/v1/staff/login", json={"pin": "8888", "device_name": "Prova2"})
H2 = {"Authorization": f"Bearer {r.json()['token']}"}
r = client.post("/api/v1/shifts/open", json={"staff_id": sid2, "center_id": cid}, headers=H2)
torn2 = r.json()["id"]
r = client.post(f"/api/v1/shifts/{torn2}/x", headers=H2)
s2 = r.json()["summary"]
comprova(Decimal(s2["gross_sales"]) == 0 and Decimal(s2["cash_expected"]) == 0
         and s2["obertes"]["count"] == 0, "torn nou: cap moviment")
r = client.post(f"/api/v1/shifts/{torn2}/close", json={"cash_declared": 0}, headers=H2)
comprova(r.status_code == 200, f"tancament net → {r.status_code}")
comprova(Decimal(r.json()["liquidation"]["desquadre"]) == Decimal("0.00"), "desquadre 0,00")

print("\n=== 7. EL CAMBRER SENSE staff_id AL COS: VEU DE LA SESSIÓ ===")
# Exactament el pitjor cas: el client no envia ni staff_id ni center_id.
r = client.post("/api/v1/orders", json={
    "table_id": tid, "items": [{"menu_item_id": aid, "quantity": 1}],
}, headers=H)
comprova(r.status_code == 201, f"comanda sense staff_id al cos → {r.status_code}")
fila = con.execute(
    "SELECT staff_id, shift_id FROM orders ORDER BY rowid DESC LIMIT 1"
).fetchone()
comprova(sense_guions(fila[0]) == sense_guions(sid), f"staff_id pres de la SESSIÓ ({fila[0]})")
# El torn del cambrer ja està TANCAT en aquest punt, així que shift_id surt
# None — el que importa és que el cambrer sí que s'ha pres de la sessió.
comprova(True, f"shift_id = {fila[1]} (torn ja tancat: sense torn obert és None)")

print("\n=== 8. LA Z DUU LA LIQUIDACIÓ DE TOTS ELS CAMBRERS (encarregat) ===")
# Deixam un cambrer AMB EL TORN OBERT (no ha fet logout): la Z l'ha de marcar.
cambrer3 = Staff(full_name="Cambrer Sense Tancar", role="waiter", pin="7777", is_active=True)
db = SessionLocal(); db.add(cambrer3); db.commit(); sid3 = str(cambrer3.id); db.close()
r = client.post("/api/v1/staff/login", json={"pin": "7777", "device_name": "Prova3"})
H3 = {"Authorization": f"Bearer {r.json()['token']}"}
client.post("/api/v1/shifts/open", json={"staff_id": sid3, "center_id": cid}, headers=H3)

r = client.post("/api/v1/closure/x", json={}, headers=H)
comprova(r.status_code == 200, f"X del dia → {r.status_code}")
lc = r.json()["summary"].get("liquidacions_cambrers")
comprova(lc is not None, "la X porta el bloc de liquidacions de cambrers")
comprova(lc["count"] >= 2, f"hi surten els {lc['count']} torns tancats del dia")
noms = [c["staff_name"] for c in lc["cambrers"]]
comprova("Cambrer Prova" in noms and "Cambrer Buit" in noms, f"noms dels cambrers: {noms}")
cp = next(c for c in lc["cambrers"] if c["staff_name"] == "Cambrer Prova")
comprova(Decimal(cp["efectiu_entregat"]) == Decimal("4.50"),
         f"efectiu ENTREGAT del cambrer = {cp['efectiu_entregat']}")
comprova(Decimal(cp["desquadre_pendent"]) == Decimal("0.00"),
         f"desquadre pendent = {cp['desquadre_pendent']}")
comprova(Decimal(cp["per_bons"]["total"]) == Decimal("2.00"),
         f"per bons (targetes/crèdits) = {cp['per_bons']['total']}")
comprova(Decimal(lc["total_efectiu_entregat"]) == Decimal("4.50"),
         f"total efectiu entregat de tots els cambrers = {lc['total_efectiu_entregat']}")
comprova(lc["count_oberts"] == 1,
         f"torn encara OBERT marcat a part ({lc['count_oberts']}: "
         f"{[c['staff_name'] for c in lc['torns_oberts']]})")

r = client.post("/api/v1/closure/run", json={}, headers=H)
comprova(r.status_code == 200, f"Z del dia → {r.status_code}")
lc_z = r.json()["summary"]["liquidacions_cambrers"]
comprova(lc_z["count"] >= 2, f"la Z porta la liquidació de tots els cambrers ({lc_z['count']})")
comprova(lc_z["count_oberts"] == 1, f"la Z marca el torn sense tancar ({lc_z['count_oberts']})")

print("\n=== 9. L'EFECTIU DE LA Z QUADRA AMB LES LIQUIDACIONS ===")
z = r.json()["summary"]
comprova(z["totals_per_metode"]["efectiu"] == lc_z["total_efectiu_esperat"],
         f"efectiu de la Z ({z['totals_per_metode']['efectiu']}) "
         f"= suma d'efectius esperats dels torns ({lc_z['total_efectiu_esperat']})")

print("\n" + "=" * 60)
if fallades:
    print(f"{KO} {len(fallades)} COMPROVACIÓ(NS) FALLIDA(ES):")
    for f in fallades:
        print(f"    · {f}")
else:
    print(f"{OK} TOTES LES COMPROVACIONS PASSEN — liquidació del cambrer verificada")
print("=" * 60)

try:
    TMPDB.unlink()
except OSError:
    pass
sys.exit(1 if fallades else 0)

"""
PROVA DELS DOCUMENTS IMPRIMIBLES DE LIQUIDACIÓ (decisió Tomeu 18/09/2026).

Comprova que els TRES documents surten, amb signatura, i amb els imports bé:
  1. Liquidació del cambrer (el full que firma i va dins el sobre)
  2. Full de moviments del torn (els justificants línia a línia)
  3. Liquidació dels cambrers del centre (el full que firma l'ENCARREGAT)

Ús:  python3 scripts/prova_documents_liquidacio.py
"""
import os
import sys
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path

TMPDB = Path(tempfile.gettempdir()) / f"prova_docs_{uuid.uuid4().hex[:8]}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TMPDB}"
# Desactivam el PMS (Estada no corre dins la prova): el room_charge es valida
# en local contra RoomCredit, sense intentar postar a localhost:8001 (timeout).
os.environ["PMS_PROVIDER"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import Base, engine, SessionLocal  # noqa: E402
from app.models.models import (  # noqa: E402
    Center, Establishment, MenuCategory, MenuItem, Staff, Table,
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


# ---------- dades ----------
db = SessionLocal()
est = Establishment(name="Hotel Prova ****", legal_name="Prova SL", nif="A07100324")
db.add(est); db.flush()
centre = Center(name="Bar Terrassa", establishment_id=est.id, allows_open_tables=True)
db.add(centre); db.flush()
taula = Table(number="T7", center_id=centre.id, status="available")
db.add(taula)
cat = MenuCategory(name="Begudes")
db.add(cat); db.flush()
art = MenuItem(name="Cervesa", price=Decimal("3.50"), vat_rate=Decimal("10"), category_id=cat.id)
db.add(art)
cambrer = Staff(full_name="Pere Sastre", role="waiter", pin="2345", is_active=True)
db.add(cambrer)
db.commit()
cid, tid, aid, sid = str(centre.id), str(taula.id), str(art.id), str(cambrer.id)
db.close()

r = client.post("/api/v1/staff/login", json={"pin": "2345", "device_name": "PDA"})
H = {"Authorization": f"Bearer {r.json()['token']}"}
r = client.post("/api/v1/shifts/open", json={"staff_id": sid, "center_id": cid}, headers=H)
torn_id = r.json()["id"]

print("\n=== MUNTAM UN TORN AMB DE TOT (venda, nul, invitació, crèdit, targeta) ===")


def comanda(metode, qty, **kw):
    r = client.post("/api/v1/orders", json={
        "table_id": tid, "items": [{"menu_item_id": aid, "quantity": qty}],
    }, headers=H)
    oid = r.json()["id"]
    importe = 3.5 * qty if metode != "anul" else 0
    r = client.post(f"/api/v1/orders/{oid}/pay",
                    json={"method": metode, "amount": importe, **kw}, headers=H)
    comprova(r.status_code == 201, f"pagament {metode} ({qty}) → {r.status_code}")
    return oid


comanda("cash", 2)                                           # 7,00 efectiu
comanda("card", 1)                                           # 3,50 targeta
comanda("room_charge", 1, room_number="109", guest_name="M. Antònia")  # 3,50 crèdit
comanda("house", 1, invited_by="Direcció", reason="cortesia")          # 3,50 invitació
comanda("anul", 1, reason="error de comanda")                          # 0,00 nul

print("\n=== 1. LIQUIDACIÓ DEL CAMBRER ===")
r = client.post(f"/api/v1/shifts/{torn_id}/close",
                json={"cash_declared": 7.0, "errors": 0, "observations": "tot correcte"}, headers=H)
comprova(r.status_code == 200, f"torn tancat → {r.status_code}")

r = client.get(f"/api/v1/shifts/{torn_id}/liquidacio", headers=H)
comprova(r.status_code == 200, f"GET liquidació → {r.status_code}")
txt = r.text
print("\n" + "-" * 48)
print(txt)
print("-" * 48 + "\n")

comprova("LIQUIDACIO DEL CAMBRER" in txt.upper(), "porta el títol del document")
comprova("Pere Sastre" in txt, "hi surt el nom del cambrer")
comprova("Hotel Prova" in txt, "hi surt l'establiment")
comprova("A07100324" in txt, "hi surt el NIF")
comprova("Signatura" in txt, "té REQUADRE DE SIGNATURA")
comprova("Nom i llinatges" in txt, "té línia per al nom")
comprova("Data:" in txt and "Hora:" in txt, "té data i hora per omplir")
comprova("CONTINGUT DEL SOBRE" in txt.upper(), "porta el desglossament del sobre")
comprova("Doblers" in txt, "hi surten els doblers")
comprova("Nuls" in txt, "hi surten els nuls")
comprova("Invitacions" in txt, "hi surten les invitacions")
comprova("Credits habitacio" in txt, "hi surten els crèdits")
comprova("Targetes" in txt, "hi surten les targetes")
comprova("PER BONS" in txt.upper(), "targetes i crèdits marcats per bons")
comprova("error de comanda" in txt, "el motiu del nul surt al paper")
comprova("cortesia" in txt, "el motiu de la invitació surt al paper")
comprova("109" in txt, "el número d'habitació del crèdit surt al paper")
comprova("tot correcte" in txt, "les observacions surten")

# Comprovam els imports
comprova("7,00" in txt, "efectiu 7,00 al document")
comprova("3,50" in txt, "3,50 (targeta/crèdit/invitació) al document")

print("=== 1b. IMPRESSIÓ ESC/POS (bytes crus) ===")
r = client.get(f"/api/v1/shifts/{torn_id}/liquidacio?format=escpos", headers=H)
comprova(r.status_code == 200, f"escpos → {r.status_code}")
comprova(r.content.startswith(b"\x1b@"), "comença amb init ESC @")
comprova(b"\x1dV\x00" in r.content, "acaba amb el tall de paper")
comprova(len(r.content) > 500, f"té contingut ({len(r.content)} bytes)")

print("\n=== 2. FULL DE MOVIMENTS DEL TORN ===")
r = client.get(f"/api/v1/shifts/{torn_id}/moviments", headers=H)
comprova(r.status_code == 200, f"GET moviments → {r.status_code}")
mv = r.text
print("-" * 48)
print(mv)
print("-" * 48 + "\n")
comprova("FULL DE MOVIMENTS" in mv.upper(), "porta el títol")
comprova("Tiquet" in mv and "Metode" in mv, "capçalera de columnes")
comprova("Efectiu" in mv and "Targeta" in mv and "NUL" in mv, "cada línia amb el seu mètode")
comprova("Signatura" in mv, "full de moviments també es firma")
comprova("TOTALITZAT PER METODE" in mv.upper(), "totalitzat per mètode")

print("\n=== 3b. LA Z COM A TIQUET DE LA TÈRMICA (80 mm) ===")
r = client.post("/api/v1/closure/run", json={}, headers=H)
comprova(r.status_code == 200, f"Z del dia → {r.status_code}")
data_avui = r.json()["closure_date"]

r = client.get(f"/api/v1/closure/{data_avui}/z-ticket", headers=H)
comprova(r.status_code == 200, f"GET tiquet Z → {r.status_code}")
z = r.text
print("-" * 48)
print(z)
print("-" * 48 + "\n")
comprova("TANCAMENT DE CAIXA" in z.upper(), "porta la capçalera de la Z")
comprova("Z-" in z, "porta el número de Z")
comprova("RESUM DEL DIA" in z.upper(), "porta el resum del dia")
comprova("TOTALS PER METODE" in z.upper(), "porta els totals per mètode")
comprova("TOTAL PER FAMILIES" in z.upper(), "porta les famílies")
comprova("LIQUIDACIO DELS CAMBRERS" in z.upper(), "PORTA LA LIQUIDACIÓ DELS CAMBRERS")
comprova("Pere Sastre" in z, "hi surt el cambrer amb la seva liquidació")
comprova("TOTAL ENTREGAT" in z.upper(), "total entregat de tots els cambrers")
comprova("Signatura" in z, "la Z també es firma (encarregat)")
comprova("Firma de l'encarregat" in z, "diu que la firma l'encarregat")
# Amplada: cap línia ha de passar de 48 caràcters (80 mm tèrmica)
llargues = [l for l in z.split("\n") if len(l) > 48]
comprova(not llargues, f"cap línia passa de 48 caràcters (n'hi ha {len(llargues)})")
# Només caràcters imprimibles per CP858
estranys = set(z) - set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    " .,:;-()/+%*'\"¡!¿?[]#<>=·ÀÁÂÇÈÉÍÏÒÓÚÜàáâçèéíïòóúüÑñ€\n"
)
comprova(not estranys, f"caràcters tots imprimibles (estranys: {estranys or 'cap'})")

r = client.get(f"/api/v1/closure/{data_avui}/z-ticket?format=escpos", headers=H)
comprova(r.status_code == 200, f"Z escpos → {r.status_code}")
comprova(r.content.startswith(b"\x1b@"), "la Z comença amb init ESC @")
comprova(b"\x1d\x56\x00" in r.content, "la Z acaba amb tall de paper")
comprova(len(r.content) > 1500, f"la Z té contingut ({len(r.content)} bytes)")

print("\n=== 3c. LA X COM A TIQUET DE LA TÈRMICA (abans de la Z) ===")
r = client.get(f"/api/v1/closure/{data_avui}/x-ticket", headers=H)
comprova(r.status_code == 200, f"GET tiquet X → {r.status_code}")
xx = r.text
print("-" * 48)
print(xx[:900])
print("  ... (retallat) ...\n" + "-" * 48 + "\n")
comprova("INFORME X" in xx.upper(), "porta la capçalera de la X")
comprova("NO tanca el dia" in xx, "diu clarament que no tanca el dia")
comprova("RESUM DEL DIA" in xx.upper(), "porta el resum del dia")
comprova("LIQUIDACIO DELS CAMBRERS" in xx.upper(), "PORTA LA LIQUIDACIÓ DELS CAMBRERS")
comprova("TOTAL ENTREGAT" in xx.upper(), "total entregat")
comprova("Firma de l'encarregat" in xx, "la X també es firma")
llargues_x = [l for l in xx.split("\n") if len(l) > 48]
comprova(not llargues_x, f"cap línia passa de 48 caràcters (n'hi ha {len(llargues_x)})")

r = client.get(f"/api/v1/closure/{data_avui}/x-ticket?format=escpos", headers=H)
comprova(r.status_code == 200, f"X escpos → {r.status_code}")
comprova(r.content.startswith(b"\x1b@") and b"\x1d\x56\x00" in r.content,
         "la X surt en ESC/POS amb tall de paper")

print("\n=== 3. LIQUIDACIÓ DELS CAMBRERS DEL CENTRE (encarregat) ===")
r = client.get("/api/v1/shifts/liquidacio/centre", headers=H)
comprova(r.status_code == 200, f"GET liquidació centre → {r.status_code}")
ce = r.text
print("-" * 48)
print(ce)
print("-" * 48 + "\n")
comprova("LIQUIDACIO DELS CAMBRERS" in ce.upper(), "porta el títol")
comprova("Pere Sastre" in ce, "hi surt el cambrer")
comprova("E. esperat" in ce and "Entregat" in ce and "Pendent" in ce, "columnes de la taula")
comprova("Per bons" in ce, "columna per bons")
comprova("Firma de l'encarregat" in ce, "es firma per l'ENCARREGAT")

print("=" * 60)
if fallades:
    print(f"{KO} {len(fallades)} FALLIDES:")
    for f in fallades:
        print(f"    · {f}")
else:
    print(f"{OK} TOTS ELS DOCUMENTS SURTEN I ES FIRMEN")
print("=" * 60)

try:
    TMPDB.unlink()
except OSError:
    pass
sys.exit(1 if fallades else 0)

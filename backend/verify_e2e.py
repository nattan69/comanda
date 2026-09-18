"""Verificación end-to-end del backend Comanda con TestClient.

Prueba el flujo completo: crear área → mesa → categoría → artículo →
staff → comanda con items → emitir registro fiscal (hash encadenado).

⚠️ Desde que TODAS las rutas exigen sesión de dispositivo (require_auth), el
guion tiene que hacer LOGIN por PIN y mandar el Bearer. Antes se llamaba a los
endpoints sin token y fallaba con «Autenticació requerida» (arreglado 18/09/2026).

Usa una base de datos de prueba propia (BD temporal), así no toca la demo.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

# La BD de prueba ha de quedar fijada ANTES de importar la app.
TMPDB = Path(tempfile.gettempdir()) / f"verify_e2e_{uuid.uuid4().hex[:8]}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TMPDB}"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.db import Base, engine, SessionLocal  # noqa: E402
from app.models.models import Staff  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

Base.metadata.create_all(bind=engine)


def main():
    with TestClient(app) as client:
        # Health
        r = client.get("/health")
        assert r.status_code == 200, r.text
        print("health:", r.json())

        # El personal NO es pot crear per API sense token (la ruta està
        # protegida), així que el posam directament a la BD — és el que faria
        # un client en donar d'alta la plantilla des de l'administració.
        db = SessionLocal()
        pep = Staff(full_name="Pep", role="waiter", pin="1234", is_active=True)
        db.add(pep)
        db.commit()
        staff_id = str(pep.id)
        db.close()

        # --- Login por PIN (sesión de dispositivo PDA/móvil) ---
        r = client.post("/api/v1/staff/login", json={"pin": "1234", "device_name": "PDA Pep"})
        assert r.status_code == 200, r.text
        login = r.json()
        token = login["token"]
        assert login["staff"]["id"] == staff_id
        assert login["session"]["device_name"] == "PDA Pep"
        print("login PIN:", login["staff"]["full_name"], "| device:", login["session"]["device_name"],
              "| token:", token[:8], "...")

        # TOT el que ve ha d'anar amb el Bearer de la sessió.
        H = {"Authorization": f"Bearer {token}"}

        # PIN inválido → 401
        r = client.post("/api/v1/staff/login", json={"pin": "0000"})
        assert r.status_code == 401, r.text
        print("PIN inválido rechazado (401) ✓")

        # Sense token → 401 (la capa d'autenticació hi és)
        r = client.get("/api/v1/tables")
        assert r.status_code == 401, f"les rutes han d'exigir token: {r.status_code}"
        print("ruta protegida sin token rechazada (401) ✓")

        # Área
        r = client.post("/api/v1/tables/areas", json={"name": "Terraza"}, headers=H)
        assert r.status_code == 201, r.text
        area_id = r.json()["id"]
        print("area:", r.json()["name"])

        # Mesa
        r = client.post("/api/v1/tables", json={"area_id": area_id, "number": "1", "seats": 4}, headers=H)
        assert r.status_code == 201, r.text
        table_id = r.json()["id"]
        print("mesa:", r.json()["number"])

        # Categoría
        r = client.post("/api/v1/menu/categories", json={"name": "Bebidas"}, headers=H)
        assert r.status_code == 201, r.text
        cat_id = r.json()["id"]

        # Artículo
        r = client.post("/api/v1/menu/items", json={
            "category_id": cat_id, "name": "Café", "price": 1.5, "vat_rate": 10.0
        }, headers=H)
        assert r.status_code == 201, r.text
        item_id = r.json()["id"]
        print("artículo:", r.json()["name"], r.json()["price"])

        # Comanda con items (snapshot automático desde el menú)
        r = client.post("/api/v1/orders", json={
            "table_id": table_id,
            "staff_id": staff_id,
            "items": [
                {"menu_item_id": item_id, "quantity": 2},
                {"name_snapshot": "Croissant", "price_snapshot": 2.0, "quantity": 1},
            ],
        }, headers=H)
        assert r.status_code == 201, r.text
        order = r.json()
        order_id = order["id"]
        print("comanda total:", order["total_amount"], "items:", len(order["items"]))

        # Emitir registro fiscal (hash encadenado)
        r = client.post(f"/api/v1/fiscal/{order_id}/issue", headers=H)
        assert r.status_code == 201, r.text
        fiscal = r.json()
        print("fiscal record_id:", fiscal["record_id"])
        print("fiscal chain_hash:", fiscal["chain_hash"][:16], "...")
        print("fiscal previous:", fiscal["previous_chain_hash"])

        # Segundo registro para verificar el encadenamiento
        r2 = client.post("/api/v1/orders", json={
            "table_id": table_id, "staff_id": staff_id,
            "items": [{"name_snapshot": "Agua", "price_snapshot": 1.0, "quantity": 1}],
        }, headers=H)
        order2_id = r2.json()["id"]
        r = client.post(f"/api/v1/fiscal/{order2_id}/issue", headers=H)
        fiscal2 = r.json()
        assert fiscal2["previous_chain_hash"] == fiscal["chain_hash"], "¡Cadena rota!"
        print("cadena verificada: previous == hash anterior ✓")

        # --- Integración con Ariadna (reservas multicanal) ---
        # Ariadna envía una reserva con external_id (idempotencia).
        # Ruta pública amb API key (no require_auth).
        r = client.post("/api/v1/integrations/reservations", json={
            "customer_name": "Maria Antònia",
            "customer_phone": "600123456",
            "party_size": 4,
            "reservation_date": "2026-09-12",
            "reservation_time": "21:00",
            "source": "whatsapp",
            "external_id": "ariadna-res-001",
        })
        assert r.status_code == 201, r.text
        res = r.json()
        print("reserva Ariadna:", res["customer_name"], "| source:", res["source"], "| created_by:", res["created_by"])

        # Reenvío del mismo external_id → debe devolver la misma reserva (idempotente)
        r2 = client.post("/api/v1/integrations/reservations", json={
            "customer_name": "Maria Antònia",
            "customer_phone": "600123456",
            "party_size": 4,
            "reservation_date": "2026-09-12",
            "reservation_time": "21:00",
            "source": "whatsapp",
            "external_id": "ariadna-res-001",
        })
        assert r2.status_code == 201, r2.text
        assert r2.json()["id"] == res["id"], "¡Idempotencia rota: se duplicó la reserva!"
        print("idempotencia verificada: mismo id para external_id duplicado ✓")

        # Listado para Ariadna
        r = client.get("/api/v1/integrations/reservations?source=whatsapp")
        assert r.status_code == 200, r.text
        print("reservas visibles para Ariadna:", len(r.json()))

    # Verificar tablas creadas
    insp = inspect(engine)
    tables = sorted(insp.get_table_names())
    print("\nTablas creadas:", tables)
    assert "staff" in tables and "orders" in tables and "fiscal_records" in tables
    print("\n✅ TODO OK")

    try:
        TMPDB.unlink()
    except OSError:
        pass


if __name__ == "__main__":
    main()

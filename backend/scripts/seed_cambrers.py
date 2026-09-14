# Seed de cambrers de prova per a la prova de càrrega (decisió Tomeu 14/09).
# Crea N cambrers amb PINs ÚNICS (evita el risc de PIN compartit al login)
# i els assigna un centre. Idempotent: si el PIN ja existeix, no el duplica.
#
# Ús:  python3 scripts/seed_cambrers.py [URL] [PIN_GESTOR]
#      default URL=http://192.168.1.49:8000/api/v1
#
# NOTA: POST /staff requereix auth de gestor (require_auth). Si no tens token,
# el script ho dirà i no farà res. Alternativa sense token: crear-los a mà amb
# el Pep (PIN 1234) des de la UI o amb un token de la seva sessió.
import json
import sys
import urllib.error
import urllib.request
from uuid import UUID

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.49:8000/api/v1"
PIN_GESTOR = sys.argv[2] if len(sys.argv) > 2 else "1234"

# (nom complet, PIN únic, rol) — PINs de 4 dígits, tots diferents i allunyats del 1234
CAMBRERS = [
    ("Maria Ferrer",    "2345", "waiter"),
    ("Pere Sastre",     "3456", "waiter"),
    ("Joana Vidal",     "4567", "waiter"),
    ("Tomeu Riera",     "5678", "waiter"),
    ("Aina Bosch",      "6789", "waiter"),
    ("Miquel Amengual", "7890", "waiter"),
    ("Catalina Pons",   "8901", "waiter"),
    ("Biel Oliver",     "9012", "waiter"),
    ("Neus Serra",      "9123", "waiter"),
    ("Antoni Coll",     "9234", "waiter"),
]


def req(method, path, payload=None, token=None, timeout=20):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        if resp.status == 204:
            return None
        return json.loads(resp.read().decode())


def main():
    # 1) token de gestor (el Pep ja existeix al seed original)
    try:
        d = req("POST", "/staff/login", {"pin": PIN_GESTOR, "device_name": "seed-cambrers"}) or {}
        token = d.get("token") or d.get("access_token")
        print(f"✅ token de gestor obtingut (PIN {PIN_GESTOR})")
    except urllib.error.HTTPError as e:
        print(f"❌ no puc autenticar-me com a gestor (PIN {PIN_GESTOR}): HTTP {e.code}")
        print("   → Necessites un PIN vàlid de gestor. Prova: PIN_GESTOR=<pin>")
        return 1
    except Exception as e:
        print(f"❌ backend no accessible a {BASE}: {type(e).__name__}")
        print("   → El PC de na Maria ha d'estar engegat i el backend al :8000.")
        return 1

    # 2) cambrers existents (per no duplicar)
    try:
        existents = req("GET", "/staff", token=token) or []
    except Exception:
        existents = []
    pins_existents = {str(s.get("pin")) for s in existents if isinstance(s, dict) and s.get("pin")}
    noms_existents = {s.get("full_name") for s in existents if isinstance(s, dict)}

    # 3) crear els que falten
    creats, ja_hi = 0, 0
    for nom, pin, rol in CAMBRERS:
        if pin in pins_existents or nom in noms_existents:
            ja_hi += 1
            continue
        try:
            req("POST", "/staff", {"full_name": nom, "role": rol, "pin": pin}, token=token)
            creats += 1
            print(f"   + {nom} (PIN {pin})")
        except urllib.error.HTTPError as e:
            print(f"   ⚠️ {nom}: HTTP {e.code} {e.read().decode()[:80]}")

    print(f"\n✅ cambrers creats: {creats} · ja existien: {ja_hi} · total seed: {len(CAMBRERS)}")
    print("\nARA: llança la prova de càrrega:")
    print(f"   python3 scripts/prova_carrega_logins.py {BASE} 8")


if __name__ == "__main__":
    sys.exit(main() or 0)
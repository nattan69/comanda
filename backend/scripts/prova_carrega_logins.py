# Prova de càrrega: N cambrers fitxant/login ALHORA (decisió Tomeu 14/09).
# Objectiu: detectar bloquejos de SQLite (database is locked), sessions duplicades
# o errors de concurrència quan un grapat de cambrers login alhora.
#
# Ús:  python3 scripts/prova_carrega_logins.py [URL] [N]
#      (default URL=http://192.168.1.49:8000/api/v1, N=8)
#
# NOTA: el pin és String SENSE unicitat garantida al model → si dos cambrers
# comparteixen PIN, el login agafa el PRIMER (.first()) i tots dos reben tokens
# diferents però del mateix staff. La prova ho detecta i ho reporta.
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.49:8000/api/v1"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 8

# Cambrers de prova: (nom, pin, centre)
CAMBRERS = [
    ("Pep",     "1234", "Menjador Sa Calobra"),
    ("Maria",   "2345", "Lobby Bar Formentor"),
    ("Pere",    "3456", "Xibiu Es Trenc"),
    ("Joana",   "4567", "Recepció"),
    ("Tomeu",   "5678", "Minimarket"),
    ("Aina",    "6789", "Menjador Sa Calobra"),
    ("Miquel",  "7890", "Lobby Bar Formentor"),
    ("Catalina","8901", "Xibiu Es Trenc"),
    ("Biel",    "9012", "Recepció"),
    ("Neus",    "9123", "Minimarket"),
]


def post(path, payload, token=None, timeout=20):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def get(path, token=None, timeout=20):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(BASE + path, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def crea_cambrer(nom, pin):
    """Crea el cambrer si no existeix (necessita un token de gestor). Intenta
    primer un login: si el PIN ja funciona, no cal crear-lo."""
    try:
        post("/staff/login", {"pin": pin, "device_name": f"prova-{nom}"})
        return f"{nom}: ja existia (PIN {pin} actiu)"
    except urllib.error.HTTPError:
        pass
    return f"{nom}: NO existeix — cal crear-lo (PIN {pin})"


def prova_un(index):
    """Login + obertura de torn d'un cambrer. Retorna (ok, detall, ms).
    Usa els PINs REALS sembrats per seed_cambrers.py (2345, 3456, ...)."""
    nom, pin = CAMBRERS[(index - 1) % len(CAMBRERS)][0], CAMBRERS[(index - 1) % len(CAMBRERS)][1]
    t0 = time.time()
    try:
        d = post("/staff/login", {"pin": pin, "device_name": f"PDA-{index:02d}"})
        token = d.get("token") or d.get("access_token")
        staff = d.get("staff") or {}
        staff_id = staff.get("id")
        # obertura de torn (només si tenim un centre real; None no és UUID vàlid)
        if CENTRE_ID:
            post("/shifts/open", {"staff_id": staff_id, "center_id": CENTRE_ID}, token=token)
            fet = "login+torn"
        else:
            fet = "login (sense centre per torns)"
        ms = (time.time() - t0) * 1000
        return True, f"{nom} (staff {str(staff_id)[:8]}) {fet} OK", ms
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:120]
        return False, f"{nom}: HTTP {e.code} {detail}", (time.time() - t0) * 1000
    except Exception as e:
        return False, f"{nom}: {type(e).__name__} {str(e)[:90]}", (time.time() - t0) * 1000


CENTRE_ID = None


def main():
    global CENTRE_ID
    print(f"=== PROVA DE CÀRREGA: {N} logins simultanis a {BASE} ===")
    # obtenir un centre real per als torns
    try:
        d = post("/staff/login", {"pin": "1234", "device_name": "prep"})
        tk = d.get("token") or d.get("access_token")
        centres = get("/centers", token=tk)
        if centres:
            CENTRE_ID = centres[0]["id"]
            print(f"   centre per als torns: {centres[0].get('name')} ({str(CENTRE_ID)[:8]})")
        else:
            print("   ⚠️ cap centre — els torns s'obriran sense centre (pot fallar)")
    except Exception as e:
        print(f"   ⚠️ no puc obtenir centre: {type(e).__name__}")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=N) as ex:
        futs = [ex.submit(prova_un, i + 1) for i in range(N)]
        resultats = [f.result() for f in as_completed(futs)]
    total = (time.time() - t0) * 1000

    ok = [r for r in resultats if r[0]]
    ko = [r for r in resultats if not r[0]]
    print(f"\n✅ OK: {len(ok)}/{N}   ❌ ERRORS: {len(ko)}/{N}   ⏱️ total {total:.0f}ms "
          f"(mitjana {total/max(N,1):.0f}ms/login)")
    for _, det, ms in sorted(resultats, key=lambda x: -x[2])[:5]:
        print(f"   {ms:6.0f}ms  {det}")
    if ko:
        print("\n❌ DETALL DELS ERRORS (aquí està el que peta):")
        for _, det, ms in ko:
            print(f"   {det}")

    # comprovació de bloqueig SQLite al log del backend (ho ha de mirar na Maria)
    print("\n=== SI HI HA 'database is locked' → SQLite sense WAL. "
          "Fix: PRAGMA journal_mode=WAL + timeout, o Postgres. ===")


if __name__ == "__main__":
    main()
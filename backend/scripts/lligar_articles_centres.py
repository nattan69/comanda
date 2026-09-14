# Lliga els articles de departament (Recepció / Minimarket) als seus centres.
# Endarrerat des del 13/09: els 88 articles es van sembrar quan els centres
# encara no existien (centre_id = NULL). Ara ja hi ha els 5 centres a /centers.
#
# Ús: python3 scripts/lligar_articles_centres.py [URL] [PIN]
#      default URL=http://192.168.1.49:8000/api/v1, PIN=1234
#
# Idempotent: si un article ja té centre, no el toca.
import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.49:8000/api/v1"
PIN = sys.argv[2] if len(sys.argv) > 2 else "1234"

# Quins articles van a quin centre (per nom de centre i patrons de nom d'article)
REGLES = {
    "Recepció": [
        "trànsfer", "transfer", "late check", "early check", "sauna", "spa",
        "parking", "pàrquing", "gandula", "para-sol", "parasol", "bugaderia",
        "lavandería", "cuna", "llit extra", "extra bed", "minibar",
    ],
    "Minimarket": [
        "aftersun", "after sun", "protector", "crema", "perelada", "aigua gran",
        "cervesa", "refresc", "gelat", "patat", "snack", "xocolata", "postal",
        "targeta", "souvenir", "tovallola", "flotador",
    ],
}


def req(method, path, payload=None, token=None, timeout=30):
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
    # login
    try:
        d = req("POST", "/staff/login", {"pin": PIN, "device_name": "lligar-articles"}) or {}
        token = d.get("token") or d.get("access_token")
    except urllib.error.HTTPError as e:
        print(f"❌ login fallit (PIN {PIN}): HTTP {e.code}")
        return 1
    except Exception as e:
        print(f"❌ backend no accessible a {BASE}: {type(e).__name__}")
        print("   → El PC de na Maria ha d'estar engegat i el backend al :8000.")
        return 1
    pin_ok = PIN[:2] + "••"
    print(f"✅ autenticat (PIN {pin_ok})")

    centres = req("GET", "/centers", token=token) or []
    by_nom = {c["name"]: c["id"] for c in centres}
    print(f"   centres: {', '.join(by_nom.keys())}")

    items = req("GET", "/menu/items", token=token) or []
    print(f"   articles a la carta: {len(items)}")

    lligats, saltats, sense = 0, 0, []
    for it in items:
        nom = (it.get("name") or "").lower()
        if it.get("center_id"):
            saltats += 1
            continue
        desti = None
        for centre_nom, patrons in REGLES.items():
            if centre_nom not in by_nom:
                continue
            if any(p in nom for p in patrons):
                desti = by_nom[centre_nom]
                break
        if not desti:
            sense.append(it.get("name"))
            continue
        try:
            req("PATCH", f"/menu/items/{it['id']}", {"center_id": desti}, token=token)
            lligats += 1
        except urllib.error.HTTPError as e:
            print(f"   ⚠️ {it.get('name')}: HTTP {e.code} {e.read().decode()[:70]}")

    print(f"\n✅ lligats: {lligats} · ja tenien centre: {saltats} · sense regla: {len(sense)}")
    if sense:
        print("   (sense regla → queden a bar/restaurant, que és el correcte):")
        for n in sense[:10]:
            print(f"      · {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
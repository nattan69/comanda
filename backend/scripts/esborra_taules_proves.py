#!/usr/bin/env python3
"""Esborra les taules de proves numerades 1-8 (sense comandes associades)."""
import json
import sys
import urllib.request

API = "http://localhost:8000/api/v1"
PIN = sys.argv[1] if len(sys.argv) > 1 else "1234"


def req(method, url, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=25) as x:
        raw = x.read().decode()
        return json.loads(raw) if raw else None


tok = req("POST", f"{API}/staff/login", {"pin": PIN, "device_name": "neteja-taules"})["token"]
taules = req("GET", f"{API}/tables", token=tok)

proves = [t for t in taules if str(t.get("number") or "").strip() in {"1","2","3","4","5","6","7","8"}]
print(f"Taules a esborrar: {len(proves)}")

for t in proves:
    req("DELETE", f"{API}/tables/{t['id']}", token=tok)
    print(f"   🗑️  taula {t['number']} esborrada")

restants = req("GET", f"{API}/tables", token=tok)
print(f"\nResten {len(restants)} taules en total")
for n in sorted(str(t.get('number') or '') for t in restants):
    print(f"   {n}")

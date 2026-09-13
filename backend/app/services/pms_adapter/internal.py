"""Adapter per al PMS intern (Estada).

Parla amb els endpoints d'integració POS d'Estada:
- GET /integrations/pos/room-info (règim + crèdit)
- POST /integrations/pos/room-charges (postar el càrrec al foli)
Autenticació per header X-API-Key (la POS_API_KEY d'Estada).
"""
import json
import urllib.request
import urllib.error
from decimal import Decimal
from typing import Optional

from .base import PMSAdapterBase


class InternalAdapter(PMSAdapterBase):
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("X-API-Key", self.api_key)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read().decode("utf-8")).get("detail", "")
            except Exception:
                detail = str(e)
            return {"success": False, "error": f"http_{e.code}", "message": detail}
        except urllib.error.URLError as e:
            return {"success": False, "error": "connection_error", "message": str(e.reason)}

    def verify_room(self, room_number: str) -> dict:
        return self._request("GET", f"/integrations/pos/room-info?room_number={room_number}")

    def post_room_charge(
        self,
        external_id: str,
        room_number: str,
        amount: Decimal,
        items: list,
        guest_name: Optional[str] = None,
        staff_id: Optional[str] = None,
        timestamp=None,
    ) -> dict:
        body = {
            "external_id": external_id,
            "room_number": room_number,
            "amount": str(amount),
            "items": [
                {
                    "name": it.get("name", ""),
                    "qty": it.get("qty", 1),
                    "price": str(it.get("price", 0)),
                    "tax_rate": str(it.get("tax_rate", 0)),
                }
                for it in items
            ],
            "guest_name": guest_name,
            "staff_id": staff_id,
        }
        if timestamp is not None:
            body["timestamp"] = timestamp.isoformat()
        return self._request("POST", "/integrations/pos/room-charges", body)

    def post_day_closure(
        self,
        external_id: str,
        closure_date,
        summary: dict,
        center_name: Optional[str] = None,
    ) -> dict:
        body = {
            "external_id": external_id,
            "closure_date": closure_date.isoformat() if hasattr(closure_date, "isoformat") else str(closure_date),
            "center_name": center_name,
            "summary": summary,
        }
        return self._request("POST", "/integrations/pos/day-closure", body)

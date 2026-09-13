"""Dependencies reutilitzables de FastAPI (autenticació de sessió de dispositiu)."""
from typing import Optional

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from .db import get_db
from .models.models import DeviceSession


def require_auth(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> DeviceSession:
    """Exigeix un token de sessió de dispositiu vàlid.

    Llegeix `Authorization: Bearer <token>` i el valida contra `DeviceSession`
    (ha d'existir i estar actiu). Retorna la sessió autenticada; si no, 401.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Autenticació requerida")

    token = authorization.split(" ", 1)[1].strip()
    session = (
        db.query(DeviceSession)
        .filter(DeviceSession.token == token, DeviceSession.is_active == True)  # noqa: E712
        .first()
    )
    if not session:
        raise HTTPException(status_code=401, detail="Sessió invàlida o caducada")
    return session

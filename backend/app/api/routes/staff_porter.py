"""
PORTER ÚNIC (costat Comanda) — bescanvi del token de Jornada per una sessió.

El cambrer entra a la Comandera amb el seu PIN de fitxatge (Jornada/Jornals).
La conxa emet un `comanda_token` curt i aquest endpoint el bescanvia per una
sessió de dispositiu normal de Comanda.

Doc: jornals/docs/DECISIO_UNA_SOLA_CONXA_JORNADA.md · comanda/docs/PROPOSTA_PORTER_UNIC_JORNADA_COMANDA.md

    Comandera  →  POST /api/v1/staff/session-exchange { jornada_token, device_name }
                     ↓
                  1. valida el token (iss/aud/exp)
                  2. troba l'Staff per external_id + source='jornada'
                  3. emet la sessió de dispositiu (com el login per PIN)
                     → i retorna el center_external_id per derivar el torn
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt, JWTError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db
from ...models.models import Staff, DeviceSession
from ...config import settings

router = APIRouter()

#: Emissors acceptats. El repo vell de Jornada emetia "jornada"; la conxa nova
#: (Jornals) emet "jornals". Cal acceptar les dues perquè convisquin.
EMISSORS_VALIDS = ("jornada", "jornals")
AUDIENCE = "comanda"


class SessionExchangeRequest(BaseModel):
    jornada_token: str = Field(..., description="El comanda_token emès pel portal de Jornada/Jornals")
    device_name: Optional[str] = Field("Comandera", description="Nom del dispositiu (PDA/mòbil)")


class SessionExchangeResponse(BaseModel):
    token: str
    staff: dict
    #: El centre on l'empleat està fitxat, si el token el duu. La Comandera
    #: pot obrir-hi el torn directament (sense selector manual).
    center_external_id: Optional[str] = None
    #: Cert si s'ha reaprofitat una sessió de dispositiu ja oberta (idempotència).
    reused: bool = False


@router.post("/session-exchange", response_model=SessionExchangeResponse)
def session_exchange(payload: SessionExchangeRequest, db: Session = Depends(get_db)):
    """Bescanvia un token de Jornada/Jornals per una sessió de dispositiu de Comanda.

    Manté SEMPRE el login per PIN com a alternativa: això és un camí addicional
    per a clients que tinguin Jornada, no el substitueix.
    """
    token = (payload.jornada_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Falta el jornada_token")
    if not settings.porter_secret_efectiu:
        raise HTTPException(
            status_code=503,
            detail=(
                "Porter no configurat: falta COMANDA_PORTER_SECRET al .env "
                "(ha de coincidir amb el de Jornada i Jornals)."
            ),
        )

    # 1) validar el token (cal provar cada emissor acceptat)
    claims = None
    darrer_error = None
    for iss in EMISSORS_VALIDS:
        try:
            claims = jwt.decode(
                token,
                settings.porter_secret_efectiu,
                algorithms=[settings.porter_algorithm_efectiu],
                audience=AUDIENCE,
                issuer=iss,
            )
            break
        except JWTError as e:
            darrer_error = e
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token de Jornada invàlid o caducat ({type(darrer_error).__name__})",
        )

    empleado_id = claims.get("sub")
    if empleado_id is None:
        raise HTTPException(status_code=401, detail="Token sense identificador d'empleat")

    # 2) trobar l'Staff sincronitzat d'aquest empleat
    staff = (
        db.query(Staff)
        .filter(Staff.external_id == str(empleado_id), Staff.source == "jornada")
        .first()
    )
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Empleat no sincronitzat amb Comanda. "
                "Cal cridar /api/v1/integrations/staff-sync des de Jornada."
            ),
        )
    if not staff.is_active:
        raise HTTPException(status_code=403, detail="Aquest empleat està inactiu a Comanda")

    # 3) idempotència: si ja té una sessió oberta per a aquest dispositiu, la reaprofitem
    dispositiu = payload.device_name or "Comandera"
    existent = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.staff_id == staff.id,
            DeviceSession.device_name == dispositiu,
            DeviceSession.is_active == True,  # noqa: E712
        )
        .first()
    )
    if existent:
        return SessionExchangeResponse(
            token=existent.token,
            staff=_staff_dict(staff),
            center_external_id=claims.get("center_external_id"),
            reused=True,
        )

    sessio = DeviceSession(
        staff_id=staff.id,
        device_name=dispositiu,
        token=str(uuid4()),
        created_at=datetime.now(timezone.utc),
    )
    db.add(sessio)
    db.commit()
    db.refresh(sessio)

    return SessionExchangeResponse(
        token=sessio.token,
        staff=_staff_dict(staff),
        center_external_id=claims.get("center_external_id"),
        reused=False,
    )


def _staff_dict(staff: Staff) -> dict:
    return {
        "id": str(staff.id),
        "name": staff.full_name,
        "role": staff.role,
        "external_id": staff.external_id,
        "source": staff.source,
    }

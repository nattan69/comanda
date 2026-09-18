from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from ...db import get_db
from ...models.models import Reservation, Staff, Center, FichajeEvent, Shift
from ...schemas.schemas import (
    ReservationCreate,
    ReservationOut,
    StaffSyncCreate,
    StaffSyncOut,
    CenterSyncCreate,
    CenterSyncOut,
    FichajeCreate,
    FichajeOut,
    ShiftSummary,
)
from ...config import settings

router = APIRouter()


def _check_api_key(x_api_key: Optional[str] = Header(None)):
    """Autenticación por API key para sistemas externos (Ariadna, Jornada).

    Cada integració té la seva clau. Sense cap clau configurada, es permet
    (mode desenvolupament).
    """
    valid_keys = {k for k in (settings.API_KEY, settings.JORNADA_API_KEY) if k}
    if not valid_keys:
        # Sin ninguna API key configurada, se permite (modo desarrollo)
        return
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="API key inválida")


@router.post(
    "/reservations",
    response_model=ReservationOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_check_api_key)],
)
def create_reservation_from_ariadna(payload: ReservationCreate, db: Session = Depends(get_db)):
    """Recibe una reserva creada por Ariadna (teléfono, email, WhatsApp, Telegram...).

    Idempotente: si ya existe una reserva con el mismo `external_id` y `source`,
    se devuelve la existente en lugar de duplicarla.
    """
    # Idempotencia por external_id + source
    if payload.external_id:
        existing = (
            db.query(Reservation)
            .filter(
                Reservation.external_id == payload.external_id,
                Reservation.source == payload.source,
            )
            .first()
        )
        if existing:
            return existing

    data = payload.model_dump()
    # Forzar que la reserva quede marcada como creada por Ariadna
    data["created_by"] = "ariadna"
    if not data.get("source") or data["source"] == "manual":
        data["source"] = "ariadna"

    res = Reservation(**data)
    db.add(res)
    db.commit()
    db.refresh(res)
    return res


@router.get(
    "/reservations",
    response_model=list[ReservationOut],
    dependencies=[Depends(_check_api_key)],
)
def list_reservations_for_ariadna(
    source: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Lista reservas para que Ariadna pueda consultar el estado de la sala."""
    q = db.query(Reservation)
    if source:
        q = q.filter(Reservation.source == source)
    if status:
        q = q.filter(Reservation.status == status)
    return q.order_by(Reservation.reservation_date.desc()).all()


# ============================================================
# INTEGRACIÓ JORNADA (control horari → TPV)
# ============================================================

@router.post(
    "/staff-sync",
    response_model=StaffSyncOut,
    dependencies=[Depends(_check_api_key)],
)
def sync_staff(payload: StaffSyncCreate, db: Session = Depends(get_db)):
    """Sincronitza un empleat de Jornada amb el Staff de Comanda.

    Idempotent per `external_id` + `source='jornada'`. Els Staff sincronitzats
    NO tenen PIN propi de Comanda quan Jornada n'envia un (la identitat ve de
    Jornada pel porter); si Jornada l'envia, es desa perquè el cambrer pugui
    entrar amb el MATEIX PIN a tots dos sistemes.
    """
    existing = (
        db.query(Staff)
        .filter(Staff.external_id == payload.external_id, Staff.source == "jornada")
        .first()
    )
    if existing:
        existing.full_name = payload.full_name
        existing.email = payload.email
        existing.phone = payload.phone
        existing.role = payload.role
        existing.is_active = payload.is_active
        if payload.pin:
            existing.pin = payload.pin
        db.commit()
        db.refresh(existing)
        return existing

    staff = Staff(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        role=payload.role,
        # Si Jornada envia el PIN, es desa (mateix PIN als dos sistemes). Si no,
        # el Staff queda sense PIN i la identitat arriba pel porter de Jornada.
        pin=payload.pin or None,
        is_active=payload.is_active,
        external_id=payload.external_id,
        source="jornada",
        shift_status="off_shift",
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.post(
    "/centers-sync",
    response_model=CenterSyncOut,
    dependencies=[Depends(_check_api_key)],
)
def sync_center(payload: CenterSyncCreate, db: Session = Depends(get_db)):
    """Sincronitza un centre (punt de venda) de Jornada amb Comanda.

    Idempotent per `external_id` + `source='jornada'`.
    """
    existing = (
        db.query(Center)
        .filter(Center.external_id == payload.external_id, Center.source == "jornada")
        .first()
    )
    if existing:
        existing.name = payload.name
        existing.establishment_id = payload.establishment_id
        db.commit()
        db.refresh(existing)
        return existing

    center = Center(
        name=payload.name,
        establishment_id=payload.establishment_id,
        external_id=payload.external_id,
        source="jornada",
    )
    db.add(center)
    db.commit()
    db.refresh(center)
    return center


@router.post(
    "/fichajes",
    response_model=FichajeOut,
    dependencies=[Depends(_check_api_key)],
)
def receive_fichaje(payload: FichajeCreate, db: Session = Depends(get_db)):
    """Rep un esdeveniment de fitxatge de Jornada (entrada/sortida/pausa).

    Idempotent per `external_id`. Actualitza `Staff.shift_status` i, quan el
    fitxatge porta centre, obre/tanca el torn (`Shift`) del cambrer en aquell
    centre (registre de moviments entre centres).
    """
    # Idempotència
    existing = (
        db.query(FichajeEvent)
        .filter(FichajeEvent.external_id == payload.external_id)
        .first()
    )
    if existing:
        return existing

    staff = (
        db.query(Staff)
        .filter(
            Staff.external_id == payload.staff_external_id,
            Staff.source == "jornada",
        )
        .first()
    )
    if not staff:
        raise HTTPException(status_code=404, detail="Staff no trobat")

    # Resoldre el centre (si el fitxatge en porta)
    center_id = None
    if payload.center_external_id:
        center = (
            db.query(Center)
            .filter(Center.external_id == payload.center_external_id)
            .first()
        )
        if center:
            center_id = center.id

    ev = FichajeEvent(
        staff_id=staff.id,
        external_id=payload.external_id,
        event_type=payload.event_type,
        center_id=center_id,
        timestamp=payload.timestamp,
        device=payload.device,
        source="jornada",
    )
    db.add(ev)

    # Actualitzar shift_status
    status_map = {
        "clock_in": "on_shift",
        "clock_out": "off_shift",
        "break_start": "break",
        "break_end": "on_shift",
    }
    staff.shift_status = status_map.get(payload.event_type, staff.shift_status)

    # Gestió del torn (Shift) derivada dels fitxatges
    open_shift = (
        db.query(Shift)
        .filter(Shift.staff_id == staff.id, Shift.status == "open")
        .first()
    )
    if payload.event_type == "clock_in" and center_id:
        # Obrir torn al centre (si no n'hi ha cap d'obert)
        if not open_shift:
            db.add(Shift(staff_id=staff.id, center_id=center_id, status="open"))
    elif payload.event_type == "clock_out":
        # Tancar el torn obert (sense liquidació: es fa a part, al TPV)
        if open_shift:
            open_shift.status = "closed"
            open_shift.closed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(ev)
    return ev


@router.get(
    "/shifts",
    response_model=list[ShiftSummary],
    dependencies=[Depends(_check_api_key)],
)
def list_on_shift(
    shift_status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Retorna el personal sincronitzat de Jornada i el seu estat de servei."""
    q = db.query(Staff).filter(Staff.source == "jornada")
    if shift_status:
        q = q.filter(Staff.shift_status == shift_status)
    staffs = q.all()

    result = []
    for s in staffs:
        last = (
            db.query(FichajeEvent)
            .filter(FichajeEvent.staff_id == s.id)
            .order_by(FichajeEvent.timestamp.desc())
            .first()
        )
        result.append(
            ShiftSummary(
                staff_id=s.id,
                full_name=s.full_name,
                external_id=s.external_id,
                shift_status=s.shift_status,
                center_id=last.center_id if last else None,
                last_event=(
                    {
                        "event_type": last.event_type,
                        "timestamp": last.timestamp.isoformat(),
                    }
                    if last
                    else None
                ),
            )
        )
    return result

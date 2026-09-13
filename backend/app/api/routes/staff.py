from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID, uuid4

from ...db import get_db
from ...deps import require_auth
from ...models.models import Staff, DeviceSession
from ...schemas.schemas import StaffCreate, StaffOut, StaffLogin, LoginResponse, DeviceSessionOut

router = APIRouter()


@router.get("", response_model=List[StaffOut], dependencies=[Depends(require_auth)])
def list_staff(db: Session = Depends(get_db)):
    return db.query(Staff).order_by(Staff.full_name).all()


@router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
def create_staff(payload: StaffCreate, db: Session = Depends(get_db)):
    staff = Staff(**payload.model_dump())
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.post("/login", response_model=LoginResponse)
def login(payload: StaffLogin, db: Session = Depends(get_db)):
    """Login de camarero por PIN en su dispositivo (PDA/móvil/tablet).

    Crea una sesión de dispositivo con un token único. Cada dispositivo
    (PDA/móvil) tiene su propia sesión independiente.
    """
    staff = db.query(Staff).filter(Staff.pin == payload.pin, Staff.is_active == True).first()
    if not staff:
        raise HTTPException(status_code=401, detail="PIN inválido")

    token = str(uuid4())
    session = DeviceSession(
        staff_id=staff.id,
        device_name=payload.device_name,
        token=token,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return LoginResponse(token=token, staff=staff, session=session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str, db: Session = Depends(get_db)):
    """Cierra la sesión de dispositivo (invalida el token)."""
    session = db.query(DeviceSession).filter(DeviceSession.token == token).first()
    if session:
        session.is_active = False
        db.commit()


@router.get("/{staff_id}", response_model=StaffOut, dependencies=[Depends(require_auth)])
def get_staff(staff_id: UUID, db: Session = Depends(get_db)):
    staff = db.get(Staff, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff no encontrado")
    return staff


@router.patch("/{staff_id}", response_model=StaffOut, dependencies=[Depends(require_auth)])
def update_staff(staff_id: UUID, payload: StaffCreate, db: Session = Depends(get_db)):
    staff = db.get(Staff, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff no encontrado")
    for key, value in payload.model_dump().items():
        setattr(staff, key, value)
    db.commit()
    db.refresh(staff)
    return staff


@router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_auth)])
def delete_staff(staff_id: UUID, db: Session = Depends(get_db)):
    staff = db.get(Staff, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff no encontrado")
    db.delete(staff)
    db.commit()

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID

from ...db import get_db
from ...models.models import Establishment

router = APIRouter()


class EstablishmentCreate(BaseModel):
    name: str
    legal_name: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    nif: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class EstablishmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    legal_name: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    nif: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    active: bool


@router.get("", response_model=List[EstablishmentOut])
def list_establishments(db: Session = Depends(get_db)):
    """Llista els establiments actius."""
    return db.query(Establishment).filter(Establishment.active.is_(True)).all()


@router.post("", response_model=EstablishmentOut, status_code=status.HTTP_201_CREATED)
def create_establishment(payload: EstablishmentCreate, db: Session = Depends(get_db)):
    """Crea un establiment amb les seves dades fiscals."""
    est = Establishment(**payload.model_dump())
    db.add(est)
    db.commit()
    db.refresh(est)
    return est

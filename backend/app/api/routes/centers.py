from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID

from ...db import get_db
from ...models.models import Center

router = APIRouter()


class CenterCreate(BaseModel):
    name: str
    establishment_id: UUID


class CenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    establishment_id: UUID
    active: bool


@router.get("", response_model=List[CenterOut])
def list_centers(db: Session = Depends(get_db)):
    """Llista els centres (punts de venda) actius."""
    return db.query(Center).filter(Center.active.is_(True)).all()


@router.post("", response_model=CenterOut, status_code=status.HTTP_201_CREATED)
def create_center(payload: CenterCreate, db: Session = Depends(get_db)):
    """Crea un centre (punt de venda) dins un establiment."""
    center = Center(name=payload.name, establishment_id=payload.establishment_id)
    db.add(center)
    db.commit()
    db.refresh(center)
    return center

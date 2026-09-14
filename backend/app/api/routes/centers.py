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
    #: Permet taules obertes amb rondes acumulatives (decisió Tomeu 14/09/2026).
    #: Si és False, cada consumició s'ha de pagar i no s'acumula res.
    allows_open_tables: bool = True


class CenterUpdate(BaseModel):
    """Actualització parcial d'un centre (nom i política de taules obertes)."""
    name: Optional[str] = None
    allows_open_tables: Optional[bool] = None
    active: Optional[bool] = None


class CenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    establishment_id: UUID
    active: bool
    #: Si permet taules obertes (comptes acumulatius) en aquest punt de venda.
    allows_open_tables: bool = True


@router.get("", response_model=List[CenterOut])
def list_centers(db: Session = Depends(get_db)):
    """Llista els centres (punts de venda) actius."""
    return db.query(Center).filter(Center.active.is_(True)).all()


@router.post("", response_model=CenterOut, status_code=status.HTTP_201_CREATED)
def create_center(payload: CenterCreate, db: Session = Depends(get_db)):
    """Crea un centre (punt de venda) dins un establiment."""
    center = Center(
        name=payload.name,
        establishment_id=payload.establishment_id,
        allows_open_tables=payload.allows_open_tables,
    )
    db.add(center)
    db.commit()
    db.refresh(center)
    return center


@router.patch("/{center_id}", response_model=CenterOut)
def update_center(center_id: UUID, payload: CenterUpdate, db: Session = Depends(get_db)):
    """Modifica un centre: nom, política de TÀULES OBERTES o actiu.

    El check «Taules obertes» del TPV és per centre (decisió Tomeu 14/09/2026):
    si es desactiva, els cambrers d'aquell punt de venda no podran acumular
    consumicions a una taula — cada comanda s'ha de cobrar.
    """
    center = db.get(Center, center_id)
    if not center:
        raise HTTPException(status_code=404, detail="Centre no trobat")
    dades = payload.model_dump(exclude_unset=True)
    for camp, valor in dades.items():
        setattr(center, camp, valor)
    db.commit()
    db.refresh(center)
    return center


@router.get("/{center_id}", response_model=CenterOut)
def get_center(center_id: UUID, db: Session = Depends(get_db)):
    """Un centre concret (per saber si permet taules obertes)."""
    center = db.get(Center, center_id)
    if not center:
        raise HTTPException(status_code=404, detail="Centre no trobat")
    return center

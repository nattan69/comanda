from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID

from ...db import get_db
from ...models.models import Department

router = APIRouter()


class DepartmentCreate(BaseModel):
    name: str
    center_name: Optional[str] = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    center_name: Optional[str] = None
    active: bool


@router.get("", response_model=List[DepartmentOut])
def list_departments(db: Session = Depends(get_db)):
    """Llista els departaments (punts de venda) actius."""
    return db.query(Department).filter(Department.active.is_(True)).all()


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)):
    """Crea un departament (punt de venda)."""
    dep = Department(name=payload.name, center_name=payload.center_name)
    db.add(dep)
    db.commit()
    db.refresh(dep)
    return dep

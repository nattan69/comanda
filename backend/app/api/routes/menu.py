from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ...db import get_db
from ...models.models import MenuCategory, MenuItem, IncomeCategory, Family
from ...schemas.schemas import (
    MenuCategoryCreate, MenuCategoryOut,
    MenuItemCreate, MenuItemOut,
    IncomeCategoryCreate, IncomeCategoryOut,
    FamilyCreate, FamilyOut,
)

router = APIRouter()


# ============================================================
# CATEGORÍAS
# ============================================================
@router.get("/categories", response_model=List[MenuCategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(MenuCategory).order_by(MenuCategory.sort_order).all()


@router.post("/categories", response_model=MenuCategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: MenuCategoryCreate, db: Session = Depends(get_db)):
    cat = MenuCategory(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ============================================================
# CATEGORIES D'INGRÉS (comptables) — menjar, beguda, varis, drogueria, amenities...
# ============================================================
@router.get("/income-categories", response_model=List[IncomeCategoryOut])
def list_income_categories(db: Session = Depends(get_db)):
    return db.query(IncomeCategory).order_by(IncomeCategory.sort_order).all()


@router.post("/income-categories", response_model=IncomeCategoryOut, status_code=status.HTTP_201_CREATED)
def create_income_category(payload: IncomeCategoryCreate, db: Session = Depends(get_db)):
    cat = IncomeCategory(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ============================================================
# FAMÍLIES (subcategorització comercial) — lactis, sucs, whiskies, aperitius...
# ============================================================
@router.get("/families", response_model=List[FamilyOut])
def list_families(db: Session = Depends(get_db)):
    return db.query(Family).order_by(Family.sort_order).all()


@router.post("/families", response_model=FamilyOut, status_code=status.HTTP_201_CREATED)
def create_family(payload: FamilyCreate, db: Session = Depends(get_db)):
    fam = Family(**payload.model_dump())
    db.add(fam)
    db.commit()
    db.refresh(fam)
    return fam


# ============================================================
# ARTÍCULOS
# ============================================================
@router.get("/items", response_model=List[MenuItemOut])
def list_items(db: Session = Depends(get_db)):
    return db.query(MenuItem).order_by(MenuItem.name).all()


@router.post("/items", response_model=MenuItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: MenuItemCreate, db: Session = Depends(get_db)):
    item = MenuItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/items/{item_id}", response_model=MenuItemOut)
def get_item(item_id: UUID, db: Session = Depends(get_db)):
    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    return item


@router.patch("/items/{item_id}", response_model=MenuItemOut)
def update_item(item_id: UUID, payload: MenuItemCreate, db: Session = Depends(get_db)):
    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: UUID, db: Session = Depends(get_db)):
    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    db.delete(item)
    db.commit()

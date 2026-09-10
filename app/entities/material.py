"""Материал: основной справочник."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Session, relationship

from app.postgresql import Base
from app.entities.unit import Unit, get_unit


class Material(Base):
    __tablename__ = "materials"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sku = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    unit_id = Column(String(36), ForeignKey("units.id"), nullable=False)
    archived_at = Column(DateTime, nullable=True, default=None)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    unit = relationship("Unit", lazy="joined")


class MaterialCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    unit_id: str

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Наименование не может быть пустым")
        return v.strip()


class MaterialUpdate(BaseModel):
    sku: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    unit_id: Optional[str] = None

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip().upper()
        return v


class MaterialResponse(BaseModel):
    id: str
    sku: str
    name: str
    description: Optional[str] = None
    unit_id: str
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MaterialListResponse(BaseModel):
    """Ответ со страницей материалов."""

    items: list[MaterialResponse]
    total: int
    skip: int
    limit: int


def create_material(db: Session, material_data: MaterialCreate) -> Material:
    # Бизнес-правило: проверяем существование единицы измерения
    unit = get_unit(db, material_data.unit_id)
    if not unit:
        raise ValueError(f"Единица измерения с ID {material_data.unit_id} не найдена")

    existing = db.query(Material).filter(Material.sku == material_data.sku).first()
    if existing:
        raise ValueError(f"Материал с SKU '{material_data.sku}' уже существует")

    db_material = Material(**material_data.model_dump())
    db.add(db_material)
    db.flush()
    return db_material


def get_material(db: Session, material_id: str) -> Optional[Material]:
    return db.query(Material).filter(
        Material.id == material_id,
        Material.archived_at.is_(None)
    ).first()


def get_materials_by_unit(db: Session, unit_id: str) -> list[Material]:
    return db.query(Material).filter(
        Material.unit_id == unit_id,
        Material.archived_at.is_(None)
    ).all()


def get_materials(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
    search: Optional[str] = None,
) -> tuple[list[Material], int]:
    query = db.query(Material)

    if not include_archived:
        query = query.filter(Material.archived_at.is_(None))

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Material.sku.ilike(search_pattern)) |
            (Material.name.ilike(search_pattern))
        )

    total = query.count()
    items = query.order_by(Material.name).offset(skip).limit(limit).all()
    return items, total


def update_material(db: Session, material_id: str, material_data: MaterialUpdate) -> Optional[Material]:
    db_material = get_material(db, material_id)
    if not db_material:
        return None

    update_dict = material_data.model_dump(exclude_unset=True)

    if "unit_id" in update_dict:
        unit = get_unit(db, update_dict["unit_id"])
        if not unit:
            raise ValueError(f"Единица измерения с ID {update_dict['unit_id']} не найдена")

    if "sku" in update_dict:
        existing = db.query(Material).filter(
            Material.sku == update_dict["sku"],
            Material.id != material_id,
            Material.archived_at.is_(None),
        ).first()
        if existing:
            raise ValueError(f"Материал с SKU '{update_dict['sku']}' уже существует")

    for key, value in update_dict.items():
        setattr(db_material, key, value)

    db.flush()
    return db_material


def archive_material(db: Session, material_id: str) -> Optional[Material]:
    db_material = get_material(db, material_id)
    if not db_material:
        return None

    db_material.archived_at = func.now()
    db.flush()
    return db_material

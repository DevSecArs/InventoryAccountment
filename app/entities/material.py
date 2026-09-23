"""Материал: основной справочник."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.entities.unit import Unit, get_unit
from app.postgresql import Base


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sku: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_id: Mapped[str] = mapped_column(String(36), ForeignKey("units.id"), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    unit: Mapped[Unit] = relationship(lazy="joined")


class MaterialCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
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
    sku: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    unit_id: str | None = None

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip().upper()
        return v


class MaterialResponse(BaseModel):
    id: str
    sku: str
    name: str
    description: str | None = None
    unit_id: str
    archived_at: datetime | None = None
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


def get_material(db: Session, material_id: str) -> Material | None:
    return (
        db.query(Material)
        .filter(Material.id == material_id, Material.archived_at.is_(None))
        .first()
    )


def get_materials_by_unit(db: Session, unit_id: str) -> list[Material]:
    return (
        db.query(Material).filter(Material.unit_id == unit_id, Material.archived_at.is_(None)).all()
    )


def has_materials_by_unit(db: Session, unit_id: str) -> bool:
    """Проверить ссылки на единицу, включая архивированные материалы."""
    return db.query(Material.id).filter(Material.unit_id == unit_id).first() is not None


def get_materials(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
    search: str | None = None,
) -> tuple[list[Material], int]:
    query = db.query(Material)

    if not include_archived:
        query = query.filter(Material.archived_at.is_(None))

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Material.sku.ilike(search_pattern)) | (Material.name.ilike(search_pattern))
        )

    total = query.count()
    items = query.order_by(Material.name).offset(skip).limit(limit).all()
    return items, total


def update_material(
    db: Session, material_id: str, material_data: MaterialUpdate
) -> Material | None:
    db_material = get_material(db, material_id)
    if not db_material:
        return None

    update_dict = material_data.model_dump(exclude_unset=True)

    if "unit_id" in update_dict:
        unit = get_unit(db, update_dict["unit_id"])
        if not unit:
            raise ValueError(f"Единица измерения с ID {update_dict['unit_id']} не найдена")

    if "sku" in update_dict:
        existing = (
            db.query(Material)
            .filter(
                Material.sku == update_dict["sku"],
                Material.id != material_id,
                Material.archived_at.is_(None),
            )
            .first()
        )
        if existing:
            raise ValueError(f"Материал с SKU '{update_dict['sku']}' уже существует")

    for key, value in update_dict.items():
        setattr(db_material, key, value)

    db.flush()
    return db_material


def archive_material(db: Session, material_id: str) -> Material | None:
    db_material = get_material(db, material_id)
    if not db_material:
        return None

    db_material.archived_at = func.now()
    db.flush()
    return db_material


def purge_archived_material(db: Session, material_id: str) -> bool:
    """Безвозвратно удалить архивный материал.

    Строки поступлений в текущей схеме ещё отсутствуют. После их появления
    ограничение внешнего ключа не позволит удалить использованный материал.
    """
    material = (
        db.query(Material)
        .filter(Material.id == material_id, Material.archived_at.is_not(None))
        .first()
    )
    if not material:
        return False
    db.delete(material)
    db.flush()
    return True

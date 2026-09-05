"""Единица измерения: справочник для материалов."""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.orm import Session

from app.postgresql import Base


# ==================== SQLAlchemy модель ====================

class Unit(Base):
    """Единица измерения (справочник)."""

    __tablename__ = "units"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    archived_at = Column(DateTime, nullable=True, default=None)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Unit(id={self.id}, code={self.code}, name={self.name})>"


# ==================== Pydantic схемы ====================

class UnitCreate(BaseModel):
    """Схема для создания единицы измерения."""

    code: str = Field(..., min_length=1, max_length=50, description="Уникальный код")
    name: str = Field(..., min_length=1, max_length=200, description="Полное наименование")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """Приводим код к верхнему регистру."""
        return v.strip().upper()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Наименование не может быть пустым")
        return v.strip()


class UnitUpdate(BaseModel):
    """Схема для обновления единицы измерения."""

    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=200)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip().upper()
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError("Наименование не может быть пустым")
        if v is not None:
            return v.strip()
        return v


class UnitResponse(BaseModel):
    """Схема ответа с данными единицы измерения."""

    id: str
    code: str
    name: str
    archived_at: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ==================== CRUD операции ====================

def create_unit(db: Session, unit_data: UnitCreate) -> Unit:
    """Создать новую единицу измерения."""
    # Проверяем уникальность кода
    existing = db.query(Unit).filter(Unit.code == unit_data.code).first()
    if existing:
        raise ValueError(f"Единица измерения с кодом '{unit_data.code}' уже существует")

    db_unit = Unit(
        code=unit_data.code,
        name=unit_data.name,
    )
    db.add(db_unit)
    db.flush()
    return db_unit


def get_unit(db: Session, unit_id: str) -> Optional[Unit]:
    """Получить единицу измерения по ID (не архивированную)."""
    return db.query(Unit).filter(Unit.id == unit_id, Unit.archived_at.is_(None)).first()


def get_unit_by_code(db: Session, code: str) -> Optional[Unit]:
    """Получить единицу измерения по коду."""
    return db.query(Unit).filter(Unit.code == code.upper(), Unit.archived_at.is_(None)).first()


def get_units(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
    search: Optional[str] = None,
) -> tuple[list[Unit], int]:
    """Получить список единиц измерения с пагинацией и поиском."""
    query = db.query(Unit)

    if not include_archived:
        query = query.filter(Unit.archived_at.is_(None))

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Unit.code.ilike(search_pattern)) | (Unit.name.ilike(search_pattern))
        )

    total = query.count()
    items = query.order_by(Unit.name).offset(skip).limit(limit).all()
    return items, total


def update_unit(db: Session, unit_id: str, unit_data: UnitUpdate) -> Optional[Unit]:
    """Обновить единицу измерения."""
    db_unit = get_unit(db, unit_id)
    if not db_unit:
        return None

    update_dict = unit_data.model_dump(exclude_unset=True)

    if "code" in update_dict:
        existing = db.query(Unit).filter(
            Unit.code == update_dict["code"],
            Unit.id != unit_id,
            Unit.archived_at.is_(None),
        ).first()
        if existing:
            raise ValueError(f"Единица измерения с кодом '{update_dict['code']}' уже существует")

    for key, value in update_dict.items():
        setattr(db_unit, key, value)

    db.flush()
    return db_unit


def archive_unit(db: Session, unit_id: str) -> Optional[Unit]:
    """Архивировать единицу измерения (мягкое удаление)."""
    db_unit = get_unit(db, unit_id)
    if not db_unit:
        return None

    # Проверяем, что единица не используется в материалах
    from app.entities.material import get_materials_by_unit
    if get_materials_by_unit(db, unit_id):
        raise ValueError("Нельзя архивировать единицу, используемую в материалах")

    db_unit.archived_at = func.now()
    db.flush()
    return db_unit

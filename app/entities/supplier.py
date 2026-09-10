"""Поставщик: справочник контрагентов."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.orm import Session

from app.postgresql import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    contact_person = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    archived_at = Column(DateTime, nullable=True, default=None)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SupplierCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    contact_person: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Наименование не может быть пустым")
        return v.strip()


class SupplierUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    contact_person: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip().upper()
        return v


class SupplierResponse(BaseModel):
    id: str
    code: str
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierListResponse(BaseModel):
    """Ответ со страницей поставщиков."""

    items: list[SupplierResponse]
    total: int
    skip: int
    limit: int


def create_supplier(db: Session, supplier_data: SupplierCreate) -> Supplier:
    existing = db.query(Supplier).filter(Supplier.code == supplier_data.code).first()
    if existing:
        raise ValueError(f"Поставщик с кодом '{supplier_data.code}' уже существует")

    db_supplier = Supplier(**supplier_data.model_dump())
    db.add(db_supplier)
    db.flush()
    return db_supplier


def get_supplier(db: Session, supplier_id: str) -> Optional[Supplier]:
    return db.query(Supplier).filter(
        Supplier.id == supplier_id,
        Supplier.archived_at.is_(None)
    ).first()


def get_suppliers(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
    search: Optional[str] = None,
) -> tuple[list[Supplier], int]:
    query = db.query(Supplier)

    if not include_archived:
        query = query.filter(Supplier.archived_at.is_(None))

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Supplier.code.ilike(search_pattern)) |
            (Supplier.name.ilike(search_pattern)) |
            (Supplier.contact_person.ilike(search_pattern))
        )

    total = query.count()
    items = query.order_by(Supplier.name).offset(skip).limit(limit).all()
    return items, total


def update_supplier(db: Session, supplier_id: str, supplier_data: SupplierUpdate) -> Optional[Supplier]:
    db_supplier = get_supplier(db, supplier_id)
    if not db_supplier:
        return None

    update_dict = supplier_data.model_dump(exclude_unset=True)

    if "code" in update_dict:
        existing = db.query(Supplier).filter(
            Supplier.code == update_dict["code"],
            Supplier.id != supplier_id,
            Supplier.archived_at.is_(None),
        ).first()
        if existing:
            raise ValueError(f"Поставщик с кодом '{update_dict['code']}' уже существует")

    for key, value in update_dict.items():
        setattr(db_supplier, key, value)

    db.flush()
    return db_supplier


def archive_supplier(db: Session, supplier_id: str) -> Optional[Supplier]:
    db_supplier = get_supplier(db, supplier_id)
    if not db_supplier:
        return None

    db_supplier.archived_at = func.now()
    db.flush()
    return db_supplier

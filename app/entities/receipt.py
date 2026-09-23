"""Черновики поступлений."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.entities.material import get_material
from app.entities.supplier import get_supplier
from app.entities.unit import get_unit
from app.postgresql import Base


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("supplier_id", "document_number"),
        CheckConstraint("status IN ('draft', 'queued', 'processing', 'posted', 'failed')"),
        Index("ix_receipts_status_received_at", "status", "received_at"),
        Index("ix_receipts_supplier_received_at", "supplier_id", "received_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False)
    document_number: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    items: Mapped[list[ReceiptItem]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan", lazy="selectin"
    )


class ReceiptItem(Base):
    __tablename__ = "receipt_items"
    __table_args__ = (
        UniqueConstraint("receipt_id", "material_id"),
        CheckConstraint("quantity > 0"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    receipt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    material_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("materials.id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    receipt: Mapped[Receipt] = relationship(back_populates="items")


class ReceiptItemPayload(BaseModel):
    material_id: str
    quantity: Decimal = Field(max_digits=18, decimal_places=3)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal) -> Decimal:
        if not value > 0:
            raise PydanticCustomError("quantity_not_positive", "Количество должно быть больше нуля")
        return value


class ReceiptItemResponse(BaseModel):
    id: str
    material_id: str
    quantity: Decimal

    class Config:
        from_attributes = True


class ReceiptCreate(BaseModel):
    supplier_id: str
    document_number: str = Field(min_length=1, max_length=64)
    received_at: datetime
    items: list[ReceiptItemPayload] = Field(min_length=1)

    @field_validator("document_number")
    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise PydanticCustomError(
                "document_number_blank", "Номер документа не может быть пустым"
            )
        return value


class ReceiptUpdate(BaseModel):
    supplier_id: str | None = None
    document_number: str | None = Field(None, min_length=1, max_length=64)
    received_at: datetime | None = None
    items: list[ReceiptItemPayload] | None = Field(None, min_length=1)

    @field_validator("document_number")
    @classmethod
    def normalize(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value


class ReceiptResponse(BaseModel):
    id: str
    supplier_id: str
    document_number: str
    received_at: datetime
    status: str
    items: list[ReceiptItemResponse]

    class Config:
        from_attributes = True


class ReceiptListResponse(BaseModel):
    items: list[ReceiptResponse]
    total: int
    skip: int
    limit: int


def _items(
    db: Session, values: list[ReceiptItemPayload] | list[dict[str, object]]
) -> list[ReceiptItem]:
    values = [ReceiptItemPayload.model_validate(item) for item in values]
    if len({item.material_id for item in values}) != len(values):
        raise ValueError("Материал повторяется")
    result = []
    for item in values:
        material = get_material(db, item.material_id)
        if material is None or get_unit(db, material.unit_id) is None:
            raise LookupError("Материал недоступен")
        result.append(ReceiptItem(material_id=item.material_id, quantity=item.quantity))
    return result


def create_receipt(db: Session, value: ReceiptCreate) -> Receipt:
    if get_supplier(db, value.supplier_id) is None:
        raise LookupError("Поставщик не найден")
    if (
        db.query(Receipt)
        .filter_by(supplier_id=value.supplier_id, document_number=value.document_number)
        .first()
    ):
        raise ValueError("Дубликат документа")
    receipt = Receipt(
        supplier_id=value.supplier_id,
        document_number=value.document_number,
        received_at=value.received_at,
    )
    receipt.items = _items(db, value.items)
    db.add(receipt)
    db.flush()
    return receipt


def get_receipt(db: Session, receipt_id: str) -> Receipt | None:
    return db.get(Receipt, receipt_id)


def get_receipts(db: Session, skip: int, limit: int) -> tuple[list[Receipt], int]:
    query = db.query(Receipt).order_by(Receipt.created_at.desc())
    return query.offset(skip).limit(limit).all(), query.count()


def update_receipt(db: Session, receipt: Receipt, value: ReceiptUpdate) -> Receipt:
    if receipt.status != "draft":
        raise ValueError("Изменять можно только черновик")
    data = value.model_dump(exclude_unset=True)
    supplier_id = data.get("supplier_id", receipt.supplier_id)
    number = data.get("document_number", receipt.document_number)
    if get_supplier(db, supplier_id) is None:
        raise LookupError("Поставщик не найден")
    if (
        db.query(Receipt)
        .filter(
            Receipt.supplier_id == supplier_id,
            Receipt.document_number == number,
            Receipt.id != receipt.id,
        )
        .first()
    ):
        raise ValueError("Дубликат документа")
    receipt.supplier_id = supplier_id
    receipt.document_number = number
    if "received_at" in data:
        receipt.received_at = data["received_at"]
    if "items" in data:
        receipt.items = _items(db, data["items"])
    db.flush()
    return receipt

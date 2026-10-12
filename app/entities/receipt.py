"""Черновики поступлений."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
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
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship, selectinload

from app.entities.material import Material, get_material
from app.entities.receipt_status_history import ReceiptStatusHistory
from app.entities.supplier import Supplier, get_supplier
from app.entities.unit import Unit, get_unit
from app.postgresql import Base


def _normalize_document_number(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise PydanticCustomError("document_number_blank", "Номер документа не может быть пустым")
    if len(normalized) > 64:
        raise PydanticCustomError(
            "document_number_too_long", "Номер документа не может быть длиннее 64 символов"
        )
    return normalized


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PydanticCustomError("received_at_timezone", "Дата поступления должна содержать часовой пояс")
    return value


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("supplier_id", "document_number"),
        CheckConstraint("status IN ('draft', 'queued', 'processing', 'posted', 'failed')"),
        CheckConstraint(
            "btrim(document_number) <> ''", name="ck_receipts_document_number_not_blank"
        ),
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
    supplier: Mapped[Supplier] = relationship(lazy="joined")


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
    material: Mapped[Material] = relationship(lazy="joined")


class ReceiptItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
    material_sku: str | None = None
    material_name: str | None = None
    unit_id: str | None = None
    unit_code: str | None = None
    unit_name: str | None = None

    class Config:
        from_attributes = True


class ReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: str
    document_number: str
    received_at: datetime
    items: list[ReceiptItemPayload] = Field(min_length=1)

    @field_validator("document_number")
    @classmethod
    def normalize(cls, value: str) -> str:
        return _normalize_document_number(value)

    @field_validator("received_at")
    @classmethod
    def validate_received_at(cls, value: datetime) -> datetime:
        return _require_timezone(value)


class ReceiptUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: str | None = None
    document_number: str | None = None
    received_at: datetime | None = None
    items: list[ReceiptItemPayload] | None = Field(None, min_length=1)

    @field_validator("document_number")
    @classmethod
    def normalize(cls, value: str | None) -> str | None:
        return _normalize_document_number(value) if value is not None else value

    @field_validator("received_at")
    @classmethod
    def validate_received_at(cls, value: datetime | None) -> datetime | None:
        return _require_timezone(value) if value is not None else value


class ReceiptResponse(BaseModel):
    id: str
    supplier_id: str
    supplier_name: str | None = None
    document_number: str
    received_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime
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
    return (
        db.query(Receipt)
        .options(
            selectinload(Receipt.items).joinedload(ReceiptItem.material).joinedload(Material.unit)
        )
        .filter(Receipt.id == receipt_id)
        .first()
    )


def get_receipt_for_update(db: Session, receipt_id: str) -> Receipt | None:
    receipt = db.execute(select(Receipt).where(Receipt.id == receipt_id).with_for_update()).scalar_one_or_none()
    if receipt is not None:
        db.execute(select(ReceiptItem).where(ReceiptItem.receipt_id == receipt_id).with_for_update()).scalars().all()
    return receipt


def get_receipts(
    db: Session,
    skip: int,
    limit: int,
    supplier_id: str | None = None,
    status: str | None = None,
    search: str | None = None,
    received_from: datetime | None = None,
    received_to: datetime | None = None,
) -> tuple[list[Receipt], int]:
    query = db.query(Receipt).options(
        selectinload(Receipt.items).joinedload(ReceiptItem.material).joinedload(Material.unit)
    )
    if supplier_id:
        query = query.filter(Receipt.supplier_id == supplier_id)
    if status:
        query = query.filter(Receipt.status == status)
    if search:
        query = query.filter(Receipt.document_number.ilike(f"%{search.strip()}%"))
    if received_from:
        query = query.filter(Receipt.received_at >= received_from)
    if received_to:
        query = query.filter(Receipt.received_at < received_to)
    query = query.order_by(Receipt.created_at.desc(), Receipt.id.desc())
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


def delete_receipt(db: Session, receipt: Receipt) -> None:
    if receipt.status != "draft":
        raise ValueError("Удалять можно только черновик")
    db.delete(receipt)
    db.flush()


def _check_posting_links(db: Session, receipt: Receipt) -> None:
    supplier = db.execute(select(Supplier).where(Supplier.id == receipt.supplier_id).with_for_update()).scalar_one_or_none()
    if supplier is None or supplier.archived_at is not None:
        raise ValueError("Поставщик архивирован или недоступен")
    items = db.execute(
        select(ReceiptItem).where(ReceiptItem.receipt_id == receipt.id).order_by(ReceiptItem.material_id).with_for_update()
    ).scalars().all()
    if not items:
        raise ValueError("Поступление должно содержать хотя бы одну строку")
    material_ids = [item.material_id for item in items]
    if len(material_ids) != len(set(material_ids)):
        raise ValueError("Материал повторяется")
    materials = db.execute(
        select(Material).where(Material.id.in_(material_ids)).order_by(Material.id).with_for_update()
    ).scalars().all()
    if len(materials) != len(material_ids) or any(material.archived_at is not None for material in materials):
        raise ValueError("Материал архивирован или недоступен")
    unit_ids = sorted({material.unit_id for material in materials})
    units = db.execute(select(Unit).where(Unit.id.in_(unit_ids)).order_by(Unit.id).with_for_update()).scalars().all()
    if len(units) != len(unit_ids) or any(unit.archived_at is not None for unit in units):
        raise ValueError("Единица измерения архивирована или недоступна")


def post_receipt(db: Session, receipt_id: str) -> Receipt:
    receipt = get_receipt_for_update(db, receipt_id)
    if receipt is None:
        raise LookupError("Поступление не найдено")
    if receipt.status == "posted":
        return get_receipt(db, receipt_id) or receipt
    if receipt.status != "draft":
        raise ValueError("Проведение доступно только для черновика")
    _check_posting_links(db, receipt)
    receipt.status = "posted"
    receipt.updated_at = func.now()
    db.add(ReceiptStatusHistory(receipt_id=receipt.id, from_status="draft", to_status="posted"))
    db.flush()
    return get_receipt(db, receipt_id) or receipt


def get_history(db: Session, receipt_id: str) -> list[ReceiptStatusHistory]:
    return (
        db.query(ReceiptStatusHistory)
        .filter(ReceiptStatusHistory.receipt_id == receipt_id)
        .order_by(ReceiptStatusHistory.changed_at, ReceiptStatusHistory.id)
        .all()
    )


def receipt_to_response(receipt: Receipt) -> dict[str, object]:
    return {
        "id": receipt.id,
        "supplier_id": receipt.supplier_id,
        "supplier_name": receipt.supplier.name if receipt.supplier else None,
        "document_number": receipt.document_number,
        "received_at": receipt.received_at,
        "status": receipt.status,
        "created_at": receipt.created_at,
        "updated_at": receipt.updated_at,
        "items": [
            {
                "id": item.id,
                "material_id": item.material_id,
                "quantity": item.quantity,
                "material_sku": item.material.sku if item.material else None,
                "material_name": item.material.name if item.material else None,
                "unit_id": item.material.unit_id if item.material else None,
                "unit_code": item.material.unit.code if item.material and item.material.unit else None,
                "unit_name": item.material.unit.name if item.material and item.material.unit else None,
            }
            for item in receipt.items
        ],
    }

"""Неизменяемая история проведения поступлений."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.postgresql import Base


class ReceiptStatusHistory(Base):
    __tablename__ = "receipt_status_history"
    __table_args__ = (
        UniqueConstraint("receipt_id", name="uq_receipt_status_history_receipt_id"),
        Index("ix_receipt_status_history_receipt_changed_id", "receipt_id", "changed_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    receipt_id: Mapped[str] = mapped_column(String(36), ForeignKey("receipts.id"), nullable=False)
    from_status: Mapped[str] = mapped_column(String(16), nullable=False)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ReceiptStatusHistoryResponse(BaseModel):
    id: str
    receipt_id: str
    from_status: str
    to_status: str
    changed_at: datetime
    reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ReceiptHistoryResponse(BaseModel):
    items: list[ReceiptStatusHistoryResponse]

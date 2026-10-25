"""Отчёт по проведённым поступлениям и экспорт CSV."""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from io import StringIO
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.engine import Result
from sqlalchemy.orm import Session

from app.entities.material import Material
from app.entities.receipt import Receipt, ReceiptItem
from app.entities.supplier import Supplier
from app.entities.unit import Unit


class SupplyReportItem(BaseModel):
    receipt_id: str
    document_number: str
    received_at: datetime
    supplier_id: str
    supplier_name: str
    material_id: str
    material_sku: str
    material_name: str
    unit_id: str
    unit_code: str
    unit_name: str
    quantity: Decimal


class SupplyReportTotal(BaseModel):
    material_id: str
    material_sku: str
    material_name: str
    unit_id: str
    unit_code: str
    unit_name: str
    quantity: Decimal


class SupplyReportResponse(BaseModel):
    items: list[SupplyReportItem]
    total: int
    skip: int
    limit: int
    totals: list[SupplyReportTotal]


def validate_period(date_from: datetime, date_to: datetime) -> None:
    if date_from.tzinfo is None or date_from.utcoffset() is None:
        raise ValueError("Параметр from должен содержать часовой пояс")
    if date_to.tzinfo is None or date_to.utcoffset() is None:
        raise ValueError("Параметр to должен содержать часовой пояс")
    if date_from >= date_to:
        raise ValueError("Параметр from должен быть меньше to")


def _base_query(
    date_from: datetime, date_to: datetime, supplier_id: str | None, material_id: str | None
) -> Select[Any]:
    query = (
        select(
            Receipt.id.label("receipt_id"),
            Receipt.document_number,
            Receipt.received_at,
            Supplier.id.label("supplier_id"),
            Supplier.name.label("supplier_name"),
            Material.id.label("material_id"),
            Material.sku.label("material_sku"),
            Material.name.label("material_name"),
            Unit.id.label("unit_id"),
            Unit.code.label("unit_code"),
            Unit.name.label("unit_name"),
            ReceiptItem.quantity,
        )
        .join(ReceiptItem, ReceiptItem.receipt_id == Receipt.id)
        .join(Supplier, Supplier.id == Receipt.supplier_id)
        .join(Material, Material.id == ReceiptItem.material_id)
        .join(Unit, Unit.id == Material.unit_id)
        .where(
            Receipt.status == "posted",
            Receipt.received_at >= date_from,
            Receipt.received_at < date_to,
        )
    )
    if supplier_id:
        query = query.where(Receipt.supplier_id == supplier_id)
    if material_id:
        query = query.where(ReceiptItem.material_id == material_id)
    return query


def _mapping_rows(result: Result[Any]) -> list[dict[str, object]]:
    return [dict(row) for row in result.mappings().all()]


def get_supply_report(
    db: Session,
    date_from: datetime,
    date_to: datetime,
    supplier_id: str | None,
    material_id: str | None,
    skip: int,
    limit: int,
) -> dict[str, object]:
    validate_period(date_from, date_to)
    base = _base_query(date_from, date_to, supplier_id, material_id).subquery()
    total = db.scalar(select(func.count()).select_from(base)) or 0
    items = _mapping_rows(
        db.execute(
            select(base)
            .order_by(base.c.received_at, base.c.receipt_id, base.c.material_id)
            .offset(skip)
            .limit(limit)
        )
    )
    totals = _mapping_rows(
        db.execute(
            select(
                base.c.material_id,
                base.c.material_sku,
                base.c.material_name,
                base.c.unit_id,
                base.c.unit_code,
                base.c.unit_name,
                func.sum(base.c.quantity).label("quantity"),
            )
            .group_by(
                base.c.material_id,
                base.c.material_sku,
                base.c.material_name,
                base.c.unit_id,
                base.c.unit_code,
                base.c.unit_name,
            )
            .order_by(base.c.material_id, base.c.unit_id)
        )
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit, "totals": totals}


def get_supply_export(
    db: Session,
    date_from: datetime,
    date_to: datetime,
    supplier_id: str | None,
    material_id: str | None,
) -> list[dict[str, object]]:
    validate_period(date_from, date_to)
    base = _base_query(date_from, date_to, supplier_id, material_id).subquery()
    return _mapping_rows(
        db.execute(select(base).order_by(base.c.received_at, base.c.receipt_id, base.c.material_id))
    )


CSV_FIELDS = [
    "receipt_id",
    "document_number",
    "received_at",
    "supplier_id",
    "supplier_name",
    "material_id",
    "material_sku",
    "material_name",
    "unit_id",
    "unit_code",
    "unit_name",
    "quantity",
]
CSV_HEADERS = [
    "ID поступления",
    "Номер документа",
    "Дата поступления",
    "ID поставщика",
    "Поставщик",
    "ID материала",
    "Артикул материала",
    "Материал",
    "ID единицы измерения",
    "Код единицы измерения",
    "Единица измерения",
    "Количество",
]


def _safe_csv(value: object) -> str:
    result = str(value)
    return f"'{result}" if result.startswith(("=", "+", "-", "@")) else result


def render_csv(rows: list[dict[str, object]]) -> str:
    buffer = StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_HEADERS)
    for row in rows:
        rendered = {key: _safe_csv(row[key]) for key in CSV_FIELDS}
        rendered["quantity"] = format(row["quantity"], "f")
        rendered["received_at"] = cast(datetime, row["received_at"]).isoformat()
        writer.writerow([rendered[key] for key in CSV_FIELDS])
    return "\ufeff" + buffer.getvalue()

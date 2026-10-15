"""Чистые unit-проверки периода и CSV-экспорта."""

import csv
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO

import pytest

from app.entities.supply_report import CSV_HEADERS, render_csv, validate_period


def _row(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "receipt_id": "receipt-1",
        "document_number": "DOC-1",
        "received_at": datetime(2026, 1, 1, 9, 30, tzinfo=UTC),
        "supplier_id": "supplier-1",
        "supplier_name": 'Поставщик, "А"\nНовый',
        "material_id": "material-1",
        "material_sku": "MAT-1",
        "material_name": "Материал",
        "unit_id": "unit-1",
        "unit_code": "KG",
        "unit_name": "Килограмм",
        "quantity": Decimal("0.100"),
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    ("date_from", "date_to"),
    [
        (datetime.fromisoformat("2026-01-01"), datetime(2026, 1, 2, tzinfo=UTC)),
        (datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)),
        (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)),
    ],
)
def test_period_requires_aware_and_forward_datetimes(
    date_from: datetime, date_to: datetime
) -> None:
    with pytest.raises(ValueError):
        validate_period(date_from, date_to)


def test_csv_uses_bom_rfc_csv_and_exact_decimal_values() -> None:
    rendered = render_csv([_row(document_number="=formula")])

    assert rendered.startswith("\ufeff")
    rows = list(csv.DictReader(StringIO(rendered.removeprefix("\ufeff"))))
    assert list(rows[0]) == CSV_HEADERS
    assert rows == [
        {
            "ID поступления": "receipt-1",
            "Номер документа": "'=formula",
            "Дата поступления": "2026-01-01T09:30:00+00:00",
            "ID поставщика": "supplier-1",
            "Поставщик": 'Поставщик, "А"\nНовый',
            "ID материала": "material-1",
            "Артикул материала": "MAT-1",
            "Материал": "Материал",
            "ID единицы измерения": "unit-1",
            "Код единицы измерения": "KG",
            "Единица измерения": "Килограмм",
            "Количество": "0.100",
        }
    ]


def test_empty_csv_contains_only_bom_and_header() -> None:
    rendered = render_csv([])
    assert rendered.startswith("\ufeff")
    assert list(csv.DictReader(StringIO(rendered.removeprefix("\ufeff")))) == []

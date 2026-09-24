from collections.abc import Callable

import pytest
from pydantic import BaseModel, ValidationError

from app.entities.auth import RegisterRequest
from app.entities.material import MaterialCreate
from app.entities.receipt import ReceiptCreate, ReceiptItemPayload, ReceiptUpdate
from app.entities.supplier import SupplierCreate
from app.entities.unit import UnitCreate


def test_catalog_keys_are_trimmed_and_normalized() -> None:
    assert UnitCreate(code=" kg ").code == "KG"
    assert MaterialCreate(sku=" sku-1 ", name=" Материал ", unit_id="unit").sku == "SKU-1"
    assert SupplierCreate(code=" supplier-1 ", name=" Поставщик ").code == "SUPPLIER-1"


@pytest.mark.parametrize("code", ["", "unknown", "kg!"])
def test_unit_rejects_invalid_si_code(code: str) -> None:
    with pytest.raises(ValidationError):
        UnitCreate(code=code)


@pytest.mark.parametrize("login", ["ab", "bad login", "   "])
def test_registration_rejects_invalid_login(login: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(login=login, password="reliable-test-password", full_name="Тест")


@pytest.mark.parametrize(
    "factory, kwargs",
    [
        (MaterialCreate, {"sku": "SKU", "name": "   ", "unit_id": "unit"}),
        (SupplierCreate, {"code": "SUP", "name": "   "}),
    ],
)
def test_catalog_rejects_blank_names(
    factory: Callable[..., BaseModel], kwargs: dict[str, str]
) -> None:
    with pytest.raises(ValidationError):
        factory(**kwargs)


@pytest.mark.parametrize(
    ("value", "normalized"),
    [
        ("D" * 64, "D" * 64),
        ("  DOC-1  ", "DOC-1"),
    ],
)
def test_receipt_document_number_is_normalized_and_has_boundary(
    value: str, normalized: str
) -> None:
    receipt = ReceiptCreate(
        supplier_id="supplier",
        document_number=value,
        received_at="2026-01-01T00:00:00+00:00",
        items=[{"material_id": "material", "quantity": "0.001"}],
    )

    assert receipt.document_number == normalized


@pytest.mark.parametrize("value", ["", "   ", "D" * 65])
def test_receipt_rejects_invalid_document_number(value: str) -> None:
    with pytest.raises(ValidationError):
        ReceiptUpdate(document_number=value)


@pytest.mark.parametrize("quantity", ["0", "-0.001", "0.0001", "1234567890123456.789"])
def test_receipt_quantity_respects_positive_numeric_18_3(quantity: str) -> None:
    with pytest.raises(ValidationError):
        ReceiptItemPayload(material_id="material", quantity=quantity)

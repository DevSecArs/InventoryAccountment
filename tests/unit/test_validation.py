import pytest
from pydantic import ValidationError

from app.entities.auth import RegisterRequest
from app.entities.material import MaterialCreate
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


@pytest.mark.parametrize("factory, kwargs", [
    (MaterialCreate, {"sku": "SKU", "name": "   ", "unit_id": "unit"}),
    (SupplierCreate, {"code": "SUP", "name": "   "}),
])
def test_catalog_rejects_blank_names(factory: object, kwargs: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        factory(**kwargs)

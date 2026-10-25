import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.entities import routers
from app.postgresql import get_session_factory


def _create_catalog(
    client: TestClient, headers: dict[str, str], suffix: str = ""
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    unit_code = {"": "KG", "2": "L", "3": "M"}.get(suffix, "S")
    unit = client.post("/api/v1/units/", json={"code": unit_code}, headers=headers).json()
    supplier = client.post(
        "/api/v1/suppliers/",
        json={"code": f"S{suffix}", "name": f"Поставщик {suffix}"},
        headers=headers,
    ).json()
    material = client.post(
        "/api/v1/materials/",
        json={"sku": f"M{suffix}", "name": f"Материал {suffix}", "unit_id": unit["id"]},
        headers=headers,
    ).json()
    return unit, supplier, material


def _receipt_payload(
    supplier_id: object, material_id: object, document_number: str = "DOC-1"
) -> dict[str, object]:
    return {
        "supplier_id": supplier_id,
        "document_number": document_number,
        "received_at": "2026-01-01T12:00:00+00:00",
        "items": [{"material_id": material_id, "quantity": "1.000"}],
    }


def _assert_error(response: Response, status_code: int) -> None:
    expected_code = "validation_error" if status_code == 422 else f"http_{status_code}"
    assert response.status_code == status_code
    body = response.json()
    assert body["code"] == expected_code
    assert {"code", "message", "details", "request_id"} <= body.keys()


def test_receipt_draft_create_read_and_replace(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    unit = client.post("/api/v1/units/", json={"code": "KG"}, headers=headers).json()
    supplier = client.post(
        "/api/v1/suppliers/", json={"code": "S", "name": "Поставщик"}, headers=headers
    ).json()
    first = client.post(
        "/api/v1/materials/",
        json={"sku": "M1", "name": "Материал", "unit_id": unit["id"]},
        headers=headers,
    ).json()
    second = client.post(
        "/api/v1/materials/",
        json={"sku": "M2", "name": "Другой", "unit_id": unit["id"]},
        headers=headers,
    ).json()
    payload = {
        "supplier_id": supplier["id"],
        "document_number": " DOC-1 ",
        "received_at": "2026-01-01T12:00:00+00:00",
        "items": [{"material_id": first["id"], "quantity": "1.250"}],
    }
    created = client.post("/api/v1/receipts/", json=payload, headers=headers)
    assert created.status_code == 201
    receipt_id = created.json()["id"]
    assert created.json()["document_number"] == "DOC-1"
    changed = client.patch(
        f"/api/v1/receipts/{receipt_id}",
        json={"items": [{"material_id": second["id"], "quantity": "2"}]},
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["items"][0]["material_id"] == second["id"]
    assert client.get(f"/api/v1/receipts/{receipt_id}").status_code == 200
    assert client.get("/api/v1/receipts/").json()["total"] == 1


def test_receipt_rejects_invalid_items(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    unit = client.post("/api/v1/units/", json={"code": "KG"}, headers=headers).json()
    supplier = client.post(
        "/api/v1/suppliers/", json={"code": "S", "name": "Поставщик"}, headers=headers
    ).json()
    material = client.post(
        "/api/v1/materials/",
        json={"sku": "M1", "name": "Материал", "unit_id": unit["id"]},
        headers=headers,
    ).json()
    payload = {
        "supplier_id": supplier["id"],
        "document_number": "DOC",
        "received_at": "2026-01-01T12:00:00+00:00",
        "items": [],
    }
    assert client.post("/api/v1/receipts/", json=payload, headers=headers).status_code == 422
    payload["items"] = [{"material_id": material["id"], "quantity": "0"}]
    assert client.post("/api/v1/receipts/", json=payload, headers=headers).status_code == 422


def test_receipt_update_rejects_blank_document_number(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    unit = client.post("/api/v1/units/", json={"code": "KG"}, headers=headers).json()
    supplier = client.post(
        "/api/v1/suppliers/", json={"code": "S", "name": "Поставщик"}, headers=headers
    ).json()
    material = client.post(
        "/api/v1/materials/",
        json={"sku": "M1", "name": "Материал", "unit_id": unit["id"]},
        headers=headers,
    ).json()
    created = client.post(
        "/api/v1/receipts/",
        json={
            "supplier_id": supplier["id"],
            "document_number": "DOC-1",
            "received_at": "2026-01-01T12:00:00+00:00",
            "items": [{"material_id": material["id"], "quantity": "1"}],
        },
        headers=headers,
    )

    response = client.patch(
        f"/api/v1/receipts/{created.json()['id']}",
        json={"document_number": "   "},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_receipt_database_rejects_blank_document_number(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    supplier = client.post(
        "/api/v1/suppliers/", json={"code": "S", "name": "Поставщик"}, headers=headers
    ).json()
    session = get_session_factory()()
    try:
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    """
                    INSERT INTO receipts (id, supplier_id, document_number, received_at, status)
                    VALUES ('00000000-0000-0000-0000-000000000001', :supplier_id, '   ', now(), 'draft')
                    """
                ),
                {"supplier_id": supplier["id"]},
            )
        session.rollback()
    finally:
        session.close()


def test_receipt_document_number_boundaries_and_supplier_uniqueness(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    _, supplier, material = _create_catalog(client, headers)

    for number in ("", "   ", "D" * 65):
        response = client.post(
            "/api/v1/receipts/",
            json=_receipt_payload(supplier["id"], material["id"], number),
            headers=headers,
        )
        _assert_error(response, 422)

    number = "D" * 64
    created = client.post(
        "/api/v1/receipts/",
        json=_receipt_payload(supplier["id"], material["id"], f"  {number}  "),
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["document_number"] == number

    duplicate = client.post(
        "/api/v1/receipts/",
        json=_receipt_payload(supplier["id"], material["id"], number),
        headers=headers,
    )
    _assert_error(duplicate, 409)

    _, another_supplier, another_material = _create_catalog(client, headers, "2")
    permitted = client.post(
        "/api/v1/receipts/",
        json=_receipt_payload(another_supplier["id"], another_material["id"], number),
        headers=headers,
    )
    assert permitted.status_code == 201


@pytest.mark.parametrize("quantity", ["0", "-1", "0.0001", "1234567890123456.789"])
def test_receipt_rejects_quantity_boundaries(
    authenticated_client: tuple[TestClient, dict[str, str]], quantity: str
) -> None:
    client, headers = authenticated_client
    _, supplier, material = _create_catalog(client, headers)
    payload = _receipt_payload(supplier["id"], material["id"])
    payload["items"] = [{"material_id": material["id"], "quantity": quantity}]

    _assert_error(client.post("/api/v1/receipts/", json=payload, headers=headers), 422)


def test_receipt_rejects_duplicate_and_unknown_items(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    _, supplier, material = _create_catalog(client, headers)
    duplicate = _receipt_payload(supplier["id"], material["id"])
    duplicate["items"] = [
        {"material_id": material["id"], "quantity": "1"},
        {"material_id": material["id"], "quantity": "2"},
    ]
    _assert_error(client.post("/api/v1/receipts/", json=duplicate, headers=headers), 409)

    unknown_supplier = _receipt_payload("missing", material["id"])
    _assert_error(client.post("/api/v1/receipts/", json=unknown_supplier, headers=headers), 404)
    unknown_material = _receipt_payload(supplier["id"], "missing")
    _assert_error(client.post("/api/v1/receipts/", json=unknown_material, headers=headers), 404)


def test_receipt_rejects_archived_links(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    _, supplier, material = _create_catalog(client, headers)
    assert client.delete(f"/api/v1/suppliers/{supplier['id']}", headers=headers).status_code == 204
    archived_supplier = client.post(
        "/api/v1/receipts/",
        json=_receipt_payload(supplier["id"], material["id"]),
        headers=headers,
    )
    _assert_error(archived_supplier, 404)

    _, active_supplier, archived_material = _create_catalog(client, headers, "2")
    assert (
        client.delete(f"/api/v1/materials/{archived_material['id']}", headers=headers).status_code
        == 204
    )
    archived_material_response = client.post(
        "/api/v1/receipts/",
        json=_receipt_payload(active_supplier["id"], archived_material["id"]),
        headers=headers,
    )
    _assert_error(archived_material_response, 404)

    unit, active_supplier, active_material = _create_catalog(client, headers, "3")
    session = get_session_factory()()
    try:
        session.execute(
            text("UPDATE units SET archived_at = now() WHERE id = :id"), {"id": unit["id"]}
        )
        session.commit()
    finally:
        session.close()
    archived_unit = client.post(
        "/api/v1/receipts/",
        json=_receipt_payload(active_supplier["id"], active_material["id"]),
        headers=headers,
    )
    _assert_error(archived_unit, 404)


def test_receipt_update_rolls_back_conflicts_and_rejects_non_draft(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    _, supplier, material = _create_catalog(client, headers)
    first = client.post(
        "/api/v1/receipts/",
        json=_receipt_payload(supplier["id"], material["id"], "DOC-1"),
        headers=headers,
    ).json()
    second = client.post(
        "/api/v1/receipts/",
        json=_receipt_payload(supplier["id"], material["id"], "DOC-2"),
        headers=headers,
    ).json()

    conflict = client.patch(
        f"/api/v1/receipts/{first['id']}",
        json={
            "document_number": second["document_number"],
            "items": [{"material_id": "missing", "quantity": "1"}],
        },
        headers=headers,
    )
    _assert_error(conflict, 409)
    assert client.get(f"/api/v1/receipts/{first['id']}").json()["document_number"] == "DOC-1"

    invalid_item = client.patch(
        f"/api/v1/receipts/{first['id']}",
        json={"document_number": "DOC-3", "items": [{"material_id": "missing", "quantity": "1"}]},
        headers=headers,
    )
    _assert_error(invalid_item, 404)
    assert client.get(f"/api/v1/receipts/{first['id']}").json()["document_number"] == "DOC-1"

    session = get_session_factory()()
    try:
        session.execute(
            text("UPDATE receipts SET status = 'posted' WHERE id = :id"), {"id": first["id"]}
        )
        session.commit()
    finally:
        session.close()
    _assert_error(
        client.patch(
            f"/api/v1/receipts/{first['id']}", json={"document_number": "DOC-3"}, headers=headers
        ),
        409,
    )


def test_receipt_pagination_errors_and_database_conflict(
    authenticated_client: tuple[TestClient, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers = authenticated_client
    for query in ("?skip=-1", "?limit=0", "?limit=1001"):
        _assert_error(client.get(f"/api/v1/receipts/{query}"), 422)
    _assert_error(client.get("/api/v1/receipts/missing"), 404)
    _, supplier, material = _create_catalog(client, headers)

    def raise_integrity_error(*args: object, **kwargs: object) -> object:
        raise IntegrityError("INSERT", {}, Exception("unique conflict"))

    monkeypatch.setattr(routers.receipt_service, "create_receipt", raise_integrity_error)
    response = client.post(
        "/api/v1/receipts/",
        json=_receipt_payload(supplier["id"], material["id"]),
        headers=headers,
    )
    _assert_error(response, 409)

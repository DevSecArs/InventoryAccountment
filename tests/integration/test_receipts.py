import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.postgresql import get_session_factory


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

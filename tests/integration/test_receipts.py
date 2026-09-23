from fastapi.testclient import TestClient


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

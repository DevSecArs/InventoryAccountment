"""Интеграционные проверки отчёта и CSV только по проведённым поступлениям."""

import csv
from io import StringIO

from fastapi.testclient import TestClient


def _setup(client: TestClient, headers: dict[str, str]) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    unit = client.post("/api/v1/units/", json={"code": "KG"}, headers=headers).json()
    supplier = client.post("/api/v1/suppliers/", json={"code": "SUP", "name": "Поставщик"}, headers=headers).json()
    first = client.post("/api/v1/materials/", json={"sku": "MAT-1", "name": "Первый", "unit_id": unit["id"]}, headers=headers).json()
    second = client.post("/api/v1/materials/", json={"sku": "MAT-2", "name": "Второй", "unit_id": unit["id"]}, headers=headers).json()
    return supplier, first, second


def _receipt(client: TestClient, headers: dict[str, str], supplier_id: object, material_id: object, number: str, received_at: str, quantity: str, posted: bool) -> dict[str, object]:
    response = client.post("/api/v1/receipts/", json={"supplier_id": supplier_id, "document_number": number, "received_at": received_at, "items": [{"material_id": material_id, "quantity": quantity}]}, headers=headers)
    assert response.status_code == 201
    receipt = response.json()
    if posted:
        assert client.post(f"/api/v1/receipts/{receipt['id']}/post", headers=headers).status_code == 200
    return receipt


def test_report_period_filters_totals_and_csv(authenticated_client: tuple[TestClient, dict[str, str]]) -> None:
    client, headers = authenticated_client
    supplier, first, second = _setup(client, headers)
    _receipt(client, headers, supplier["id"], first["id"], "BEFORE", "2025-12-31T23:59:59+00:00", "1.000", True)
    _receipt(client, headers, supplier["id"], first["id"], "FROM", "2026-01-01T00:00:00+00:00", "0.100", True)
    _receipt(client, headers, supplier["id"], second["id"], "INSIDE", "2026-01-01T12:00:00+00:00", "0.200", True)
    _receipt(client, headers, supplier["id"], first["id"], "TO", "2026-01-02T00:00:00+00:00", "9.000", True)
    _receipt(client, headers, supplier["id"], first["id"], "DRAFT", "2026-01-01T13:00:00+00:00", "5.000", False)
    url = "/api/v1/reports/supplies?from=2026-01-01T00:00:00%2B00:00&to=2026-01-02T00:00:00%2B00:00"
    report = client.get(url)
    assert report.status_code == 200
    payload = report.json()
    assert [item["document_number"] for item in payload["items"]] == ["FROM", "INSIDE"]
    assert payload["total"] == 2
    assert {(item["material_id"], item["quantity"]) for item in payload["totals"]} == {(first["id"], "0.100"), (second["id"], "0.200")}
    assert [item["document_number"] for item in client.get(f"{url}&material_id={first['id']}").json()["items"]] == ["FROM"]
    export = client.get(url.replace("/supplies?", "/supplies/export?"))
    assert export.status_code == 200
    rows = list(csv.DictReader(StringIO(export.text.removeprefix("\ufeff"))))
    assert [row["document_number"] for row in rows] == ["FROM", "INSIDE"]
    assert [row["quantity"] for row in rows] == ["0.100", "0.200"]


def test_report_requires_valid_aware_forward_period(authenticated_client: tuple[TestClient, dict[str, str]]) -> None:
    client, _ = authenticated_client
    for query in ("", "?from=2026-01-01T00:00:00&to=2026-01-02T00:00:00", "?from=2026-01-02T00:00:00%2B00:00&to=2026-01-01T00:00:00%2B00:00"):
        assert client.get(f"/api/v1/reports/supplies{query}").status_code == 422

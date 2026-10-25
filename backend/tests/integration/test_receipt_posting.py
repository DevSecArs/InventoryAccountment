"""Интеграционные проверки согласованного синхронного проведения."""

from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.postgresql import get_session_factory


def _catalog(
    client: TestClient, headers: dict[str, str]
) -> tuple[dict[str, object], dict[str, object]]:
    unit = client.post("/api/v1/units/", json={"code": "KG"}, headers=headers).json()
    supplier = client.post(
        "/api/v1/suppliers/", json={"code": "SUP", "name": "Поставщик"}, headers=headers
    ).json()
    material = client.post(
        "/api/v1/materials/",
        json={"sku": "MAT", "name": "Материал", "unit_id": unit["id"]},
        headers=headers,
    ).json()
    return supplier, material


def _draft(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    supplier, material = _catalog(client, headers)
    response = client.post(
        "/api/v1/receipts/",
        json={
            "supplier_id": supplier["id"],
            "document_number": "POST-1",
            "received_at": "2026-01-01T12:00:00+00:00",
            "items": [{"material_id": material["id"], "quantity": "0.100"}],
        },
        headers=headers,
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_post_is_atomic_idempotent_and_records_one_history_entry(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    draft = _draft(client, headers)

    first = client.post(f"/api/v1/receipts/{draft['id']}/post", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "posted"
    repeated = client.post(f"/api/v1/receipts/{draft['id']}/post", headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "posted"
    assert repeated.json()["updated_at"] == first.json()["updated_at"]

    history = client.get(f"/api/v1/receipts/{draft['id']}/history")
    assert history.status_code == 200
    assert [
        {key: item[key] for key in ("from_status", "to_status")} for item in history.json()["items"]
    ] == [{"from_status": "draft", "to_status": "posted"}]

    session = get_session_factory()()
    try:
        persisted = session.execute(
            text("SELECT status FROM receipts WHERE id = :id"), {"id": draft["id"]}
        ).scalar_one()
        history_count = session.execute(
            text("SELECT count(*) FROM receipt_status_history WHERE receipt_id = :id"),
            {"id": draft["id"]},
        ).scalar_one()
    finally:
        session.close()
    assert persisted == "posted"
    assert history_count == 1


def test_post_rejects_non_draft_legacy_status_without_transforming_it(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    draft = _draft(client, headers)
    session = get_session_factory()()
    try:
        session.execute(
            text("UPDATE receipts SET status = 'queued' WHERE id = :id"), {"id": draft["id"]}
        )
        session.commit()
    finally:
        session.close()

    response = client.post(f"/api/v1/receipts/{draft['id']}/post", headers=headers)
    assert response.status_code == 409
    assert client.get(f"/api/v1/receipts/{draft['id']}").json()["status"] == "queued"
    assert client.get(f"/api/v1/receipts/{draft['id']}/history").json()["items"] == []


def test_delete_locks_and_removes_draft(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated_client
    draft = _draft(client, headers)
    deleted = client.delete(f"/api/v1/receipts/{draft['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/receipts/{draft['id']}").status_code == 404


def test_concurrent_post_records_only_one_transition(
    authenticated_client: tuple[TestClient, dict[str, str]],
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.http import app

    client, headers = authenticated_client
    draft = _draft(client, headers)
    barrier = Barrier(2, timeout=10)

    def post() -> int:
        with TestClient(app, base_url="https://testserver") as independent_client:
            independent_client.cookies.update(client.cookies)
            barrier.wait()
            return cast(
                int,
                independent_client.post(
                    f"/api/v1/receipts/{draft['id']}/post", headers=headers
                ).status_code,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(post) for _ in range(2)]
        assert [future.result(timeout=20) for future in futures] == [200, 200]
    assert len(client.get(f"/api/v1/receipts/{draft['id']}/history").json()["items"]) == 1
    assert client.delete(f"/api/v1/receipts/{draft['id']}", headers=headers).status_code == 409

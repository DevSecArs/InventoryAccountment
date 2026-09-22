from fastapi.testclient import TestClient


def test_health_and_error_format(client: TestClient) -> None:
    live = client.get("/health/live", headers={"X-Request-ID": "dd6e9c35-4b8c-41d9-b157-7d72b4c83968"})
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert live.headers["X-Request-ID"] == "dd6e9c35-4b8c-41d9-b157-7d72b4c83968"

    unauthorized = client.get("/api/v1/units/")
    assert unauthorized.status_code == 401
    assert {"code", "message", "details", "request_id"} <= unauthorized.json().keys()


def test_authentication_and_csrf_are_required(client: TestClient) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        json={"login": "admin", "password": "reliable-test-password", "full_name": "Администратор"},
    )
    assert registered.status_code == 201
    assert registered.json()["user"]["login"] == "admin"
    assert client.post("/api/v1/units/", json={"code": "KG"}).status_code == 403

    csrf = registered.json()["csrf_token"]
    assert client.post("/api/v1/units/", json={"code": "KG"}, headers={"X-CSRF-Token": csrf}).status_code == 201
    assert client.post("/api/v1/auth/register", json={"login": "next", "password": "reliable-test-password", "full_name": "Следующий"}).status_code == 409


def test_catalog_crud_pagination_search_and_archiving(authenticated_client: tuple[TestClient, dict[str, str]]) -> None:
    client, headers = authenticated_client
    unit = client.post("/api/v1/units/", json={"code": "kg"}, headers=headers)
    assert unit.status_code == 201
    unit_id = unit.json()["id"]

    supplier = client.post("/api/v1/suppliers/", json={"code": " acme ", "name": " АСМЕ "}, headers=headers)
    assert supplier.status_code == 201
    assert supplier.json()["code"] == "ACME"
    assert client.post("/api/v1/suppliers/", json={"code": "ACME", "name": "Дубликат"}, headers=headers).status_code == 400

    material = client.post("/api/v1/materials/", json={"sku": " steel-01 ", "name": " Сталь ", "unit_id": unit_id}, headers=headers)
    assert material.status_code == 201
    material_id = material.json()["id"]

    page = client.get("/api/v1/materials/?skip=0&limit=1&search=steel")
    assert page.status_code == 200
    assert page.json()["total"] == 1
    assert page.json()["items"][0]["sku"] == "STEEL-01"

    assert client.delete(f"/api/v1/materials/{material_id}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/materials/{material_id}").status_code == 404
    archived = client.get("/api/v1/materials/?include_archived=true")
    assert archived.json()["total"] == 1
    assert archived.json()["items"][0]["archived_at"] is not None

    assert client.delete(f"/api/v1/units/{unit_id}", headers=headers).status_code == 204


def test_catalog_updates_purge_and_missing_records(authenticated_client: tuple[TestClient, dict[str, str]]) -> None:
    client, headers = authenticated_client
    first_unit = client.post("/api/v1/units/", json={"code": "KG"}, headers=headers).json()
    second_unit = client.post("/api/v1/units/", json={"code": "L"}, headers=headers).json()
    assert client.get("/api/v1/units/si-options").status_code == 200
    assert client.get(f"/api/v1/units/{first_unit['id']}").status_code == 200
    assert client.put(f"/api/v1/units/{second_unit['id']}", json={"name": "Литр хранения"}, headers=headers).status_code == 200

    supplier = client.post("/api/v1/suppliers/", json={"code": "s-1", "name": "Первый"}, headers=headers).json()
    assert client.get(f"/api/v1/suppliers/{supplier['id']}").status_code == 200
    changed_supplier = client.put(
        f"/api/v1/suppliers/{supplier['id']}",
        json={"name": "Изменённый", "email": "test@example.invalid"},
        headers=headers,
    )
    assert changed_supplier.status_code == 200
    assert changed_supplier.json()["name"] == "Изменённый"

    material = client.post(
        "/api/v1/materials/",
        json={"sku": "m-1", "name": "Первый материал", "unit_id": first_unit["id"]},
        headers=headers,
    ).json()
    assert client.get(f"/api/v1/materials/{material['id']}").status_code == 200
    changed_material = client.put(
        f"/api/v1/materials/{material['id']}",
        json={"sku": "m-2", "name": "Изменённый материал", "unit_id": second_unit["id"]},
        headers=headers,
    )
    assert changed_material.status_code == 200
    assert changed_material.json()["sku"] == "M-2"
    assert client.put(
        f"/api/v1/materials/{material['id']}", json={"unit_id": "missing"}, headers=headers
    ).status_code == 400

    assert client.delete(f"/api/v1/materials/{material['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/materials/{material['id']}/purge", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/suppliers/{supplier['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/suppliers/{supplier['id']}/purge", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/units/{first_unit['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/units/{first_unit['id']}/purge", headers=headers).status_code == 204
    assert client.get("/api/v1/suppliers/missing").status_code == 404
    assert client.put("/api/v1/materials/missing", json={"name": "Нет"}, headers=headers).status_code == 404


def test_login_profile_and_logout(client: TestClient) -> None:
    payload = {"login": "admin", "password": "reliable-test-password", "full_name": "Администратор"}
    registered = client.post("/api/v1/auth/register", json=payload)
    csrf = registered.json()["csrf_token"]
    assert client.get("/api/v1/auth/me").status_code == 200
    profile = client.put("/api/v1/auth/me", json={"full_name": "Новый администратор"}, headers={"X-CSRF-Token": csrf})
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Новый администратор"
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/login", json={"login": "admin", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"login": " ADMIN ", "password": payload["password"]}).status_code == 200

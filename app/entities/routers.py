from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from app.postgresql import DatabaseSession
from app.entities import unit as unit_service
from app.entities import material as material_service
from app.entities import supplier as supplier_service
from app.entities import auth as auth_service
from app.config import settings


auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=auth_service.SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=settings.APP_ENV != "development",
        samesite="strict",
        max_age=int(auth_service.SESSION_LIFETIME.total_seconds()),
        path="/",
    )


@auth_router.post("/register", response_model=auth_service.AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: auth_service.RegisterRequest, response: Response, db: DatabaseSession):
    """Создать единственного начального администратора в пустой БД."""
    try:
        user = auth_service.create_user(db, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    token, session = auth_service.create_session(db, user)
    _set_session_cookie(response, token)
    return {"user": user, "csrf_token": session.csrf_token}


@auth_router.post("/login", response_model=auth_service.AuthResponse)
def login(payload: auth_service.LoginRequest, response: Response, db: DatabaseSession):
    user = db.query(auth_service.User).filter(auth_service.User.login == payload.login).first()
    if not user or not auth_service._verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    token, session = auth_service.create_session(db, user)
    _set_session_cookie(response, token)
    return {"user": user, "csrf_token": session.csrf_token}


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    session = request.state.auth_session
    db.delete(session)
    response.delete_cookie(auth_service.SESSION_COOKIE, path="/")


@auth_router.get("/me", response_model=auth_service.AuthResponse)
def get_profile(request: Request, user: auth_service.User = auth_service.CurrentUser):
    return {"user": user, "csrf_token": request.state.auth_session.csrf_token}


@auth_router.put("/me", response_model=auth_service.UserResponse)
def update_profile(payload: auth_service.ProfileUpdate, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    user.full_name = payload.full_name
    user.email = payload.email.strip() if payload.email else None
    db.flush()
    return user


unit_router = APIRouter(prefix="/units", tags=["Units"])


@unit_router.get("/", response_model=unit_service.UnitListResponse)
def get_units(
    db: DatabaseSession,
    user: auth_service.User = auth_service.CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_archived: bool = False,
    search: str | None = None,
):
    items, total = unit_service.get_units(db, skip, limit, include_archived, search)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@unit_router.post("/", response_model=unit_service.UnitResponse, status_code=status.HTTP_201_CREATED)
def create_unit(unit_data: unit_service.UnitCreate, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    try:
        return unit_service.create_unit(db, unit_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@unit_router.get("/{unit_id}", response_model=unit_service.UnitResponse)
def get_unit(unit_id: str, db: DatabaseSession, user: auth_service.User = auth_service.CurrentUser):
    unit = unit_service.get_unit(db, unit_id)
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Единица измерения не найдена")
    return unit


@unit_router.put("/{unit_id}", response_model=unit_service.UnitResponse)
def update_unit(unit_id: str, unit_data: unit_service.UnitUpdate, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    try:
        unit = unit_service.update_unit(db, unit_id, unit_data)
        if not unit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Единица измерения не найдена")
        return unit
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@unit_router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_unit(unit_id: str, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    try:
        unit = unit_service.archive_unit(db, unit_id)
        if not unit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Единица измерения не найдена")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@unit_router.delete("/{unit_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
def purge_unit(unit_id: str, db: DatabaseSession, user: auth_service.User = auth_service.AdminUser):
    try:
        if not unit_service.purge_archived_unit(db, unit_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Архивная единица измерения не найдена")
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


material_router = APIRouter(prefix="/materials", tags=["Materials"])


@material_router.get("/", response_model=material_service.MaterialListResponse)
def get_materials(
    db: DatabaseSession,
    user: auth_service.User = auth_service.CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_archived: bool = False,
    search: str | None = None,
):
    items, total = material_service.get_materials(db, skip, limit, include_archived, search)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@material_router.post("/", response_model=material_service.MaterialResponse, status_code=status.HTTP_201_CREATED)
def create_material(material_data: material_service.MaterialCreate, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    try:
        return material_service.create_material(db, material_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@material_router.get("/{material_id}", response_model=material_service.MaterialResponse)
def get_material(material_id: str, db: DatabaseSession, user: auth_service.User = auth_service.CurrentUser):
    material = material_service.get_material(db, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Материал не найден")
    return material


@material_router.put("/{material_id}", response_model=material_service.MaterialResponse)
def update_material(material_id: str, material_data: material_service.MaterialUpdate, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    try:
        material = material_service.update_material(db, material_id, material_data)
        if not material:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Материал не найден")
        return material
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@material_router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_material(material_id: str, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    material = material_service.archive_material(db, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Материал не найден")


@material_router.delete("/{material_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
def purge_material(material_id: str, db: DatabaseSession, user: auth_service.User = auth_service.AdminUser):
    if not material_service.purge_archived_material(db, material_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Архивный материал не найден")


supplier_router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@supplier_router.get("/", response_model=supplier_service.SupplierListResponse)
def get_suppliers(
    db: DatabaseSession,
    user: auth_service.User = auth_service.CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_archived: bool = False,
    search: str | None = None,
):
    items, total = supplier_service.get_suppliers(db, skip, limit, include_archived, search)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@supplier_router.post("/", response_model=supplier_service.SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(supplier_data: supplier_service.SupplierCreate, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    try:
        return supplier_service.create_supplier(db, supplier_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@supplier_router.get("/{supplier_id}", response_model=supplier_service.SupplierResponse)
def get_supplier(supplier_id: str, db: DatabaseSession, user: auth_service.User = auth_service.CurrentUser):
    supplier = supplier_service.get_supplier(db, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Поставщик не найден")
    return supplier


@supplier_router.put("/{supplier_id}", response_model=supplier_service.SupplierResponse)
def update_supplier(supplier_id: str, supplier_data: supplier_service.SupplierUpdate, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    try:
        supplier = supplier_service.update_supplier(db, supplier_id, supplier_data)
        if not supplier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Поставщик не найден")
        return supplier
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@supplier_router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_supplier(supplier_id: str, db: DatabaseSession, user: auth_service.User = auth_service.CsrfUser):
    supplier = supplier_service.archive_supplier(db, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Поставщик не найден")


@supplier_router.delete("/{supplier_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
def purge_supplier(supplier_id: str, db: DatabaseSession, user: auth_service.User = auth_service.AdminUser):
    if not supplier_service.purge_archived_supplier(db, supplier_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Архивный поставщик не найден")

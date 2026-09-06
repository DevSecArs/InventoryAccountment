from fastapi import APIRouter, HTTPException, Query, status
from app.postgresql import DatabaseSession
from app.entities import unit as unit_service
from app.entities import material as material_service
from app.entities import supplier as supplier_service


unit_router = APIRouter(prefix="/units", tags=["Units"])


@unit_router.get("/", response_model=dict)
def get_units(
    db: DatabaseSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_archived: bool = False,
    search: str | None = None,
):
    items, total = unit_service.get_units(db, skip, limit, include_archived, search)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@unit_router.post("/", response_model=unit_service.UnitResponse, status_code=status.HTTP_201_CREATED)
def create_unit(unit_data: unit_service.UnitCreate, db: DatabaseSession):
    try:
        return unit_service.create_unit(db, unit_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@unit_router.get("/{unit_id}", response_model=unit_service.UnitResponse)
def get_unit(unit_id: str, db: DatabaseSession):
    unit = unit_service.get_unit(db, unit_id)
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Единица измерения не найдена")
    return unit


@unit_router.put("/{unit_id}", response_model=unit_service.UnitResponse)
def update_unit(unit_id: str, unit_data: unit_service.UnitUpdate, db: DatabaseSession):
    try:
        unit = unit_service.update_unit(db, unit_id, unit_data)
        if not unit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Единица измерения не найдена")
        return unit
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@unit_router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_unit(unit_id: str, db: DatabaseSession):
    try:
        unit = unit_service.archive_unit(db, unit_id)
        if not unit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Единица измерения не найдена")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


material_router = APIRouter(prefix="/materials", tags=["Materials"])


@material_router.get("/", response_model=dict)
def get_materials(
    db: DatabaseSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_archived: bool = False,
    search: str | None = None,
):
    items, total = material_service.get_materials(db, skip, limit, include_archived, search)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@material_router.post("/", response_model=material_service.MaterialResponse, status_code=status.HTTP_201_CREATED)
def create_material(material_data: material_service.MaterialCreate, db: DatabaseSession):
    try:
        return material_service.create_material(db, material_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@material_router.get("/{material_id}", response_model=material_service.MaterialResponse)
def get_material(material_id: str, db: DatabaseSession):
    material = material_service.get_material(db, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Материал не найден")
    return material


@material_router.put("/{material_id}", response_model=material_service.MaterialResponse)
def update_material(material_id: str, material_data: material_service.MaterialUpdate, db: DatabaseSession):
    try:
        material = material_service.update_material(db, material_id, material_data)
        if not material:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Материал не найден")
        return material
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@material_router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_material(material_id: str, db: DatabaseSession):
    material = material_service.archive_material(db, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Материал не найден")


supplier_router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@supplier_router.get("/", response_model=dict)
def get_suppliers(
    db: DatabaseSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_archived: bool = False,
    search: str | None = None,
):
    items, total = supplier_service.get_suppliers(db, skip, limit, include_archived, search)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@supplier_router.post("/", response_model=supplier_service.SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(supplier_data: supplier_service.SupplierCreate, db: DatabaseSession):
    try:
        return supplier_service.create_supplier(db, supplier_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@supplier_router.get("/{supplier_id}", response_model=supplier_service.SupplierResponse)
def get_supplier(supplier_id: str, db: DatabaseSession):
    supplier = supplier_service.get_supplier(db, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Поставщик не найден")
    return supplier


@supplier_router.put("/{supplier_id}", response_model=supplier_service.SupplierResponse)
def update_supplier(supplier_id: str, supplier_data: supplier_service.SupplierUpdate, db: DatabaseSession):
    try:
        supplier = supplier_service.update_supplier(db, supplier_id, supplier_data)
        if not supplier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Поставщик не найден")
        return supplier
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@supplier_router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_supplier(supplier_id: str, db: DatabaseSession):
    supplier = supplier_service.archive_supplier(db, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Поставщик не найден")
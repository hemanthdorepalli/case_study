from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AdminUserOut, CameraCreate, CameraOut, StaffUserCreate, TenantCreate, TenantOut
from app.security import get_current_admin
from app.services import admin_service

# Every route in this router requires a platform admin.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])

T = TypeVar("T")


def _run(action: Callable[[], T]) -> T:
    try:
        return action()
    except admin_service.TenantNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found") from None
    except admin_service.AlreadyExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(db: Session = Depends(get_db)) -> list[TenantOut]:
    return admin_service.list_tenants(db)


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def create_tenant(body: TenantCreate, db: Session = Depends(get_db)) -> TenantOut:
    return _run(lambda: admin_service.create_tenant(db, body))


@router.get("/users", response_model=list[AdminUserOut])
def list_users(tenant_id: int | None = None, db: Session = Depends(get_db)) -> list[AdminUserOut]:
    return admin_service.list_users(db, tenant_id)


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def create_staff_user(body: StaffUserCreate, db: Session = Depends(get_db)) -> AdminUserOut:
    return _run(lambda: admin_service.create_staff_user(db, body))


@router.get("/cameras", response_model=list[CameraOut])
def list_cameras(tenant_id: int | None = None, db: Session = Depends(get_db)) -> list[CameraOut]:
    return admin_service.list_cameras(db, tenant_id)


@router.post("/cameras", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def create_camera(body: CameraCreate, db: Session = Depends(get_db)) -> CameraOut:
    return _run(lambda: admin_service.create_camera(db, body))

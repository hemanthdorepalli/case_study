"""Platform administration: tenants, staff users and cameras.

Only platform admins (who belong to no tenant) reach this module, so the target tenant
legitimately comes from the request body here - unlike the tenant-scoped case endpoints.
"""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import Camera, Tenant, User
from app.schemas import (
    AdminUserOut,
    CameraCreate,
    CameraOut,
    StaffUserCreate,
    TenantCreate,
    TenantOut,
)
from app.security import hash_password


class TenantNotFoundError(Exception):
    pass


class AlreadyExistsError(Exception):
    pass


def _commit_or_conflict(db: Session, message: str) -> None:
    # The unique constraints are the source of truth, so a concurrent duplicate also becomes a 409.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AlreadyExistsError(message) from None


def _require_tenant(db: Session, tenant_id: int) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise TenantNotFoundError(tenant_id)
    return tenant


# --- tenants ---

def list_tenants(db: Session) -> list[TenantOut]:
    user_count = select(func.count()).where(User.tenant_id == Tenant.id).scalar_subquery()
    camera_count = select(func.count()).where(Camera.tenant_id == Tenant.id).scalar_subquery()
    rows = db.execute(select(Tenant, user_count, camera_count).order_by(Tenant.name)).all()
    return [
        TenantOut(id=t.id, name=t.name, created_at=t.created_at, user_count=users, camera_count=cameras)
        for t, users, cameras in rows
    ]


def create_tenant(db: Session, body: TenantCreate) -> TenantOut:
    tenant = Tenant(name=body.name)
    db.add(tenant)
    _commit_or_conflict(db, f"Tenant '{body.name}' already exists")
    return TenantOut(id=tenant.id, name=tenant.name, created_at=tenant.created_at, user_count=0, camera_count=0)


# --- users ---

def _user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=user.tenant.name if user.tenant else None,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def list_users(db: Session, tenant_id: int | None = None) -> list[AdminUserOut]:
    # Staff only: platform admins aren't agency users, so they don't belong in this list.
    stmt = select(User).options(joinedload(User.tenant)).where(User.role == "staff").order_by(User.username)
    if tenant_id is not None:
        stmt = stmt.where(User.tenant_id == tenant_id)
    return [_user_out(user) for user in db.scalars(stmt)]


def create_staff_user(db: Session, body: StaffUserCreate) -> AdminUserOut:
    tenant = _require_tenant(db, body.tenant_id)
    # Admins create staff only; the DB CHECK also guarantees staff always belong to a tenant.
    user = User(
        tenant_id=tenant.id,
        username=body.username,
        password_hash=hash_password(body.password),
        role="staff",
    )
    db.add(user)
    _commit_or_conflict(db, f"Username '{body.username}' is already taken")
    db.refresh(user)
    return _user_out(user)


# --- cameras ---

def _camera_out(camera: Camera) -> CameraOut:
    return CameraOut(
        id=camera.id,
        tenant_id=camera.tenant_id,
        tenant_name=camera.tenant.name,
        label=camera.label,
        is_active=camera.is_active,
        created_at=camera.created_at,
    )


def list_cameras(db: Session, tenant_id: int | None = None) -> list[CameraOut]:
    stmt = select(Camera).options(joinedload(Camera.tenant)).order_by(Camera.id)
    if tenant_id is not None:
        stmt = stmt.where(Camera.tenant_id == tenant_id)
    return [_camera_out(camera) for camera in db.scalars(stmt)]


def create_camera(db: Session, body: CameraCreate) -> CameraOut:
    tenant = _require_tenant(db, body.tenant_id)
    camera = Camera(id=body.id, tenant_id=tenant.id, label=body.label)
    db.add(camera)
    _commit_or_conflict(db, f"Camera '{body.id}' already exists")
    db.refresh(camera)
    return _camera_out(camera)

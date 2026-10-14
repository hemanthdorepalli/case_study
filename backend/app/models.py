from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

CASE_STATUSES = ("pending_claim", "active", "closed")
OPEN_CASE_STATUSES = ("pending_claim", "active")
USER_ROLES = ("admin", "staff")


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'staff')", name="ck_users_role"),
        # Admins run the platform and belong to no tenant; staff always belong to exactly one.
        CheckConstraint(
            "(role = 'admin' AND tenant_id IS NULL) OR (role = 'staff' AND tenant_id IS NOT NULL)",
            name="ck_users_role_matches_tenant",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), server_default="staff")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant | None] = relationship()


class Camera(Base):
    __tablename__ = "cameras"

    # External id printed on the device (e.g. "cam_1001"); cameras send it in every scan.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True)
    label: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship()


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint("status IN ('pending_claim', 'active', 'closed')", name="ck_cases_status"),
        # A pending case belongs to nobody; once claimed it belongs to exactly one tenant.
        CheckConstraint(
            "(status = 'pending_claim' AND tenant_id IS NULL)"
            " OR (status <> 'pending_claim' AND tenant_id IS NOT NULL)",
            name="ck_cases_owner_matches_status",
        ),
        CheckConstraint("char_length(vin) = 17", name="ck_cases_vin_length"),
        # At most one open (pending or active) case per VIN across ALL tenants.
        Index(
            "uq_cases_open_vin",
            "vin",
            unique=True,
            postgresql_where=text("status IN ('pending_claim', 'active')"),
        ),
        Index("ix_cases_tenant_status", "tenant_id", "status"),
        Index("ix_cases_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vin: Mapped[str] = mapped_column(String(17))
    status: Mapped[str] = mapped_column(String(20))
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    origin_tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Scan(Base):
    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_scans_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_scans_longitude"),
        CheckConstraint("char_length(vin) = 17", name="ck_scans_vin_length"),
        Index("ix_scans_vin_scanned_at", "vin", "scanned_at"),
        Index("ix_scans_tenant_scanned_at", "tenant_id", "scanned_at"),
        Index("ix_scans_camera_id", "camera_id"),
        Index("ix_scans_matched_case_id", "matched_case_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Copied from the camera at ingest time so ownership never depends on client input.
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"))
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id", ondelete="RESTRICT"))
    plate: Mapped[str] = mapped_column(String(16))
    vin: Mapped[str] = mapped_column(String(17))
    latitude: Mapped[float] = mapped_column(Double)
    longitude: Mapped[float] = mapped_column(Double)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    image_url: Mapped[str | None] = mapped_column(String(2048))
    matched_case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

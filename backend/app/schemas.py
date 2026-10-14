"""Pydantic request/response models."""
import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
)

# ISO 3779: 17 characters, digits and capital letters except I, O and Q.
_VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def _check_vin(value: str) -> str:
    if not _VIN_RE.fullmatch(value):
        raise ValueError("VIN must be exactly 17 letters/digits and must not contain I, O or Q")
    return value


Vin = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True), AfterValidator(_check_vin)]
Plate = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=16)]


class CaseStatus(StrEnum):
    PENDING_CLAIM = "pending_claim"
    ACTIVE = "active"
    CLOSED = "closed"


class ScanFlow(StrEnum):
    EXISTING_CASE = "existing_case"
    ALREADY_OPEN_ELSEWHERE = "already_open_elsewhere"
    NEW_CASE_CREATED = "new_case_created"
    NOT_ELIGIBLE = "not_eligible"


# ---------- auth ----------

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    tenant_id: int | None  # None for platform admins
    tenant_name: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


# ---------- scans ----------

class ScanIn(BaseModel):
    # Unknown fields (including any "tenant_id") are ignored: the tenant always comes from the camera.
    camera_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    plate: Plate
    vin: Vin
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    scanned_at: AwareDatetime
    image_url: HttpUrl | None = Field(default=None, max_length=2048)


class ScanIngestResponse(BaseModel):
    scan_id: int
    tenant_id: int
    flow: ScanFlow
    case_id: int | None


class OwnTrailScan(BaseModel):
    source: Literal["own"] = "own"
    id: int
    camera_id: str
    plate: str
    vin: str
    latitude: float
    longitude: float
    scanned_at: datetime
    image_url: str | None


class NetworkTrailScan(BaseModel):
    """A sighting by another tenant's camera: location only, no camera/image/tenant identity."""

    source: Literal["network"] = "network"
    plate: str
    vin: str
    latitude: float
    longitude: float
    scanned_at: datetime


TrailScan = Annotated[OwnTrailScan | NetworkTrailScan, Field(discriminator="source")]


# ---------- cases ----------

class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vin: str
    status: CaseStatus
    created_at: datetime
    claimed_at: datetime | None
    closed_at: datetime | None
    assigned_user_id: int | None
    is_mine: bool
    scan_count: int


# ---------- admin ----------

def _check_bcrypt_length(value: str) -> str:
    # bcrypt only uses the first 72 bytes; reject longer passwords instead of silently truncating them.
    if len(value.encode()) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return value


Password = Annotated[str, StringConstraints(min_length=8), AfterValidator(_check_bcrypt_length)]


class TenantCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]


class TenantOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    user_count: int
    camera_count: int


class StaffUserCreate(BaseModel):
    username: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    ]
    password: Password
    tenant_id: int


class AdminUserOut(BaseModel):
    id: int
    username: str
    role: str
    tenant_id: int | None
    tenant_name: str | None
    is_active: bool
    created_at: datetime


class CameraCreate(BaseModel):
    id: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{1,64}$")]
    tenant_id: int
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CameraOut(BaseModel):
    id: str
    tenant_id: int
    tenant_name: str
    label: str
    is_active: bool
    created_at: datetime

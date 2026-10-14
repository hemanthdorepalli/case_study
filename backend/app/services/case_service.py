"""Case queries and commands. All tenant scoping for cases is defined in this module."""
from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import Case, Scan, User
from app.schemas import CaseOut, CaseStatus, NetworkTrailScan, OwnTrailScan


class CaseNotFoundError(Exception):
    pass


class CaseNotClaimableError(Exception):
    def __init__(self, status: str):
        super().__init__(status)
        self.status = status


# --- scoping rules (user.tenant_id always comes from the DB user, never from the request) ---

def _visible_to(user: User) -> ColumnElement[bool]:
    """The tenant's own cases (any status) plus every pending_claim case, which the whole network may see."""
    return or_(Case.tenant_id == user.tenant_id, Case.status == CaseStatus.PENDING_CLAIM)


def _owned_by(user: User) -> ColumnElement[bool]:
    return Case.tenant_id == user.tenant_id


def _get_case(db: Session, case_id: int, scope: ColumnElement[bool]) -> Case:
    # Out-of-scope and non-existent cases both raise NotFound, so other tenants' cases stay invisible.
    case = db.scalar(select(Case).where(Case.id == case_id, scope))
    if case is None:
        raise CaseNotFoundError(case_id)
    return case


# --- queries ---

def list_cases(db: Session, user: User, status: CaseStatus | None = None) -> list[CaseOut]:
    stmt = select(Case).where(_visible_to(user))
    if status is not None:
        stmt = stmt.where(Case.status == status)
    cases = db.scalars(stmt.order_by(Case.created_at.desc(), Case.id.desc())).all()
    return _to_case_out(db, user, cases)


def get_case(db: Session, user: User, case_id: int) -> CaseOut:
    return _to_case_out(db, user, [_get_case(db, case_id, _visible_to(user))])[0]


def get_trail(db: Session, user: User, case_id: int) -> list[OwnTrailScan | NetworkTrailScan]:
    # Only the owning tenant gets a trail; pending cases have none until claimed.
    case = _get_case(db, case_id, _owned_by(user))
    scans = db.scalars(
        select(Scan).where(Scan.vin == case.vin).order_by(Scan.scanned_at, Scan.id)
    ).all()
    return [_trail_entry(scan, user) for scan in scans]


# --- commands ---

def claim_case(db: Session, user: User, case_id: int) -> CaseOut:
    # One conditional UPDATE: Postgres locks the row, so among concurrent claims exactly one
    # still sees status='pending_claim' and wins; the rest update 0 rows. No read-then-write race.
    stmt = (
        update(Case)
        .where(Case.id == case_id, Case.status == CaseStatus.PENDING_CLAIM)
        .values(
            status=CaseStatus.ACTIVE,
            tenant_id=user.tenant_id,
            assigned_user_id=user.id,
            claimed_at=func.now(),
        )
        .returning(Case)
    )
    claimed = db.scalars(stmt).one_or_none()
    db.commit()
    if claimed is not None:
        return _to_case_out(db, user, [claimed])[0]

    existing = db.get(Case, case_id)
    # The owner and the originating tenant (whose camera opened it) already know the case exists,
    # so they get a 409 with its status. Anyone else gets 404 so we don't leak its existence.
    if existing is None or user.tenant_id not in (existing.tenant_id, existing.origin_tenant_id):
        raise CaseNotFoundError(case_id)
    raise CaseNotClaimableError(existing.status)


# --- mapping ---

def _to_case_out(db: Session, user: User, cases: Sequence[Case]) -> list[CaseOut]:
    counts = _scan_counts(db, user, {case.vin for case in cases})
    result = []
    for case in cases:
        is_mine = case.tenant_id == user.tenant_id
        total, own = counts.get(case.vin, (0, 0))
        result.append(
            CaseOut(
                id=case.id,
                vin=case.vin,
                status=case.status,
                created_at=case.created_at,
                claimed_at=case.claimed_at,
                closed_at=case.closed_at,
                assigned_user_id=case.assigned_user_id,
                is_mine=is_mine,
                # Mirrors trail visibility: own cases count every sighting (own + network);
                # for pending cases only our own scans count, since the network trail isn't visible yet.
                scan_count=total if is_mine else own,
            )
        )
    return result


def _scan_counts(db: Session, user: User, vins: set[str]) -> dict[str, tuple[int, int]]:
    """(total scans, scans by the user's tenant) per VIN, in one grouped query."""
    if not vins:
        return {}
    rows = db.execute(
        select(
            Scan.vin,
            func.count().label("total"),
            func.count().filter(Scan.tenant_id == user.tenant_id).label("own"),
        )
        .where(Scan.vin.in_(vins))
        .group_by(Scan.vin)
    ).all()
    return {row.vin: (row.total, row.own) for row in rows}


def _trail_entry(scan: Scan, user: User) -> OwnTrailScan | NetworkTrailScan:
    if scan.tenant_id == user.tenant_id:
        return OwnTrailScan(
            id=scan.id,
            camera_id=scan.camera_id,
            plate=scan.plate,
            vin=scan.vin,
            latitude=scan.latitude,
            longitude=scan.longitude,
            scanned_at=scan.scanned_at,
            image_url=scan.image_url,
        )
    # Another tenant's sighting: share where/when to help recover the vehicle,
    # but never the camera, image or tenant that produced it.
    return NetworkTrailScan(
        plate=scan.plate,
        vin=scan.vin,
        latitude=scan.latitude,
        longitude=scan.longitude,
        scanned_at=scan.scanned_at,
    )

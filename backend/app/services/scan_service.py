"""Scan ingest: store every valid scan, then route it into exactly one flow."""
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import OPEN_CASE_STATUSES, Camera, Case, Scan
from app.schemas import CaseStatus, ScanFlow, ScanIn, ScanIngestResponse
from app.services.eligibility import EligibilityClient

logger = logging.getLogger(__name__)

OPEN_VIN_INDEX = "uq_cases_open_vin"


class CameraNotFoundError(Exception):
    pass


class CameraInactiveError(Exception):
    pass


def ingest_scan(db: Session, payload: ScanIn, eligibility: EligibilityClient) -> ScanIngestResponse:
    camera = _get_active_camera(db, payload.camera_id)

    # The tenant comes from the registered camera, never from the payload.
    scan = Scan(
        tenant_id=camera.tenant_id,
        camera_id=camera.id,
        plate=payload.plate,
        vin=payload.vin,
        latitude=payload.latitude,
        longitude=payload.longitude,
        scanned_at=payload.scanned_at,
        image_url=str(payload.image_url) if payload.image_url else None,
    )
    db.add(scan)
    db.flush()  # the scan is kept whatever the case logic below decides

    flow, case_id = _match_open_case(db, scan)
    if flow is None:
        flow, case_id = _open_case_if_eligible(db, scan, eligibility)

    db.commit()
    logger.info("Scan %s from %s for VIN %s -> %s", scan.id, camera.id, scan.vin, flow)
    return ScanIngestResponse(scan_id=scan.id, tenant_id=scan.tenant_id, flow=flow, case_id=case_id)


def _get_active_camera(db: Session, camera_id: str) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise CameraNotFoundError(camera_id)
    if not camera.is_active:
        raise CameraInactiveError(camera_id)
    return camera


def _match_open_case(db: Session, scan: Scan) -> tuple[ScanFlow | None, int | None]:
    """Existing-case flow. uq_cases_open_vin guarantees at most one open case per VIN."""
    open_case = db.scalar(
        select(Case).where(Case.vin == scan.vin, Case.status.in_(OPEN_CASE_STATUSES))
    )
    if open_case is None:
        return None, None
    if open_case.status == CaseStatus.ACTIVE and open_case.tenant_id == scan.tenant_id:
        scan.matched_case_id = open_case.id
        return ScanFlow.EXISTING_CASE, open_case.id
    # Pending, or active for another tenant: don't open a duplicate and don't reveal its id or owner.
    return ScanFlow.ALREADY_OPEN_ELSEWHERE, None


def _open_case_if_eligible(
    db: Session, scan: Scan, eligibility: EligibilityClient
) -> tuple[ScanFlow, int | None]:
    """New-case flow: open a pending_claim case owned by nobody, if the partner says it's still eligible."""
    if not eligibility.is_eligible(scan.vin):
        return ScanFlow.NOT_ELIGIBLE, None

    case = Case(
        vin=scan.vin,
        status=CaseStatus.PENDING_CLAIM,
        tenant_id=None,
        origin_tenant_id=scan.tenant_id,
    )
    try:
        # SAVEPOINT: if a concurrent scan opened a case for this VIN after our check above,
        # uq_cases_open_vin rejects this insert and only the savepoint is rolled back - the scan survives.
        with db.begin_nested():
            db.add(case)
    except IntegrityError as exc:
        if getattr(exc.orig.diag, "constraint_name", None) != OPEN_VIN_INDEX:
            raise
        logger.info("Lost the race to open a case for VIN %s; using the existing case", scan.vin)
        flow, case_id = _match_open_case(db, scan)
        return flow or ScanFlow.ALREADY_OPEN_ELSEWHERE, case_id

    return ScanFlow.NEW_CASE_CREATED, case.id

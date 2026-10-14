from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import CaseOut, CaseStatus, TrailScan
from app.security import get_current_staff
from app.services import case_service

router = APIRouter(prefix="/cases", tags=["cases"])

CaseId = Annotated[int, Path(ge=1, le=2_147_483_647)]


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")


@router.get("", response_model=list[CaseOut])
def list_cases(
    status_filter: Annotated[CaseStatus | None, Query(alias="status")] = None,
    user: User = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> list[CaseOut]:
    return case_service.list_cases(db, user, status_filter)


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: CaseId, user: User = Depends(get_current_staff), db: Session = Depends(get_db)) -> CaseOut:
    try:
        return case_service.get_case(db, user, case_id)
    except case_service.CaseNotFoundError:
        raise _not_found() from None


@router.post("/{case_id}/claim", response_model=CaseOut)
def claim_case(case_id: CaseId, user: User = Depends(get_current_staff), db: Session = Depends(get_db)) -> CaseOut:
    try:
        return case_service.claim_case(db, user, case_id)
    except case_service.CaseNotFoundError:
        raise _not_found() from None
    except case_service.CaseNotClaimableError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Case is not claimable (current status: {exc.status})"
        ) from None


@router.get("/{case_id}/scans", response_model=list[TrailScan])
def case_trail(
    case_id: CaseId, user: User = Depends(get_current_staff), db: Session = Depends(get_db)
) -> list[TrailScan]:
    try:
        return case_service.get_trail(db, user, case_id)
    except case_service.CaseNotFoundError:
        raise _not_found() from None

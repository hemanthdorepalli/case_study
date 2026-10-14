from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ScanIn, ScanIngestResponse
from app.services import scan_service
from app.services.eligibility import EligibilityClient, get_eligibility_client

router = APIRouter(tags=["scans"])


@router.post("/scans", status_code=status.HTTP_201_CREATED, response_model=ScanIngestResponse)
def create_scan(
    payload: ScanIn,
    db: Session = Depends(get_db),
    eligibility: EligibilityClient = Depends(get_eligibility_client),
) -> ScanIngestResponse:
    """Camera webhook (unauthenticated in this case study).

    Deliberately a sync `def`: FastAPI runs it in a worker thread, so the blocking eligibility
    HTTP call (which in dev targets this same process) can't stall the event loop.
    """
    try:
        return scan_service.ingest_scan(db, payload, eligibility)
    except scan_service.CameraNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found") from None
    except scan_service.CameraInactiveError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Camera is inactive") from None

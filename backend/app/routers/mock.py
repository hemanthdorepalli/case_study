"""Stand-in for the external partner network (Appendix A). No auth, by design."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas import Vin

router = APIRouter(prefix="/mock/partner-network", tags=["mock"])


class EligibilityRequest(BaseModel):
    vin: Vin


class EligibilityResponse(BaseModel):
    vin: str
    still_eligible_for_repo: bool


@router.post("/eligibility", response_model=EligibilityResponse)
def eligibility(body: EligibilityRequest) -> EligibilityResponse:
    return EligibilityResponse(vin=body.vin, still_eligible_for_repo=not body.vin.endswith("0"))

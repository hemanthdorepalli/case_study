"""Client for the partner network's "still eligible for repo?" check."""
import logging
from typing import Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EligibilityClient(Protocol):
    def is_eligible(self, vin: str) -> bool: ...


class HttpEligibilityClient:
    def __init__(self, url: str, timeout_seconds: float, transport: httpx.BaseTransport | None = None):
        self._url = url
        self._timeout = timeout_seconds
        self._transport = transport  # injectable so tests can simulate failures without a network

    def is_eligible(self, vin: str) -> bool:
        """Return the partner's answer, or False if the partner can't be reached.

        Failing closed means an outage never creates cases we can't verify; the scan
        itself is still stored, so nothing is lost.
        """
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.post(self._url, json={"vin": vin})
                response.raise_for_status()
                return response.json()["still_eligible_for_repo"] is True
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Eligibility check failed for VIN %s; treating as not eligible: %r", vin, exc)
            return False


def get_eligibility_client() -> EligibilityClient:
    """FastAPI dependency; tests replace it via app.dependency_overrides."""
    return HttpEligibilityClient(settings.mock_eligibility_url, settings.eligibility_timeout_seconds)

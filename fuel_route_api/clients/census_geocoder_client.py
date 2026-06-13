from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

from core.exceptions import GeocodeNotFoundError, UpstreamUnavailableError

logger = logging.getLogger(__name__)


class CensusGeocoderClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = base_url or settings.CENSUS_GEOCODER_URL
        self.timeout_seconds = timeout_seconds or settings.CENSUS_GEOCODER_TIMEOUT_SECONDS

    def geocode(self, address: str) -> dict[str, Any]:
        params = {"address": address, "benchmark": "Public_AR_Current", "format": "json"}
        logger.info("census.request", extra={"address": address})

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(self.base_url, params=params)
        except httpx.RequestError as exc:
            logger.exception("census.request_failed")
            raise UpstreamUnavailableError("Census geocoder request failed.") from exc

        if response.status_code >= 500:
            raise UpstreamUnavailableError("Census geocoder is unavailable.")
        if response.status_code >= 300:
            raise GeocodeNotFoundError(f"Unable to geocode address: {address}")

        payload = response.json()
        matches = payload.get("result", {}).get("addressMatches", [])
        if not matches:
            raise GeocodeNotFoundError(f"Unable to geocode address: {address}")

        match = matches[0]
        coordinates = match["coordinates"]
        return {
            "latitude": float(coordinates["y"]),
            "longitude": float(coordinates["x"]),
            "formatted_address": match.get("matchedAddress", address),
            "confidence": 1.0,
            "source": "census",
        }

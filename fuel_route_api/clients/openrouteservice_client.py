from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

from core.exceptions import GeocodeNotFoundError, RouteNotFoundError, UpstreamUnavailableError

logger = logging.getLogger(__name__)


class OpenRouteServiceClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        profile: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.ORS_API_KEY
        self.base_url = (base_url or settings.ORS_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.ORS_TIMEOUT_SECONDS
        self.profile = profile or settings.ORS_PROFILE

    def get_route(
        self,
        start_lon: float,
        start_lat: float,
        end_lon: float,
        end_lat: float,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise UpstreamUnavailableError(
                "OpenRouteService API key is not configured. Set ORS_API_KEY in your environment."
            )

        url = f"{self.base_url}/v2/directions/{self.profile}/geojson"
        payload = {
            "coordinates": [[start_lon, start_lat], [end_lon, end_lat]],
            "instructions": False,
            "geometry_simplify": True,
        }
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        logger.info(
            "ors.request",
            extra={
                "start": [start_lon, start_lat],
                "end": [end_lon, end_lat],
                "profile": self.profile,
            },
        )

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            logger.exception("ors.request_failed")
            raise UpstreamUnavailableError("OpenRouteService request failed.") from exc

        if response.status_code >= 500:
            raise UpstreamUnavailableError("OpenRouteService is unavailable.")
        if response.status_code == 404 or response.status_code == 400:
            raise RouteNotFoundError("No driving route found between the provided locations.")
        if response.status_code >= 300:
            raise UpstreamUnavailableError(
                f"OpenRouteService returned unexpected status {response.status_code}."
            )

        data = response.json()
        if not data.get("features"):
            raise RouteNotFoundError("No driving route found between the provided locations.")
        return data

    def geocode(self, address: str) -> dict[str, Any]:
        if not self.api_key:
            raise UpstreamUnavailableError(
                "OpenRouteService API key is not configured. Set ORS_API_KEY in your environment."
            )

        url = f"{self.base_url}/geocode/search"
        headers = {"Authorization": self.api_key}
        params = {"text": address, "size": 1, "boundary.country": "US"}

        logger.info("ors.geocode.request", extra={"address": address})

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, params=params, headers=headers)
        except httpx.RequestError as exc:
            logger.exception("ors.geocode_failed")
            raise UpstreamUnavailableError("OpenRouteService geocoding failed.") from exc

        if response.status_code >= 500:
            raise UpstreamUnavailableError("OpenRouteService is unavailable.")
        if response.status_code >= 300:
            raise GeocodeNotFoundError(f"Unable to geocode address: {address}")

        features = response.json().get("features", [])
        if not features:
            raise GeocodeNotFoundError(f"Unable to geocode address: {address}")

        feature = features[0]
        lon, lat = feature["geometry"]["coordinates"]
        return {
            "latitude": float(lat),
            "longitude": float(lon),
            "formatted_address": feature["properties"].get("label", address),
            "confidence": float(feature["properties"].get("confidence", 1.0) or 1.0),
            "source": "openrouteservice",
        }

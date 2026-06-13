from __future__ import annotations

import logging

from django.core.cache import cache

from clients.census_geocoder_client import CensusGeocoderClient
from clients.openrouteservice_client import OpenRouteServiceClient
from core.cache_keys import geocode_cache_key
from core.exceptions import GeocodeNotFoundError, ValidationError
from core.normalization import normalize_address
from services.types import Coordinates, GeocodeResult

logger = logging.getLogger(__name__)


class GeocodingService:
    def __init__(
        self,
        census_client: CensusGeocoderClient | None = None,
        ors_client: OpenRouteServiceClient | None = None,
    ) -> None:
        self.census_client = census_client or CensusGeocoderClient()
        self.ors_client = ors_client or OpenRouteServiceClient()

    def geocode(self, address: str) -> GeocodeResult:
        try:
            normalized = normalize_address(address)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        cache_key = f"geocode:{geocode_cache_key(normalized)}"
        cached = cache.get(cache_key)
        if cached:
            logger.info("geocode.cache_hit", extra={"address": normalized})
            return self._result_from_cache(address, cached)

        from apps.fuel.models import GeocodeCache

        address_hash = geocode_cache_key(normalized)
        db_cached = GeocodeCache.objects.filter(address_hash=address_hash).first()
        if db_cached:
            payload = {
                "normalized_address": normalized,
                "latitude": db_cached.latitude,
                "longitude": db_cached.longitude,
                "formatted_address": db_cached.formatted_address,
                "confidence": 1.0,
                "source": db_cached.source,
            }
            cache.set(cache_key, payload, 86400)
            return self._result_from_cache(address, payload)

        payload = self._lookup_address(normalized)
        cache_payload = {
            "normalized_address": normalized,
            "latitude": payload["latitude"],
            "longitude": payload["longitude"],
            "formatted_address": payload["formatted_address"],
            "confidence": payload["confidence"],
            "source": payload["source"],
        }
        GeocodeCache.objects.update_or_create(
            address_hash=address_hash,
            defaults={
                "address_normalized": normalized,
                "latitude": payload["latitude"],
                "longitude": payload["longitude"],
                "formatted_address": payload["formatted_address"],
                "source": payload["source"],
            },
        )
        cache.set(cache_key, cache_payload, 86400)
        logger.info("geocode.success", extra={"address": normalized, "source": payload["source"]})
        return self._result_from_cache(address, cache_payload)

    def _lookup_address(self, normalized: str) -> dict:
        census_query = normalized if normalized.upper().endswith("USA") else f"{normalized}, USA"
        try:
            return self.census_client.geocode(census_query)
        except GeocodeNotFoundError:
            logger.info("geocode.census_miss", extra={"address": census_query})
            return self.ors_client.geocode(census_query)

    def _result_from_cache(self, address: str, payload: dict) -> GeocodeResult:
        return GeocodeResult(
            input_address=address,
            normalized_address=payload["normalized_address"],
            coordinates=Coordinates(payload["latitude"], payload["longitude"]),
            formatted_address=payload["formatted_address"],
            confidence=float(payload["confidence"]),
            source=payload["source"],
        )

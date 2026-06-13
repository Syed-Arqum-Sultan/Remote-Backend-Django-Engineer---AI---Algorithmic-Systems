from __future__ import annotations

import logging
import time
from typing import Any

from clients.census_geocoder_client import CensusGeocoderClient
from clients.openrouteservice_client import OpenRouteServiceClient
from core.exceptions import GeocodeNotFoundError, UpstreamUnavailableError
from core.normalization import build_station_geocode_queries, normalize_city, normalize_state

logger = logging.getLogger(__name__)


def geocode_station_address(
    *,
    address: str,
    city: str,
    state: str,
    ors_client: OpenRouteServiceClient | None = None,
    census_client: CensusGeocoderClient | None = None,
) -> dict[str, Any] | None:
    """Geocode a fuel station using ORS first, then Census, with query fallbacks."""
    ors = ors_client or OpenRouteServiceClient()
    census = census_client or CensusGeocoderClient()
    normalize_city(city)
    normalize_state(state)
    queries = build_station_geocode_queries(address, city, state)

    for query in queries:
        try:
            result = ors.geocode(query)
            result["source"] = "openrouteservice"
            time.sleep(0.12)
            return result
        except GeocodeNotFoundError:
            logger.debug("ors.geocode_miss", extra={"query": query})
        except UpstreamUnavailableError:
            logger.warning("ors.geocode_unavailable", extra={"query": query})
            break

    for query in queries:
        try:
            result = census.geocode(query)
            time.sleep(0.12)
            return result
        except (GeocodeNotFoundError, UpstreamUnavailableError):
            logger.debug("census.geocode_miss", extra={"query": query})

    return None

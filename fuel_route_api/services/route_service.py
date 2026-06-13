from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache

from clients.openrouteservice_client import OpenRouteServiceClient
from core.cache_keys import route_cache_key
from core.constants import METERS_PER_MILE
from core.geo import build_cumulative_distances
from services.types import RouteResult

logger = logging.getLogger(__name__)


class RouteService:
    def __init__(self, ors_client: OpenRouteServiceClient | None = None) -> None:
        self.ors_client = ors_client or OpenRouteServiceClient()

    def get_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
    ) -> RouteResult:
        cache_key = route_cache_key(
            start_lat,
            start_lon,
            end_lat,
            end_lon,
            settings.ORS_PROFILE,
            settings.DATASET_VERSION,
            settings.ALGO_VERSION,
        )
        cached = cache.get(cache_key)
        if cached:
            logger.info("route.cache_hit", extra={"cache_key": cache_key[:12]})
            return RouteResult(**cached, cache_hit=True)

        payload = self.ors_client.get_route(start_lon, start_lat, end_lon, end_lat)
        result = self._parse_route(payload)
        cache.set(
            cache_key,
            {
                "distance_miles": result.distance_miles,
                "duration_seconds": result.duration_seconds,
                "geometry_geojson": result.geometry_geojson,
                "coordinates": result.coordinates,
                "cumdist_meters": result.cumdist_meters,
            },
            604800,
        )
        logger.info(
            "route.success",
            extra={"distance_miles": result.distance_miles, "cache_key": cache_key[:12]},
        )
        return RouteResult(
            distance_miles=result.distance_miles,
            duration_seconds=result.duration_seconds,
            geometry_geojson=result.geometry_geojson,
            coordinates=result.coordinates,
            cumdist_meters=result.cumdist_meters,
            cache_hit=False,
        )

    def _parse_route(self, payload: dict[str, Any]) -> RouteResult:
        feature = payload["features"][0]
        geometry = feature["geometry"]
        coordinates = [(lat, lon) for lon, lat in geometry["coordinates"]]
        properties = feature["properties"]
        summary = properties.get("summary", {})
        distance_meters = float(summary.get("distance", 0.0))
        duration_seconds = int(summary.get("duration", 0))

        segments = properties.get("segments", [])
        if segments and "distance" in segments[0]:
            distance_meters = float(segments[0]["distance"])

        cumdist_meters = build_cumulative_distances(coordinates)
        if cumdist_meters and distance_meters > cumdist_meters[-1]:
            scale = distance_meters / cumdist_meters[-1]
            cumdist_meters = [value * scale for value in cumdist_meters]

        return RouteResult(
            distance_miles=distance_meters / METERS_PER_MILE,
            duration_seconds=duration_seconds,
            geometry_geojson=geometry,
            coordinates=coordinates,
            cumdist_meters=cumdist_meters,
            cache_hit=False,
        )

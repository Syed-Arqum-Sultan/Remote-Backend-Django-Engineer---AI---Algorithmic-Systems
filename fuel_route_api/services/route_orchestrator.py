from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings

from apps.fuel.models import FuelStation, GeocodeStatus
from core.geo import decimate_route_for_projection, project_point_to_route, route_corridor_bounds
from services.fuel_optimizer import FuelOptimizer
from services.geocoding_service import GeocodingService
from services.route_service import RouteService
from services.types import RouteOptimizeResult, StationCandidate

logger = logging.getLogger(__name__)


class RouteOrchestrator:
    def __init__(
        self,
        geocoding_service: GeocodingService | None = None,
        route_service: RouteService | None = None,
        fuel_optimizer: FuelOptimizer | None = None,
    ) -> None:
        self.geocoding_service = geocoding_service or GeocodingService()
        self.route_service = route_service or RouteService()
        self.fuel_optimizer = fuel_optimizer or FuelOptimizer()

    def optimize_route(
        self,
        start_address: str,
        destination_address: str,
        *,
        include_geometry: bool = True,
    ) -> RouteOptimizeResult:
        logger.info(
            "route.optimize.start",
            extra={"start": start_address, "destination": destination_address},
        )
        start = self.geocoding_service.geocode(start_address)
        destination = self.geocoding_service.geocode(destination_address)
        route = self.route_service.get_route(
            start.coordinates.latitude,
            start.coordinates.longitude,
            destination.coordinates.latitude,
            destination.coordinates.longitude,
        )
        candidates = self._find_station_candidates(route)
        fuel_plan = self.fuel_optimizer.optimize(candidates, route.distance_miles)

        warnings: list[str] = []
        if not candidates:
            warnings.append("No fuel stations were found within the route corridor.")

        result = RouteOptimizeResult(
            start=start,
            destination=destination,
            route=route,
            fuel_plan=fuel_plan,
            warnings=warnings,
            cached=route.cache_hit,
        )
        if not include_geometry:
            result.route.geometry_geojson = {}
        logger.info(
            "route.optimize.complete",
            extra={
                "distance_miles": route.distance_miles,
                "stop_count": fuel_plan.stop_count,
                "cached": route.cache_hit,
            },
        )
        return result

    def _find_station_candidates(self, route) -> list[StationCandidate]:
        corridor_miles = settings.CORRIDOR_MILES
        min_lat, max_lat, min_lon, max_lon = route_corridor_bounds(
            route.coordinates,
            corridor_miles,
        )

        queryset = FuelStation.objects.filter(
            geocode_status=GeocodeStatus.OK,
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__gte=min_lat,
            latitude__lte=max_lat,
            longitude__gte=min_lon,
            longitude__lte=max_lon,
        )

        projection_coordinates, projection_cumdist = decimate_route_for_projection(
            route.coordinates,
            route.cumdist_meters,
            max_points=settings.PROJECTION_MAX_POINTS,
        )

        candidates: list[StationCandidate] = []
        for station in queryset.iterator():
            projection = project_point_to_route(
                station.latitude,
                station.longitude,
                projection_coordinates,
                projection_cumdist,
            )
            if projection is None:
                continue
            if projection.cross_track_miles > corridor_miles:
                continue
            if projection.mile_marker < 0.01:
                continue
            if projection.mile_marker > route.distance_miles - 0.01:
                continue
            candidates.append(
                StationCandidate(
                    opis_id=station.opis_id,
                    name=station.name,
                    address=station.address,
                    city=station.city,
                    state=station.state,
                    retail_price=Decimal(str(station.retail_price)),
                    latitude=station.latitude,
                    longitude=station.longitude,
                    mile_marker=projection.mile_marker,
                    cross_track_miles=projection.cross_track_miles,
                )
            )
        return candidates

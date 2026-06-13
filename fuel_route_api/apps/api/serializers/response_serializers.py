from __future__ import annotations

from django.conf import settings

from core.constants import TANK_GALLONS, VEHICLE_MPG, VEHICLE_RANGE_MILES
from services.types import RouteOptimizeResult


def serialize_optimize_result(
    result: RouteOptimizeResult,
    *,
    include_geometry: bool = True,
) -> dict:
    geometry = result.route.geometry_geojson if include_geometry else None
    return {
        "start": {
            "input": result.start.input_address,
            "coordinates": [
                result.start.coordinates.longitude,
                result.start.coordinates.latitude,
            ],
            "formatted_address": result.start.formatted_address,
            "confidence": result.start.confidence,
        },
        "destination": {
            "input": result.destination.input_address,
            "coordinates": [
                result.destination.coordinates.longitude,
                result.destination.coordinates.latitude,
            ],
            "formatted_address": result.destination.formatted_address,
            "confidence": result.destination.confidence,
        },
        "route": {
            "distance_miles": round(result.route.distance_miles, 2),
            "duration_seconds": result.route.duration_seconds,
            "geometry": geometry,
        },
        "fuel_plan": {
            "vehicle": {
                "range_miles": VEHICLE_RANGE_MILES,
                "mpg": VEHICLE_MPG,
                "tank_gallons": TANK_GALLONS,
            },
            "stops": [
                {
                    "opis_id": stop.opis_id,
                    "name": stop.name,
                    "address": stop.address,
                    "city": stop.city,
                    "state": stop.state,
                    "mile_marker": stop.mile_marker,
                    "retail_price": stop.retail_price,
                    "gallons_purchased": stop.gallons_purchased,
                    "segment_cost": stop.segment_cost,
                }
                for stop in result.fuel_plan.stops
            ],
            "total_fuel_cost": float(result.fuel_plan.total_fuel_cost),
            "total_gallons_purchased": float(result.fuel_plan.total_gallons_purchased),
            "stop_count": result.fuel_plan.stop_count,
        },
        "warnings": result.warnings,
        "meta": {
            "cached": result.cached,
            "algorithm_version": settings.ALGO_VERSION,
            "dataset_version": settings.DATASET_VERSION,
        },
    }

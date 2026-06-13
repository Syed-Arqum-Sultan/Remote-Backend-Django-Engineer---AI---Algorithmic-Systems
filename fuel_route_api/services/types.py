from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class GeocodeResult:
    input_address: str
    normalized_address: str
    coordinates: Coordinates
    formatted_address: str
    confidence: float
    source: str


@dataclass(frozen=True)
class RouteResult:
    distance_miles: float
    duration_seconds: int
    geometry_geojson: dict[str, Any]
    coordinates: list[tuple[float, float]]
    cumdist_meters: list[float]
    cache_hit: bool


@dataclass(frozen=True)
class StationCandidate:
    opis_id: int
    name: str
    address: str
    city: str
    state: str
    retail_price: Decimal
    latitude: float
    longitude: float
    mile_marker: float
    cross_track_miles: float


@dataclass(frozen=True)
class FuelStopPlan:
    opis_id: int
    name: str
    address: str
    city: str
    state: str
    mile_marker: float
    retail_price: float
    gallons_purchased: float
    segment_cost: float


@dataclass(frozen=True)
class FuelPlanResult:
    stops: list[FuelStopPlan]
    total_fuel_cost: Decimal
    total_gallons_purchased: Decimal
    stop_count: int


@dataclass(frozen=True)
class RouteOptimizeResult:
    start: GeocodeResult
    destination: GeocodeResult
    route: RouteResult
    fuel_plan: FuelPlanResult
    warnings: list[str]
    cached: bool

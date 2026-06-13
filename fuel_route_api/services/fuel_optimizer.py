from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from core.constants import TANK_GALLONS, VEHICLE_MPG, VEHICLE_RANGE_MILES
from core.exceptions import NoFeasibleFuelPlanError
from services.types import FuelPlanResult, FuelStopPlan, StationCandidate

logger = logging.getLogger(__name__)


class FuelOptimizer:
    def __init__(
        self,
        *,
        range_miles: float | None = None,
        mpg: float | None = None,
    ) -> None:
        self.range_miles = range_miles or settings.VEHICLE_RANGE_MILES
        self.mpg = mpg or settings.VEHICLE_MPG
        self.tank_gallons = self.range_miles / self.mpg

    def optimize(
        self,
        candidates: list[StationCandidate],
        total_distance_miles: float,
    ) -> FuelPlanResult:
        if total_distance_miles <= self.range_miles:
            return FuelPlanResult(
                stops=[],
                total_fuel_cost=Decimal("0.00"),
                total_gallons_purchased=Decimal("0.00"),
                stop_count=0,
            )

        stations = sorted(candidates, key=lambda item: (item.mile_marker, item.opis_id))
        if not stations:
            raise NoFeasibleFuelPlanError(
                "No fuel stations found within the route corridor.",
            )

        reachable = [station for station in stations if station.mile_marker <= self.range_miles]
        if not reachable and total_distance_miles > self.range_miles:
            raise NoFeasibleFuelPlanError(
                "No fuel stations within the first 500 miles of the route.",
            )

        best_cost = Decimal("Infinity")
        best_last_index: int | None = None
        dp: list[Decimal] = [Decimal("Infinity")] * len(stations)
        parent: list[int | None] = [None] * len(stations)

        for index, station in enumerate(stations):
            if station.mile_marker <= self.range_miles:
                dp[index] = self._segment_cost(station.mile_marker, station.retail_price)
                parent[index] = -1

            for prev_index, previous in enumerate(stations[:index]):
                delta = station.mile_marker - previous.mile_marker
                if delta > self.range_miles:
                    continue
                candidate_cost = dp[prev_index] + self._segment_cost(delta, station.retail_price)
                if candidate_cost < dp[index]:
                    dp[index] = candidate_cost
                    parent[index] = prev_index

        for index, station in enumerate(stations):
            remaining = total_distance_miles - station.mile_marker
            if remaining <= self.range_miles and dp[index] < best_cost:
                best_cost = dp[index]
                best_last_index = index

        if best_last_index is None or best_cost == Decimal("Infinity"):
            raise NoFeasibleFuelPlanError(
                "Unable to reach the destination with the available fuel stations.",
            )

        stop_indices: list[int] = []
        cursor: int | None = best_last_index
        while cursor is not None and cursor >= 0:
            stop_indices.append(cursor)
            cursor = parent[cursor]
        stop_indices.reverse()

        stops: list[FuelStopPlan] = []
        total_gallons = Decimal("0.00")
        previous_marker = 0.0
        for index in stop_indices:
            station = stations[index]
            delta = station.mile_marker - previous_marker
            gallons = Decimal(str(delta / self.mpg)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            segment_cost = (gallons * station.retail_price).quantize(Decimal("0.01"), ROUND_HALF_UP)
            stops.append(
                FuelStopPlan(
                    opis_id=station.opis_id,
                    name=station.name,
                    address=station.address,
                    city=station.city,
                    state=station.state,
                    mile_marker=round(station.mile_marker, 2),
                    retail_price=float(station.retail_price),
                    gallons_purchased=float(gallons),
                    segment_cost=float(segment_cost),
                )
            )
            total_gallons += gallons
            previous_marker = station.mile_marker

        logger.info(
            "fuel_optimizer.success",
            extra={"stop_count": len(stops), "total_cost": str(best_cost)},
        )
        return FuelPlanResult(
            stops=stops,
            total_fuel_cost=best_cost.quantize(Decimal("0.01"), ROUND_HALF_UP),
            total_gallons_purchased=total_gallons.quantize(Decimal("0.01"), ROUND_HALF_UP),
            stop_count=len(stops),
        )

    def _segment_cost(self, miles: float, price: Decimal) -> Decimal:
        gallons = Decimal(str(miles / self.mpg))
        return gallons * price

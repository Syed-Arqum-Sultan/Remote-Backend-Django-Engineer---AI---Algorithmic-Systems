import pytest
from decimal import Decimal

from services.fuel_optimizer import FuelOptimizer
from services.types import StationCandidate


@pytest.mark.django_db
def test_optimizer_no_stops_for_short_route():
    optimizer = FuelOptimizer()
    result = optimizer.optimize([], total_distance_miles=250)
    assert result.stop_count == 0
    assert result.total_fuel_cost == Decimal("0.00")


def test_optimizer_picks_cheaper_station():
    optimizer = FuelOptimizer(range_miles=500, mpg=10)
    candidates = [
        StationCandidate(
            opis_id=1,
            name="Expensive",
            address="A",
            city="X",
            state="TX",
            retail_price=Decimal("4.00"),
            latitude=30.0,
            longitude=-95.0,
            mile_marker=400.0,
            cross_track_miles=1.0,
        ),
        StationCandidate(
            opis_id=2,
            name="Cheap",
            address="B",
            city="Y",
            state="TX",
            retail_price=Decimal("3.00"),
            latitude=30.1,
            longitude=-96.0,
            mile_marker=450.0,
            cross_track_miles=1.0,
        ),
    ]
    result = optimizer.optimize(candidates, total_distance_miles=700)
    assert result.stop_count >= 1
    assert result.total_fuel_cost > Decimal("0.00")

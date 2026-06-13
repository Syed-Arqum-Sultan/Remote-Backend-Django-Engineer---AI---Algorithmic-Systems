import pytest
from unittest.mock import patch

from rest_framework.test import APIClient

from decimal import Decimal

from services.types import (
    Coordinates,
    FuelPlanResult,
    FuelStopPlan,
    GeocodeResult,
    RouteOptimizeResult,
    RouteResult,
)


@pytest.mark.django_db
@patch("apps.api.views.route_optimize_view.get_route_orchestrator")
def test_route_optimize_endpoint(mock_factory):
    mock_orchestrator = mock_factory.return_value
    mock_orchestrator.optimize_route.return_value = RouteOptimizeResult(
        start=GeocodeResult(
            input_address="New York, NY",
            normalized_address="New York, NY",
            coordinates=Coordinates(40.7128, -74.0060),
            formatted_address="New York, NY",
            confidence=1.0,
            source="census",
        ),
        destination=GeocodeResult(
            input_address="Chicago, IL",
            normalized_address="Chicago, IL",
            coordinates=Coordinates(41.8781, -87.6298),
            formatted_address="Chicago, IL",
            confidence=1.0,
            source="census",
        ),
        route=RouteResult(
            distance_miles=790.0,
            duration_seconds=50000,
            geometry_geojson={"type": "LineString", "coordinates": [[-74.0, 40.7], [-87.6, 41.8]]},
            coordinates=[(40.7, -74.0), (41.8, -87.6)],
            cumdist_meters=[0.0, 100000.0],
            cache_hit=False,
        ),
        fuel_plan=FuelPlanResult(
            stops=[
                FuelStopPlan(
                    opis_id=123,
                    name="Test Stop",
                    address="I-80",
                    city="Cleveland",
                    state="OH",
                    mile_marker=400.0,
                    retail_price=3.25,
                    gallons_purchased=40.0,
                    segment_cost=130.0,
                )
            ],
            total_fuel_cost=Decimal("130.00"),
            total_gallons_purchased=Decimal("40.00"),
            stop_count=1,
        ),
        warnings=[],
        cached=False,
    )

    client = APIClient()
    response = client.post(
        "/api/v1/routes/optimize/",
        {"start": "New York, NY", "destination": "Chicago, IL"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["fuel_plan"]["stop_count"] == 1
    assert response.data["route"]["distance_miles"] == 790.0

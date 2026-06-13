from core.constants import METERS_PER_MILE
import pytest
from core.geo import (
    build_cumulative_distances,
    decimate_route_for_projection,
    project_point_to_route,
    route_corridor_bounds,
)


def test_route_corridor_bounds_is_tighter_than_one_degree_padding():
    coordinates = [(32.75, -97.33), (36.16, -86.78)]
    min_lat, max_lat, min_lon, max_lon = route_corridor_bounds(coordinates, corridor_miles=5.0)

    old_min_lat = min(lat for lat, _ in coordinates) - 1.0
    old_max_lat = max(lat for lat, _ in coordinates) + 1.0
    old_min_lon = min(lon for _, lon in coordinates) - 1.0
    old_max_lon = max(lon for _, lon in coordinates) + 1.0

    assert min_lat > old_min_lat
    assert max_lat < old_max_lat
    assert min_lon > old_min_lon
    assert max_lon < old_max_lon


def test_project_point_uses_scaled_route_distance():
    coordinates = [(40.0, -88.0), (41.0, -87.0)]
    haversine_cumdist = build_cumulative_distances(coordinates)
    ors_distance_meters = haversine_cumdist[-1] * 1.15
    scale = ors_distance_meters / haversine_cumdist[-1]
    cumdist_meters = [value * scale for value in haversine_cumdist]
    route_distance_miles = ors_distance_meters / METERS_PER_MILE

    midpoint_lat = 40.5
    midpoint_lon = -87.5
    projection = project_point_to_route(
        midpoint_lat,
        midpoint_lon,
        coordinates,
        cumdist_meters,
    )

    assert projection is not None
    assert projection.cross_track_miles < 1.0
    assert abs(projection.mile_marker - (route_distance_miles / 2)) < 5.0


def test_decimate_route_for_projection_reduces_points_preserving_distance():
    coordinates = [(40.0 + index * 0.01, -88.0 + index * 0.01) for index in range(5000)]
    cumdist_meters = build_cumulative_distances(coordinates)
    scale = 1_000_000 / cumdist_meters[-1]
    cumdist_meters = [value * scale for value in cumdist_meters]

    decimated_coordinates, decimated_cumdist = decimate_route_for_projection(
        coordinates,
        cumdist_meters,
        max_points=400,
    )

    assert len(decimated_coordinates) <= 400
    assert decimated_cumdist[-1] == pytest.approx(cumdist_meters[-1])
    assert decimated_coordinates[0] == coordinates[0]
    assert decimated_coordinates[-1] == coordinates[-1]


def test_project_point_rejects_far_off_route_station():
    coordinates = [(40.0, -88.0), (41.0, -87.0)]
    cumdist_meters = build_cumulative_distances(coordinates)

    projection = project_point_to_route(
        45.0,
        -100.0,
        coordinates,
        cumdist_meters,
    )

    assert projection is not None
    assert projection.cross_track_miles > 100.0

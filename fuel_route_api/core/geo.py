from __future__ import annotations

import math
from dataclasses import dataclass

from core.constants import METERS_PER_MILE


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_miles * math.asin(math.sqrt(a))


def cross_track_miles(
    point_lat: float,
    point_lon: float,
    seg_start: tuple[float, float],
    seg_end: tuple[float, float],
) -> float:
    lat1, lon1 = seg_start
    lat2, lon2 = seg_end
    distance_start_to_point = haversine_miles(lat1, lon1, point_lat, point_lon)
    if haversine_miles(lat1, lon1, lat2, lon2) < 1e-6:
        return distance_start_to_point

    bearing12 = _bearing(lat1, lon1, lat2, lon2)
    bearing1p = _bearing(lat1, lon1, point_lat, point_lon)
    angular_distance = distance_start_to_point / 3958.8
    return abs(
        math.asin(
            math.sin(angular_distance)
            * math.sin(math.radians(bearing1p - bearing12))
        )
        * 3958.8
    )


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return math.degrees(math.atan2(y, x))


@dataclass(frozen=True)
class MileMarkerResult:
    mile_marker: float
    cross_track_miles: float
    segment_index: int


def decimate_route_for_projection(
    coordinates: list[tuple[float, float]],
    cumdist_meters: list[float],
    *,
    max_points: int = 400,
) -> tuple[list[tuple[float, float]], list[float]]:
    """Reduce polyline density for station projection while preserving total distance."""
    if len(coordinates) <= max_points or len(cumdist_meters) != len(coordinates):
        return coordinates, cumdist_meters

    total_meters = cumdist_meters[-1]
    step = (len(coordinates) - 1) / (max_points - 1)
    indices: list[int] = []
    seen: set[int] = set()
    for step_index in range(max_points):
        index = min(len(coordinates) - 1, int(round(step_index * step)))
        if index not in seen:
            seen.add(index)
            indices.append(index)
    if indices[-1] != len(coordinates) - 1:
        indices.append(len(coordinates) - 1)

    decimated_coordinates = [coordinates[index] for index in indices]
    decimated_cumdist = build_cumulative_distances(decimated_coordinates)
    if decimated_cumdist and decimated_cumdist[-1] > 0:
        scale = total_meters / decimated_cumdist[-1]
        decimated_cumdist = [value * scale for value in decimated_cumdist]
    return decimated_coordinates, decimated_cumdist


def route_corridor_bounds(
    coordinates: list[tuple[float, float]],
    corridor_miles: float,
) -> tuple[float, float, float, float]:
    """Return min/max lat/lon for a route polyline buffered by corridor width."""
    if not coordinates:
        return (-90.0, 90.0, -180.0, 180.0)

    min_lat = max_lat = coordinates[0][0]
    min_lon = max_lon = coordinates[0][1]
    for lat, lon in coordinates:
        lat_buffer = corridor_miles / 69.0
        lon_buffer = corridor_miles / max(69.0 * math.cos(math.radians(lat)), 1.0)
        min_lat = min(min_lat, lat - lat_buffer)
        max_lat = max(max_lat, lat + lat_buffer)
        min_lon = min(min_lon, lon - lon_buffer)
        max_lon = max(max_lon, lon + lon_buffer)
    return min_lat, max_lat, min_lon, max_lon


def project_point_to_route(
    point_lat: float,
    point_lon: float,
    coordinates: list[tuple[float, float]],
    cumdist_meters: list[float],
) -> MileMarkerResult | None:
    if len(coordinates) < 2 or len(cumdist_meters) != len(coordinates):
        return None

    best_marker = 0.0
    best_cross_track = float("inf")
    best_index = 0

    for index in range(len(coordinates) - 1):
        start = coordinates[index]
        end = coordinates[index + 1]
        fraction, cross_track = _fraction_along_segment_min_cross_track(
            start,
            end,
            point_lat,
            point_lon,
        )
        segment_length = max(cumdist_meters[index + 1] - cumdist_meters[index], 0.0)
        distance_along = cumdist_meters[index] + fraction * segment_length
        if cross_track < best_cross_track:
            best_cross_track = cross_track
            best_marker = distance_along / METERS_PER_MILE
            best_index = index

    return MileMarkerResult(
        mile_marker=best_marker,
        cross_track_miles=best_cross_track,
        segment_index=best_index,
    )


def _fraction_along_segment_min_cross_track(
    start: tuple[float, float],
    end: tuple[float, float],
    point_lat: float,
    point_lon: float,
    *,
    samples: int = 21,
) -> tuple[float, float]:
    best_fraction = 0.0
    best_cross_track = float("inf")

    for step in range(samples):
        fraction = step / (samples - 1) if samples > 1 else 0.0
        candidate_lat = start[0] + fraction * (end[0] - start[0])
        candidate_lon = start[1] + fraction * (end[1] - start[1])
        cross_track = haversine_miles(point_lat, point_lon, candidate_lat, candidate_lon)
        if cross_track < best_cross_track:
            best_cross_track = cross_track
            best_fraction = fraction

    refined_fraction = best_fraction
    refined_cross_track = best_cross_track
    step_size = 1.0 / (samples - 1) if samples > 1 else 1.0
    for _ in range(8):
        step_size *= 0.5
        for delta in (-step_size, step_size):
            candidate_fraction = max(0.0, min(1.0, refined_fraction + delta))
            candidate_lat = start[0] + candidate_fraction * (end[0] - start[0])
            candidate_lon = start[1] + candidate_fraction * (end[1] - start[1])
            candidate_cross_track = haversine_miles(
                point_lat,
                point_lon,
                candidate_lat,
                candidate_lon,
            )
            if candidate_cross_track < refined_cross_track:
                refined_cross_track = candidate_cross_track
                refined_fraction = candidate_fraction

    return refined_fraction, refined_cross_track


def build_cumulative_distances(coordinates: list[tuple[float, float]]) -> list[float]:
    if not coordinates:
        return []
    cumulative = [0.0]
    for index in range(1, len(coordinates)):
        lat1, lon1 = coordinates[index - 1]
        lat2, lon2 = coordinates[index]
        segment_meters = haversine_miles(lat1, lon1, lat2, lon2) * METERS_PER_MILE
        cumulative.append(cumulative[-1] + segment_meters)
    return cumulative

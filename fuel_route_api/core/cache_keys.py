import hashlib
import json

from core.normalization import round_coords


def geocode_cache_key(normalized_address: str) -> str:
    return hashlib.sha256(normalized_address.lower().encode("utf-8")).hexdigest()


def route_cache_key(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    profile: str,
    dataset_version: str,
    algo_version: str,
) -> str:
    start = round_coords(start_lat, start_lon)
    end = round_coords(end_lat, end_lon)
    payload = {
        "start": start,
        "end": end,
        "profile": profile,
        "dataset_version": dataset_version,
        "algo_version": algo_version,
    }
    encoded = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

import re


def normalize_address(address: str) -> str:
    cleaned = " ".join(address.strip().split())
    if not cleaned:
        raise ValueError("Address must not be empty")
    return cleaned


def normalize_city(city: str) -> str:
    return " ".join(city.strip().split())


def normalize_state(state: str) -> str:
    return state.strip().upper()[:2]


def build_station_query(address: str, city: str, state: str) -> str:
    return f"{address}, {normalize_city(city)}, {normalize_state(state)}, USA"


def round_coords(latitude: float, longitude: float, precision: int = 3) -> tuple[float, float]:
    return round(latitude, precision), round(longitude, precision)


def normalize_station_address(address: str) -> str:
    cleaned = " ".join(address.strip().split())
    cleaned = cleaned.replace(" ,", ",").replace(",,", ",")
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"\bI-8I\b", "I-81", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bST 22\b", "SR-22", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(I|US|SR)-\s+(\d+)\b", r"\1-\2", cleaned, flags=re.IGNORECASE)
    return cleaned


def parse_highway_ref(address: str) -> str | None:
    normalized = normalize_station_address(address).upper()
    match = re.search(r"\b(I-\d+|US-\d+|US \d+|SR-\d+)\b", normalized)
    if not match:
        return None
    return match.group(1).replace(" ", "-")


def build_station_geocode_queries(address: str, city: str, state: str) -> list[str]:
    normalized_address = normalize_station_address(address)
    normalized_city = normalize_city(city)
    normalized_state = normalize_state(state)
    queries = [
        build_station_query(normalized_address, normalized_city, normalized_state),
    ]

    primary_part = normalized_address.split("&")[0].strip().rstrip(",")
    if primary_part and primary_part != normalized_address:
        queries.append(
            build_station_query(primary_part, normalized_city, normalized_state)
        )

    highway = parse_highway_ref(normalized_address)
    if highway:
        queries.append(f"{highway}, {normalized_city}, {normalized_state}, USA")

    exit_match = re.search(
        r"EXIT\s+([A-Z0-9-]+)",
        normalized_address,
        flags=re.IGNORECASE,
    )
    if highway and exit_match:
        queries.append(
            f"{highway}, EXIT {exit_match.group(1)}, {normalized_city}, "
            f"{normalized_state}, USA"
        )

    queries.append(f"{normalized_city}, {normalized_state}, USA")
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        if query not in seen:
            seen.add(query)
            deduped.append(query)
    return deduped

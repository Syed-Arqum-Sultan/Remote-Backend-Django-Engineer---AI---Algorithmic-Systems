from core.normalization import build_station_geocode_queries, normalize_station_address, parse_highway_ref


def test_normalize_station_address_fixes_known_typos():
    assert normalize_station_address("I-8I, EXIT 77") == "I-81, EXIT 77"
    assert normalize_station_address("I-35,  EXIT 271") == "I-35, EXIT 271"


def test_parse_highway_ref():
    assert parse_highway_ref("I-44, EXIT 283 & US-69") == "I-44"
    assert parse_highway_ref("US-46") == "US-46"


def test_build_station_geocode_queries_deduplicates():
    queries = build_station_geocode_queries(
        "I-75, EXIT 224",
        "Ellenton",
        "FL",
    )
    assert queries[0].endswith("Ellenton, FL, USA")
    assert "I-75, Ellenton, FL, USA" in queries
    assert "I-75, EXIT 224, Ellenton, FL, USA" in queries
    assert len(queries) == len(set(queries))

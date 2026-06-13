# Fuel Route Optimizer API

Django REST API that returns a driving route and cost-optimized fuel stops for US trips using the assessment fuel price dataset.

## Stack

- Django 5.2 + Django REST Framework
- SQLite
- OpenRouteService (routing/map geometry)
- US Census Geocoder (address geocoding)
- Min-cost dynamic programming fuel optimizer (500 mile range, 10 MPG)

## Quick start

```bash
cd fuel_route_api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set `ORS_API_KEY` in `.env` (free key from https://openrouteservice.org/dev/#/signup).

```bash
python manage.py migrate
python manage.py import_fuel_stations --file ../fuel-Prices/fuel-prices-for-be-assessment.csv
python manage.py generate_station_fixture --file ../fuel-Prices/fuel-prices-for-be-assessment.csv --workers 5
python manage.py import_fuel_stations --file ../fuel-Prices/fuel-prices-for-be-assessment.csv
python manage.py runserver
```

The `generate_station_fixture` step geocodes ~6,738 stations via the free Census API and takes roughly **30-45 minutes**. It writes progress to `fixtures/station_coords.json` every 100 stations, so you can re-run import while it is still running.

For a quicker demo while the full fixture builds:

```bash
python manage.py generate_station_fixture --limit 1500 --workers 5
python manage.py import_fuel_stations --file ../fuel-Prices/fuel-prices-for-be-assessment.csv
```

## API

### Health

`GET /api/v1/health/`

### Optimize route

`POST /api/v1/routes/optimize/`

```json
{
  "start": "New York, NY",
  "destination": "Chicago, IL",
  "include_geometry": true
}
```

Example response fields:

- `route.geometry` GeoJSON LineString for map display
- `fuel_plan.stops` ordered optimal fuel stops
- `fuel_plan.total_fuel_cost` total purchase cost in USD
- `meta.cached` whether the route came from cache (no new ORS call)

## External API usage

| Call | When | Count |
|---|---|---|
| OpenRouteService directions | New start/end pair | 1 |
| Census geocoder | New address text | 0-2, then cached |

Repeat requests for the same route should hit the in-memory cache and make **zero** routing API calls.

## Tests

```bash
pytest
```

## Postman

Import [`postman_collection.json`](postman_collection.json) and set `base_url` to `http://127.0.0.1:8000`.

## Loom demo checklist (5 min)

1. Show `.env` has `ORS_API_KEY` and mention fuel CSV import.
2. Postman `POST /api/v1/routes/optimize/` with New York, NY -> Chicago, IL.
3. Highlight route geometry, fuel stops, and `total_fuel_cost`.
4. Repeat the same request and show `meta.cached = true`.
5. Open `services/route_orchestrator.py` and `services/fuel_optimizer.py`.

## Architecture

- `apps/api/` HTTP layer only
- `services/` business logic
- `clients/` OpenRouteService and Census HTTP clients
- `apps/fuel/` models and import commands

## Notes

- Fuel stations are geocoded once at import time from the CSV addresses.
- The optimizer assumes a full tank at start and refill-to-full at each stop.
- Corridor matching uses a configurable mile buffer (`CORRIDOR_MILES`, default 5).

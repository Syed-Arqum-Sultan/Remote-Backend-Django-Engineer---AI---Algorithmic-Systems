"""Find multi-stop routes using only geocode-cached cities."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from apps.fuel.models import GeocodeCache  # noqa: E402
from core.exceptions import DomainError  # noqa: E402
from services.route_orchestrator import RouteOrchestrator  # noqa: E402

MIN_STOPS = int(sys.argv[1]) if len(sys.argv) > 1 else 4

cities = sorted(GeocodeCache.objects.values_list("address_normalized", flat=True))
orch = RouteOrchestrator()
results: list[dict] = []

for index, start in enumerate(cities):
    for dest in cities[index + 1 :]:
        try:
            result = orch.optimize_route(start, dest)
        except DomainError as exc:
            print(f"FAIL {start} -> {dest}: {exc.message}")
            continue
        if result.route.distance_miles <= 500:
            continue
        row = {
            "start": start,
            "destination": dest,
            "distance": round(result.route.distance_miles, 1),
            "stops": result.fuel_plan.stop_count,
            "cost": float(result.fuel_plan.total_fuel_cost),
        }
        results.append(row)
        print(f"{row['stops']} stops | {row['distance']}mi | {start} -> {dest}")

results.sort(key=lambda row: (-row["stops"], -row["distance"]))
multi = [row for row in results if row["stops"] >= MIN_STOPS]

print(f"\nRoutes with >={MIN_STOPS} stops: {len(multi)}\n")
for row in multi:
    print(json.dumps({"start": row["start"], "destination": row["destination"], "include_geometry": True}, indent=2))
    print(f"  -> {row['stops']} stops | {row['distance']} mi | ${row['cost']:.2f}\n")

if not multi:
    print("None found. Top 10 by stops:")
    for row in results[:10]:
        print(row)

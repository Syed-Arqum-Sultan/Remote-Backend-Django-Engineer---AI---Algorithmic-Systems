from __future__ import annotations

import csv
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.fuel.models import FuelStation, GeocodeStatus
from core.normalization import normalize_city, normalize_state
from core.station_geocoding import geocode_station_address

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import fuel stations from the assessment CSV."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--file",
            type=str,
            default="../fuel-Prices/fuel-prices-for-be-assessment.csv",
            help="Path to fuel prices CSV.",
        )
        parser.add_argument(
            "--fixture",
            type=str,
            default=str(settings.BASE_DIR / "fixtures" / "station_coords.json"),
            help="Optional JSON fixture with opis_id -> {latitude, longitude}.",
        )
        parser.add_argument(
            "--live-geocode",
            action="store_true",
            help="Geocode missing stations via Census API.",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=3,
            help="Concurrent geocoding workers when --live-geocode is enabled.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit number of stations to geocode (0 = all missing).",
        )

    def handle(self, *args, **options) -> None:
        csv_path = Path(options["file"]).resolve()
        fixture_path = Path(options["fixture"]).resolve()
        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
            return

        deduped = self._load_csv(csv_path)
        self.stdout.write(f"Loaded {len(deduped)} unique OPIS stations from CSV.")

        fixture_coords = self._load_fixture(fixture_path)
        created_count = self._upsert_stations(deduped, fixture_coords)
        self.stdout.write(self.style.SUCCESS(f"Upserted {created_count} stations."))

        if options["live_geocode"]:
            self._geocode_missing(limit=options["limit"], workers=options["workers"])
        else:
            missing = FuelStation.objects.filter(geocode_status=GeocodeStatus.PENDING).count()
            if missing:
                self.stdout.write(
                    self.style.WARNING(
                        f"{missing} stations still need coordinates. "
                        "Re-run with --live-geocode or provide fixtures/station_coords.json."
                    )
                )

    def _load_csv(self, csv_path: Path) -> dict[int, dict]:
        deduped: dict[int, dict] = {}
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                opis_id = int(row["OPIS Truckstop ID"])
                price = Decimal(row["Retail Price"])
                current = deduped.get(opis_id)
                if current is None or price < current["retail_price"]:
                    deduped[opis_id] = {
                        "opis_id": opis_id,
                        "name": row["Truckstop Name"].strip(),
                        "address": row["Address"].strip(),
                        "city": normalize_city(row["City"]),
                        "state": normalize_state(row["State"]),
                        "rack_id": int(row["Rack ID"]) if row["Rack ID"] else None,
                        "retail_price": price,
                    }
        return deduped

    def _load_fixture(self, fixture_path: Path) -> dict[int, dict]:
        if not fixture_path.exists():
            return {}
        with fixture_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return {int(key): value for key, value in payload.items()}

    def _upsert_stations(
        self,
        deduped: dict[int, dict],
        fixture_coords: dict[int, dict],
    ) -> int:
        count = 0
        with transaction.atomic():
            for station_data in deduped.values():
                coords = fixture_coords.get(station_data["opis_id"])
                defaults = {
                    "name": station_data["name"],
                    "address": station_data["address"],
                    "city": station_data["city"],
                    "state": station_data["state"],
                    "rack_id": station_data["rack_id"],
                    "retail_price": station_data["retail_price"],
                }
                if coords:
                    defaults.update(
                        {
                            "latitude": float(coords["latitude"]),
                            "longitude": float(coords["longitude"]),
                            "geocode_status": GeocodeStatus.OK,
                            "geocode_source": "fixture",
                        }
                    )
                else:
                    defaults.update(
                        {
                            "latitude": None,
                            "longitude": None,
                            "geocode_status": GeocodeStatus.PENDING,
                            "geocode_source": None,
                        }
                    )
                FuelStation.objects.update_or_create(
                    opis_id=station_data["opis_id"],
                    defaults=defaults,
                )
                count += 1
        return count

    def _geocode_missing(self, *, limit: int, workers: int) -> None:
        queryset = FuelStation.objects.filter(geocode_status=GeocodeStatus.PENDING)
        if limit:
            station_ids = list(queryset.values_list("opis_id", flat=True)[:limit])
            stations = list(FuelStation.objects.filter(opis_id__in=station_ids))
        else:
            stations = list(queryset)

        if not stations:
            self.stdout.write("No pending stations to geocode.")
            return

        success = 0
        failed = 0

        def geocode_station(station: FuelStation) -> tuple[FuelStation, bool]:
            result = geocode_station_address(
                address=station.address,
                city=station.city,
                state=station.state,
            )
            if result is None:
                station.geocode_status = GeocodeStatus.FAILED
                station.save(update_fields=["geocode_status"])
                return station, False
            station.latitude = result["latitude"]
            station.longitude = result["longitude"]
            station.geocode_status = GeocodeStatus.OK
            station.geocode_source = result.get("source", "unknown")
            station.save(
                update_fields=[
                    "latitude",
                    "longitude",
                    "geocode_status",
                    "geocode_source",
                ]
            )
            return station, True

        self.stdout.write(f"Geocoding {len(stations)} stations with {workers} workers...")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(geocode_station, station) for station in stations]
            for index, future in enumerate(as_completed(futures), start=1):
                _, ok = future.result()
                if ok:
                    success += 1
                else:
                    failed += 1
                if index % 100 == 0:
                    self.stdout.write(f"Processed {index}/{len(stations)} stations...")

        self.stdout.write(
            self.style.SUCCESS(
                f"Geocoding complete. success={success}, failed={failed}"
            )
        )

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from core.station_geocoding import geocode_station_address
from core.normalization import normalize_city, normalize_state


class Command(BaseCommand):
    help = "Generate station_coords.json fixture from the assessment CSV (ORS + Census)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--file",
            type=str,
            default="../fuel-Prices/fuel-prices-for-be-assessment.csv",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=str(settings.BASE_DIR / "fixtures" / "station_coords.json"),
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=2,
            help="Concurrent workers (keep low to respect ORS rate limits).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit stations for quick fixture generation.",
        )
        parser.add_argument(
            "--import-after",
            action="store_true",
            help="Run import_fuel_stations when geocoding completes.",
        )

    def handle(self, *args, **options) -> None:
        import csv

        csv_path = Path(options["file"]).resolve()
        output_path = Path(options["output"]).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        deduped: dict[int, dict] = {}
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                opis_id = int(row["OPIS Truckstop ID"])
                if opis_id not in deduped:
                    deduped[opis_id] = {
                        "address": row["Address"].strip(),
                        "city": normalize_city(row["City"]),
                        "state": normalize_state(row["State"]),
                    }

        stations = list(deduped.items())
        if options["limit"]:
            stations = stations[: options["limit"]]

        fixture: dict[str, dict[str, float]] = {}
        if output_path.exists():
            with output_path.open(encoding="utf-8") as handle:
                fixture = json.load(handle)
            self.stdout.write(f"Resuming with {len(fixture)} existing geocoded stations.")

        pending = [(opis_id, data) for opis_id, data in stations if str(opis_id) not in fixture]

        def geocode_item(item: tuple[int, dict]) -> tuple[int, dict[str, float] | None]:
            opis_id, station = item
            result = geocode_station_address(
                address=station["address"],
                city=station["city"],
                state=station["state"],
            )
            if result is None:
                return opis_id, None
            return opis_id, {
                "latitude": result["latitude"],
                "longitude": result["longitude"],
                "source": result.get("source", "unknown"),
            }

        self.stdout.write(
            f"Geocoding {len(pending)} stations via ORS (Census fallback), "
            f"{options['workers']} workers..."
        )
        success = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=options["workers"]) as executor:
            futures = [executor.submit(geocode_item, item) for item in pending]
            for index, future in enumerate(as_completed(futures), start=1):
                opis_id, coords = future.result()
                if coords:
                    fixture[str(opis_id)] = coords
                    success += 1
                else:
                    failed += 1
                if index % 100 == 0:
                    self.stdout.write(
                        f"Processed {index}/{len(pending)} "
                        f"(total geocoded: {len(fixture)}, new: {success}, failed: {failed})"
                    )
                    with output_path.open("w", encoding="utf-8") as handle:
                        json.dump(fixture, handle)

        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(fixture, handle)

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(fixture)} geocoded stations to {output_path} "
                f"({failed} failures this run)"
            )
        )

        if options["import_after"]:
            self.stdout.write("Running import_fuel_stations...")
            subprocess.run(
                [
                    sys.executable,
                    "manage.py",
                    "import_fuel_stations",
                    "--file",
                    str(csv_path),
                    "--fixture",
                    str(output_path),
                ],
                check=True,
            )
            self.stdout.write(self.style.SUCCESS("Import complete."))

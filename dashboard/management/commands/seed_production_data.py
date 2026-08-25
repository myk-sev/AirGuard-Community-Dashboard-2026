import math
import random
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import Forecast, Reading, Sensor


class Command(BaseCommand):
    help = "Initialize the production manifest and add non-destructive example data"

    def add_arguments(self, parser):
        parser.add_argument("--days-back", type=int, default=30)
        parser.add_argument("--days-forward", type=int, default=30)

    def handle(self, *args, **options):
        days_back = max(1, options["days_back"])
        days_forward = max(1, options["days_forward"])
        call_command("seed_db", verbosity=0)
        now = timezone.now().replace(second=0, microsecond=0)
        rng = random.Random(20260825)
        readings_created = forecasts_created = 0

        for sensor_index, sensor in enumerate(Sensor.objects.filter(enabled=True)):
            has_recent_import = sensor.readings.filter(
                observed_at__gte=now - timedelta(days=7), ingest_batch__isnull=False
            ).exists()
            preserve_imported_vmos = sensor.external_id.startswith("BGC-B") and sensor.readings.filter(ingest_batch__isnull=False).exists()
            if not has_recent_import and not preserve_imported_vmos:
                rows = []
                for hour in range(days_back * 24, -1, -1):
                    observed_at = now - timedelta(hours=hour)
                    daily = math.sin((observed_at.hour - 7) / 24 * math.tau) * 2.5
                    peak = 18 if 14 <= observed_at.hour <= 17 else 0
                    pm25 = max(1, 6 + sensor_index * 0.7 + daily + peak + rng.uniform(-1, 1))
                    rows.append(Reading(sensor=sensor, observed_at=observed_at, pm25=round(pm25, 2)))
                before = Reading.objects.filter(sensor=sensor).count()
                Reading.objects.bulk_create(rows, ignore_conflicts=True, batch_size=1000)
                readings_created += Reading.objects.filter(sensor=sensor).count() - before

            forecasts = []
            for hour in range(1, days_forward * 24 + 1):
                forecast_at = now + timedelta(hours=hour)
                peak = 24 * math.exp(-((hour % 24 - 16) ** 2) / 22)
                forecasts.append(Forecast(
                    sensor=sensor,
                    forecast_at=forecast_at,
                    pm25=round(max(1, 7 + sensor_index * 0.7 + peak + rng.uniform(-1, 1)), 2),
                    temperature=round(68 + 8 * math.sin((forecast_at.hour - 8) / 24 * math.tau), 1),
                    relative_humidity=round(58 - 12 * math.sin((forecast_at.hour - 8) / 24 * math.tau), 1),
                    wind_speed=round(5 + rng.uniform(0, 5), 1),
                    wind_direction=("N", "NE", "E", "SE", "S", "SW", "W", "NW")[hour % 8],
                    generated_at=now,
                    source="example",
                    run_id="production-example",
                ))
            before = Forecast.objects.filter(sensor=sensor).count()
            Forecast.objects.bulk_create(forecasts, ignore_conflicts=True, batch_size=1000)
            forecasts_created += Forecast.objects.filter(sensor=sensor).count() - before

        self.stdout.write(self.style.SUCCESS(
            f"Initialized {Sensor.objects.filter(enabled=True).count()} sensors; "
            f"created {readings_created} example readings and {forecasts_created} forecasts."
        ))

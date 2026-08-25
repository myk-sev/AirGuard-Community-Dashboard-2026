from datetime import UTC

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dashboard.models import Forecast
from dashboard.weather import fetch_weather


class Command(BaseCommand):
    help = "Update future forecast rows with Open-Meteo outdoor weather"

    def add_arguments(self, parser):
        parser.add_argument("--ignore-errors", action="store_true")

    def handle(self, *args, **options):
        try:
            if not settings.AIRGUARD_WEATHER_LATITUDE or not settings.AIRGUARD_WEATHER_LONGITUDE:
                raise ValueError("AIRGUARD_WEATHER_LATITUDE and AIRGUARD_WEATHER_LONGITUDE are required")
            hourly = fetch_weather(
                settings.AIRGUARD_WEATHER_URL,
                settings.AIRGUARD_WEATHER_LATITUDE,
                settings.AIRGUARD_WEATHER_LONGITUDE,
                settings.AIRGUARD_WEATHER_TIMEOUT_SECONDS,
            )
            retrieved_at = timezone.now()
            forecasts = []
            for forecast in Forecast.objects.filter(forecast_at__gte=retrieved_at):
                hour = forecast.forecast_at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
                if weather := hourly.get(hour):
                    for field, value in weather.items():
                        setattr(forecast, field, value)
                    forecast.weather_source = "open-meteo"
                    forecast.weather_generated_at = retrieved_at
                    forecasts.append(forecast)
            Forecast.objects.bulk_update(forecasts, (
                "temperature", "relative_humidity", "wind_speed", "wind_direction",
                "weather_source", "weather_generated_at",
            ))
            self.stdout.write(self.style.SUCCESS(f"Updated weather on {len(forecasts)} forecast rows."))
        except Exception as exc:
            if options["ignore_errors"]:
                self.stderr.write(self.style.WARNING(f"Weather update skipped: {exc}"))
                return
            raise CommandError(f"Weather update failed: {exc}") from exc

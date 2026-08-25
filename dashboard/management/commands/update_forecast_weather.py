from django.core.management.base import BaseCommand, CommandError
from dashboard.weather import update_forecast_weather


class Command(BaseCommand):
    help = "Update future forecast rows with Open-Meteo outdoor weather"

    def add_arguments(self, parser):
        parser.add_argument("--ignore-errors", action="store_true")

    def handle(self, *args, **options):
        try:
            updated = update_forecast_weather()
            self.stdout.write(self.style.SUCCESS(f"Updated weather on {updated} forecast rows."))
        except Exception as exc:
            if options["ignore_errors"]:
                self.stderr.write(self.style.WARNING(f"Weather update skipped: {exc}"))
                return
            raise CommandError(f"Weather update failed: {exc}") from exc

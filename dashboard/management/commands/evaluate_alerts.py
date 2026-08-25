from django.core.management.base import BaseCommand

from dashboard.alerts import evaluate_alerts


class Command(BaseCommand):
    help = "Evaluate active subscriptions against available forecasts"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Queued {evaluate_alerts()} alert emails"))

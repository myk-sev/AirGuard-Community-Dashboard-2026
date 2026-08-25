from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone

from dashboard.models import OutboundEmail, Suppression


class Command(BaseCommand):
    help = "Send pending AirGuard email from the database outbox"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        sent = 0
        now = timezone.now()
        OutboundEmail.objects.filter(status="sending", next_attempt_at__lt=now - timedelta(minutes=15)).update(status="failed")
        pending = OutboundEmail.objects.filter(
            status__in=("pending", "failed"),
            attempts__lt=settings.AIRGUARD_EMAIL_MAX_ATTEMPTS,
            next_attempt_at__lte=now,
        ).order_by("created_at")[:options["limit"]]
        for item in pending:
            claimed = OutboundEmail.objects.filter(
                pk=item.pk,
                status__in=("pending", "failed"),
                attempts__lt=settings.AIRGUARD_EMAIL_MAX_ATTEMPTS,
                next_attempt_at__lte=timezone.now(),
            ).update(status="sending", attempts=F("attempts") + 1)
            if not claimed:
                continue
            item.refresh_from_db(fields=("attempts",))
            if Suppression.objects.filter(email__iexact=item.to_email).exists():
                item.status = "suppressed"
                item.save(update_fields=("status",))
                continue
            try:
                message = EmailMultiAlternatives(item.subject, item.text_body, settings.DEFAULT_FROM_EMAIL, [item.to_email])
                if item.html_body:
                    message.attach_alternative(item.html_body, "text/html")
                message.send(fail_silently=False)
                item.status, item.sent_at, item.last_error = "sent", timezone.now(), ""
                sent += 1
            except Exception as error:
                item.status = "failed"
                item.last_error = str(error)[:2000]
                item.next_attempt_at = timezone.now() + timedelta(minutes=min(60, 2 ** item.attempts))
            item.save(update_fields=("status", "sent_at", "last_error", "next_attempt_at"))
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} emails"))

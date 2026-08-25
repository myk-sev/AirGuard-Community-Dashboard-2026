import imaplib

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dashboard.mailbox import NoMeasurementAttachments, process_message


class Command(BaseCommand):
    help = "Import unread Govee CSV attachments from the configured mailbox"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25)

    def process(self, raw_message):
        return process_message(raw_message)

    def handle(self, *args, **options):
        if not all((settings.GOVEE_IMAP_HOST, settings.GOVEE_IMAP_USER, settings.GOVEE_IMAP_PASSWORD, settings.GOVEE_MAIL_ALLOWED_SENDER)):
            raise CommandError("Set GOVEE_IMAP_HOST, GOVEE_IMAP_USER, GOVEE_IMAP_PASSWORD, and GOVEE_MAIL_ALLOWED_SENDER.")
        processed = ignored = failed = 0
        with imaplib.IMAP4_SSL(
            settings.GOVEE_IMAP_HOST,
            settings.GOVEE_IMAP_PORT,
            timeout=settings.GOVEE_IMAP_TIMEOUT_SECONDS,
        ) as mailbox:
            mailbox.login(settings.GOVEE_IMAP_USER, settings.GOVEE_IMAP_PASSWORD)
            status, _ = mailbox.select(settings.GOVEE_IMAP_FOLDER)
            if status != "OK":
                raise CommandError("The mailbox folder could not be opened.")
            status, data = mailbox.uid("search", None, "UNSEEN", "FROM", f'"{settings.GOVEE_MAIL_ALLOWED_SENDER}"')
            if status != "OK":
                raise CommandError("The mailbox search failed.")
            for message_uid in data[0].split()[-options["limit"]:]:
                status, payload = mailbox.uid("fetch", message_uid, "(RFC822)")
                raw_message = next((item[1] for item in payload or [] if isinstance(item, tuple)), None)
                if status != "OK" or not raw_message:
                    failed += 1
                    continue
                try:
                    _, results = self.process(raw_message)
                    processed += bool(results)
                    ignored += not results
                    mailbox.uid("store", message_uid, "+FLAGS", "\\Seen")
                except NoMeasurementAttachments:
                    ignored += 1
                    mailbox.uid("store", message_uid, "+FLAGS", "\\Seen")
                except ValueError as error:
                    failed += 1
                    self.stderr.write(f"Govee message {message_uid.decode(errors='replace')} failed: {error}")
        summary = f"Processed {processed}; ignored {ignored}; failed {failed} Govee messages"
        if failed:
            raise CommandError(summary)
        self.stdout.write(self.style.SUCCESS(summary))

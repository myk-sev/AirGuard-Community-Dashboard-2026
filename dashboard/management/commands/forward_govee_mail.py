import json
import uuid
from pathlib import PurePath
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import CommandError

from dashboard.mailbox import measurement_attachments

from .process_govee_mail import Command as MailCommand


class Command(MailCommand):
    help = "Forward unread Govee CSV attachments to a remote AirGuard dashboard"

    def handle(self, *args, **options):
        if not settings.AIRGUARD_UPLOAD_URL.startswith("https://") or not settings.AIRGUARD_INGEST_TOKEN:
            raise CommandError("Set a public HTTPS AIRGUARD_UPLOAD_URL and AIRGUARD_INGEST_TOKEN.")
        return super().handle(*args, **options)

    def process(self, raw_message):
        _, attachments = measurement_attachments(raw_message)
        return None, [self.upload(name, content) for name, content in attachments]

    def upload(self, name, content):
        boundary = uuid.uuid4().hex
        filename = PurePath(name.replace("\\", "/")).name.replace('"', "")
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: text/csv\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        request = Request(
            settings.AIRGUARD_UPLOAD_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {settings.AIRGUARD_INGEST_TOKEN}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=settings.GOVEE_IMAP_TIMEOUT_SECONDS) as response:
                result = json.loads(response.read())
        except (HTTPError, URLError, OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Dashboard upload failed: {error}") from None
        if result.get("error"):
            raise ValueError(f"Dashboard upload failed: {result['error']}")
        return result

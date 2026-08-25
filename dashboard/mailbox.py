import hashlib
import io
import zipfile
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime, parseaddr
from pathlib import PurePosixPath

from django.conf import settings
from django.core.files.base import ContentFile

from .ingestion import import_govee_csv
from .models import InboundMessage


class NoMeasurementAttachments(ValueError):
    pass


def _attachments(message):
    for part in message.iter_attachments():
        name = part.get_filename() or "attachment"
        content = part.get_payload(decode=True) or b""
        if name.casefold().endswith(".csv"):
            yield name, content
        elif name.casefold().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    members = [item for item in archive.infolist() if not item.is_dir() and item.filename.casefold().endswith(".csv")]
                    if sum(item.file_size for item in members) > settings.AIRGUARD_MAX_UPLOAD_BYTES:
                        raise ValueError("The ZIP attachments are too large.")
                    for item in members:
                        path = PurePosixPath(item.filename)
                        if path.is_absolute() or ".." in path.parts:
                            raise ValueError("The ZIP contains an unsafe filename.")
                        yield path.name, archive.read(item)
            except zipfile.BadZipFile:
                raise ValueError("The ZIP attachment is not valid.") from None


def measurement_attachments(raw_message):
    if len(raw_message) > settings.AIRGUARD_MAX_UPLOAD_BYTES * 2:
        raise ValueError("The email message is too large.")
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    sender = parseaddr(message.get("From", ""))[1].casefold()
    allowed_sender = settings.GOVEE_MAIL_ALLOWED_SENDER.casefold()
    if allowed_sender and sender != allowed_sender:
        raise ValueError("The message sender is not allowed.")
    attachments = list(_attachments(message))
    if not attachments:
        raise NoMeasurementAttachments("The message has no CSV attachment.")
    return message, attachments


def process_message(raw_message):
    message, attachments = measurement_attachments(raw_message)
    sender = parseaddr(message.get("From", ""))[1].casefold()
    message_id = message.get("Message-ID") or hashlib.sha256(raw_message).hexdigest()
    existing = InboundMessage.objects.filter(message_id=message_id).first()
    if existing and existing.status == "processed":
        return existing, []

    inbound = existing or InboundMessage(message_id=message_id)
    inbound.sender = sender
    inbound.subject = str(message.get("Subject", ""))[:255]
    date = message.get("Date")
    inbound.received_at = parsedate_to_datetime(date) if date else None
    if not inbound.pk:
        inbound.raw_file.save(f"{hashlib.sha256(raw_message).hexdigest()}.eml", ContentFile(raw_message), save=False)
    inbound.status, inbound.error = "received", ""
    inbound.save()

    try:
        results = [import_govee_csv(content, name, inbound_message=inbound) for name, content in attachments]
        inbound.status = "processed"
        inbound.save(update_fields=("status", "error"))
        return inbound, results
    except ValueError as error:
        inbound.status, inbound.error = "failed", str(error)
        inbound.save(update_fields=("status", "error"))
        raise

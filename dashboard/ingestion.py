import csv
import hashlib
import io
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import IngestBatch, Reading, Sensor


TIMESTAMP_NAMES = (
    "time",
    "timestamp",
    "time(dd/mm/yyyy h:mm:ss a)",
    "timestamp for sample frequency every 1 min min",
)
PM25_NAMES = ("pm25", "pm2.5(µg/m³)", "pm2.5(ug/m3)", "pm2.5")


def _value(row, names):
    values = {str(key).replace("\xa0", " ").strip().casefold(): value for key, value in row.items()}
    return next((values[key] for name in names if (key := name.casefold()) in values and values[key] not in (None, "")), None)


def _observed_at(value, sensor):
    observed_at = parse_datetime(str(value or ""))
    if observed_at is None:
        for date_format in ("%d/%m/%Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"):
            try:
                observed_at = datetime.strptime(str(value), date_format)
                break
            except ValueError:
                pass
    if observed_at is None:
        raise ValueError("Measurement time is not a supported date format.")
    observed_at = observed_at.replace(tzinfo=ZoneInfo(sensor.timezone)) if timezone.is_naive(observed_at) else observed_at
    if observed_at > timezone.now() + timedelta(minutes=settings.AIRGUARD_MAX_FUTURE_MINUTES):
        raise ValueError("Measurement time is too far in the future.")
    return observed_at


def sensor_id_from_filename(filename):
    return Path(filename).stem.split("_export_", 1)[0]


def import_govee_csv(content, filename, *, inbound_message=None, sensor_id=None):
    if len(content) > settings.AIRGUARD_MAX_UPLOAD_BYTES:
        raise ValueError("The measurement file is too large.")
    if Path(filename).suffix.casefold() != ".csv":
        raise ValueError("The measurement attachment must be a CSV file.")

    digest = hashlib.sha256(content).hexdigest()
    batch = IngestBatch.objects.filter(source="govee", sha256=digest).first()
    if batch and batch.status == "processed":
        return {"batch": batch.id, "sensor": batch.readings.values_list("sensor_id", flat=True).first(), "created": 0, "updated": 0, "duplicate": True}
    if batch is None:
        batch = IngestBatch(source="govee", filename=Path(filename).name, sha256=digest, inbound_message=inbound_message)
        batch.raw_file.save(Path(filename).name, ContentFile(content), save=False)
        batch.save()

    try:
        sensor = Sensor.objects.get(external_id__iexact=sensor_id or sensor_id_from_filename(filename), enabled=True)
        text = content.decode("utf-8-sig")
        rows = [row for row in csv.DictReader(io.StringIO(text)) if any(row.values())]
        if not rows:
            raise ValueError("The uploaded CSV has no measurements.")

        created = 0
        with transaction.atomic():
            for row in rows:
                value = _value(row, PM25_NAMES)
                try:
                    pm25 = float(value) + sensor.calibration_offset
                except (TypeError, ValueError):
                    raise ValueError("Each measurement needs a numeric PM2.5 value.") from None
                if not 0 <= pm25 <= settings.AIRGUARD_MAX_PM25:
                    raise ValueError("PM2.5 is outside the accepted measurement range.")
                observed_at = _observed_at(_value(row, TIMESTAMP_NAMES), sensor)
                _, was_created = Reading.objects.update_or_create(
                    sensor=sensor,
                    observed_at=observed_at,
                    defaults={"pm25": pm25, "ingest_batch": batch},
                )
                created += was_created
        batch.status = "processed"
        batch.rows = len(rows)
        batch.created_rows = created
        batch.updated_rows = len(rows) - created
        batch.error = ""
        batch.save(update_fields=("status", "rows", "created_rows", "updated_rows", "error", "updated_at"))
        return {"batch": batch.id, "sensor": sensor.id, "created": created, "updated": len(rows) - created, "duplicate": False}
    except (Sensor.DoesNotExist, UnicodeDecodeError) as error:
        message = "Unknown or disabled Govee sensor." if isinstance(error, Sensor.DoesNotExist) else "The uploaded CSV must use UTF-8 encoding."
        batch.status, batch.error = "failed", message
        batch.save(update_fields=("status", "error", "updated_at"))
        raise ValueError(message) from None
    except ValueError as error:
        batch.status, batch.error = "failed", str(error)
        batch.save(update_fields=("status", "error", "updated_at"))
        raise

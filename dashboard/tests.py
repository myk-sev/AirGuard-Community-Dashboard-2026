import io
import json
import re
import tempfile
import zipfile
from datetime import UTC, timedelta
from email.message import EmailMessage
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model
from django.db.models import F
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .alerts import evaluate_alerts
from .aqi import nowcast, pm25_to_aqi
from .emailing import unsubscribe_token
from .mailbox import process_message
from .models import (
    AlertEvent,
    Building,
    Forecast,
    InboundMessage,
    IngestBatch,
    OutboundEmail,
    ProviderEvent,
    Reading,
    Sensor,
    Subscription,
    Suppression,
)
from .weather import cardinal_direction


class FakeImap:
    def __init__(self, messages):
        self.messages = messages
        self.seen = []
        self.uid_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def login(self, *_):
        return "OK", []

    def select(self, _):
        return "OK", [b""]

    def uid(self, command, *args):
        self.uid_calls.append((command, args))
        if command == "search":
            return "OK", [b" ".join(self.messages)]
        if command == "fetch":
            return "OK", [(b"RFC822", self.messages[args[0]])]
        if command == "store":
            self.seen.append(args[0])
            return "OK", []
        raise AssertionError(command)


class AqiTests(TestCase):
    def test_revised_pm25_breakpoints(self):
        self.assertEqual(pm25_to_aqi(9.0), 50)
        self.assertEqual(pm25_to_aqi(9.1), 51)
        self.assertEqual(pm25_to_aqi(35.4), 100)
        self.assertEqual(pm25_to_aqi(35.5), 101)

    def test_nowcast_keeps_constant_concentration(self):
        self.assertAlmostEqual(nowcast([10] * 12), 10)


@override_settings(
    AIRGUARD_INGEST_TOKEN="test-ingest-token",
    AIRGUARD_POSTMARK_WEBHOOK_TOKEN="test-webhook-token",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class DashboardTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory()
        cls.media_settings = override_settings(MEDIA_ROOT=cls.media.name)
        cls.media_settings.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.media_settings.disable()
        cls.media.cleanup()

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_public_pages_render(self):
        for name in ("home", "readings", "resources", "notifications"):
            self.assertEqual(self.client.get(reverse(f"dashboard:{name}")).status_code, 200)

    def test_home_has_status_and_aqi_explanation(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "Updated")
        self.assertContains(response, "What does AQI mean?")

    def test_status_api_serializes_last_update(self):
        response = self.client.get(reverse("dashboard:status_api"))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json()["epoch_updated_at"], float)

    def test_health_reports_database_and_pipeline_state(self):
        response = self.client.get(reverse("dashboard:health"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertIn("pending_email", response.json())

    def test_design_options_render(self):
        for option in ("bands", "motif", "typography", "conventional", "placards"):
            response = self.client.get(reverse("dashboard:design_option", args=(option,)))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f"design-{option}")

    def test_building_page_has_enabled_sensor_controls(self):
        building = Building.objects.first()
        response = self.client.get(reverse("dashboard:building", args=(building.slug,)))
        self.assertEqual(response.context["building"]["reporting"], 3)
        self.assertContains(response, "data-sensor-id", count=3)

    def test_old_sensor_reading_remains_available(self):
        sensor = Building.objects.first().sensors.first()
        sensor.readings.update(observed_at=F("observed_at") - timedelta(days=30))
        response = self.client.get(reverse("dashboard:building", args=(sensor.building.slug,)))
        snapshot = next(item for item in response.context["building"]["sensors"] if item["id"] == sensor.id)
        self.assertFalse(snapshot["is_stale"])
        self.assertIsNotNone(snapshot["aqi"])

    def test_sensor_without_readings_remains_unavailable(self):
        sensor = Building.objects.first().sensors.first()
        sensor.readings.all().delete()
        response = self.client.get(reverse("dashboard:building", args=(sensor.building.slug,)))
        snapshot = next(item for item in response.context["building"]["sensors"] if item["id"] == sensor.id)
        self.assertTrue(snapshot["is_stale"])
        self.assertIsNone(snapshot["aqi"])

    def test_history_is_aggregated_and_bounded(self):
        sensor = Building.objects.first().sensors.first()
        seven_days = self.client.get(reverse("dashboard:readings_api", args=(sensor.id,)), {"range": "7d"}).json()["readings"]
        thirty_days = self.client.get(reverse("dashboard:readings_api", args=(sensor.id,)), {"range": "30d"}).json()["readings"]
        self.assertLessEqual(len(seven_days), 168)
        self.assertLessEqual(len(thirty_days), 120)
        self.assertEqual(seven_days[-3]["data_status"], "historical")

    def test_readings_csv_contains_quality_status(self):
        sensor = Building.objects.first().sensors.first()
        response = self.client.get(reverse("dashboard:readings_csv", args=(sensor.id,)), {"range": "24h"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"pm25_ug_m3", response.content)
        self.assertIn(b"data_status", response.content)

    @patch("dashboard.views.refresh_forecast_weather_if_stale")
    def test_forecast_api_contains_provenance_and_weather(self, refresh_weather):
        sensor = Building.objects.first().sensors.first()
        first = self.client.get(reverse("dashboard:forecast_api", args=(sensor.id,))).json()["forecasts"][0]
        refresh_weather.assert_called_once()
        for key in ("temperature", "relative_humidity", "wind_speed", "wind_direction", "generated_at", "source", "run_id", "weather_source", "weather_generated_at"):
            self.assertIn(key, first)

    @override_settings(AIRGUARD_WEATHER_LATITUDE="41.6881", AIRGUARD_WEATHER_LONGITUDE="-86.2355")
    @patch("dashboard.weather.fetch_weather")
    def test_weather_update_preserves_pm25_provenance(self, fetch_weather):
        forecast = Forecast.objects.filter(forecast_at__gte=timezone.now()).first()
        hour = forecast.forecast_at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        fetch_weather.return_value = {hour: {
            "temperature": 72.5,
            "relative_humidity": 54.0,
            "wind_speed": 8.2,
            "wind_direction": "WNW",
        }}
        original = (forecast.pm25, forecast.source, forecast.run_id)

        call_command("update_forecast_weather", verbosity=0)

        forecast.refresh_from_db()
        self.assertEqual((forecast.pm25, forecast.source, forecast.run_id), original)
        self.assertEqual((forecast.temperature, forecast.relative_humidity, forecast.wind_speed, forecast.wind_direction), (72.5, 54.0, 8.2, "WNW"))
        self.assertEqual(forecast.weather_source, "open-meteo")
        self.assertIsNotNone(forecast.weather_generated_at)

    def test_wind_degrees_are_converted_to_cardinal_direction(self):
        self.assertEqual(cardinal_direction(0), "N")
        self.assertEqual(cardinal_direction(270), "W")
        self.assertEqual(cardinal_direction(348.75), "N")

    def test_subscription_requires_consent_and_queues_verification(self):
        building = Building.objects.first()
        url = reverse("dashboard:subscription_api")
        payload = {"email": "resident@example.org", "building": building.id, "alert_rule": "who_pm25_24h", "locale": "es"}
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type="application/json").status_code, 400)
        payload["consent"] = True
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        subscription = Subscription.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(subscription.enabled)
        self.assertEqual(subscription.threshold, 15)
        email = OutboundEmail.objects.get()
        self.assertEqual(email.kind, "verification")
        self.assertIn("AirGuard Community Dashboard", email.html_body)
        self.assertIn("Confirmar alertas", email.html_body)

    def test_subscription_form_excludes_disabled_demo_buildings(self):
        disabled = Building.objects.first()
        disabled.sensors.update(enabled=False)
        response = self.client.get(reverse("dashboard:notifications"))
        choices = response.context["form"].fields["building"].queryset
        self.assertTrue(choices.exists())
        self.assertNotIn(disabled, choices)

    def test_verification_activates_subscription_and_unsubscribe_stops_it(self):
        building = Building.objects.first()
        self.client.post(reverse("dashboard:notifications"), {
            "email": "resident@example.org",
            "building": building.id,
            "alert_rule": "aqi_101",
            "locale": "en",
            "consent": "on",
        })
        item = OutboundEmail.objects.get()
        verify_path = re.search(r"http://testserver([^\s]+/verify/[^\s]+/)", item.text_body).group(1)
        self.assertEqual(self.client.get(verify_path).status_code, 200)
        subscription = Subscription.objects.get()
        self.assertTrue(subscription.enabled)
        self.assertIsNotNone(subscription.verified_at)

        token = unsubscribe_token(subscription)
        response = self.client.post(reverse("dashboard:unsubscribe", args=(token,)))
        subscription.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(subscription.enabled)
        self.assertTrue(Suppression.objects.filter(email=subscription.email).exists())

    def test_facility_form_is_unlisted_for_search_engines(self):
        user = get_user_model().objects.create_user("facility", password="test", is_staff=True)
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:facility_notifications"))
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_facility_form_requires_staff_login(self):
        response = self.client.get(reverse("dashboard:facility_notifications"))
        self.assertRedirects(response, "/admin/login/?next=/facility-notifications/")

    @override_settings(AIRGUARD_SIGNUP_LIMIT_PER_HOUR=1)
    def test_subscription_api_is_rate_limited(self):
        cache.clear()
        url = reverse("dashboard:subscription_api")
        self.client.post(url, "{}", content_type="application/json")
        self.assertEqual(self.client.post(url, "{}", content_type="application/json").status_code, 429)

    def test_measurement_endpoint_requires_token(self):
        response = self.client.post(reverse("dashboard:measurements", args=("custom",)), "{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_custom_measurement_creates_and_updates_a_reading(self):
        sensor = Sensor.objects.first()
        observed_at = timezone.now().replace(second=37, microsecond=0)
        payload = {"sensor": sensor.external_id, "time": observed_at.isoformat(), "pm25": 12.5}
        url = reverse("dashboard:measurements", args=("custom",))
        headers = {"HTTP_AUTHORIZATION": "Bearer test-ingest-token"}
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type="application/json", **headers).json()["created"], 1)
        payload["pm25"] = 14.5
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type="application/json", **headers).json()["updated"], 1)
        self.assertEqual(Reading.objects.get(sensor=sensor, observed_at=observed_at).pm25, 14.5)

    def test_real_govee_filename_imports_and_archives_csv(self):
        call_command("seed_db", verbosity=0)
        observed_at = timezone.localtime().replace(second=37, microsecond=0)
        content = ("Time(DD/MM/YYYY h:mm:ss A),PM2.5(µg/m³)\n" f"{observed_at.strftime('%d/%m/%Y %I:%M:%S %p')},17.25\n").encode()
        upload = SimpleUploadedFile("BGC-B6_export_202608241200.csv", content, content_type="text/csv")
        url = reverse("dashboard:measurements", args=("govee",))
        headers = {"HTTP_AUTHORIZATION": "Bearer test-ingest-token"}
        response = self.client.post(url, {"file": upload}, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created"], 1)
        self.assertEqual(IngestBatch.objects.get().status, "processed")
        self.assertTrue(IngestBatch.objects.get().raw_file.name.endswith(".csv"))

    def test_duplicate_govee_attachment_is_idempotent(self):
        call_command("seed_db", verbosity=0)
        content = b"Time(DD/MM/YYYY h:mm:ss A),PM2.5(ug/m3)\n24/08/2026 02:00:00 PM,10\n"
        url = reverse("dashboard:measurements", args=("govee",))
        headers = {"HTTP_AUTHORIZATION": "Bearer test-ingest-token"}
        for _ in range(2):
            upload = SimpleUploadedFile("BGC-B7_export_202608241200.csv", content, content_type="text/csv")
            response = self.client.post(url, {"file": upload}, **headers)
        self.assertTrue(response.json()["duplicate"])
        self.assertEqual(IngestBatch.objects.count(), 1)

    def test_govee_attachment_bulk_updates_existing_readings(self):
        call_command("seed_db", verbosity=0)
        observed_at = timezone.localtime().replace(second=0, microsecond=0)
        url = reverse("dashboard:measurements", args=("govee",))
        headers = {"HTTP_AUTHORIZATION": "Bearer test-ingest-token"}
        for pm25 in (10, 12):
            content = ("Time(DD/MM/YYYY h:mm:ss A),PM2.5(ug/m3)\n" f"{observed_at.strftime('%d/%m/%Y %I:%M:%S %p')},{pm25}\n").encode()
            upload = SimpleUploadedFile(f"BGC-B6_export_{pm25}.csv", content, content_type="text/csv")
            response = self.client.post(url, {"file": upload}, **headers)

        self.assertEqual(response.json()["updated"], 1)
        self.assertEqual(Reading.objects.get(sensor__external_id="BGC-B6", observed_at=observed_at).pm25, 12)

    def test_govee_attachment_bulk_imports_large_export(self):
        call_command("seed_db", verbosity=0)
        start = timezone.localtime().replace(second=0, microsecond=0) - timedelta(minutes=2000)
        lines = ["Time(DD/MM/YYYY h:mm:ss A),PM2.5(ug/m3)"]
        lines.extend(f"{(start + timedelta(minutes=minute)).strftime('%d/%m/%Y %I:%M:%S %p')},10" for minute in range(2001))
        upload = SimpleUploadedFile("BGC-B8_export_large.csv", "\n".join(lines).encode(), content_type="text/csv")
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("dashboard:measurements", args=("govee",)),
                {"file": upload},
                HTTP_AUTHORIZATION="Bearer test-ingest-token",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created"], 2001)

    @override_settings(GOVEE_SOURCE_TIMEZONE="Etc/GMT-8")
    def test_govee_source_timezone_converts_phone_timestamps(self):
        call_command("seed_db", verbosity=0)
        expected = timezone.now().replace(second=0, microsecond=0) - timedelta(minutes=10)
        phone_time = expected.astimezone(ZoneInfo("Etc/GMT-8"))
        content = ("Time(DD/MM/YYYY h:mm:ss A),PM2.5(ug/m3)\n" f"{phone_time.strftime('%d/%m/%Y %I:%M:%S %p')},10\n").encode()
        upload = SimpleUploadedFile("BGC-B6_export_timezone.csv", content, content_type="text/csv")
        response = self.client.post(
            reverse("dashboard:measurements", args=("govee",)),
            {"file": upload},
            HTTP_AUTHORIZATION="Bearer test-ingest-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reading.objects.get(ingest_batch__isnull=False).observed_at, expected)

    @override_settings(GOVEE_MAIL_ALLOWED_SENDER="noreply@govee.example")
    def test_mailbox_processes_zip_and_archives_message(self):
        call_command("seed_db", verbosity=0)
        csv_content = b"Time(DD/MM/YYYY h:mm:ss A),PM2.5(ug/m3)\n24/08/2026 02:00:00 PM,10\n"
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("BGC-B8_export_202608241200.csv", csv_content)
        message = EmailMessage()
        message["From"] = "noreply@govee.example"
        message["To"] = "airguard@example.org"
        message["Subject"] = "Govee export"
        message["Message-ID"] = "<test-govee@example.org>"
        message.set_content("Attached")
        message.add_attachment(archive.getvalue(), maintype="application", subtype="zip", filename="exports.zip")
        inbound, results = process_message(message.as_bytes())
        self.assertEqual(inbound.status, "processed")
        self.assertEqual(results[0]["created"], 1)
        self.assertEqual(InboundMessage.objects.count(), 1)

    @override_settings(
        GOVEE_IMAP_HOST="imap.example.org",
        GOVEE_IMAP_USER="airguard@example.org",
        GOVEE_IMAP_PASSWORD="app-password",
        GOVEE_IMAP_FOLDER="INBOX",
        GOVEE_MAIL_ALLOWED_SENDER="no-reply@govee.com",
    )
    def test_mailbox_command_processes_export_and_ignores_non_export(self):
        call_command("seed_db", verbosity=0)
        export = EmailMessage()
        export["From"] = "no-reply@govee.com"
        export["Message-ID"] = "<export@example.org>"
        export.set_content("Attached")
        export.add_attachment(
            b"Time(DD/MM/YYYY h:mm:ss A),PM2.5(ug/m3)\n24/08/2026 02:00:00 PM,10\n",
            maintype="text",
            subtype="csv",
            filename="BGC-B6_export_202608241400.csv",
        )
        notice = EmailMessage()
        notice["From"] = "no-reply@govee.com"
        notice.set_content("Verification notice")
        mailbox = FakeImap({b"1": export.as_bytes(), b"2": notice.as_bytes()})
        output = io.StringIO()

        with patch("dashboard.management.commands.process_govee_mail.imaplib.IMAP4_SSL", return_value=mailbox):
            call_command("process_govee_mail", stdout=output)

        self.assertEqual(mailbox.seen, [b"1", b"2"])
        self.assertIn(("search", (None, "UNSEEN", "FROM", '"no-reply@govee.com"')), mailbox.uid_calls)
        self.assertIn(("fetch", (b"1", "(BODY.PEEK[])")), mailbox.uid_calls)
        self.assertIn("Processed 1; ignored 1; failed 0", output.getvalue())
        self.assertEqual(Reading.objects.filter(ingest_batch__isnull=False).count(), 1)

    @override_settings(
        GOVEE_IMAP_HOST="imap.example.org",
        GOVEE_IMAP_USER="airguard@example.org",
        GOVEE_IMAP_PASSWORD="app-password",
        GOVEE_MAIL_ALLOWED_SENDER="no-reply@govee.com",
    )
    def test_mailbox_all_option_includes_read_messages(self):
        mailbox = FakeImap({})
        with patch("dashboard.management.commands.process_govee_mail.imaplib.IMAP4_SSL", return_value=mailbox):
            call_command("process_govee_mail", "--all", stdout=io.StringIO())
        self.assertIn(("search", (None, "ALL", "FROM", '"no-reply@govee.com"')), mailbox.uid_calls)

    @override_settings(
        GOVEE_IMAP_HOST="imap.example.org",
        GOVEE_IMAP_USER="airguard@example.org",
        GOVEE_IMAP_PASSWORD="app-password",
        GOVEE_IMAP_FOLDER="INBOX",
        GOVEE_MAIL_ALLOWED_SENDER="no-reply@govee.com",
    )
    def test_mailbox_command_continues_after_a_failed_export(self):
        call_command("seed_db", verbosity=0)

        def message(message_id, filename, value):
            item = EmailMessage()
            item["From"] = "no-reply@govee.com"
            item["Message-ID"] = message_id
            item.set_content("Attached")
            item.add_attachment(
                f"Time(DD/MM/YYYY h:mm:ss A),PM2.5(ug/m3)\n24/08/2026 02:00:00 PM,{value}\n".encode(),
                maintype="text",
                subtype="csv",
                filename=filename,
            )
            return item.as_bytes()

        mailbox = FakeImap(
            {
                b"1": message("<failed@example.org>", "BGC-B6_export_202608241400.csv", "bad"),
                b"2": message("<valid@example.org>", "BGC-B7_export_202608241400.csv", "12"),
            }
        )
        with patch("dashboard.management.commands.process_govee_mail.imaplib.IMAP4_SSL", return_value=mailbox):
            with self.assertRaises(CommandError):
                call_command("process_govee_mail", stderr=io.StringIO())

        self.assertEqual(mailbox.seen, [b"2"])
        self.assertEqual(Reading.objects.filter(ingest_batch__isnull=False).count(), 1)
        self.assertEqual(InboundMessage.objects.filter(status="failed").count(), 1)
        self.assertEqual(InboundMessage.objects.filter(status="processed").count(), 1)

    @override_settings(
        GOVEE_IMAP_HOST="imap.example.org",
        GOVEE_IMAP_USER="airguard@example.org",
        GOVEE_IMAP_PASSWORD="app-password",
        GOVEE_IMAP_FOLDER="INBOX",
        GOVEE_MAIL_ALLOWED_SENDER="no-reply@govee.com",
        AIRGUARD_UPLOAD_URL="https://dashboard.example.org/api/v1/measurements/govee/",
        AIRGUARD_INGEST_TOKEN="ingest-token",
    )
    def test_forward_mailbox_command_uploads_to_remote_dashboard(self):
        def export(sensor):
            message = EmailMessage()
            message["From"] = "no-reply@govee.com"
            message.set_content("Attached")
            message.add_attachment(
                b"Time(DD/MM/YYYY h:mm:ss A),PM2.5(ug/m3)\n24/08/2026 02:00:00 PM,10\n",
                maintype="text",
                subtype="csv",
                filename=f"{sensor}_export_202608241400.csv",
            )
            return message.as_bytes()

        mailbox = FakeImap({b"1": export("BGC-B6"), b"2": export("BGC-B7")})
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"created": 1}'
        output = io.StringIO()

        with (
            patch("dashboard.management.commands.process_govee_mail.imaplib.IMAP4_SSL", return_value=mailbox),
            patch("dashboard.management.commands.forward_govee_mail.urlopen", return_value=response) as upload,
        ):
            call_command("forward_govee_mail", stdout=output)

        request = upload.call_args_list[0].args[0]
        self.assertEqual(request.full_url, "https://dashboard.example.org/api/v1/measurements/govee/")
        self.assertEqual(request.get_header("Authorization"), "Bearer ingest-token")
        self.assertIn(b'filename="BGC-B6_export_202608241400.csv"', request.data)
        self.assertEqual(upload.call_count, 2)
        self.assertEqual(mailbox.seen, [b"1", b"2"])
        self.assertIn("Processed 2; ignored 0; failed 0", output.getvalue())

    @override_settings(
        GOVEE_IMAP_HOST="imap.example.org",
        GOVEE_IMAP_USER="airguard@example.org",
        GOVEE_IMAP_PASSWORD="app-password",
        GOVEE_MAIL_ALLOWED_SENDER="no-reply@govee.com",
        AIRGUARD_UPLOAD_URL="https://dashboard.example.org/api/v1/measurements/govee/",
        AIRGUARD_INGEST_TOKEN="ingest-token",
    )
    def test_forward_mailbox_reports_dashboard_rejection(self):
        export = EmailMessage()
        export["From"] = "no-reply@govee.com"
        export.set_content("Attached")
        export.add_attachment(b"bad", maintype="text", subtype="csv", filename="unknown.csv")
        mailbox = FakeImap({b"1": export.as_bytes()})
        rejection = HTTPError("https://dashboard.example.org", 400, "Bad Request", {}, io.BytesIO(b'{"error":"Unknown sensor"}'))
        error_output = io.StringIO()

        with (
            patch("dashboard.management.commands.process_govee_mail.imaplib.IMAP4_SSL", return_value=mailbox),
            patch("dashboard.management.commands.forward_govee_mail.urlopen", side_effect=rejection),
            self.assertRaises(CommandError),
        ):
            call_command("forward_govee_mail", stderr=error_output)

        self.assertIn("Unknown sensor", error_output.getvalue())
        self.assertEqual(mailbox.seen, [])

    def test_postmark_complaint_suppresses_future_email(self):
        building = Building.objects.first()
        subscription = Subscription.objects.create(email="resident@example.org", building=building, threshold=51, verified_at=timezone.now(), enabled=True)
        payload = {"RecordType": "SpamComplaint", "ID": 123, "Recipient": subscription.email}
        response = self.client.post(
            reverse("dashboard:postmark_event"),
            json.dumps(payload),
            content_type="application/json",
            HTTP_X_AIRGUARD_WEBHOOK_TOKEN="test-webhook-token",
        )
        subscription.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(subscription.enabled)
        self.assertEqual(ProviderEvent.objects.count(), 1)
        self.assertEqual(Suppression.objects.count(), 1)

    def test_seed_db_materializes_authoritative_sensor_manifest(self):
        call_command("seed_db", verbosity=0)
        self.assertEqual(Sensor.objects.filter(enabled=True).count(), 10)
        self.assertEqual(Sensor.objects.get(external_id="BGC-B6").name, "Lounge")
        self.assertFalse(Sensor.objects.filter(external_id__startswith="riverside-").first().enabled)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AlertTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_alert_evaluation_is_idempotent_and_outbox_sends(self):
        building = Building.objects.first()
        subscription = Subscription.objects.create(
            email="verified@example.org",
            building=building,
            threshold_kind="who_pm25_24h",
            threshold=15,
            verified_at=timezone.now(),
            enabled=True,
            unsubscribe_token_hash="set",
        )
        Forecast.objects.filter(sensor__building=building).update(pm25=100, generated_at=timezone.now())
        self.assertEqual(evaluate_alerts(), 1)
        self.assertEqual(evaluate_alerts(), 0)
        self.assertEqual(AlertEvent.objects.filter(subscription=subscription).count(), 1)
        self.assertEqual(OutboundEmail.objects.filter(kind="alert").count(), 1)
        call_command("send_outbox", verbosity=0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].alternatives[0].mimetype, "text/html")
        self.assertIn("AirGuard Community Dashboard", mail.outbox[0].alternatives[0].content)
        self.assertEqual(OutboundEmail.objects.get(kind="alert").status, "sent")

    def test_suppressed_address_is_not_sent(self):
        Suppression.objects.create(email="blocked@example.org", reason="bounce")
        OutboundEmail.objects.create(event_key="test", kind="alert", to_email="blocked@example.org", subject="Test", text_body="Test")
        call_command("send_outbox", verbosity=0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(OutboundEmail.objects.get().status, "suppressed")

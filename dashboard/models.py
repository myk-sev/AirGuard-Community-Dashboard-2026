from django.db import models
from django.utils import timezone


class Building(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=32, default="building-2")
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "name")

    def __str__(self):
        return self.name


class Sensor(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="sensors")
    name = models.CharField(max_length=80)
    placement = models.SlugField(max_length=80)
    external_id = models.CharField(max_length=80, unique=True)
    source = models.CharField(max_length=20, default="govee")
    enabled = models.BooleanField(default=True)
    timezone = models.CharField(max_length=64, default="America/New_York")
    calibration_offset = models.FloatField(default=0)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("building", "display_order", "name")

    def __str__(self):
        return f"{self.building}: {self.name}"


class InboundMessage(models.Model):
    STATUS = (("received", "Received"), ("processed", "Processed"), ("failed", "Failed"))

    message_id = models.CharField(max_length=255, unique=True)
    sender = models.EmailField(blank=True)
    subject = models.CharField(max_length=255, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    raw_file = models.FileField(upload_to="inbound/%Y/%m")
    status = models.CharField(max_length=16, choices=STATUS, default="received")
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class IngestBatch(models.Model):
    STATUS = (("received", "Received"), ("processed", "Processed"), ("failed", "Failed"))

    source = models.CharField(max_length=20)
    filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    raw_file = models.FileField(upload_to="measurements/%Y/%m")
    inbound_message = models.ForeignKey(InboundMessage, null=True, blank=True, on_delete=models.SET_NULL, related_name="batches")
    status = models.CharField(max_length=16, choices=STATUS, default="received")
    rows = models.PositiveIntegerField(default=0)
    created_rows = models.PositiveIntegerField(default=0)
    updated_rows = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("source", "sha256"), name="unique_ingest_file")]


class Reading(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name="readings")
    observed_at = models.DateTimeField()
    pm25 = models.FloatField()
    ingest_batch = models.ForeignKey(IngestBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="readings")

    class Meta:
        ordering = ("observed_at",)
        constraints = [models.UniqueConstraint(fields=("sensor", "observed_at"), name="unique_sensor_reading")]


class Forecast(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name="forecasts")
    forecast_at = models.DateTimeField()
    pm25 = models.FloatField()
    temperature = models.FloatField()
    relative_humidity = models.FloatField()
    wind_speed = models.FloatField()
    wind_direction = models.CharField(max_length=16)
    generated_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=80, default="pending")
    run_id = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ("forecast_at",)
        constraints = [models.UniqueConstraint(fields=("sensor", "forecast_at"), name="unique_sensor_forecast")]


class Subscription(models.Model):
    AUDIENCES = (("community", "Community"), ("facility", "Facility manager"))
    THRESHOLD_KINDS = (
        ("aqi", "Forecast AQI"),
        ("who_pm25_24h", "WHO 24-hour PM2.5 guideline"),
        ("epa_pm25_24h", "EPA 24-hour PM2.5 standard"),
    )
    LOCALES = (("en", "English"), ("es", "Spanish"))

    email = models.EmailField()
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="subscriptions")
    threshold_kind = models.CharField(max_length=24, choices=THRESHOLD_KINDS, default="aqi")
    threshold = models.FloatField()
    locale = models.CharField(max_length=2, choices=LOCALES, default="en")
    audience = models.CharField(max_length=16, choices=AUDIENCES, default="community")
    consent_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_token_hash = models.CharField(max_length=64, blank=True)
    unsubscribe_token_hash = models.CharField(max_length=64, blank=True)
    enabled = models.BooleanField(default=False)
    in_alert = models.BooleanField(default=False)
    last_alert_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("email", "building", "audience"), name="unique_subscription")]

    def __str__(self):
        return f"{self.email}: {self.building}"


class AlertEvent(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="alert_events")
    event_key = models.CharField(max_length=160, unique=True)
    predicted_at = models.DateTimeField()
    predicted_value = models.FloatField()
    threshold = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)


class OutboundEmail(models.Model):
    STATUS = (("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent"), ("failed", "Failed"), ("suppressed", "Suppressed"))
    KINDS = (("verification", "Verification"), ("alert", "Alert"))

    event_key = models.CharField(max_length=160, unique=True)
    kind = models.CharField(max_length=16, choices=KINDS)
    subscription = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.SET_NULL, related_name="outbound_emails")
    alert_event = models.ForeignKey(AlertEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name="outbound_emails")
    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    text_body = models.TextField()
    html_body = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS, default="pending")
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    provider_id = models.CharField(max_length=160, blank=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)


class Suppression(models.Model):
    email = models.EmailField(unique=True)
    reason = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)


class ProviderEvent(models.Model):
    provider_id = models.CharField(max_length=160, unique=True)
    email = models.EmailField(blank=True)
    kind = models.CharField(max_length=80)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

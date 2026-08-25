from collections import defaultdict
from datetime import UTC, timedelta
from statistics import mean, median

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .aqi import nowcast, pm25_to_aqi
from .emailing import queue_alert
from .models import AlertEvent, Forecast, Reading, Subscription


def _hour(value):
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _hourly(queryset, time_field):
    by_sensor = defaultdict(list)
    for sensor_id, stamp, value in queryset.values_list("sensor_id", time_field, "pm25"):
        by_sensor[(_hour(stamp), sensor_id)].append(value)
    by_hour = defaultdict(list)
    for (stamp, _), values in by_sensor.items():
        by_hour[stamp].append(mean(values))
    return {stamp: median(values) for stamp, values in by_hour.items()}


def _crossing(subscription, now):
    sensor_ids = subscription.building.sensors.filter(enabled=True).values_list("id", flat=True)
    start = now - timedelta(hours=23)
    observed = _hourly(Reading.objects.filter(sensor_id__in=sensor_ids, observed_at__gte=start, observed_at__lte=now), "observed_at")
    forecasts = _hourly(
        Forecast.objects.filter(
            sensor_id__in=sensor_ids,
            forecast_at__gt=now,
            forecast_at__lte=now + timedelta(hours=24),
            generated_at__gte=now - timedelta(hours=settings.AIRGUARD_FORECAST_MAX_AGE_HOURS),
        ),
        "forecast_at",
    )
    series = dict(observed)
    for stamp in sorted(forecasts):
        series[stamp] = forecasts[stamp]
        if subscription.threshold_kind == "aqi":
            values = [series[item] for item in sorted(series, reverse=True) if item <= stamp][:12]
            concentration = nowcast(values)
            value = pm25_to_aqi(concentration) if concentration is not None else None
        else:
            values = [series.get(stamp - timedelta(hours=offset)) for offset in range(24)]
            present = [value for value in values if value is not None]
            value = mean(present) if len(present) >= 18 else None
        if value is not None and value >= subscription.threshold:
            return stamp, value
    return None


def evaluate_alerts(now=None):
    now = now or timezone.now()
    created = 0
    for subscription in Subscription.objects.select_related("building").filter(enabled=True, verified_at__isnull=False):
        crossing = _crossing(subscription, now)
        if crossing is None:
            if subscription.in_alert:
                subscription.in_alert = False
                subscription.save(update_fields=("in_alert", "updated_at"))
            continue
        if subscription.in_alert and subscription.last_alert_at and now - subscription.last_alert_at < timedelta(hours=settings.AIRGUARD_ALERT_COOLDOWN_HOURS):
            continue
        predicted_at, value = crossing
        event_key = f"alert:{subscription.id}:{subscription.threshold_kind}:{predicted_at.date().isoformat()}"
        with transaction.atomic():
            event, was_created = AlertEvent.objects.get_or_create(
                event_key=event_key,
                defaults={
                    "subscription": subscription,
                    "predicted_at": predicted_at,
                    "predicted_value": value,
                    "threshold": subscription.threshold,
                },
            )
            if was_created:
                queue_alert(event)
                created += 1
            subscription.in_alert = True
            subscription.last_alert_at = now
            subscription.save(update_fields=("in_alert", "last_alert_at", "updated_at"))
    return created

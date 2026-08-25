import csv
import hashlib
import json
from collections import defaultdict
from datetime import UTC, timedelta
from secrets import compare_digest
from statistics import mean, median

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core import signing
from django.db import connection
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .aqi import aqi_category, nowcast, pm25_to_aqi
from .emailing import queue_verification, token_hash
from .forms import SubscriptionForm
from .ingestion import import_govee_csv
from .models import Building, Forecast, IngestBatch, OutboundEmail, ProviderEvent, Reading, Sensor, Subscription, Suppression
from .weather import refresh_forecast_weather_if_stale


STALE_AFTER = timedelta(minutes=15)
RANGE_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
DESIGN_TEMPLATES = {
    "bands": "dashboard/home_design_bands.html",
    "motif": "dashboard/home_design_motif.html",
    "typography": "dashboard/home_design_typography.html",
    "conventional": "dashboard/home_design_conventional.html",
    "placards": "dashboard/home_design_placards.html",
}


def _hourly_values(readings):
    grouped = defaultdict(list)
    for stamp, value in readings:
        grouped[stamp.astimezone(UTC).replace(minute=0, second=0, microsecond=0)].append(value)
    return [(stamp, mean(values)) for stamp, values in sorted(grouped.items())]


def _sensor_snapshot(sensor, now=None):
    now = now or timezone.now()
    latest = sensor.readings.order_by("-observed_at").first()
    stale = not latest or now - latest.observed_at > STALE_AFTER
    aqi = None
    if not stale:
        hourly = _hourly_values(sensor.readings.filter(observed_at__gte=now - timedelta(hours=12)).values_list("observed_at", "pm25"))
        concentration = nowcast([value for _, value in reversed(hourly)])
        aqi = pm25_to_aqi(concentration) if concentration is not None else None
    category = aqi_category(aqi) if aqi is not None else {"label": "Unavailable", "css_class": "unavailable"}
    return {
        "id": sensor.id,
        "name": sensor.name,
        "placement": sensor.placement,
        "pm25": round(latest.pm25, 1) if latest else None,
        "aqi": aqi,
        "category": category["label"],
        "category_class": category["css_class"],
        "observed_at": latest.observed_at if latest else None,
        "is_stale": stale,
    }


def _building_summary(building, now=None):
    sensors = [_sensor_snapshot(sensor, now) for sensor in building.sensors.filter(enabled=True)]
    valid = [sensor["aqi"] for sensor in sensors if sensor["aqi"] is not None]
    aqi = round(median(valid)) if valid else None
    category = aqi_category(aqi) if aqi is not None else {"label": "Unavailable", "css_class": "unavailable"}
    return {
        "id": building.id,
        "name": building.name,
        "slug": building.slug,
        "icon": building.icon,
        "aqi": aqi,
        "category": category["label"],
        "category_class": category["css_class"],
        "reporting": len(valid),
        "total": len(sensors),
        "sensors": sensors,
    }


def _network_status():
    now = timezone.now()
    snapshots = [_sensor_snapshot(sensor, now) for sensor in Sensor.objects.filter(enabled=True).select_related("building")]
    valid = [sensor["aqi"] for sensor in snapshots if sensor["aqi"] is not None]
    total = len(snapshots)
    current_aqi = round(median(valid)) if len(valid) >= (total + 1) // 2 and valid else None
    current_category = aqi_category(current_aqi) if current_aqi is not None else {"label": "Unavailable", "css_class": "unavailable"}
    grouped = defaultdict(list)
    for forecast in Forecast.objects.filter(
        sensor__enabled=True,
        forecast_at__gte=now,
        forecast_at__lte=now + timedelta(hours=24),
        generated_at__gte=now - timedelta(hours=settings.AIRGUARD_FORECAST_MAX_AGE_HOURS),
    ):
        grouped[forecast.forecast_at].append(pm25_to_aqi(forecast.pm25))
    points = [(stamp, round(median(values))) for stamp, values in grouped.items() if values]
    peak_stamp, peak_aqi = max(points, key=lambda point: point[1]) if points else (None, None)
    peak_category = aqi_category(peak_aqi) if peak_aqi is not None else {"label": "Unavailable", "css_class": "unavailable"}
    updated_at = max((sensor["observed_at"] for sensor in snapshots if sensor["observed_at"]), default=None)
    return {
        "aqi": current_aqi,
        "category": current_category["label"],
        "category_class": current_category["css_class"],
        "reporting": len(valid),
        "total": total,
        "updated_at": updated_at,
        "epoch_updated_at": updated_at.timestamp() if updated_at else 0,
        "forecast_aqi": peak_aqi,
        "forecast_category": peak_category["label"],
        "forecast_category_class": peak_category["css_class"],
        "forecast_at": peak_stamp,
        "message": get_home_message(current_aqi),
        "message_key": "unavailableMessage" if current_aqi is None else "goodStatusMessage" if current_aqi <= 50 else "moderateStatusMessage" if current_aqi <= 100 else "unhealthyStatusMessage",
    }


def _buildings():
    return Building.objects.filter(sensors__enabled=True).distinct().prefetch_related("sensors")


def _home_context():
    return {"status": _network_status(), "buildings": [_building_summary(item) for item in _buildings()]}


def home(request):
    return render(request, "dashboard/home.html", _home_context())


def design_option(request, option):
    if option not in DESIGN_TEMPLATES:
        raise Http404("Unknown design option")
    return render(request, DESIGN_TEMPLATES[option], _home_context())


def readings(request):
    return render(request, "dashboard/readings.html", {"buildings": [_building_summary(item) for item in _buildings()]})


def building(request, slug):
    item = get_object_or_404(_buildings(), slug=slug)
    return render(request, "dashboard/building.html", {"building": _building_summary(item)})


def resources(request):
    return render(request, "dashboard/resources.html")


def _save_subscription(form, audience, request):
    data = form.cleaned_data
    subscription = Subscription.objects.filter(email__iexact=data["email"], building=data["building"], audience=audience).first()
    if subscription is None:
        subscription = Subscription(email=data["email"].casefold(), building=data["building"], audience=audience)
    subscription.threshold_kind = data["threshold_kind"]
    subscription.threshold = data["threshold"]
    subscription.locale = data["locale"]
    subscription.consent_at = timezone.now()
    subscription.enabled = bool(subscription.verified_at)
    subscription.save()
    Suppression.objects.filter(email__iexact=subscription.email, reason="unsubscribe").delete()
    verification_queued = not subscription.verified_at
    if verification_queued:
        queue_verification(subscription, request)
    return subscription, verification_queued


def _signup_allowed(request):
    key = "signup:" + hashlib.sha256(request.META.get("REMOTE_ADDR", "unknown").encode()).hexdigest()
    if cache.add(key, 1, 3600):
        return True
    try:
        return cache.incr(key) <= settings.AIRGUARD_SIGNUP_LIMIT_PER_HOUR
    except ValueError:
        return True


def _subscription_page(request, audience):
    state = ""
    if request.method == "POST":
        if not _signup_allowed(request):
            return HttpResponse("Too many signup attempts. Try again later.", status=429)
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            _, verification_queued = _save_subscription(form, audience, request)
            state = "verification" if verification_queued else "updated"
            form = SubscriptionForm(initial={"locale": form.cleaned_data["locale"]})
    else:
        form = SubscriptionForm(initial={"locale": "en"})
    return render(request, "dashboard/notifications.html", {"form": form, "state": state, "audience": audience})


@require_http_methods(["GET", "POST"])
def notifications(request):
    return _subscription_page(request, "community")


@require_http_methods(["GET", "POST"])
@staff_member_required
def facility_notifications(request):
    response = _subscription_page(request, "facility")
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@require_GET
def verify_subscription(request, token):
    try:
        payload = signing.loads(
            token,
            salt="airguard-verification",
            max_age=settings.AIRGUARD_VERIFY_MAX_AGE_HOURS * 3600,
        )
    except signing.BadSignature:
        raise Http404("Invalid or expired verification link")
    subscription = get_object_or_404(
        Subscription,
        id=payload.get("subscription"),
        verification_token_hash=token_hash(token),
    )
    subscription.verified_at = timezone.now()
    subscription.enabled = True
    subscription.verification_token_hash = ""
    subscription.save(update_fields=("verified_at", "enabled", "verification_token_hash", "updated_at"))
    return render(request, "dashboard/subscription_status.html", {"status": "verified"})


@require_http_methods(["GET", "POST"])
def unsubscribe(request, token):
    try:
        subscription_id = signing.loads(token, salt="airguard-unsubscribe")
    except signing.BadSignature:
        raise Http404("Invalid unsubscribe link")
    subscription = get_object_or_404(Subscription, id=subscription_id)
    status = "confirm"
    if request.method == "POST":
        subscription.enabled = False
        subscription.in_alert = False
        subscription.save(update_fields=("enabled", "in_alert", "updated_at"))
        Suppression.objects.update_or_create(email=subscription.email, defaults={"reason": "unsubscribe"})
        status = "unsubscribed"
    return render(request, "dashboard/subscription_status.html", {"status": status, "token": token})


@require_GET
def status_api(request):
    status = _network_status()
    return JsonResponse({key: value.isoformat() if hasattr(value, "isoformat") else value for key, value in status.items()})


@require_GET
def health(request):
    connection.ensure_connection()
    latest_reading = Reading.objects.filter(sensor__enabled=True).order_by("-observed_at").values_list("observed_at", flat=True).first()
    latest_ingest = IngestBatch.objects.filter(status="processed").order_by("-updated_at").values_list("updated_at", flat=True).first()
    return JsonResponse({
        "ok": True,
        "database": "available",
        "enabled_sensors": Sensor.objects.filter(enabled=True).count(),
        "latest_reading_at": latest_reading.isoformat() if latest_reading else None,
        "latest_ingest_at": latest_ingest.isoformat() if latest_ingest else None,
        "pending_email": OutboundEmail.objects.filter(status__in=("pending", "failed")).count(),
    })


@require_GET
def buildings_api(request):
    return JsonResponse({"buildings": [_building_summary(item) for item in _buildings()]})


@require_GET
def building_api(request, slug):
    return JsonResponse(_building_summary(get_object_or_404(_buildings(), slug=slug)))


def _history(sensor_id, range_name):
    if range_name not in RANGE_HOURS:
        raise Http404("Unknown time range")
    sensor = get_object_or_404(Sensor, id=sensor_id, enabled=True)
    readings = sensor.readings.filter(observed_at__gte=timezone.now() - timedelta(hours=RANGE_HOURS[range_name])).values_list("observed_at", "pm25")
    bucket_hours = 6 if range_name == "30d" else 1
    buckets = defaultdict(list)
    for stamp, value in readings:
        utc = stamp.astimezone(UTC)
        bucket = utc.replace(hour=utc.hour - utc.hour % bucket_hours, minute=0, second=0, microsecond=0)
        buckets[bucket].append(value)
    readings = [(stamp, mean(values)) for stamp, values in sorted(buckets.items())]
    return sensor, readings[-(RANGE_HOURS[range_name] // bucket_hours):]


@require_GET
def readings_api(request, sensor_id):
    sensor, readings = _history(sensor_id, request.GET.get("range", "24h"))
    now = timezone.now()
    return JsonResponse({
        "sensor": {"id": sensor.id, "name": sensor.name, "building": sensor.building.name},
        "readings": [
            {
                "timestamp": stamp.isoformat(),
                "pm25": round(value, 1),
                "aqi": pm25_to_aqi(value),
                "category": aqi_category(pm25_to_aqi(value))["label"],
                "data_status": "current" if now - stamp <= STALE_AFTER else "historical",
            }
            for stamp, value in readings
        ],
    })


@require_GET
def readings_csv(request, sensor_id):
    sensor, readings = _history(sensor_id, request.GET.get("range", "24h"))
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="airguard-{sensor.external_id}-readings.csv"'
    writer = csv.writer(response)
    writer.writerow(("timestamp", "pm25_ug_m3", "aqi", "category", "data_status"))
    now = timezone.now()
    for stamp, value in readings:
        aqi = pm25_to_aqi(value)
        writer.writerow((stamp.isoformat(), f"{value:.1f}", aqi, aqi_category(aqi)["label"], "current" if now - stamp <= STALE_AFTER else "historical"))
    return response


@require_GET
def forecast_api(request, sensor_id):
    sensor = get_object_or_404(Sensor, id=sensor_id, enabled=True)
    try:
        refresh_forecast_weather_if_stale()
    except Exception:
        pass
    now = timezone.now()
    forecasts = sensor.forecasts.filter(
        forecast_at__gte=now,
        generated_at__gte=now - timedelta(hours=settings.AIRGUARD_FORECAST_MAX_AGE_HOURS),
    ).order_by("forecast_at")[:24]
    return JsonResponse({
        "sensor": {"id": sensor.id, "name": sensor.name, "building": sensor.building.name},
        "forecasts": [
            {
                "timestamp": item.forecast_at.isoformat(),
                "pm25": round(item.pm25, 1),
                "aqi": pm25_to_aqi(item.pm25),
                "category": aqi_category(pm25_to_aqi(item.pm25))["label"],
                "temperature": round(item.temperature, 1),
                "relative_humidity": round(item.relative_humidity),
                "wind_speed": round(item.wind_speed, 1),
                "wind_direction": item.wind_direction,
                "generated_at": item.generated_at.isoformat(),
                "source": item.source,
                "run_id": item.run_id,
                "weather_source": item.weather_source,
                "weather_generated_at": item.weather_generated_at.isoformat() if item.weather_generated_at else None,
            }
            for item in forecasts
        ],
    })


@require_POST
def subscription_api(request):
    if not _signup_allowed(request):
        return JsonResponse({"error": "Too many signup attempts. Try again later."}, status=429)
    try:
        data = json.loads(request.body or "{}")
        if "alert_rule" not in data and "threshold" in data:
            data["alert_rule"] = f"aqi_{int(data['threshold'])}"
        data["consent"] = data.get("consent") is True
        audience = data.pop("audience", "community")
        if audience not in dict(Subscription.AUDIENCES):
            raise ValueError
        form = SubscriptionForm(data)
        if not form.is_valid():
            return JsonResponse({"error": "Invalid subscription", "fields": form.errors.get_json_data()}, status=400)
        subscription, verification_queued = _save_subscription(form, audience, request)
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid subscription"}, status=400)
    return JsonResponse({"id": subscription.id, "saved": True, "verification_queued": verification_queued})


def _authorized(request, setting_name, header):
    expected = getattr(settings, setting_name)
    provided = request.headers.get(header, "")
    if header == "Authorization" and provided.startswith("Bearer "):
        provided = provided[7:]
    return bool(expected) and compare_digest(provided, expected)


def _custom_upload(request):
    data = json.loads(request.body or "{}")
    sensor = Sensor.objects.get(external_id__iexact=str(data.get("sensor", "")), enabled=True)
    observed_at = parse_datetime(str(data.get("time", "")))
    if observed_at is None:
        raise ValueError("Measurement time must be an ISO 8601 timestamp.")
    if timezone.is_naive(observed_at):
        observed_at = timezone.make_aware(observed_at, timezone.get_default_timezone())
    if observed_at > timezone.now() + timedelta(minutes=settings.AIRGUARD_MAX_FUTURE_MINUTES):
        raise ValueError("Measurement time is too far in the future.")
    try:
        pm25 = float(data["pm25"]) + sensor.calibration_offset
    except (KeyError, TypeError, ValueError):
        raise ValueError("A numeric PM2.5 value is required.") from None
    if not 0 <= pm25 <= settings.AIRGUARD_MAX_PM25:
        raise ValueError("PM2.5 is outside the accepted measurement range.")
    reading, created = Reading.objects.update_or_create(sensor=sensor, observed_at=observed_at, defaults={"pm25": pm25})
    return {"sensor": reading.sensor_id, "created": int(created), "updated": int(not created)}


@csrf_exempt
@require_POST
def measurements(request, sensor_type):
    if not settings.AIRGUARD_INGEST_TOKEN:
        return JsonResponse({"error": "Measurement ingestion is not configured."}, status=503)
    if not _authorized(request, "AIRGUARD_INGEST_TOKEN", "Authorization"):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    try:
        if sensor_type == "govee":
            uploaded = request.FILES.get("file")
            if not uploaded:
                raise ValueError("Upload a CSV file in the file field.")
            result = import_govee_csv(uploaded.read(), uploaded.name, sensor_id=request.POST.get("sensor") or None)
        elif sensor_type == "custom":
            result = _custom_upload(request)
        else:
            return JsonResponse({"error": "Unknown measurement source."}, status=404)
    except Sensor.DoesNotExist:
        return JsonResponse({"error": "Unknown or disabled sensor."}, status=400)
    except (ValueError, json.JSONDecodeError) as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse(result)


@csrf_exempt
@require_POST
def postmark_event(request):
    if not settings.AIRGUARD_POSTMARK_WEBHOOK_TOKEN:
        return JsonResponse({"error": "Email events are not configured."}, status=503)
    if not _authorized(request, "AIRGUARD_POSTMARK_WEBHOOK_TOKEN", "X-AirGuard-Webhook-Token"):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    try:
        data = json.loads(request.body)
        kind = str(data.get("RecordType") or data.get("Type") or "unknown")
        email = str(data.get("Recipient") or data.get("Email") or "").casefold()
        provider_id = str(data.get("ID") or data.get("MessageID") or hashlib.sha256(request.body).hexdigest())
        _, created = ProviderEvent.objects.get_or_create(provider_id=provider_id, defaults={"email": email, "kind": kind, "payload": data})
        if created and kind.casefold() in {"bounce", "spamcomplaint", "subscriptionchange"} and email:
            Suppression.objects.update_or_create(email=email, defaults={"reason": kind})
            Subscription.objects.filter(email__iexact=email).update(enabled=False, in_alert=False)
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid provider event"}, status=400)
    return JsonResponse({"accepted": True, "duplicate": not created})


def get_home_message(aqi):
    if aqi is None:
        return "Data unavailable. Check again after participating sensors report current measurements."
    if aqi <= 50:
        return "Air quality conditions are favorable for most people."
    if aqi <= 100:
        return "Most people can continue normal activities. Sensitive people may prefer a lower-reading room."
    return "Particle levels may affect health. Consider a lower-reading room and reduce strenuous activity."

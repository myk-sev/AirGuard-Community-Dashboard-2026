import csv
import json
from collections import defaultdict
from datetime import timedelta
from statistics import median

from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .aqi import aqi_category, nowcast, pm25_to_aqi
from .forms import SubscriptionForm
from .models import Building, Forecast, Sensor, Subscription
from .csv_cat import concatenate


STALE_AFTER = timedelta(minutes=60)
RANGE_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}

time_last_mailed = 0


def _sensor_snapshot(sensor, now=None):
    aqi = None
    now = now or timezone.now()
    readings = list(sensor.readings.order_by("-observed_at")[:12])
    latest = readings[0] if readings else None
    stale = not latest or now - latest.observed_at > STALE_AFTER

    if not stale:
        concentration = nowcast([reading.pm25 for reading in readings])
        aqi = pm25_to_aqi(concentration)

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
    placement_order = {"gym": 0, "hallway": 1, "entrance": 2}
    sensors = [_sensor_snapshot(sensor, now) for sensor in sorted(building.sensors.all(), key=lambda sensor: placement_order[sensor.placement])]
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
    snapshots = [_sensor_snapshot(sensor, now) for sensor in Sensor.objects.select_related("building")]
    valid = [sensor["aqi"] for sensor in snapshots if sensor["aqi"] is not None]
    total = len(snapshots)
    current_aqi = round(median(valid)) if len(valid) >= (total + 1) // 2 and valid else None
    current_category = aqi_category(current_aqi) if current_aqi is not None else {"label": "Unavailable", "css_class": "unavailable"}

    grouped = defaultdict(list)
    end = now + timedelta(hours=24)
    for forecast in Forecast.objects.filter(forecast_at__gte=now, forecast_at__lte=end):
        grouped[forecast.forecast_at].append(pm25_to_aqi(forecast.pm25))
    forecast_points = [(stamp, round(median(values))) for stamp, values in grouped.items() if values]
    peak_stamp, peak_aqi = max(forecast_points, key=lambda point: point[1]) if forecast_points else (None, None)
    peak_category = aqi_category(peak_aqi) if peak_aqi is not None else {"label": "Unavailable", "css_class": "unavailable"}
    # HACK: too long
    epoch_updated_at = max((sensor["observed_at"] for sensor in snapshots if sensor["observed_at"]), default=None).timestamp if max((sensor["observed_at"] for sensor in snapshots if sensor["observed_at"]), default=None) is not None else 0
    return {
        "aqi": current_aqi,
        "category": current_category["label"],
        "category_class": current_category["css_class"],
        "reporting": len(valid),
        "total": total,
        "updated_at": max((sensor["observed_at"] for sensor in snapshots if sensor["observed_at"]), default=None),
        "epoch_updated_at": epoch_updated_at,
        "forecast_aqi": peak_aqi,
        "forecast_category": peak_category["label"],
        "forecast_at": peak_stamp,
        "message": get_home_message(current_aqi),
    }


def home(request):
    return render(request, "dashboard/home.html", {"status": _network_status(), "buildings": [_building_summary(item) for item in Building.objects.prefetch_related("sensors")]})


def readings(request):
    return render(request, "dashboard/readings.html", {"buildings": [_building_summary(item) for item in Building.objects.prefetch_related("sensors")]})


def building(request, slug):
    item = get_object_or_404(Building.objects.prefetch_related("sensors"), slug=slug)
    summary = _building_summary(item)
    return render(request, "dashboard/building.html", {"building": summary})


def resources(request):
    return render(request, "dashboard/resources.html")


def _subscription_page(request, audience, template):
    saved = False
    if request.method == "POST":
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            Subscription.objects.update_or_create(
                email=data["email"], building=data["building"], audience=audience,
                defaults={"threshold": data["threshold"], "locale": data["locale"]},
            )
            saved = True
            form = SubscriptionForm(initial={"locale": data["locale"]})
    else:
        form = SubscriptionForm(initial={"locale": "en"})
    return render(request, template, {"form": form, "saved": saved, "audience": audience})


@require_http_methods(["GET", "POST"])
def notifications(request):
    return _subscription_page(request, "community", "dashboard/notifications.html")


@require_http_methods(["GET", "POST"])
def facility_notifications(request):
    response = _subscription_page(request, "facility", "dashboard/notifications.html")
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@require_GET
def status_api(request):
    status = _network_status()
    return JsonResponse({key: value.isoformat() if hasattr(value, "isoformat") else value for key, value in status.items()})


@require_GET
def buildings_api(request):
    return JsonResponse({"buildings": [_building_summary(item) for item in Building.objects.prefetch_related("sensors")]})


@require_GET
def building_api(request, slug):
    return JsonResponse(_building_summary(get_object_or_404(Building.objects.prefetch_related("sensors"), slug=slug)))


def _history(sensor_id, range_name):
    if range_name not in RANGE_HOURS:
        raise Http404("Unknown time range")
    sensor = get_object_or_404(Sensor, id=sensor_id)
    start = timezone.now() - timedelta(hours=RANGE_HOURS[range_name])
    readings = list(sensor.readings.filter(observed_at__gte=start).order_by("observed_at"))
    if range_name == "30d":
        readings = readings[::6]
    return sensor, readings


@require_GET
def readings_api(request, sensor_id):
    sensor, readings = _history(sensor_id, request.GET.get("range", "24h"))
    return JsonResponse({
        "sensor": {"id": sensor.id, "name": sensor.name, "building": sensor.building.name},
        "readings": [{"timestamp": item.observed_at.isoformat(), "pm25": round(item.pm25, 1), "aqi": pm25_to_aqi(item.pm25), "category": aqi_category(pm25_to_aqi(item.pm25))["label"], "data_status": "current"} for item in readings],
    })


@require_GET
def readings_csv(request, sensor_id):
    sensor, readings = _history(sensor_id, request.GET.get("range", "24h"))
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="airguard-{sensor.external_id}-readings.csv"'
    writer = csv.writer(response)
    writer.writerow(("timestamp", "pm25_ug_m3", "aqi", "category", "data_status"))
    for item in readings:
        aqi = pm25_to_aqi(item.pm25)
        writer.writerow((item.observed_at.isoformat(), f"{item.pm25:.1f}", aqi, aqi_category(aqi)["label"], "current"))
    return response


@require_GET
def forecast_api(request, sensor_id):
    sensor = get_object_or_404(Sensor, id=sensor_id)
    forecasts = sensor.forecasts.filter(forecast_at__gte=timezone.now()).order_by("forecast_at")[:24]
    return JsonResponse({
        "sensor": {"id": sensor.id, "name": sensor.name, "building": sensor.building.name},
        "forecasts": [{"timestamp": item.forecast_at.isoformat(), "pm25": round(item.pm25, 1), "aqi": pm25_to_aqi(item.pm25), "category": aqi_category(pm25_to_aqi(item.pm25))["label"], "temperature": round(item.temperature, 1), "relative_humidity": round(item.relative_humidity), "wind_speed": round(item.wind_speed, 1), "wind_direction": item.wind_direction} for item in forecasts],
    })


@require_POST
def subscription_api(request):
    try:
        data = json.loads(request.body or "{}")
        building = Building.objects.get(id=data["building"])
        threshold = int(data["threshold"])
        if threshold not in dict(Subscription.THRESHOLDS):
            raise ValueError
        subscription, _ = Subscription.objects.update_or_create(
            email=data["email"], building=building, audience=data.get("audience", "community"),
            defaults={"threshold": threshold, "locale": data.get("locale", "en")},
        )
    except (Building.DoesNotExist, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid subscription"}, status=400)
    return JsonResponse({"id": subscription.id, "saved": True})

@require_POST
def measurements(request, sensor_name):
    if sensor_name == "govee":
        govee_upload(request)
    elif sensor_name == "custom":
        custom_upload(request)

def govee_upload(request):
    form = UploadFileForm(request.POST, request.FILES)

    if form.is_valid():
        data = csv.DictReader(request.FILES["file"])

        sensor = Sensor.objects.get_or_create(
            # NOTE: Building should already be in the system
            building=Building.objects.get(slug = data.get("building")).id,
            name=data.get("location").title(),
            placement=data.get("location"),
            external_id=f"{data.get("building")}-{placement}", # might be unnecessary?
        )

        observed_at = data.get("time")
        pm25 = data.get("PM2.5(µg/m³)")
        reading = Reading.objects.create(sensor=sensor, observed_at=observed_at, pm25=pm25)

        if (timezone.now() - time_last_mailed > STALE_AFTER + 60):
            # import model

            model = torch.load(PATH, weight_only=False)
            model.eval()

            # export model data to dict forecast

            if (forecast):
                for i in range (timezone.now(), timezone.now() + 360000, 600):
                    Forecast.objects.update_or_create(
                        sensor=data.sensor,
                        forecast_at=data.forecast_at,
                        pm25=data.pm25,
                        temperature=data.temperature,
                        relative_humidity=data.relative_humidity,
                        wind_speed=data.wind_speed,
                        wind_direction=data.wind_direction,
                    )

            send_emails()
            time_last_mailed = timezone.now()

def custom_upload(request):
    data = json.loads(request.body)

    if data is not None:
        sensor = Sensor.objects.get_or_create(
            # NOTE: Building should already be in the system
            building=Building.objects.get(slug = data.get("building")).id,
            name=data.get("location").title(),
            placement=data.get("location"),
            external_id=f"{data.get("building")}-{placement}",
        )

        observed_at = data.get("time")
        pm25 = data.get("PM2.5(µg/m³)")
        reading = Reading.objects.create(sensor=sensor, observed_at=observed_at, pm25=pm25)

# TODO: Server admins: Set up email authentication
def send_emails():
    for i in Subscription.objects.all():
        if (_building_summary(Building.objects.get(id = i.building_id)).get("aqi") > i.threshold):
            message = format("\n========== PM2.5 HEALTH SUMMARY ==========\nHealth Category: {}\nWhat to do: {}\n==========================================",
                             classify_pm25(_building_summary(Building.objects.get(id = i.building_id)).get("aqi") )) # TODO: check for whether this should be aqi or pm_25

            send_mail(
                "AirGuard Air Quality Alert",
                message,
                "no-reply@airguard.nd.edu", # example sender email
                i.email,
                fail_silently=False,
            )

        # TODO: check for forecasted warning, too
        if Forecast.object.get_latetst_by(Building.objects.get(id = i.building)).get("pm25") > i.threshold):
            message = format("\n========== PM2.5 FORECAST SUMMARY ==========\nHealth Category: {}\nWhat to do: {}\n==========================================",
                             classify_pm25(_building_summary(Building.objects.get(id = i.building_id)).get("aqi") )) # TODO: check for whether this should be aqi or pm_25

            send_mail(
                "AirGuard Air Quality Alert",
                message,
                "no-reply@airguard.nd.edu", # example sender email
                i.email,
                fail_silently=False,
            )

def get_home_message(aqi):
    if aqi is None:
        return "Data Unavailable"

    match (int((aqi - 1)/50)):
        case 0:
            return "Air quality conditions are generally suitable for most individuals. Sensitive groups may benefit from limiting prolonged exposure to outdoor air."
        case 1:
            return "Air quality conditions are favorable for most individuals. People can safely continue normal activities with minimal concern."
        case _:
            return "Air quality conditions may pose health concerns for the general population. Consider reducing prolonged outdoor activities and taking precautions when spending time outside."

def classify_aqi(pm25):

    if pm25 <= 9:
        return (
            "Good (0-9 µg/m³)",
            "PM2.5 levels within this range are generally considered safe for the general population. However, sensitive groups may still experience minor health effects with prolonged exposure."
        )

    elif pm25 <= 35.4:
        return (
            "Moderate (9-35.4 µg/m³)",
            "At these levels, individuals with respiratory or heart conditions, children, and older adults may experience increased respiratory symptoms. It is advised for these groups to limit prolonged outdoor exertion."
        )

    elif pm25 <= 55.4:
        return (
            "Unhealthy (35.4-55.4 µg/m³)",
            "When PM2.5 levels reach this range, even healthy individuals may experience adverse health effects, including aggravated respiratory conditions and reduced lung function. It is recommended to minimize outdoor activities, especially during strenuous exercise."
        )

    elif pm25 <=1000 :
        return (
            "Very Unhealthy",
            "PM2.5 levels in this range pose a significant risk to everyone, leading to serious health effects. It is crucial to stay indoors and use air purifiers if available."
        )

    else:
        return (
            "Hazardous (>250 µg/m³)",
            "Levels exceeding this threshold are extremely dangerous and can cause immediate and severe health effects, including respiratory distress and cardiovascular issues."
        )

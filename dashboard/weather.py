import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.utils import timezone


VARIABLES = "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
DIRECTIONS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")


def cardinal_direction(degrees):
    return DIRECTIONS[round(float(degrees) / 22.5) % 16]


def fetch_weather(url, latitude, longitude, timeout):
    query = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "hourly": VARIABLES,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "UTC",
        "forecast_hours": 48,
    })
    with urlopen(f"{url}?{query}", timeout=timeout) as response:
        payload = json.loads(response.read())

    hourly = payload["hourly"]
    keys = ("time", "temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_direction_10m")
    if not hourly["time"] or len({len(hourly[key]) for key in keys}) != 1:
        raise ValueError("Weather response has incomplete hourly data")

    return {
        datetime.fromisoformat(stamp).replace(tzinfo=UTC): {
            "temperature": float(temperature),
            "relative_humidity": float(humidity),
            "wind_speed": float(speed),
            "wind_direction": cardinal_direction(direction),
        }
        for stamp, temperature, humidity, speed, direction in zip(*(hourly[key] for key in keys))
    }


def update_forecast_weather():
    from .models import Forecast

    hourly = fetch_weather(
        settings.AIRGUARD_WEATHER_URL,
        settings.AIRGUARD_WEATHER_LATITUDE,
        settings.AIRGUARD_WEATHER_LONGITUDE,
        settings.AIRGUARD_WEATHER_TIMEOUT_SECONDS,
    )
    retrieved_at = timezone.now()
    forecasts = []
    for forecast in Forecast.objects.filter(forecast_at__gte=retrieved_at):
        hour = forecast.forecast_at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        if weather := hourly.get(hour):
            for field, value in weather.items():
                setattr(forecast, field, value)
            forecast.weather_source = "open-meteo"
            forecast.weather_generated_at = retrieved_at
            forecasts.append(forecast)
    Forecast.objects.bulk_update(forecasts, (
        "temperature", "relative_humidity", "wind_speed", "wind_direction",
        "weather_source", "weather_generated_at",
    ))
    return len(forecasts)


def refresh_forecast_weather_if_stale():
    from .models import Forecast

    now = timezone.now()
    if Forecast.objects.filter(
        forecast_at__gte=now,
        weather_source="open-meteo",
        weather_generated_at__gte=now - timedelta(hours=1),
    ).exists():
        return 0
    return update_forecast_weather()

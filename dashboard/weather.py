import json
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.request import urlopen


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

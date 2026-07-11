from math import floor


BREAKPOINTS = (
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 325.4, 301, 500),
)

CATEGORIES = (
    (50, "Good", "good"),
    (100, "Moderate", "moderate"),
    (150, "Unhealthy for sensitive groups", "sensitive"),
    (200, "Unhealthy", "unhealthy"),
    (300, "Very unhealthy", "very-unhealthy"),
    (500, "Hazardous", "hazardous"),
)


def pm25_to_aqi(pm25):
    concentration = floor(max(0, pm25) * 10) / 10
    for low_c, high_c, low_i, high_i in BREAKPOINTS:
        if concentration <= high_c:
            return round((high_i - low_i) / (high_c - low_c) * (concentration - low_c) + low_i)
    return 500


def aqi_category(aqi):
    for ceiling, label, css_class in CATEGORIES:
        if aqi <= ceiling:
            return {"label": label, "css_class": css_class}
    return {"label": "Hazardous", "css_class": "hazardous"}


def nowcast(concentrations):
    values = [max(0, value) for value in concentrations[:12]]
    if len(values) < 2 or len(values[:3]) < 2:
        return None
    highest = max(values)
    weight = max(0.5, min(values) / highest) if highest else 1
    weighted = sum(value * weight**index for index, value in enumerate(values))
    divisor = sum(weight**index for index in range(len(values)))
    return weighted / divisor

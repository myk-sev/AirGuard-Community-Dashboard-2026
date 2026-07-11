from django.db import models


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
    PLACEMENTS = (("gym", "Gym"), ("hallway", "Hallway"), ("entrance", "Entrance"))

    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="sensors")
    name = models.CharField(max_length=80)
    placement = models.CharField(max_length=16, choices=PLACEMENTS)
    external_id = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ("building", "placement")

    def __str__(self):
        return f"{self.building}: {self.name}"


class Reading(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name="readings")
    observed_at = models.DateTimeField()
    pm25 = models.FloatField()

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

    class Meta:
        ordering = ("forecast_at",)
        constraints = [models.UniqueConstraint(fields=("sensor", "forecast_at"), name="unique_sensor_forecast")]


class Subscription(models.Model):
    AUDIENCES = (("community", "Community"), ("facility", "Facility manager"))
    THRESHOLDS = ((51, "Moderate or above"), (101, "Unhealthy for sensitive groups or above"), (151, "Unhealthy or above"))
    LOCALES = (("en", "English"), ("es", "Spanish"))

    email = models.EmailField()
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="subscriptions")
    threshold = models.PositiveSmallIntegerField(choices=THRESHOLDS)
    locale = models.CharField(max_length=2, choices=LOCALES, default="en")
    audience = models.CharField(max_length=16, choices=AUDIENCES, default="community")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("email", "building", "audience"), name="unique_subscription")]

    def __str__(self):
        return f"{self.email}: {self.building}"

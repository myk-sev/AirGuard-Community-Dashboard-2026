import pandas as pd

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import Building, Forecast, Reading, Sensor


BUILDINGS = (
    ("Robinson Center", "robinson-center", "school"),
    ("Boys and Girls Club Main Building", "bgc-main", "school"),
    ("Boys and Girls Club Satellite Building", "bgc-satellite", "school"),
)
PLACEMENTS = (("gym", "Gym"), ("hallway", "Hallway"), ("entrance", "Entrance"))


class Command(BaseCommand):
    help = "Create deterministic AirGuard development data"

    def handle(self, *args, **options):
        Reading.objects.all().delete()
        Forecast.objects.all().delete()
        Sensor.objects.all().delete()
        Building.objects.all().delete()

        now = timezone.now().replace(second=0, microsecond=0)
        sensors = []
        # TODO: store this outside of code
        for building_index, (name, slug, icon) in enumerate(BUILDINGS):
            building = Building.objects.create(name=name, slug=slug, icon=icon, display_order=building_index)
            for placement_index, (placement, label) in enumerate(PLACEMENTS):
                sensor = Sensor.objects.create(
                    building=building,
                    name=label,
                    placement=placement,
                    external_id=f"{slug}-{placement}",
                )
                sensors.append((sensor, building_index, placement_index))

        # TODO: read csv to database

        readings = []

        # HACK: this could be done a little cleaner. try figuring out how to make the pandas and django file systems work together
        df = pd.read_csv(default_storage.path("historical_measurements.csv"), index_col=False, header=0) # use defualt_storage path with pandas opening
        for
        # read dataframe data to individual objects
        # bulk create objects in sqlite
        # readings = []
        # for sensor, building_index, placement_index in sensors:
        #     stale = building_index == 2 and placement_index == 2
        #     for hour in range(24 * 30, -1, -1):
        #         if stale and hour < 3:
        #             continue
        #         observed_at = now - timedelta(hours=hour)
        #         daily = math.sin((observed_at.hour - 7) / 24 * math.tau) * 3.5
        #         event = 24 if 14 <= observed_at.hour <= 17 and hour < 48 else 0
        #         base = 5 + building_index * 2.5 + placement_index * 1.8
        #         pm25 = max(1, base + daily + event + rng.uniform(-1.5, 1.5))
        #         readings.append(Reading(sensor=sensor, observed_at=observed_at, pm25=pm25))
        # Reading.objects.bulk_create(readings, batch_size=2000)

        # TODO: generate forecast

        # directions = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        # forecasts = []
        # for sensor, building_index, placement_index in sensors:
        #     for hour in range(1, 25):
        #         forecast_at = now + timedelta(hours=hour)
        #         afternoon_peak = 30 * math.exp(-((hour - 5) ** 2) / 14)
        #         pm25 = 7 + building_index * 2 + placement_index + afternoon_peak + rng.uniform(-1, 1)
        #         forecasts.append(Forecast(
        #             sensor=sensor,
        #             forecast_at=forecast_at,
        #             pm25=max(1, pm25),
        #             temperature=68 + 8 * math.sin((forecast_at.hour - 8) / 24 * math.tau),
        #             relative_humidity=58 - 12 * math.sin((forecast_at.hour - 8) / 24 * math.tau),
        #             wind_speed=5 + rng.uniform(0, 5),
        #             wind_direction=directions[(hour // 3 + building_index) % len(directions)],
        #         ))
        # Forecast.objects.bulk_create(forecasts, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f"Created {len(sensors)} sensors, {len(readings)} readings, and {len(forecasts)} forecasts"))

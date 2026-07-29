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
            # FIXME: doesn't work with get_or_create(), could result in problems with adding new buildings
            building = Building.objects.create(
                name=name,
                slug=slug,
                icon=icon,
                display_order=building_index
            )

            for placement_index, (placement, label) in enumerate(PLACEMENTS):
                sensor = Sensor.objects.get_or_create(
                    building=building,
                    name=label,
                    placement=placement,
                    external_id=f"{slug}-{placement}",
                )
                sensors.append(sensor)


        self.stdout.write(self.style.SUCCESS(f"Database has {len(sensors)} sensors"))

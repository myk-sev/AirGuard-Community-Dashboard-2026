from django.core.management.base import BaseCommand

from dashboard.models import Building, Sensor
from dashboard.sensor_manifest import BUILDINGS, SENSORS


class Command(BaseCommand):
    help = "Create or update the production buildings and sensors"

    def handle(self, *args, **options):
        for building_index, (name, slug, icon) in enumerate(BUILDINGS):
            Building.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "icon": icon, "display_order": building_index},
            )
        buildings = {building.slug: building for building in Building.objects.filter(slug__in=[item[1] for item in BUILDINGS])}
        for display_order, (external_id, building_slug, name, placement) in enumerate(SENSORS):
            Sensor.objects.update_or_create(
                external_id=external_id,
                defaults={
                    "building": buildings[building_slug],
                    "name": name,
                    "placement": placement,
                    "source": "govee",
                    "enabled": True,
                    "display_order": display_order,
                },
            )
        Sensor.objects.exclude(external_id__in=[item[0] for item in SENSORS]).update(enabled=False)
        self.stdout.write(self.style.SUCCESS(f"Database has {len(SENSORS)} configured sensors"))

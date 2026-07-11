import json

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .aqi import nowcast, pm25_to_aqi
from .models import Building, Subscription


class AqiTests(TestCase):
    def test_revised_pm25_breakpoints(self):
        self.assertEqual(pm25_to_aqi(9.0), 50)
        self.assertEqual(pm25_to_aqi(9.1), 51)
        self.assertEqual(pm25_to_aqi(35.4), 100)
        self.assertEqual(pm25_to_aqi(35.5), 101)

    def test_nowcast_keeps_constant_concentration(self):
        self.assertAlmostEqual(nowcast([10] * 12), 10)


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_public_pages_render(self):
        for name in ("home", "readings", "resources", "notifications"):
            self.assertEqual(self.client.get(reverse(f"dashboard:{name}")).status_code, 200)

    def test_current_readings_omits_updated_timestamp(self):
        response = self.client.get(reverse("dashboard:readings"))
        self.assertNotContains(response, "Updated")
        self.assertContains(response, "Click any building card")

    def test_home_has_status_and_aqi_explanation(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "Updated")
        self.assertContains(response, "What does AQI mean?")

    def test_building_page_has_three_sensor_controls(self):
        building = Building.objects.first()
        response = self.client.get(reverse("dashboard:building", args=(building.slug,)))
        self.assertEqual(response.context["building"]["reporting"], 3)
        self.assertContains(response, "data-sensor-id", count=3)

    def test_readings_api_and_csv(self):
        sensor = Building.objects.first().sensors.first()
        api = self.client.get(reverse("dashboard:readings_api", args=(sensor.id,)), {"range": "24h"})
        self.assertEqual(api.status_code, 200)
        self.assertGreater(len(api.json()["readings"]), 20)
        csv_response = self.client.get(reverse("dashboard:readings_csv", args=(sensor.id,)), {"range": "24h"})
        self.assertEqual(csv_response.status_code, 200)
        self.assertTrue(csv_response["Content-Disposition"].endswith('readings.csv"'))
        self.assertIn(b"pm25_ug_m3", csv_response.content)

    def test_forecast_api_contains_weather(self):
        sensor = Building.objects.first().sensors.first()
        response = self.client.get(reverse("dashboard:forecast_api", args=(sensor.id,)))
        first = response.json()["forecasts"][0]
        self.assertIn("temperature", first)
        self.assertIn("relative_humidity", first)
        self.assertIn("wind_speed", first)
        self.assertIn("wind_direction", first)

    def test_subscription_api_creates_and_updates(self):
        building = Building.objects.first()
        payload = {"email": "resident@example.org", "building": building.id, "threshold": 101, "locale": "es"}
        url = reverse("dashboard:subscription_api")
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type="application/json").status_code, 200)
        payload["threshold"] = 151
        self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(Subscription.objects.get().threshold, 151)

    def test_facility_form_is_unlisted_for_search_engines(self):
        response = self.client.get(reverse("dashboard:facility_notifications"))
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

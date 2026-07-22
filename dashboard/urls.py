from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("readings/", views.readings, name="readings"),
    path("buildings/<slug:slug>/", views.building, name="building"),
    path("resources/", views.resources, name="resources"),
    path("notifications/", views.notifications, name="notifications"),
    path("facility-notifications/", views.facility_notifications, name="facility_notifications"),
    path("api/v1/status/", views.status_api, name="status_api"),
    path("api/v1/buildings/", views.buildings_api, name="buildings_api"),
    path("api/v1/buildings/<slug:slug>/", views.building_api, name="building_api"),
    path("api/v1/sensors/<int:sensor_id>/readings/", views.readings_api, name="readings_api"),
    path("api/v1/sensors/<int:sensor_id>/readings.csv", views.readings_csv, name="readings_csv"),
    path("api/v1/sensors/<int:sensor_id>/forecast/", views.forecast_api, name="forecast_api"),
    path("api/v1/subscriptions/", views.subscription_api, name="subscription_api"),
    path("api/v1/measurements/<slug:building>/<slug:location>", views.measurements, name="measurements"),
]

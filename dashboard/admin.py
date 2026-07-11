from django.contrib import admin

from .models import Building, Forecast, Reading, Sensor, Subscription


admin.site.register((Building, Sensor, Reading, Forecast, Subscription))

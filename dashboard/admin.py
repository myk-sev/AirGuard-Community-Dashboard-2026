from django.contrib import admin

from .models import (
    AlertEvent,
    Building,
    Forecast,
    InboundMessage,
    IngestBatch,
    OutboundEmail,
    ProviderEvent,
    Reading,
    Sensor,
    Subscription,
    Suppression,
)


admin.site.register((Building, Sensor, Reading, Forecast, Subscription, InboundMessage, IngestBatch, AlertEvent, OutboundEmail, Suppression, ProviderEvent))

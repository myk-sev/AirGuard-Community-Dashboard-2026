from django import forms

from .models import Building, Subscription


class SubscriptionForm(forms.ModelForm):
    ALERT_RULES = (
        ("aqi_51", "Forecast AQI: Moderate or above"),
        ("aqi_101", "Forecast AQI: Unhealthy for sensitive groups or above"),
        ("aqi_151", "Forecast AQI: Unhealthy or above"),
        ("who_pm25_24h", "WHO 24-hour PM2.5 guideline (15 µg/m³)"),
        ("epa_pm25_24h", "EPA 24-hour PM2.5 standard (35 µg/m³)"),
    )
    alert_rule = forms.ChoiceField(choices=ALERT_RULES, widget=forms.Select(attrs={"class": "form-select"}))
    consent = forms.BooleanField()

    class Meta:
        model = Subscription
        fields = ("email", "building", "locale")
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "name@example.org", "class": "form-control"}),
            "building": forms.Select(attrs={"class": "form-select"}),
            "locale": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["building"].queryset = Building.objects.filter(sensors__enabled=True).distinct()

    def clean(self):
        cleaned = super().clean()
        rule = cleaned.get("alert_rule", "")
        if rule.startswith("aqi_"):
            cleaned["threshold_kind"], cleaned["threshold"] = "aqi", float(rule.removeprefix("aqi_"))
        elif rule == "who_pm25_24h":
            cleaned["threshold_kind"], cleaned["threshold"] = rule, 15.0
        elif rule == "epa_pm25_24h":
            cleaned["threshold_kind"], cleaned["threshold"] = rule, 35.0
        return cleaned

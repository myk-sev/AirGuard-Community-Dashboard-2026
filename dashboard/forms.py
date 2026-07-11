from django import forms

from .models import Subscription


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ("email", "building", "threshold", "locale")
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "name@example.org", "class": "form-control"}),
            "building": forms.Select(attrs={"class": "form-select"}),
            "threshold": forms.Select(attrs={"class": "form-select"}),
            "locale": forms.HiddenInput(),
        }

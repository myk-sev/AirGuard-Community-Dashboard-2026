import hashlib
import secrets

from django.conf import settings
from django.core import signing
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import OutboundEmail, Subscription


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _absolute_url(request, path):
    return request.build_absolute_uri(path) if request else settings.AIRGUARD_SITE_URL.rstrip("/") + path


def _url(request, name, token):
    return _absolute_url(request, reverse(name, args=(token,)))


def _html(context):
    return render_to_string("dashboard/email.html", context)


def unsubscribe_token(subscription):
    return signing.dumps(subscription.id, salt="airguard-unsubscribe")


def queue_verification(subscription, request=None):
    verification_token = signing.dumps(
        {"subscription": subscription.id, "nonce": secrets.token_urlsafe(16)},
        salt="airguard-verification",
    )
    unsubscribe = unsubscribe_token(subscription)
    subscription.verification_token_hash = token_hash(verification_token)
    subscription.unsubscribe_token_hash = token_hash(unsubscribe)
    subscription.save(update_fields=("verification_token_hash", "unsubscribe_token_hash", "updated_at"))
    verify_url = _url(request, "dashboard:verify_subscription", verification_token)
    unsubscribe_url = _url(request, "dashboard:unsubscribe", unsubscribe)
    spanish = subscription.locale == "es"
    subject = "Confirme sus alertas de AirGuard" if spanish else "Confirm your AirGuard alerts"
    body = (
        f"Confirme su dirección para activar las alertas de {subscription.building.name}:\n\n{verify_url}\n\n"
        f"Si no solicitó estas alertas, puede cancelar aquí:\n{unsubscribe_url}\n\n"
        "— AirGuard\nAire comunitario más accesible"
        if spanish else
        f"Confirm your address to activate alerts for {subscription.building.name}:\n\n{verify_url}\n\n"
        f"If you did not request these alerts, unsubscribe here:\n{unsubscribe_url}\n\n"
        "— AirGuard\nCommunity Air Made Accessible"
    )
    subscription.outbound_emails.filter(kind="verification", status__in=("pending", "failed")).update(status="suppressed")
    return OutboundEmail.objects.create(
        event_key=f"verification:{subscription.id}:{subscription.verification_token_hash}",
        kind="verification",
        subscription=subscription,
        to_email=subscription.email,
        subject=subject,
        text_body=body,
        html_body=_html({
            "locale": subscription.locale,
            "preheader": f"{'Confirme' if spanish else 'Confirm'} AirGuard alerts for {subscription.building.name}",
            "eyebrow": "Confirmación de correo" if spanish else "Email confirmation",
            "heading": subject,
            "intro": (
                f"Confirme su dirección para activar las alertas de pronóstico de {subscription.building.name}."
                if spanish else
                f"Confirm your address to activate forecast alerts for {subscription.building.name}."
            ),
            "details": [
                ("Edificio" if spanish else "Building", subscription.building.name),
                ("Tipo" if spanish else "Notification", "Alerta de pronóstico" if spanish else "Forecast threshold alert"),
            ],
            "cta_label": "Confirmar alertas" if spanish else "Confirm alerts",
            "cta_url": verify_url,
            "secondary_label": "Cancelar esta solicitud" if spanish else "Cancel this request",
            "secondary_url": unsubscribe_url,
            "notice": (
                "Si no solicitó estas alertas, no confirme esta dirección."
                if spanish else
                "If you did not request these alerts, do not confirm this address."
            ),
        }),
    )


def queue_alert(event, request=None):
    subscription = event.subscription
    unsubscribe_url = _url(request, "dashboard:unsubscribe", unsubscribe_token(subscription))
    spanish = subscription.locale == "es"
    predicted_at = timezone.localtime(event.predicted_at)
    local_time = predicted_at.strftime("%d/%m/%Y a las %I:%M %p" if spanish else "%b %d at %I:%M %p")
    if subscription.threshold_kind == "aqi":
        value = f"AQI {event.predicted_value:.0f}"
        benchmark = f"su nivel de alerta de AQI {event.threshold:.0f}" if spanish else f"your AQI alert level of {event.threshold:.0f}"
    else:
        value = f"{event.predicted_value:.1f} µg/m³"
        benchmark_name = "la guía de 24 horas de la OMS" if subscription.threshold_kind.startswith("who") else "el estándar de 24 horas de la EPA"
        benchmark = benchmark_name if spanish else ("the WHO 24-hour guideline" if subscription.threshold_kind.startswith("who") else "the EPA 24-hour standard")
    subject = f"Alerta de aire prevista para {subscription.building.name}" if spanish else f"Forecast air alert for {subscription.building.name}"
    readings_url = _absolute_url(request, reverse("dashboard:building", args=(subscription.building.slug,)))
    body = (
        f"El pronóstico de AirGuard indica que {benchmark} puede superarse cerca de {local_time}. Valor previsto: {value}.\n\n"
        "Esta comparación de sensores interiores de bajo costo es una guía de salud, no una determinación regulatoria.\n\n"
        f"Ver lecturas: {readings_url}\n\nCancelar alertas: {unsubscribe_url}\n\n"
        "— AirGuard\nAire comunitario más accesible"
        if spanish else
        f"AirGuard forecasts that {benchmark} may be exceeded near {local_time}. Projected value: {value}.\n\n"
        "This indoor low-cost sensor comparison is health guidance, not a regulatory determination.\n\n"
        f"View readings: {readings_url}\n\nUnsubscribe: {unsubscribe_url}\n\n"
        "— AirGuard\nCommunity Air Made Accessible"
    )
    return OutboundEmail.objects.get_or_create(
        event_key=event.event_key,
        defaults={
            "kind": "alert",
            "subscription": subscription,
            "alert_event": event,
            "to_email": subscription.email,
            "subject": subject,
            "text_body": body,
            "html_body": _html({
                "locale": subscription.locale,
                "preheader": f"{subscription.building.name}: {value}",
                "eyebrow": "Notificación de pronóstico" if spanish else "Forecast notification",
                "heading": "Puede superarse su umbral de calidad del aire" if spanish else "Your air quality threshold may be exceeded",
                "intro": (
                    f"El pronóstico de AirGuard indica que {benchmark} puede superarse cerca de {local_time}."
                    if spanish else
                    f"AirGuard forecasts that {benchmark} may be exceeded near {local_time}."
                ),
                "details": [
                    ("Edificio" if spanish else "Building", subscription.building.name),
                    ("Hora prevista" if spanish else "Forecast time", local_time),
                    ("Valor previsto" if spanish else "Projected value", value),
                ],
                "cta_label": "Ver lecturas actuales" if spanish else "View current readings",
                "cta_url": readings_url,
                "secondary_label": "Cancelar alertas" if spanish else "Unsubscribe",
                "secondary_url": unsubscribe_url,
                "notice": (
                    "Esta comparación de sensores interiores de bajo costo es una guía de salud, no una determinación regulatoria."
                    if spanish else
                    "This indoor low-cost sensor comparison is health guidance, not a regulatory determination."
                ),
            }),
        },
    )[0]

"""Queue templated notification emails (Step 40)."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from apps.accounts.models import Role
from apps.accounts.notification_preferences import is_notification_enabled

logger = logging.getLogger(__name__)


def frontend_base_url() -> str:
    return getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")


def resolve_user_language(user) -> str:
    role = getattr(user, "role", None)
    if role == Role.PATIENT:
        profile = getattr(user, "patient_profile", None)
        if profile is not None and profile.preferred_language:
            return profile.preferred_language
    return "English"


def queue_notification_email(
    *,
    user,
    event_key: str,
    template_key: str,
    context: dict[str, Any],
    language: str | None = None,
) -> bool:
    """Enqueue a templated email if the user opted in for this event."""
    if not getattr(settings, "NOTIFICATION_EMAIL_ENABLED", True):
        return False
    if not is_notification_enabled(user, channel="email", event_key=event_key):
        return False
    from .tasks import send_notification_email

    send_notification_email.delay(
        user_id=user.pk,
        event_key=event_key,
        template_key=template_key,
        context=context,
        language=language or resolve_user_language(user),
    )
    return True


def notify_care_request_received_email(request) -> bool:
    caregiver_user = request.caregiver.user
    expires = request.expires_at.strftime("%Y-%m-%d %H:%M UTC") if request.expires_at else "soon"
    patient_label = (
        getattr(request.patient, "patient_profile", None)
        and request.patient.patient_profile.display_name
    ) or request.patient.email
    return queue_notification_email(
        user=caregiver_user,
        event_key="care_request_received",
        template_key="care_request_received",
        context={
            "caregiver_name": request.caregiver.display_name,
            "patient_label": patient_label,
            "message": request.message or "(no message)",
            "request_id": request.pk,
            "expires_at": expires,
        },
        language=resolve_user_language(caregiver_user),
    )


def notify_care_request_accepted_email(request, *, relationship) -> bool:
    checkout_url = f"{frontend_base_url()}/requests/{request.pk}/checkout"
    patient_name = (
        getattr(request.patient, "patient_profile", None)
        and request.patient.patient_profile.display_name
    ) or request.patient.email.split("@")[0]
    return queue_notification_email(
        user=request.patient,
        event_key="care_request_accepted",
        template_key="care_request_accepted",
        context={
            "patient_name": patient_name,
            "caregiver_name": request.caregiver.display_name,
            "checkout_url": checkout_url,
        },
    )


def notify_payment_due_email(request, *, amount_lkr: str = "see checkout") -> bool:
    checkout_url = f"{frontend_base_url()}/requests/{request.pk}/checkout"
    patient_name = (
        getattr(request.patient, "patient_profile", None)
        and request.patient.patient_profile.display_name
    ) or request.patient.email.split("@")[0]
    return queue_notification_email(
        user=request.patient,
        event_key="payment_due",
        template_key="payment_due",
        context={
            "patient_name": patient_name,
            "caregiver_name": request.caregiver.display_name,
            "amount_lkr": amount_lkr,
            "checkout_url": checkout_url,
        },
    )


def notify_anomaly_alert_email(
    *,
    user,
    alert_title: str,
    detail: str,
) -> bool:
    user_name = user.first_name or user.email.split("@")[0]
    return queue_notification_email(
        user=user,
        event_key="security_payment_alert",
        template_key="anomaly_alert",
        context={
            "user_name": user_name,
            "alert_title": alert_title,
            "detail": detail,
        },
    )

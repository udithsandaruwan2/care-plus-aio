"""Queue Web Push notifications respecting preference toggles (Step 41)."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from apps.accounts.notification_preferences import is_notification_enabled
from apps.accounts.webpush import vapid_configured

logger = logging.getLogger(__name__)


def frontend_base_url() -> str:
    return getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")


def queue_web_push(
    *,
    user,
    event_key: str,
    title: str,
    body: str,
    url: str = "/",
) -> bool:
    """Enqueue browser push if VAPID is configured and the user opted in."""
    if not getattr(settings, "WEB_PUSH_ENABLED", True):
        return False
    if not vapid_configured():
        return False
    if not is_notification_enabled(user, channel="push", event_key=event_key):
        return False
    if not user.push_subscriptions.exists():
        return False

    from .tasks import send_web_push_notification

    send_web_push_notification.delay(
        user_id=user.pk,
        event_key=event_key,
        title=title,
        body=body,
        url=url,
    )
    return True


def notify_care_request_received_push(request) -> bool:
    caregiver_user = request.caregiver.user
    patient_label = (
        getattr(request.patient, "patient_profile", None)
        and request.patient.patient_profile.display_name
    ) or request.patient.email
    return queue_web_push(
        user=caregiver_user,
        event_key="care_request_received",
        title="New care request",
        body=f"{patient_label} sent you a care request.",
        url=f"{frontend_base_url()}/requests",
    )


def notify_care_request_accepted_push(request) -> bool:
    return queue_web_push(
        user=request.patient,
        event_key="care_request_accepted",
        title="Care request accepted",
        body=f"{request.caregiver.display_name} accepted your request. Complete checkout to start care.",
        url=f"{frontend_base_url()}/requests/{request.pk}/checkout",
    )

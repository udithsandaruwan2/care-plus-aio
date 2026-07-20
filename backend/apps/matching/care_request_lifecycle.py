"""Care-request expiry + mid-TTL reminder notifications (Step 28)."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import CareRequest, CareRequestStatus
from .push import push_care_request_update

logger = logging.getLogger(__name__)


def care_request_ttl_hours() -> int:
    return max(1, int(getattr(settings, "CARE_REQUEST_TTL_HOURS", 72)))


def reminder_offset() -> timedelta:
    """Send reminder at halfway through the TTL (N/2)."""
    hours = care_request_ttl_hours() / 2.0
    return timedelta(hours=max(0.5, hours))


def _from_email() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@careplus.local")


def _email_enabled() -> bool:
    return bool(getattr(settings, "CARE_REQUEST_NOTIFY_EMAIL_ENABLED", True))


def _payload(request: CareRequest, *, event: str) -> dict:
    return {
        "event": event,
        "id": request.pk,
        "status": request.status,
        "patient_id": request.patient_id,
        "caregiver_id": request.caregiver_id,
        "caregiver_name": request.caregiver.display_name,
        "patient_email": request.patient.email,
        "message": request.message,
        "expires_at": request.expires_at.isoformat() if request.expires_at else None,
        "responded_at": request.responded_at.isoformat() if request.responded_at else None,
    }


def notify_care_request_reminder(request: CareRequest) -> None:
    """Email + WebSocket nudge for a still-pending request at ~N/2."""
    payload = _payload(request, event="reminder")
    push_care_request_update(request.patient_id, payload)
    push_care_request_update(request.caregiver.user_id, payload)

    if not _email_enabled():
        return

    hours_left = max(0, int((request.expires_at - timezone.now()).total_seconds() // 3600))
    subject = "Care Plus: request still pending"
    patient_body = (
        f"Hi,\n\n"
        f"Your care request to {request.caregiver.display_name} is still pending. "
        f"It expires in about {hours_left} hour(s).\n\n"
        f"— Care Plus\n"
    )
    caregiver_body = (
        f"Hi {request.caregiver.display_name},\n\n"
        f"You have a pending care request from {request.patient.email}. "
        f"Please accept or reject before it expires "
        f"(about {hours_left} hour(s) left).\n\n"
        f"— Care Plus\n"
    )
    try:
        send_mail(subject, patient_body, _from_email(), [request.patient.email], fail_silently=False)
        send_mail(
            subject,
            caregiver_body,
            _from_email(),
            [request.caregiver.user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Care request reminder email failed for request=%s", request.pk)


def notify_care_request_expired(request: CareRequest) -> None:
    """Email + WebSocket when a pending request auto-expires."""
    payload = _payload(request, event="expired")
    push_care_request_update(request.patient_id, payload)
    push_care_request_update(request.caregiver.user_id, payload)

    if not _email_enabled():
        return

    subject = "Care Plus: care request expired"
    patient_body = (
        f"Hi,\n\n"
        f"Your care request to {request.caregiver.display_name} expired without a response. "
        f"You can send a new request anytime.\n\n"
        f"— Care Plus\n"
    )
    caregiver_body = (
        f"Hi {request.caregiver.display_name},\n\n"
        f"A care request from {request.patient.email} expired without your response.\n\n"
        f"— Care Plus\n"
    )
    try:
        send_mail(subject, patient_body, _from_email(), [request.patient.email], fail_silently=False)
        send_mail(
            subject,
            caregiver_body,
            _from_email(),
            [request.caregiver.user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Care request expiry email failed for request=%s", request.pk)


@transaction.atomic
def send_pending_care_request_reminders() -> int:
    """Send one mid-TTL reminder per pending request that has crossed N/2."""
    now = timezone.now()
    # Reminder when created_at + N/2 <= now < expires_at and not yet reminded.
    due = (
        CareRequest.objects.select_related("patient", "caregiver", "caregiver__user")
        .filter(
            status=CareRequestStatus.PENDING,
            reminder_sent_at__isnull=True,
            expires_at__gt=now,
            created_at__lte=now - reminder_offset(),
        )
        .order_by("created_at")
    )
    count = 0
    for request in due:
        notify_care_request_reminder(request)
        request.reminder_sent_at = now
        request.save(update_fields=["reminder_sent_at", "updated_at"])
        count += 1
    return count


@transaction.atomic
def expire_stale_care_requests_with_notice() -> int:
    """Expire pending requests past expires_at and notify both parties."""
    now = timezone.now()
    stale = list(
        CareRequest.objects.select_related("patient", "caregiver", "caregiver__user").filter(
            status=CareRequestStatus.PENDING,
            expires_at__lt=now,
        )
    )
    if not stale:
        return 0

    CareRequest.objects.filter(pk__in=[r.pk for r in stale]).update(
        status=CareRequestStatus.EXPIRED,
        responded_at=now,
        updated_at=now,
    )
    for request in stale:
        request.status = CareRequestStatus.EXPIRED
        request.responded_at = now
        notify_care_request_expired(request)
    return len(stale)

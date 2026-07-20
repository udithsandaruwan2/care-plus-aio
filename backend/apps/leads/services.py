"""Lead create / contact helpers (Step 27)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role

from .models import Lead, LeadStatus

logger = logging.getLogger(__name__)


def create_lead(
    *,
    name: str,
    email: str,
    phone: str = "",
    message: str = "",
    city: str = "",
    preferred_language: str = "",
    source: str = "marketing_form",
) -> Lead:
    lead = Lead.objects.create(
        name=(name or "").strip(),
        email=(email or "").strip().lower(),
        phone=(phone or "").strip(),
        message=(message or "").strip(),
        city=(city or "").strip(),
        preferred_language=(preferred_language or "").strip(),
        source=(source or "marketing_form").strip() or "marketing_form",
        status=LeadStatus.NEW,
    )
    if getattr(settings, "LEAD_ACK_EMAIL_ENABLED", True):
        try:
            send_lead_acknowledgement(lead)
        except Exception:
            logger.exception("Lead acknowledgement email failed for lead=%s", lead.pk)
    return lead


def send_lead_acknowledgement(lead: Lead) -> bool:
    """Send a short acknowledgement email; no-op when email backend is unset."""
    if lead.ack_email_sent:
        return False
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@careplus.local")
    subject = "We received your Care Plus enquiry"
    body = (
        f"Hi {lead.name},\n\n"
        "Thanks for contacting Care Plus. Our team will follow up shortly.\n\n"
        "— Care Plus\n"
    )
    sent = send_mail(
        subject,
        body,
        from_email,
        [lead.email],
        fail_silently=False,
    )
    if sent:
        lead.ack_email_sent = True
        lead.save(update_fields=["ack_email_sent", "updated_at"])
    return bool(sent)


@transaction.atomic
def mark_lead_contacted(lead: Lead, *, actor, notes: str = "") -> Lead:
    if getattr(actor, "role", None) != Role.ADMIN and not getattr(actor, "is_staff", False):
        raise ValidationError("Only admins can mark leads as contacted.")
    if lead.status == LeadStatus.CONTACTED:
        return lead
    if lead.status == LeadStatus.CLOSED:
        raise ValidationError("Cannot mark a closed lead as contacted.")

    lead.status = LeadStatus.CONTACTED
    lead.contacted_at = timezone.now()
    lead.contacted_by = actor
    if notes.strip():
        lead.admin_notes = notes.strip()
    lead.save(
        update_fields=[
            "status",
            "contacted_at",
            "contacted_by",
            "admin_notes",
            "updated_at",
        ]
    )
    return lead

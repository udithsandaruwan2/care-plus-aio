"""Celery delivery for templated notification emails (Step 40)."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from .render import render_notification_email

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="accounts.send_notification_email")
def send_notification_email(
    user_id: int,
    event_key: str,
    template_key: str,
    context: dict,
    language: str = "English",
) -> dict:
    """Render si/ta/en copy and send via Django email backend."""
    from apps.accounts.notification_preferences import is_notification_enabled

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("send_notification_email: user %s not found", user_id)
        return {"sent": False, "reason": "user_not_found"}

    if not is_notification_enabled(user, channel="email", event_key=event_key):
        return {"sent": False, "reason": "disabled"}

    email = (user.email or "").strip()
    if not email:
        return {"sent": False, "reason": "no_email"}

    subject, body = render_notification_email(
        template_key, language=language, context=context
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@careplus.local")
    try:
        sent = send_mail(
            subject,
            body,
            from_email,
            [email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "send_notification_email failed user=%s template=%s", user_id, template_key
        )
        raise
    return {
        "sent": bool(sent),
        "user_id": user_id,
        "template_key": template_key,
        "event_key": event_key,
        "language": language,
    }

"""VAPID Web Push helpers (Step 41)."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


def vapid_configured() -> bool:
    return bool(
        getattr(settings, "VAPID_PUBLIC_KEY", "").strip()
        and getattr(settings, "VAPID_PRIVATE_KEY", "").strip()
    )


def vapid_public_key() -> str:
    return (getattr(settings, "VAPID_PUBLIC_KEY", "") or "").strip()


def send_web_push(
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    payload: dict[str, Any],
) -> bool:
    """Send one Web Push message. Returns False on gone/invalid subscription."""
    if not vapid_configured():
        logger.debug("VAPID keys not configured; skipping web push.")
        return False

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed; skipping web push.")
        return False

    subscription_info = {
        "endpoint": endpoint,
        "keys": {"p256dh": p256dh, "auth": auth},
    }
    claims = {
        "sub": getattr(settings, "VAPID_SUBJECT", "mailto:noreply@careplus.local"),
    }
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY.strip(),
            vapid_claims=claims,
        )
        return True
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            logger.info("Push subscription gone (%s): %s", status, endpoint[:80])
            return False
        logger.exception("Web push failed for endpoint=%s", endpoint[:80])
        return False

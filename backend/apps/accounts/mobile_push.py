"""Mobile push helpers for FCM/APNs delivery (Step 49)."""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)


def mobile_push_configured() -> bool:
    return bool(getattr(settings, "FCM_CREDENTIALS_JSON", "").strip())


@lru_cache(maxsize=1)
def _firebase_messaging():
    creds_raw = (getattr(settings, "FCM_CREDENTIALS_JSON", "") or "").strip()
    if not creds_raw:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except Exception:
        logger.exception("firebase_admin is not installed.")
        return None
    try:
        if creds_raw.startswith("{"):
            info = json.loads(creds_raw)
            cred = credentials.Certificate(info)
        else:
            cred = credentials.Certificate(creds_raw)
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(cred)
        return messaging
    except Exception:
        logger.exception("Failed to initialize Firebase Admin SDK.")
        return None


def send_mobile_push(*, token: str, title: str, body: str, data: dict[str, str] | None = None) -> bool:
    """Send one push notification to a registered device token."""
    messaging = _firebase_messaging()
    if messaging is None:
        return False
    payload_data = data or {}
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=body),
        data=payload_data,
    )
    try:
        messaging.send(message)
        return True
    except Exception:
        logger.exception("send_mobile_push failed.")
        return False


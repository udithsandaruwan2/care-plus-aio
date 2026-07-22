"""Notification event registry and preference helpers (Step 39)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

NotificationCategory = Literal["security", "transactional", "marketing"]
NotificationChannel = Literal["email", "push"]


@dataclass(frozen=True)
class NotificationEventSpec:
    key: str
    label: str
    description: str
    category: NotificationCategory
    default_email: bool = True
    default_push: bool = True

    @property
    def locked(self) -> bool:
        return self.category == "security"


NOTIFICATION_EVENTS: dict[str, NotificationEventSpec] = {
    "security_login_alert": NotificationEventSpec(
        key="security_login_alert",
        label="Sign-in security alerts",
        description="Unusual sign-in attempts and account security notices.",
        category="security",
    ),
    "security_payment_alert": NotificationEventSpec(
        key="security_payment_alert",
        label="Payment security alerts",
        description="Failed payments, chargebacks, and payment anomalies.",
        category="security",
    ),
    "care_request_received": NotificationEventSpec(
        key="care_request_received",
        label="Care request received",
        description="When a patient sends you a care request or you submit one.",
        category="transactional",
    ),
    "care_request_reminder": NotificationEventSpec(
        key="care_request_reminder",
        label="Care request reminders",
        description="Mid-TTL reminders before a pending request expires.",
        category="transactional",
    ),
    "care_request_expired": NotificationEventSpec(
        key="care_request_expired",
        label="Care request expired",
        description="When a pending request expires without a response.",
        category="transactional",
    ),
    "care_request_accepted": NotificationEventSpec(
        key="care_request_accepted",
        label="Care request accepted",
        description="When a caregiver accepts your request.",
        category="transactional",
    ),
    "care_request_rejected": NotificationEventSpec(
        key="care_request_rejected",
        label="Care request declined",
        description="When a caregiver declines your request.",
        category="transactional",
    ),
    "new_message": NotificationEventSpec(
        key="new_message",
        label="New chat messages",
        description="When your care partner sends an in-app message.",
        category="transactional",
        default_push=True,
        default_email=False,
    ),
    "payment_receipt": NotificationEventSpec(
        key="payment_receipt",
        label="Payment receipts",
        description="Email receipts after successful checkout.",
        category="transactional",
        default_push=False,
    ),
    "payment_due": NotificationEventSpec(
        key="payment_due",
        label="Payment due reminders",
        description="Checkout reminders after a caregiver accepts your request.",
        category="transactional",
        default_push=True,
        default_email=True,
    ),
    "marketing_newsletter": NotificationEventSpec(
        key="marketing_newsletter",
        label="Care Plus newsletter",
        description="Product updates and community stories.",
        category="marketing",
        default_push=False,
    ),
    "marketing_promotions": NotificationEventSpec(
        key="marketing_promotions",
        label="Promotions and offers",
        description="Discounts and seasonal campaigns.",
        category="marketing",
        default_push=False,
    ),
}

CHANNELS: tuple[NotificationChannel, ...] = ("email", "push")


def default_channel_map() -> dict[str, dict[str, bool]]:
    out: dict[str, dict[str, bool]] = {ch: {} for ch in CHANNELS}
    for spec in NOTIFICATION_EVENTS.values():
        out["email"][spec.key] = spec.default_email
        out["push"][spec.key] = spec.default_push
    return out


def merge_preferences(stored: dict | None) -> dict[str, dict[str, bool]]:
    merged = default_channel_map()
    if not stored:
        return merged
    for channel in CHANNELS:
        overrides = stored.get(channel) or {}
        if not isinstance(overrides, dict):
            continue
        for event_key, value in overrides.items():
            if event_key in NOTIFICATION_EVENTS and isinstance(value, bool):
                merged[channel][event_key] = value
    for spec in NOTIFICATION_EVENTS.values():
        if spec.locked:
            for channel in CHANNELS:
                merged[channel][spec.key] = True
    return merged


def apply_preference_patch(current: dict[str, dict[str, bool]], patch: dict) -> dict[str, dict[str, bool]]:
    merged = {ch: dict(current[ch]) for ch in CHANNELS}
    for channel in CHANNELS:
        updates = patch.get(channel) or {}
        if not isinstance(updates, dict):
            raise ValueError(f"Invalid preference payload for channel '{channel}'.")
        for event_key, value in updates.items():
            if event_key not in NOTIFICATION_EVENTS:
                raise ValueError(f"Unknown notification event '{event_key}'.")
            if not isinstance(value, bool):
                raise ValueError(f"Preference for '{event_key}' must be a boolean.")
            spec = NOTIFICATION_EVENTS[event_key]
            if spec.locked and value is False:
                raise ValueError(f"Security alerts for '{event_key}' cannot be disabled.")
            merged[channel][event_key] = value
    for spec in NOTIFICATION_EVENTS.values():
        if spec.locked:
            for channel in CHANNELS:
                merged[channel][spec.key] = True
    return merged


def preferences_payload(merged: dict[str, dict[str, bool]]) -> dict:
    events = []
    for spec in NOTIFICATION_EVENTS.values():
        events.append(
            {
                "key": spec.key,
                "label": spec.label,
                "description": spec.description,
                "category": spec.category,
                "locked": spec.locked,
                "email": merged["email"][spec.key],
                "push": merged["push"][spec.key],
            }
        )
    return {
        "channels": merged,
        "events": events,
    }


def is_notification_enabled(
    user,
    *,
    channel: NotificationChannel,
    event_key: str,
) -> bool:
    if event_key not in NOTIFICATION_EVENTS:
        return True
    spec = NOTIFICATION_EVENTS[event_key]
    if spec.locked:
        return True
    from .models import NotificationPreference

    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    merged = merge_preferences(pref.channels)
    return bool(merged[channel].get(event_key, True))

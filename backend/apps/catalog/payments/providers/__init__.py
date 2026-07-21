"""Payment provider factory."""

from __future__ import annotations

from django.conf import settings

from .mock import MockProvider
from .payhere import PayHereProvider


def get_payment_provider():
    name = (getattr(settings, "PAYMENT_PROVIDER", "mock") or "mock").strip().lower()
    if name == "payhere":
        return PayHereProvider()
    return MockProvider()

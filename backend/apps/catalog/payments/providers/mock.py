"""Dev mock payment provider — never auto-succeeds (Step 31)."""

from __future__ import annotations

import uuid
from typing import Mapping

from .base import CreateIntentResult, WebhookEvent


class MockProvider:
    name = "mock"

    def create_intent(self, *, order, payment_intent) -> CreateIntentResult:
        intent_id = f"mock_{uuid.uuid4().hex}"
        return CreateIntentResult(
            provider_intent_id=intent_id,
            client_payload={
                "mode": "mock",
                "confirm_path": f"/api/v1/payments/mock/{intent_id}/confirm/",
                "amount_lkr": str(order.total_lkr),
                "currency": order.currency,
            },
            provider_response={"provider": "mock", "auto_succeeded": False},
        )

    def verify_webhook_signature(self, *, body: bytes, headers: Mapping[str, str]) -> bool:
        # Mock has no webhook path; signature always rejected.
        return False

    def parse_webhook(self, *, body: bytes) -> WebhookEvent:
        raise NotImplementedError("MockProvider does not accept webhooks.")

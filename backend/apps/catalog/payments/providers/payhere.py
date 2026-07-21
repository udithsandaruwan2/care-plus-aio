"""PayHere payment provider stub with notify signature verification (Step 31)."""

from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from typing import Mapping
from urllib.parse import parse_qs

from django.conf import settings

from .base import CreateIntentResult, WebhookEvent


def payhere_md5sig(
    *,
    merchant_id: str,
    order_id: str,
    amount: str,
    currency: str,
    status_code: str,
    merchant_secret: str,
) -> str:
    """PayHere notify MD5 signature (uppercase hex)."""
    secret_hash = hashlib.md5(merchant_secret.encode("utf-8")).hexdigest().upper()
    raw = f"{merchant_id}{order_id}{amount}{currency}{status_code}{secret_hash}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def _decode_body(body: bytes) -> dict:
    text = body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)
    text = text.strip()
    if not text:
        return {}
    if text.startswith("{"):
        data = json.loads(text)
        return {str(k): str(v) if not isinstance(v, (dict, list)) else v for k, v in data.items()}
    parsed = parse_qs(text, keep_blank_values=True)
    return {k: (v[0] if isinstance(v, list) and v else "") for k, v in parsed.items()}


class PayHereProvider:
    name = "payhere"

    def __init__(
        self,
        *,
        merchant_id: str | None = None,
        merchant_secret: str | None = None,
        sandbox: bool | None = None,
        notify_url: str | None = None,
    ):
        self.merchant_id = merchant_id if merchant_id is not None else getattr(
            settings, "PAYHERE_MERCHANT_ID", ""
        )
        self.merchant_secret = merchant_secret if merchant_secret is not None else getattr(
            settings, "PAYHERE_MERCHANT_SECRET", ""
        )
        self.sandbox = (
            sandbox if sandbox is not None else bool(getattr(settings, "PAYHERE_SANDBOX", True))
        )
        self.notify_url = notify_url if notify_url is not None else getattr(
            settings, "PAYHERE_NOTIFY_URL", ""
        )

    def create_intent(self, *, order, payment_intent) -> CreateIntentResult:
        order_id = f"ph_{order.pk}_{uuid.uuid4().hex[:12]}"
        checkout_host = (
            "https://sandbox.payhere.lk/pay/checkout"
            if self.sandbox
            else "https://www.payhere.lk/pay/checkout"
        )
        amount = f"{Decimal(order.total_lkr):.2f}"
        payload = {
            "mode": "payhere",
            "sandbox": self.sandbox,
            "checkout_url": checkout_host,
            "merchant_id": self.merchant_id,
            "order_id": order_id,
            "amount": amount,
            "currency": order.currency,
            "notify_url": self.notify_url or "/api/v1/payments/payhere/webhook/",
            # Live redirect/form posting is wired in Step 32 UI.
            "stub": True,
        }
        return CreateIntentResult(
            provider_intent_id=order_id,
            client_payload=payload,
            provider_response={"provider": "payhere", "stub": True},
        )

    def verify_webhook_signature(self, *, body: bytes, headers: Mapping[str, str]) -> bool:
        del headers  # PayHere posts md5sig in the body.
        if not self.merchant_id or not self.merchant_secret:
            return False
        data = _decode_body(body)
        expected = payhere_md5sig(
            merchant_id=str(data.get("merchant_id", "")),
            order_id=str(data.get("order_id", "")),
            amount=str(data.get("payhere_amount", data.get("amount", ""))),
            currency=str(data.get("payhere_currency", data.get("currency", ""))),
            status_code=str(data.get("status_code", "")),
            merchant_secret=self.merchant_secret,
        )
        received = str(data.get("md5sig", "")).upper()
        if not received:
            return False
        # Also require merchant_id match when configured.
        if str(data.get("merchant_id", "")) != str(self.merchant_id):
            return False
        return received == expected

    def parse_webhook(self, *, body: bytes) -> WebhookEvent:
        data = _decode_body(body)
        status_code = str(data.get("status_code", ""))
        succeeded = status_code == "2"
        return WebhookEvent(
            provider_intent_id=str(data.get("order_id", "")),
            succeeded=succeeded,
            raw=data,
            failure_code="" if succeeded else status_code or "unknown",
            failure_message="" if succeeded else str(data.get("status_message", "payment_failed")),
        )

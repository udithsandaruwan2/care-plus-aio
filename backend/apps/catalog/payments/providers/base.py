"""Payment provider abstractions (Step 31)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class CreateIntentResult:
    provider_intent_id: str
    client_payload: dict[str, Any] = field(default_factory=dict)
    provider_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebhookEvent:
    provider_intent_id: str
    succeeded: bool
    raw: dict[str, Any] = field(default_factory=dict)
    failure_code: str = ""
    failure_message: str = ""


class PaymentProvider(Protocol):
    name: str

    def create_intent(self, *, order, payment_intent) -> CreateIntentResult: ...

    def verify_webhook_signature(self, *, body: bytes, headers: Mapping[str, str]) -> bool: ...

    def parse_webhook(self, *, body: bytes) -> WebhookEvent: ...

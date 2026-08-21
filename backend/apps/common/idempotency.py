"""Idempotent write receipts for offline outbox replay (Step 95)."""

from __future__ import annotations

from django.conf import settings
from django.db import models, transaction


class IdempotencyScope(models.TextChoices):
    CARE_REQUEST_CREATE = "care_request_create", "Care request create"
    MESSAGE_SEND = "message_send", "Message send"
    PAYMENT_CONFIRM = "payment_confirm", "Payment confirm"


class IdempotencyRecord(models.Model):
    """Stores the first successful (or permanent) response for a client key."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="idempotency_records",
    )
    scope = models.CharField(max_length=32, choices=IdempotencyScope.choices, db_index=True)
    key = models.CharField(max_length=128)
    status_code = models.PositiveSmallIntegerField()
    response_body = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "scope", "key"),
                name="common_idempotency_user_scope_key_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "scope", "-created_at"], name="idempo_user_scope_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.scope}:{self.key} user={self.user_id}"


def resolve_idempotency_key(request, *, body_field: str = "idempotency_key") -> str:
    """Prefer ``Idempotency-Key`` header; fall back to JSON body field."""
    header = (request.META.get("HTTP_IDEMPOTENCY_KEY") or "").strip()
    if header:
        return header[:128]
    data = getattr(request, "data", None)
    if isinstance(data, dict):
        raw = data.get(body_field) or data.get("idempotency_key")
        if raw is not None and str(raw).strip():
            return str(raw).strip()[:128]
    return ""


@transaction.atomic
def run_idempotent(*, user, scope: str, key: str, execute):
    """Run ``execute() -> (body: dict, status_code: int)`` once per user/scope/key.

    Replays return the stored body/status. Empty ``key`` skips persistence.
    """
    key = (key or "").strip()[:128]
    if not key:
        return (*execute(), False)

    existing = (
        IdempotencyRecord.objects.select_for_update()
        .filter(user=user, scope=scope, key=key)
        .first()
    )
    if existing is not None:
        return existing.response_body, int(existing.status_code), True

    body, status_code = execute()
    status_code = int(status_code)
    # Persist success and permanent client errors so retries do not double-create.
    if status_code < 500:
        IdempotencyRecord.objects.create(
            user=user,
            scope=scope,
            key=key,
            status_code=status_code,
            response_body=body if isinstance(body, dict) else {"detail": body},
        )
    return body, status_code, False

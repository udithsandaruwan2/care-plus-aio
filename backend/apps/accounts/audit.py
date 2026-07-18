"""Append-only audit trail helpers (HIPAA / PDPA).

Prefer :func:`record_audit` from request handlers. Production paths enqueue a
Celery task so the HTTP request is not blocked by the write; tests and
eager-mode use the sync path.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from .models import AuditAction, AuditLog
from .tasks import write_audit_log


def client_ip(request) -> str | None:
    """Best-effort client IP (honours X-Forwarded-For when behind a proxy)."""
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def record_audit(
    *,
    actor,
    action: str,
    request=None,
    target_type: str = "",
    target_id: str | int = "",
    metadata: dict[str, Any] | None = None,
    async_: bool | None = None,
) -> None:
    """Record an immutable audit row (async via Celery unless sync/eager)."""
    if action not in AuditAction.values:
        raise ValueError(f"Unknown audit action: {action!r}")

    actor_id = getattr(actor, "pk", None) if actor is not None else None
    payload = {
        "actor_id": actor_id,
        "action": action,
        "ip": client_ip(request),
        "target_type": target_type or "",
        "target_id": str(target_id) if target_id != "" else "",
        "metadata": metadata or {},
    }

    eager = getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
    if async_ is False or eager:
        write_audit_log(**payload)
        return
    write_audit_log.delay(**payload)


def write_audit_row(
    *,
    actor_id: int | None,
    action: str,
    ip: str | None = None,
    target_type: str = "",
    target_id: str = "",
    metadata: dict | None = None,
) -> AuditLog:
    """Synchronous insert used by the Celery task and sync callers."""
    return AuditLog.objects.create(
        actor_id=actor_id,
        action=action,
        ip=ip,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata or {},
    )

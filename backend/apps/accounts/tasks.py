"""Celery tasks for the accounts app."""

from celery import shared_task


@shared_task(name="accounts.write_audit_log")
def write_audit_log(
    actor_id: int | None,
    action: str,
    ip: str | None = None,
    target_type: str = "",
    target_id: str = "",
    metadata: dict | None = None,
) -> int:
    """Persist one immutable AuditLog row; returns the new row's primary key."""
    # Local import avoids circular imports at worker boot.
    from .audit import write_audit_row

    row = write_audit_row(
        actor_id=actor_id,
        action=action,
        ip=ip,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
    )
    return row.pk

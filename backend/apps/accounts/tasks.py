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


@shared_task(name="accounts.purge_erased_accounts")
def purge_erased_accounts_task(older_than_days: int = 30) -> dict:
    """Scheduled residual PHI purge for erased accounts (Step 69)."""
    from .privacy import purge_erased_accounts

    return purge_erased_accounts(older_than_days=older_than_days)

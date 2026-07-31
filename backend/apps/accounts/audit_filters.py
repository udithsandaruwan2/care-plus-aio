"""Audit log query helpers (Step 58)."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError

from apps.accounts.models import AuditAction, AuditLog

COLOMBO = ZoneInfo("Asia/Colombo")
CSV_ROW_CAP = 10_000


def _parse_date(value: str, *, end_of_day: bool = False):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        day = datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError({"detail": f"Invalid date '{raw}'. Use YYYY-MM-DD."}) from exc
    wall = time(23, 59, 59, 999999) if end_of_day else time.min
    return datetime.combine(day, wall, tzinfo=COLOMBO)


def filtered_audit_logs(params) -> QuerySet[AuditLog]:
    qs = AuditLog.objects.select_related("actor").all().order_by("-ts")

    action = (params.get("action") or "").strip()
    if action:
        if action not in {c.value for c in AuditAction}:
            raise ValidationError({"action": "Unknown audit action."})
        qs = qs.filter(action=action)

    actor = (params.get("actor") or "").strip()
    if actor:
        if actor.isdigit():
            qs = qs.filter(actor_id=int(actor))
        else:
            qs = qs.filter(actor__email__icontains=actor)

    date_from = _parse_date(params.get("date_from") or "")
    if date_from is not None:
        qs = qs.filter(ts__gte=date_from)

    date_to = _parse_date(params.get("date_to") or "", end_of_day=True)
    if date_to is not None:
        qs = qs.filter(ts__lte=date_to)

    return qs

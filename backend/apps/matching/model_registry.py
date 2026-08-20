"""Persist and resolve trained model artifacts (Step 88)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from django.db import transaction
from django.utils.dateparse import parse_datetime

from .models import ModelKind, ModelVersion

logger = logging.getLogger(__name__)


def resolve_model_version(kind: str, version: str) -> ModelVersion | None:
    """Look up a registry row by kind + version string (MatchRun provenance)."""
    ver = (version or "").strip()
    if not ver:
        return None
    return ModelVersion.objects.filter(kind=kind, version=ver).first()


def active_model(kind: str) -> ModelVersion | None:
    return ModelVersion.objects.filter(kind=kind, is_active=True).first()


@transaction.atomic
def register_model_version(
    *,
    kind: str,
    version: str,
    rows_trained_on: int = 0,
    metrics: dict | None = None,
    artifact_path: str = "",
    trained_at: datetime | str | None = None,
    activate: bool = True,
) -> ModelVersion:
    """Insert or update a ModelVersion and optionally make it the sole active of its kind."""
    ver = (version or "").strip()
    if not ver:
        raise ValueError("ModelVersion.version is required")

    when: datetime
    if isinstance(trained_at, datetime):
        when = trained_at if trained_at.tzinfo else trained_at.replace(tzinfo=UTC)
    elif isinstance(trained_at, str) and trained_at.strip():
        parsed = parse_datetime(trained_at.strip())
        when = parsed if parsed is not None else datetime.now(UTC)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
    else:
        when = datetime.now(UTC)

    if activate:
        ModelVersion.objects.filter(kind=kind, is_active=True).exclude(version=ver).update(
            is_active=False
        )

    row, created = ModelVersion.objects.update_or_create(
        kind=kind,
        version=ver,
        defaults={
            "trained_at": when,
            "rows_trained_on": int(rows_trained_on or 0),
            "metrics": metrics or {},
            "artifact_path": (artifact_path or "")[:512],
            "is_active": bool(activate),
        },
    )
    if not created and activate and not row.is_active:
        row.is_active = True
        row.save(update_fields=["is_active"])
    logger.info(
        "model_registry.register",
        extra={
            "model_kind": kind,
            "model_version": ver,
            "model_active": row.is_active,
            "row_created": created,
            "rows_trained": row.rows_trained_on,
        },
    )
    return row

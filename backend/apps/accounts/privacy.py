"""PDPA data export + right-to-erasure (Step 69 / 105).

Step 105 completes the data-subject export: every user-linked model is
represented (or explicitly excluded), MatchResult/weights/versions/consent/
audit are included, and JSON responses stream section-by-section.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from apps.accounts.audit import record_audit
from apps.accounts.models import (
    AuditAction,
    MobilePushDevice,
    NotificationPreference,
    PushSubscription,
    Role,
)

EXPORT_SCHEMA_VERSION = 2

# Models with a concrete FK/O2O to User → top-level export key.
# Keep in sync with discover_user_linked_models(); the completeness test enforces this.
EXPORT_USER_MODELS: dict[str, str] = {
    "accounts.ConsentLog": "consents",
    "accounts.AuditLog": "audit_logs",
    "accounts.NotificationPreference": "notification_preferences",
    "accounts.PushSubscription": "push_subscriptions",
    "accounts.MobilePushDevice": "mobile_push_devices",
    "matching.PatientProfile": "patient_profile",
    "matching.CaregiverProfile": "caregiver_profile",
    "matching.MatchRun": "match_runs",
    "matching.Interaction": "interactions",
    "matching.CareRequest": "care_requests",
    "matching.CareRelationship": "care_relationships",
    "matching.Review": "reviews",
    "matching.Shift": "shifts",
    "voice.VoiceIntent": "voice_intents",
    "voice.DialogueSession": "dialogue_sessions",
    "voice.VoiceTurnTiming": "voice_turn_timings",
    "health_monitoring.HealthMetric": "health_metrics",
    "health_monitoring.HealthEvent": "health_events",
    "medical_records.MedicalRecord": "medical_records",
    "messaging.Message": "messages",
    "catalog.Order": "orders",
    "catalog.PaymentIntent": "payment_intents",
}

# Nested under a parent section (no direct User FK, or covered via parent).
EXPORT_NESTED_MODELS: dict[str, str] = {
    "matching.MatchResult": "match_runs",
    "medical_records.MedicalRecordAttachment": "medical_records",
    "catalog.OrderLineItem": "orders",
    "messaging.MessageThread": "care_relationships",
    "matching.CaregiverAvailabilitySlot": "caregiver_profile",
}

# User-linked models that must NOT appear in a DSAR export.
EXPORT_MODEL_EXCLUSIONS: frozenset[str] = frozenset(
    {
        "accounts.EmailOtp",  # secrets
        "accounts.User",  # root subject → "user" key
        "admin.LogEntry",  # Django admin, not product data
        "common.IdempotencyRecord",  # transport dedupe keys
        "leads.Lead",  # contacted_by is staff; subject matched by email only at erase
    }
)


def _iso(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def discover_user_linked_models() -> set[str]:
    """Labels of concrete models with a FK/O2O to AUTH_USER_MODEL."""
    user_label = settings.AUTH_USER_MODEL
    if "." not in user_label:
        user_label = f"accounts.{user_label}"
    found: set[str] = set()
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if not getattr(field, "concrete", False):
                continue
            if not (getattr(field, "many_to_one", False) or getattr(field, "one_to_one", False)):
                continue
            if getattr(field, "many_to_many", False):
                continue
            rel = getattr(field, "related_model", None)
            if rel is None:
                continue
            if rel._meta.label == user_label or rel._meta.label == "accounts.User":
                found.add(model._meta.label)
                break
    return found


def export_coverage_gaps() -> set[str]:
    """User-linked models missing from EXPORT_USER_MODELS and exclusions."""
    return discover_user_linked_models() - set(EXPORT_USER_MODELS) - EXPORT_MODEL_EXCLUSIONS


def _iter_consents(user) -> Iterator[dict[str, Any]]:
    from apps.accounts.models import ConsentLog

    for row in ConsentLog.objects.filter(user=user).order_by("-ts").iterator(chunk_size=200):
        yield {"scope": row.scope, "granted": row.granted, "ts": _iso(row.ts)}


def _iter_audit_logs(user) -> Iterator[dict[str, Any]]:
    from apps.accounts.models import AuditLog

    for row in AuditLog.objects.filter(actor=user).order_by("-ts").iterator(chunk_size=200):
        yield {
            "id": row.pk,
            "action": row.action,
            "ts": _iso(row.ts),
            "ip": row.ip,
            "request_id": row.request_id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "metadata": row.metadata or {},
        }


def _notification_preferences(user) -> dict[str, Any] | None:
    pref = NotificationPreference.objects.filter(user=user).first()
    return pref.channels if pref else None


def _iter_push_subscriptions(user) -> Iterator[dict[str, Any]]:
    for row in PushSubscription.objects.filter(user=user).order_by("-updated_at").iterator(
        chunk_size=100
    ):
        yield {
            "id": row.pk,
            "endpoint": row.endpoint,
            "user_agent": row.user_agent,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }


def _iter_mobile_push_devices(user) -> Iterator[dict[str, Any]]:
    for row in MobilePushDevice.objects.filter(user=user).order_by("-updated_at").iterator(
        chunk_size=100
    ):
        # Token is device-identifying; include for DSAR completeness (owner-only).
        yield {
            "id": row.pk,
            "platform": row.platform,
            "token": row.token,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(getattr(row, "updated_at", None)),
        }


def _patient_profile(user) -> dict[str, Any] | None:
    patient = getattr(user, "patient_profile", None)
    if patient is None:
        return None
    return {
        "display_name": patient.display_name,
        "city": patient.city,
        "preferred_language": patient.preferred_language,
        "languages": list(patient.languages or []),
        "conditions": list(patient.conditions or []),
        "care_level": patient.care_level,
        "height_cm": patient.height_cm,
        "weight_kg": patient.weight_kg,
        "blood_type": patient.blood_type,
        "medications": list(patient.medications or []),
        "allergies": list(patient.allergies or []),
        "emergency_contact_name": patient.emergency_contact_name,
        "emergency_contact_phone": patient.emergency_contact_phone,
    }


def _caregiver_profile(user) -> dict[str, Any] | None:
    caregiver = getattr(user, "caregiver_profile", None)
    if caregiver is None:
        return None
    slots = [
        {
            "id": s.pk,
            "weekday": s.weekday,
            "start_time": str(s.start_time),
            "end_time": str(s.end_time),
            "timezone": s.timezone,
            "is_active": s.is_active,
        }
        for s in caregiver.availability_slots.all().order_by("weekday", "start_time")
    ]
    return {
        "display_name": caregiver.display_name,
        "city": caregiver.city,
        "bio": caregiver.bio,
        "languages": list(caregiver.languages or []),
        "specialties": list(caregiver.specialties or []),
        "certifications": list(caregiver.certifications or []),
        "care_levels": list(caregiver.care_levels or []),
        "years_experience": caregiver.years_experience,
        "is_active": caregiver.is_active,
        "is_available": caregiver.is_available,
        "is_approved": caregiver.is_approved,
        "availability_slots": slots,
    }


def _iter_voice_intents(user) -> Iterator[dict[str, Any]]:
    from apps.voice.models import VoiceIntent

    for intent in VoiceIntent.objects.filter(user=user).order_by("-ts").iterator(chunk_size=200):
        yield {
            "id": intent.pk,
            "raw_text": intent.raw_text,
            "condition": intent.condition,
            "language": intent.language,
            "languages": intent.languages,
            "care_level": intent.care_level,
            "urgency": intent.urgency,
            "source": intent.source,
            "ts": _iso(intent.ts),
        }


def _iter_dialogue_sessions(user) -> Iterator[dict[str, Any]]:
    from apps.voice.models import DialogueSession

    for session in (
        DialogueSession.objects.filter(user=user).order_by("-updated_at").iterator(chunk_size=50)
    ):
        yield {
            "id": session.pk,
            "lang": session.lang,
            "active": session.active,
            "intent_chips": session.intent_chips,
            "open_questions": session.open_questions,
            "route_history": session.route_history,
            "turns": session.turns,
            "last_match_run_id": session.last_match_run_id,
            "updated_at": _iso(session.updated_at),
        }


def _iter_voice_turn_timings(user) -> Iterator[dict[str, Any]]:
    from apps.voice.models import VoiceTurnTiming

    for row in VoiceTurnTiming.objects.filter(user=user).order_by("-created_at").iterator(
        chunk_size=200
    ):
        yield {
            "id": row.pk,
            "request_id": row.request_id,
            "route": row.route,
            "situation": row.situation,
            "asr_ms": row.asr_ms,
            "intent_ms": row.intent_ms,
            "route_ms": row.route_ms,
            "match_ms": row.match_ms,
            "chat_ms": row.chat_ms,
            "tts_ms": row.tts_ms,
            "total_ms": row.total_ms,
            "created_at": _iso(row.created_at),
        }


def _iter_health_metrics(user) -> Iterator[dict[str, Any]]:
    from apps.health_monitoring.models import HealthMetric

    for metric in (
        HealthMetric.objects.filter(patient=user).order_by("-recorded_at").iterator(chunk_size=500)
    ):
        yield {
            "id": metric.pk,
            "kind": metric.kind,
            "value": metric.value,
            "unit": metric.unit,
            "source": metric.source,
            "recorded_at": _iso(metric.recorded_at),
            "metadata": metric.metadata,
        }


def _iter_health_events(user) -> Iterator[dict[str, Any]]:
    from apps.health_monitoring.models import HealthEvent

    for event in (
        HealthEvent.objects.filter(patient=user).order_by("-created_at").iterator(chunk_size=200)
    ):
        yield {
            "id": event.pk,
            "event_type": event.event_type,
            "kind": event.kind,
            "rule_key": event.rule_key,
            "severity": event.severity,
            "sample_count": event.sample_count,
            "payload": event.payload,
            "rematch_run_id": event.rematch_run_id,
            "created_at": _iso(event.created_at),
        }


def _iter_medical_records(user) -> Iterator[dict[str, Any]]:
    from apps.medical_records.models import MedicalRecord

    qs = (
        MedicalRecord.objects.filter(patient=user)
        .select_related("condition")
        .prefetch_related("attachments")
        .order_by("-created_at")
    )
    for record in qs.iterator(chunk_size=100):
        # iterator() ignores prefetch — load attachments per row.
        attachments = [
            {
                "id": att.pk,
                "original_name": att.original_name,
                "content_type": att.content_type,
                "size_bytes": att.size_bytes,
                "uploaded_at": _iso(att.uploaded_at),
            }
            for att in record.attachments.all()
        ]
        yield {
            "id": record.pk,
            "title": record.title,
            "description": record.description,
            "condition_slug": record.condition.slug if record.condition_id else "",
            "sensitive_notes": record.sensitive_notes,
            "recorded_at": str(record.recorded_at) if record.recorded_at else None,
            "deleted_at": _iso(record.deleted_at),
            "attachments": attachments,
        }


def _iter_match_runs(user) -> Iterator[dict[str, Any]]:
    from apps.matching.models import MatchRun

    qs = (
        MatchRun.objects.filter(user=user, deleted_at__isnull=True)
        .prefetch_related("results")
        .order_by("-created_at")
    )
    for run in qs.iterator(chunk_size=50):
        results = [
            {
                "caregiver_id": hit.caregiver_id,
                "rank": hit.rank,
                "score": hit.score,
                "cbf": hit.cbf,
                "cf": hit.cf,
                "geo": hit.geo,
                "trust": hit.trust,
                "explanation": hit.explanation,
                "distance_m": hit.distance_m,
                "was_exploratory": bool(getattr(hit, "was_exploratory", False)),
            }
            for hit in run.results.all().order_by("rank")
        ]
        yield {
            "id": run.pk,
            "query": run.query,
            "condition": run.condition,
            "language": run.language,
            "care_level": run.care_level,
            "emergency": run.emergency,
            "latency_ms": run.latency_ms,
            "weights": list(run.weights or []),
            "cf_version": run.cf_version,
            "embedding_backend": run.embedding_backend,
            "index_version": run.index_version,
            "weights_source": run.weights_source,
            "variant": getattr(run, "variant", "") or "",
            "cf_model_id": run.cf_model_id,
            "faiss_model_id": run.faiss_model_id,
            "filters": run.filters or {},
            "request_id": run.request_id,
            "created_at": _iso(run.created_at),
            "results": results,
        }


def _iter_interactions(user) -> Iterator[dict[str, Any]]:
    from apps.matching.models import Interaction

    for row in (
        Interaction.objects.filter(patient=user).order_by("-created_at").iterator(chunk_size=200)
    ):
        yield {
            "id": row.pk,
            "caregiver_id": row.caregiver_id,
            "kind": row.kind,
            "weight": row.weight,
            "rating": row.rating,
            "metadata": row.metadata or {},
            "created_at": _iso(row.created_at),
        }


def _iter_care_requests(user) -> Iterator[dict[str, Any]]:
    from apps.matching.models import CareRequest

    for req in (
        CareRequest.objects.filter(patient=user).order_by("-created_at").iterator(chunk_size=100)
    ):
        yield {
            "id": req.pk,
            "caregiver_id": req.caregiver_id,
            "status": req.status,
            "message": req.message,
            "match_run_id": req.match_run_id,
            "expires_at": _iso(req.expires_at),
            "responded_at": _iso(req.responded_at),
            "created_at": _iso(req.created_at),
        }


def _iter_care_relationships(user) -> Iterator[dict[str, Any]]:
    from apps.matching.models import CareRelationship
    from apps.messaging.models import MessageThread

    for rel in (
        CareRelationship.objects.filter(patient=user).order_by("-started_at").iterator(chunk_size=50)
    ):
        try:
            thread_id = rel.message_thread.pk
        except MessageThread.DoesNotExist:
            thread_id = None
        yield {
            "id": rel.pk,
            "caregiver_id": rel.caregiver_id,
            "care_request_id": rel.care_request_id,
            "status": rel.status,
            "is_primary": rel.is_primary,
            "started_at": _iso(rel.started_at),
            "ended_at": _iso(rel.ended_at),
            "end_reason": rel.end_reason,
            "message_thread_id": thread_id,
        }


def _iter_reviews(user) -> Iterator[dict[str, Any]]:
    from apps.matching.models import Review

    for row in Review.objects.filter(patient=user).order_by("-created_at").iterator(chunk_size=100):
        yield {
            "id": row.pk,
            "relationship_id": row.relationship_id,
            "caregiver_id": row.caregiver_id,
            "rating": row.rating,
            "comment": row.comment,
            "status": row.status,
            "created_at": _iso(row.created_at),
        }


def _iter_shifts(user) -> Iterator[dict[str, Any]]:
    from apps.matching.models import Shift

    for row in Shift.objects.filter(patient=user).order_by("-starts_at").iterator(chunk_size=100):
        yield {
            "id": row.pk,
            "caregiver_id": row.caregiver_id,
            "starts_at": _iso(row.starts_at),
            "ends_at": _iso(row.ends_at),
            "timezone": row.timezone,
            "status": row.status,
            "notes": row.notes,
            "created_at": _iso(row.created_at),
        }


def _iter_messages(user) -> Iterator[dict[str, Any]]:
    from apps.messaging.models import Message

    for msg in Message.objects.filter(sender=user).order_by("-created_at").iterator(chunk_size=200):
        yield {
            "id": msg.pk,
            "thread_id": msg.thread_id,
            "body": msg.body,
            "read_at": _iso(msg.read_at),
            "created_at": _iso(msg.created_at),
        }


def _iter_orders(user) -> Iterator[dict[str, Any]]:
    from apps.catalog.models import Order

    for order in (
        Order.objects.filter(patient=user)
        .prefetch_related("lines")
        .order_by("-created_at")
        .iterator(chunk_size=50)
    ):
        lines = [
            {
                "id": line.pk,
                "kind": line.kind,
                "slug": line.slug,
                "name": line.name,
                "catalog_id": line.catalog_id,
                "quantity": line.quantity,
                "unit_price_lkr": str(line.unit_price_lkr),
                "line_total_lkr": str(line.line_total_lkr),
            }
            for line in order.lines.all()
        ]
        yield {
            "id": order.pk,
            "care_request_id": order.care_request_id,
            "status": order.status,
            "days": order.days,
            "currency": order.currency,
            "subtotal_lkr": str(order.subtotal_lkr),
            "total_lkr": str(order.total_lkr),
            "receipt_email_sent": order.receipt_email_sent,
            "receipt_sent_at": _iso(order.receipt_sent_at),
            "created_at": _iso(order.created_at),
            "lines": lines,
        }


def _iter_payment_intents(user) -> Iterator[dict[str, Any]]:
    from apps.catalog.models import PaymentIntent

    for pi in (
        PaymentIntent.objects.filter(patient=user).order_by("-created_at").iterator(chunk_size=50)
    ):
        yield {
            "id": pi.pk,
            "order_id": pi.order_id,
            "provider": pi.provider,
            "status": pi.status,
            "amount_lkr": str(pi.amount_lkr),
            "currency": pi.currency,
            "provider_intent_id": pi.provider_intent_id,
            "failure_code": pi.failure_code,
            "failure_message": pi.failure_message,
            "confirmed_at": _iso(pi.confirmed_at),
            "created_at": _iso(pi.created_at),
        }


def iter_export_sections(user) -> Iterator[tuple[str, Any]]:
    """Yield (section_key, value) for streaming / assembly.

    List sections yield iterators of row dicts; singleton sections yield a
    dict/None value.
    """
    yield "consents", _iter_consents(user)
    yield "audit_logs", _iter_audit_logs(user)
    yield "notification_preferences", _notification_preferences(user)
    yield "push_subscriptions", _iter_push_subscriptions(user)
    yield "mobile_push_devices", _iter_mobile_push_devices(user)
    yield "patient_profile", _patient_profile(user)
    yield "caregiver_profile", _caregiver_profile(user)
    yield "voice_intents", _iter_voice_intents(user)
    yield "dialogue_sessions", _iter_dialogue_sessions(user)
    yield "voice_turn_timings", _iter_voice_turn_timings(user)
    yield "health_metrics", _iter_health_metrics(user)
    yield "health_events", _iter_health_events(user)
    yield "medical_records", _iter_medical_records(user)
    yield "match_runs", _iter_match_runs(user)
    yield "interactions", _iter_interactions(user)
    yield "care_requests", _iter_care_requests(user)
    yield "care_relationships", _iter_care_relationships(user)
    yield "reviews", _iter_reviews(user)
    yield "shifts", _iter_shifts(user)
    yield "messages", _iter_messages(user)
    yield "orders", _iter_orders(user)
    yield "payment_intents", _iter_payment_intents(user)


def _materialize_section(value: Any) -> Any:
    if isinstance(value, Iterator):
        return list(value)
    return value


def build_user_export(user) -> dict[str, Any]:
    """Assemble a portable JSON snapshot of the caller's personal data."""
    payload: dict[str, Any] = {
        "exported_at": timezone.now().isoformat(),
        "schema_version": EXPORT_SCHEMA_VERSION,
        "user": {
            "id": user.pk,
            "email": user.email,
            "role": user.role,
            "date_joined": _iso(user.date_joined),
            "is_active": user.is_active,
            "erased_at": _iso(getattr(user, "erased_at", None)),
        },
    }
    for key, value in iter_export_sections(user):
        payload[key] = _materialize_section(value)
    return payload


def stream_user_export_json(user) -> Iterator[bytes]:
    """Stream a complete JSON object section-by-section (Step 105)."""
    enc = json.JSONEncoder(ensure_ascii=False, separators=(",", ":"))
    yield b"{"
    yield f'"exported_at":{enc.encode(timezone.now().isoformat())}'.encode()
    yield f',"schema_version":{EXPORT_SCHEMA_VERSION}'.encode()
    user_obj = {
        "id": user.pk,
        "email": user.email,
        "role": user.role,
        "date_joined": _iso(user.date_joined),
        "is_active": user.is_active,
        "erased_at": _iso(getattr(user, "erased_at", None)),
    }
    yield b',"user":'
    yield enc.encode(user_obj).encode()

    for key, value in iter_export_sections(user):
        yield f',"{key}":'.encode()
        if isinstance(value, dict) or value is None or isinstance(value, (str, int, float, bool)):
            yield enc.encode(value).encode()
            continue
        # Iterator of rows
        yield b"["
        first = True
        for row in value:
            if not first:
                yield b","
            first = False
            yield enc.encode(row).encode()
        yield b"]"
    yield b"}"


def render_export_pdf(payload: dict[str, Any]) -> bytes:
    """Render a compact PDF summary of the export payload (reportlab)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 48
    c.setFont("Helvetica-Bold", 14)
    c.drawString(48, y, "Care Plus — Personal data export")
    y -= 22
    c.setFont("Helvetica", 10)
    user = payload.get("user") or {}
    list_keys = [
        "consents",
        "audit_logs",
        "voice_intents",
        "dialogue_sessions",
        "voice_turn_timings",
        "health_metrics",
        "health_events",
        "medical_records",
        "match_runs",
        "interactions",
        "care_requests",
        "care_relationships",
        "reviews",
        "shifts",
        "messages",
        "orders",
        "payment_intents",
        "push_subscriptions",
        "mobile_push_devices",
    ]
    lines = [
        f"Exported at: {payload.get('exported_at')}",
        f"Schema version: {payload.get('schema_version')}",
        f"User id: {user.get('id')}  Role: {user.get('role')}",
        f"Email: {user.get('email')}",
        "",
    ]
    for key in list_keys:
        lines.append(f"{key.replace('_', ' ').title()}: {len(payload.get(key) or [])}")
    lines.extend(
        [
            "",
            "Full machine-readable copy is available via format=json.",
            "Sensitive fields are included for the account owner only.",
        ]
    )
    for line in lines:
        if y < 64:
            c.showPage()
            y = height - 48
            c.setFont("Helvetica", 10)
        c.drawString(48, y, line[:110])
        y -= 14

    c.showPage()
    y = height - 48
    c.setFont("Helvetica-Bold", 12)
    c.drawString(48, y, "JSON appendix (truncated)")
    y -= 18
    c.setFont("Courier", 7)
    blob = json.dumps(payload, ensure_ascii=False, indent=2)
    for line in blob.splitlines()[:120]:
        if y < 40:
            c.showPage()
            y = height - 48
            c.setFont("Courier", 7)
        c.drawString(40, y, line[:120])
        y -= 9
    c.save()
    return buf.getvalue()


def _scrub_patient_profile(user) -> None:
    profile = getattr(user, "patient_profile", None)
    if profile is None:
        return
    profile.display_name = "Erased"
    profile.location = None
    profile.city = ""
    profile.languages = []
    profile.conditions = []
    profile.medications = []
    profile.allergies = []
    profile.height_cm = None
    profile.weight_kg = None
    profile.blood_type = ""
    profile.emergency_contact_name = ""
    profile.emergency_contact_phone = ""
    profile.save()


def _scrub_caregiver_profile(user) -> bool:
    """Returns True if FAISS rebuild is required."""
    profile = getattr(user, "caregiver_profile", None)
    if profile is None:
        return False
    profile.display_name = "Erased"
    profile.bio = ""
    profile.city = ""
    profile.nic_id = ""
    profile.certifications = []
    profile.specialties = []
    profile.languages = []
    profile.care_levels = []
    profile.certification_docs = []
    profile.embedding = []
    profile.is_active = False
    profile.is_available = False
    profile.is_approved = False
    profile.save()
    return True


def _wipe_medical_records(user) -> int:
    from apps.medical_records.models import MedicalRecord, MedicalRecordAttachment

    count = 0
    for record in MedicalRecord.objects.filter(patient=user):
        record.sensitive_notes = ""
        record.title = "Erased"
        record.description = ""
        if record.deleted_at is None:
            record.deleted_at = timezone.now()
        record.save(
            update_fields=[
                "sensitive_notes_ciphertext",
                "title",
                "description",
                "deleted_at",
                "updated_at",
            ]
        )
        for att in MedicalRecordAttachment.objects.filter(record=record):
            if att.file:
                att.file.delete(save=False)
            att.original_name = ""
            att.save(update_fields=["original_name", "file"])
        count += 1
    return count


@transaction.atomic
def erase_user_account(*, user, password: str, request=None) -> dict[str, Any]:
    """Right-to-erasure: deactivate, anonymize, wipe PHI, evict FAISS if caregiver."""
    if getattr(user, "erased_at", None):
        raise ValidationError("Account already erased.")
    if user.role in (Role.ADMIN, Role.AUDITOR):
        raise ValidationError("Admin/auditor accounts cannot self-erase; contact ops.")

    if not password or not user.check_password(password):
        raise AuthenticationFailed("Password confirmation failed.")

    from apps.health_monitoring.models import HealthEvent, HealthMetric
    from apps.matching.models import CareRequest, Interaction, MatchRun
    from apps.messaging.models import Message
    from apps.voice.models import DialogueSession, VoiceIntent, VoiceTurnTiming

    stats = {
        "voice_intents": VoiceIntent.objects.filter(user=user).count(),
        "dialogue_sessions": DialogueSession.objects.filter(user=user).count(),
        "voice_turn_timings": VoiceTurnTiming.objects.filter(user=user).count(),
        "health_metrics": HealthMetric.objects.filter(patient=user).count(),
        "health_events": HealthEvent.objects.filter(patient=user).count(),
    }

    VoiceIntent.objects.filter(user=user).delete()
    DialogueSession.objects.filter(user=user).delete()
    VoiceTurnTiming.objects.filter(user=user).delete()
    HealthMetric.objects.filter(patient=user).delete()
    HealthEvent.objects.filter(patient=user).delete()
    Interaction.objects.filter(patient=user).delete()
    Message.objects.filter(sender=user).update(body="[erased]")
    CareRequest.objects.filter(patient=user).update(message="")
    for run in MatchRun.objects.filter(user=user):
        run.query = ""
        run.condition = ""
        run.save(update_fields=["query_ciphertext", "condition_ciphertext"])

    medical_wiped = _wipe_medical_records(user)
    stats["medical_records"] = medical_wiped

    PushSubscription.objects.filter(user=user).delete()
    MobilePushDevice.objects.filter(user=user).delete()
    NotificationPreference.objects.filter(user=user).delete()

    _scrub_patient_profile(user)
    needs_faiss = _scrub_caregiver_profile(user)

    try:
        from apps.leads.models import Lead

        Lead.objects.filter(email__iexact=user.email).update(
            name="Erased",
            email=f"erased+lead-{user.pk}@deleted.local",
            phone="",
            message="",
        )
    except Exception:
        pass

    original_email = user.email
    user.email = f"erased+{user.pk}@deleted.local"
    user.first_name = ""
    user.last_name = ""
    user.is_active = False
    user.erased_at = timezone.now()
    user.set_unusable_password()
    user.save(
        update_fields=[
            "email",
            "first_name",
            "last_name",
            "is_active",
            "erased_at",
            "password",
        ]
    )

    faiss_rebuilt = False
    if needs_faiss:
        from apps.matching.faiss_index import evict_caregiver_from_index

        profile = user.caregiver_profile
        evict_caregiver_from_index(profile.pk)
        faiss_rebuilt = True

    record_audit(
        actor=user,
        action=AuditAction.REQUEST_ERASURE,
        request=request,
        target_type="user",
        target_id=user.pk,
        metadata={
            "original_email_domain": original_email.split("@")[-1] if "@" in original_email else "",
            "stats": stats,
            "faiss_rebuilt": faiss_rebuilt,
        },
        async_=False,
    )
    return {
        "erased": True,
        "user_id": user.pk,
        "erased_at": user.erased_at.isoformat(),
        "faiss_rebuilt": faiss_rebuilt,
        "stats": stats,
    }


def purge_erased_accounts(*, older_than_days: int = 30) -> dict[str, int]:
    """Hard-delete residual PHI rows for accounts erased longer than N days.

    Keeps the anonymized User + AuditLog rows (actor PROTECT).
    """
    from django.contrib.auth import get_user_model

    from apps.health_monitoring.models import HealthEvent, HealthMetric
    from apps.voice.models import DialogueSession, VoiceIntent, VoiceTurnTiming

    User = get_user_model()
    cutoff = timezone.now() - timedelta(days=max(1, older_than_days))
    erased_ids = list(
        User.objects.filter(erased_at__isnull=False, erased_at__lte=cutoff).values_list(
            "id", flat=True
        )
    )
    if not erased_ids:
        return {
            "users": 0,
            "voice_intents": 0,
            "dialogue_sessions": 0,
            "voice_turn_timings": 0,
            "health_metrics": 0,
            "health_events": 0,
        }

    vi = VoiceIntent.objects.filter(user_id__in=erased_ids).delete()[0]
    ds = DialogueSession.objects.filter(user_id__in=erased_ids).delete()[0]
    vt = VoiceTurnTiming.objects.filter(user_id__in=erased_ids).delete()[0]
    hm = HealthMetric.objects.filter(patient_id__in=erased_ids).delete()[0]
    he = HealthEvent.objects.filter(patient_id__in=erased_ids).delete()[0]
    return {
        "users": len(erased_ids),
        "voice_intents": vi,
        "dialogue_sessions": ds,
        "voice_turn_timings": vt,
        "health_metrics": hm,
        "health_events": he,
    }

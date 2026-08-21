"""PDPA data export + right-to-erasure (Step 69)."""

from __future__ import annotations

import io
import json
from datetime import timedelta
from typing import Any

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


def _iso(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def build_user_export(user) -> dict[str, Any]:
    """Assemble a portable JSON snapshot of the caller's personal data."""
    payload: dict[str, Any] = {
        "exported_at": timezone.now().isoformat(),
        "schema_version": 1,
        "user": {
            "id": user.pk,
            "email": user.email,
            "role": user.role,
            "date_joined": _iso(user.date_joined),
            "is_active": user.is_active,
            "erased_at": _iso(getattr(user, "erased_at", None)),
        },
        "consents": [],
        "patient_profile": None,
        "caregiver_profile": None,
        "voice_intents": [],
        "dialogue_sessions": [],
        "health_metrics": [],
        "health_events": [],
        "medical_records": [],
        "match_runs": [],
        "care_requests": [],
        "messages": [],
        "notification_preferences": None,
    }

    from apps.accounts.models import ConsentLog

    for row in ConsentLog.objects.filter(user=user).order_by("-ts")[:100]:
        payload["consents"].append(
            {
                "scope": row.scope,
                "granted": row.granted,
                "ts": _iso(row.ts),
            }
        )

    pref = NotificationPreference.objects.filter(user=user).first()
    if pref:
        payload["notification_preferences"] = pref.channels

    patient = getattr(user, "patient_profile", None)
    if patient is not None:
        payload["patient_profile"] = {
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

    caregiver = getattr(user, "caregiver_profile", None)
    if caregiver is not None:
        payload["caregiver_profile"] = {
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
        }

    from apps.voice.models import DialogueSession, VoiceIntent

    for intent in VoiceIntent.objects.filter(user=user).order_by("-ts")[:200]:
        payload["voice_intents"].append(
            {
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
        )

    for session in DialogueSession.objects.filter(user=user).order_by("-updated_at")[:50]:
        payload["dialogue_sessions"].append(
            {
                "id": session.pk,
                "lang": session.lang,
                "active": session.active,
                "intent_chips": session.intent_chips,
                "open_questions": session.open_questions,
                "route_history": session.route_history,
                "turns": session.turns,
                "updated_at": _iso(session.updated_at),
            }
        )

    from apps.health_monitoring.models import HealthEvent, HealthMetric

    for metric in HealthMetric.objects.filter(patient=user).order_by("-recorded_at")[:500]:
        payload["health_metrics"].append(
            {
                "id": metric.pk,
                "kind": metric.kind,
                "value": metric.value,
                "unit": metric.unit,
                "source": metric.source,
                "recorded_at": _iso(metric.recorded_at),
                "metadata": metric.metadata,
            }
        )

    for event in HealthEvent.objects.filter(patient=user).order_by("-created_at")[:200]:
        payload["health_events"].append(
            {
                "id": event.pk,
                "event_type": event.event_type,
                "kind": event.kind,
                "rule_key": event.rule_key,
                "severity": event.severity,
                "sample_count": event.sample_count,
                "payload": event.payload,
                "created_at": _iso(event.created_at),
            }
        )

    from apps.medical_records.models import MedicalRecord

    for record in MedicalRecord.objects.filter(patient=user).order_by("-created_at")[:200]:
        payload["medical_records"].append(
            {
                "id": record.pk,
                "title": record.title,
                "description": record.description,
                "condition_slug": record.condition.slug if record.condition_id else "",
                "sensitive_notes": record.sensitive_notes,
                "recorded_at": str(record.recorded_at) if record.recorded_at else None,
                "deleted_at": _iso(record.deleted_at),
            }
        )

    from apps.matching.models import CareRequest, MatchResult, MatchRun

    for run in MatchRun.objects.filter(user=user, deleted_at__isnull=True).order_by(
        "-created_at"
    )[:100]:
        payload["match_runs"].append(
            {
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
                "filters": run.filters or {},
                "request_id": run.request_id,
                "created_at": _iso(run.created_at),
                "results": [
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
                    }
                    for hit in MatchResult.objects.filter(run=run).order_by("rank")
                ],
            }
        )

    for req in CareRequest.objects.filter(patient=user).order_by("-created_at")[:100]:
        payload["care_requests"].append(
            {
                "id": req.pk,
                "status": req.status,
                "message": req.message,
                "created_at": _iso(req.created_at),
            }
        )

    from apps.messaging.models import Message

    for msg in Message.objects.filter(sender=user).order_by("-created_at")[:300]:
        payload["messages"].append(
            {
                "id": msg.pk,
                "thread_id": msg.thread_id,
                "body": msg.body,
                "created_at": _iso(msg.created_at),
            }
        )

    return payload


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
    lines = [
        f"Exported at: {payload.get('exported_at')}",
        f"User id: {user.get('id')}  Role: {user.get('role')}",
        f"Email: {user.get('email')}",
        "",
        f"Consents: {len(payload.get('consents') or [])}",
        f"Voice intents: {len(payload.get('voice_intents') or [])}",
        f"Dialogue sessions: {len(payload.get('dialogue_sessions') or [])}",
        f"Health metrics: {len(payload.get('health_metrics') or [])}",
        f"Health events: {len(payload.get('health_events') or [])}",
        f"Medical records: {len(payload.get('medical_records') or [])}",
        f"Match runs: {len(payload.get('match_runs') or [])}",
        f"Care requests: {len(payload.get('care_requests') or [])}",
        f"Messages: {len(payload.get('messages') or [])}",
        "",
        "Full machine-readable copy is available via format=json.",
        "Sensitive fields are included for the account owner only.",
    ]
    for line in lines:
        if y < 64:
            c.showPage()
            y = height - 48
            c.setFont("Helvetica", 10)
        c.drawString(48, y, line[:110])
        y -= 14

    # Append a truncated JSON appendix for auditors / portability.
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

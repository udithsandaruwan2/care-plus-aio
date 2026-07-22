"""Message thread access, send, and read receipts (Step 38)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Role
from apps.matching.models import CareRelationship, CareRelationshipStatus

from .models import Message, MessageThread


def _participant_user_ids(rel: CareRelationship) -> tuple[int, int]:
    return rel.patient_id, rel.caregiver.user_id


def can_access_thread(user, thread: MessageThread) -> bool:
    rel = thread.relationship
    if rel.status != CareRelationshipStatus.ACTIVE:
        return False
    patient_id, caregiver_user_id = _participant_user_ids(rel)
    return user.pk in (patient_id, caregiver_user_id)


def get_thread_for_user(user, thread_id: int) -> MessageThread:
    try:
        thread = MessageThread.objects.select_related(
            "relationship",
            "relationship__caregiver",
            "relationship__caregiver__user",
            "relationship__patient",
        ).get(pk=thread_id)
    except MessageThread.DoesNotExist as exc:
        raise ValidationError("Message thread not found.") from exc
    if not can_access_thread(user, thread):
        raise PermissionDenied("You cannot access this message thread.")
    return thread


def get_or_create_thread_for_relationship(rel: CareRelationship) -> MessageThread:
    if rel.status != CareRelationshipStatus.ACTIVE:
        raise ValidationError("Messaging is only available for active care relationships.")
    thread, _ = MessageThread.objects.get_or_create(relationship=rel)
    return thread


def current_thread_for_user(user) -> MessageThread | None:
    qs = CareRelationship.objects.select_related(
        "caregiver",
        "caregiver__user",
        "patient",
        "patient__patient_profile",
    ).filter(status=CareRelationshipStatus.ACTIVE, is_primary=True)
    role = getattr(user, "role", None)
    if role == Role.PATIENT:
        rel = qs.filter(patient=user).first()
    elif role == Role.CAREGIVER:
        rel = qs.filter(caregiver__user=user).first()
    else:
        return None
    if rel is None:
        return None
    return get_or_create_thread_for_relationship(rel)


@transaction.atomic
def send_message(*, thread: MessageThread, sender, body: str) -> Message:
    if not can_access_thread(sender, thread):
        raise PermissionDenied("You cannot send messages in this thread.")
    text = (body or "").strip()
    if not text:
        raise ValidationError("Message body cannot be empty.")
    if len(text) > 4000:
        raise ValidationError("Message is too long (max 4000 characters).")
    return Message.objects.create(thread=thread, sender=sender, body=text)


@transaction.atomic
def mark_messages_read(*, thread: MessageThread, reader, last_read_message_id: int) -> int:
    if not can_access_thread(reader, thread):
        raise PermissionDenied("You cannot access this message thread.")
    try:
        anchor = Message.objects.get(pk=last_read_message_id, thread=thread)
    except Message.DoesNotExist as exc:
        raise ValidationError("Message not found in this thread.") from exc

    now = timezone.now()
    updated = (
        Message.objects.filter(
            thread=thread,
            created_at__lte=anchor.created_at,
            read_at__isnull=True,
        )
        .exclude(sender=reader)
        .update(read_at=now)
    )
    return updated

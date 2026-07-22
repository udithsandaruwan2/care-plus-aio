"""In-app messaging between patient and caregiver (Step 38)."""

from django.conf import settings
from django.db import models


class MessageThread(models.Model):
    """One thread per active care relationship."""

    relationship = models.OneToOneField(
        "matching.CareRelationship",
        on_delete=models.CASCADE,
        related_name="message_thread",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"MessageThread#{self.pk} rel={self.relationship_id}"


class Message(models.Model):
    """Text message within a care relationship thread."""

    thread = models.ForeignKey(
        MessageThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="messages_sent",
    )
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=["thread", "created_at"], name="msg_thread_created_idx"),
        ]

    def __str__(self):
        return f"Message#{self.pk} thread={self.thread_id} sender={self.sender_id}"

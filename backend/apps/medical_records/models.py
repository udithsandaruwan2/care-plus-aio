"""MedicalRecord models with encrypted sensitive fields (Step 34)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .encryption import decrypt_field, encrypt_field


class MedicalRecord(models.Model):
    """Patient-owned clinical note linked to a canonical condition term."""

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="medical_records",
    )
    condition = models.ForeignKey(
        "vocab.ConditionTerm",
        on_delete=models.PROTECT,
        related_name="medical_records",
        limit_choices_to={"active": True},
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    sensitive_notes_ciphertext = models.TextField(blank=True, default="")
    recorded_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-recorded_at", "-created_at")
        indexes = [
            models.Index(fields=["patient", "-created_at"], name="mr_patient_created_idx"),
        ]

    def __str__(self):
        return f"MedicalRecord#{self.pk} {self.title} (patient={self.patient_id})"

    @property
    def sensitive_notes(self) -> str:
        return decrypt_field(self.sensitive_notes_ciphertext)

    @sensitive_notes.setter
    def sensitive_notes(self, value: str) -> None:
        self.sensitive_notes_ciphertext = encrypt_field(value or "")


class MedicalRecordAttachment(models.Model):
    """Attachment stub — upload APIs ship in Step 35."""

    record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="medical_records/%Y/%m/", blank=True)
    original_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=128, blank=True, default="")
    size_bytes = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at",)

    def __str__(self):
        return f"Attachment#{self.pk} for record {self.record_id}"

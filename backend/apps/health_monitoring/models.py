"""Timeseries health metrics for monitoring and alerts (Step 45).

Step 68: free-form metadata / event payloads are encrypted at rest.
Numeric vitals stay plaintext so Timescale aggregations and anomaly rules work.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.encryption import decrypt_json, encrypt_json


class HealthMetricKind(models.TextChoices):
    HEART_RATE = "heart_rate", "Heart rate"
    BLOOD_GLUCOSE = "blood_glucose", "Blood glucose"
    SPO2 = "spo2", "SpO2"


class HealthEventType(models.TextChoices):
    HEALTH_CRITICAL = "health_critical", "Health critical"


class HealthMetric(models.Model):
    """One physiological metric sample at a point in time."""

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="health_metrics",
    )
    kind = models.CharField(max_length=32, choices=HealthMetricKind.choices, db_index=True)
    value = models.FloatField()
    unit = models.CharField(max_length=24, blank=True, default="")
    source = models.CharField(max_length=64, blank=True, default="manual")
    recorded_at = models.DateTimeField(db_index=True)
    metadata_ciphertext = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-recorded_at",)
        indexes = [
            models.Index(fields=["patient", "kind", "-recorded_at"], name="hm_patient_kind_ts_idx"),
            models.Index(fields=["kind", "-recorded_at"], name="hm_kind_ts_idx"),
        ]

    def __str__(self):
        return f"HealthMetric#{self.pk} patient={self.patient_id} {self.kind}={self.value}"

    @property
    def metadata(self) -> dict:
        return decrypt_json(self.metadata_ciphertext, default={})

    @metadata.setter
    def metadata(self, value: dict | None) -> None:
        self.metadata_ciphertext = encrypt_json(value or {})


class HealthEvent(models.Model):
    """Detected health monitoring event (Step 46 rules daemon)."""

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="health_events",
    )
    event_type = models.CharField(
        max_length=32,
        choices=HealthEventType.choices,
        default=HealthEventType.HEALTH_CRITICAL,
        db_index=True,
    )
    kind = models.CharField(max_length=32, choices=HealthMetricKind.choices, db_index=True)
    rule_key = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=24, blank=True, default="critical")
    window_start = models.DateTimeField()
    window_end = models.DateTimeField(db_index=True)
    sample_count = models.PositiveIntegerField(default=0)
    handled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    rematch_run = models.ForeignKey(
        "matching.MatchRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="health_events",
    )
    payload_ciphertext = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["patient", "event_type", "-created_at"], name="he_patient_type_ts_idx"),
            models.Index(fields=["kind", "rule_key", "-created_at"], name="he_kind_rule_ts_idx"),
        ]

    def __str__(self):
        return f"HealthEvent#{self.pk} patient={self.patient_id} {self.event_type} {self.rule_key}"

    @property
    def payload(self) -> dict:
        return decrypt_json(self.payload_ciphertext, default={})

    @payload.setter
    def payload(self, value: dict | None) -> None:
        self.payload_ciphertext = encrypt_json(value or {})

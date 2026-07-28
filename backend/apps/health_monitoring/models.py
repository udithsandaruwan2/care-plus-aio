"""Timeseries health metrics for monitoring and alerts (Step 45)."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class HealthMetricKind(models.TextChoices):
    HEART_RATE = "heart_rate", "Heart rate"
    BLOOD_GLUCOSE = "blood_glucose", "Blood glucose"
    SPO2 = "spo2", "SpO2"


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
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-recorded_at",)
        indexes = [
            models.Index(fields=["patient", "kind", "-recorded_at"], name="hm_patient_kind_ts_idx"),
            models.Index(fields=["kind", "-recorded_at"], name="hm_kind_ts_idx"),
        ]

    def __str__(self):
        return f"HealthMetric#{self.pk} patient={self.patient_id} {self.kind}={self.value}"


"""Periodic anomaly detection tasks (Step 46)."""

from celery import shared_task


@shared_task(name="health_monitoring.detect_health_anomalies")
def detect_health_anomalies() -> dict:
    from .services import detect_glucose_anomalies

    events = detect_glucose_anomalies()
    return {"created": len(events)}


"""Periodic anomaly detection tasks (Step 46)."""

from celery import shared_task


@shared_task(name="health_monitoring.detect_health_anomalies")
def detect_health_anomalies() -> dict:
    from .services import detect_glucose_anomalies

    events = detect_glucose_anomalies()
    dispatched = 0
    for event in events:
        if event.event_type != "health_critical" or event.handled_at is not None:
            continue
        from apps.matching.emergency import emergency_rematch_for_health_event

        out = emergency_rematch_for_health_event(event)
        if out.get("created"):
            dispatched += 1
    return {"created": len(events), "dispatched": dispatched}


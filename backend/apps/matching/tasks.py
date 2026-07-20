"""Celery tasks for offline CF training + care-request lifecycle."""

from celery import shared_task


@shared_task(name="matching.train_cf_model")
def train_cf_model() -> dict:
    """Nightly ALS retrain on the interaction log."""
    from .cf_train import train_cf_als

    return train_cf_als()


@shared_task(name="matching.expire_care_requests")
def expire_care_requests() -> dict:
    """Hourly sweep: pending requests past expires_at → expired (+ notify)."""
    from .care_requests import expire_stale_care_requests

    count = expire_stale_care_requests()
    return {"expired": count}


@shared_task(name="matching.remind_care_requests")
def remind_care_requests() -> dict:
    """Hourly sweep: mid-TTL reminders for still-pending requests."""
    from .care_request_lifecycle import send_pending_care_request_reminders

    count = send_pending_care_request_reminders()
    return {"reminded": count}

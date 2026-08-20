"""Celery tasks for offline CF training + care-request lifecycle."""

from celery import shared_task


@shared_task(name="matching.train_cf_model")
def train_cf_model(force: bool = False) -> dict:
    """Nightly ALS retrain on the interaction log (gated promotion — Step 91)."""
    from .cf_train import train_cf_als

    return train_cf_als(force=bool(force))


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


@shared_task(name="matching.recompute_caregiver_trust")
def recompute_caregiver_trust(caregiver_id: int) -> dict:
    """Recompute one caregiver trust score after review moderation."""
    from .trust import recompute_caregiver_trust as recompute_one

    return recompute_one(caregiver_id)


@shared_task(name="matching.recompute_all_caregiver_trust")
def recompute_all_caregiver_trust() -> dict:
    """Batch recompute trust scores for all caregivers."""
    from .trust import recompute_all_caregiver_trust as recompute_all

    return recompute_all()


@shared_task(name="matching.refresh_caregiver_embedding")
def refresh_caregiver_embedding(caregiver_id: int) -> dict:
    """Re-embed one caregiver and rebuild FAISS (Step 89)."""
    from .faiss_index import refresh_caregiver_embedding as refresh_one

    return refresh_one(int(caregiver_id))


@shared_task(name="matching.rebuild_caregiver_index_if_stale")
def rebuild_caregiver_index_if_stale(force: bool = False) -> dict:
    """Periodic consistency rebuild — no-op when membership unchanged (Step 89)."""
    from .faiss_index import rebuild_index_if_stale

    return rebuild_index_if_stale(force=bool(force))

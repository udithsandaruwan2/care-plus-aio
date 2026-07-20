"""Celery tasks for offline CF training (Step 21)."""

from celery import shared_task


@shared_task(name="matching.train_cf_model")
def train_cf_model() -> dict:
    """Nightly ALS retrain on the interaction log."""
    from .cf_train import train_cf_als

    return train_cf_als()

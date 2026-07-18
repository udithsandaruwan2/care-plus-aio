"""Celery application (Redis broker + result backend — lean profile)."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "careplus.settings.dev")

app = Celery("careplus")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Smoke-test task; logs its own request context."""
    print(f"[celery] debug_task ran — request id={self.request.id}")
    return "ok"

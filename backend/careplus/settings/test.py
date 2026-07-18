"""Test settings — Celery runs inline so audit tasks write in the same process."""

from .dev import *  # noqa: F401,F403

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

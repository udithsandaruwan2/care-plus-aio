from django.db import models  # noqa: F401 — migrations discover models via AppConfig

from .idempotency import IdempotencyRecord, IdempotencyScope  # noqa: F401

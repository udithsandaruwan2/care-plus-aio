"""Redis distributed lock helpers (Step 51 Redlock-style booking)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import redis
from django.conf import settings
from rest_framework.exceptions import APIException


class LockUnavailable(APIException):
    status_code = 503
    default_detail = "Scheduling lock unavailable. Try again shortly."
    default_code = "lock_unavailable"


class LockNotAcquired(APIException):
    status_code = 409
    default_detail = "Could not acquire scheduling lock. Try again."
    default_code = "lock_not_acquired"


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)


@contextmanager
def redis_lock(
    key: str,
    *,
    timeout: float = 10.0,
    blocking_timeout: float = 5.0,
) -> Iterator[None]:
    """
    Acquire a Redis mutex for `key` (SET NX EX style via redis-py Lock).

    Used to serialize caregiver schedule mutations so concurrent bookings
    cannot both commit overlapping shifts.
    """
    try:
        client = redis_client()
        client.ping()
    except Exception as exc:  # noqa: BLE001 — surface as API 503
        raise LockUnavailable() from exc

    lock = client.lock(
        name=f"careplus:lock:{key}",
        timeout=timeout,
        blocking_timeout=blocking_timeout,
        thread_local=False,
    )
    acquired = lock.acquire(blocking=True)
    if not acquired:
        raise LockNotAcquired()
    try:
        yield
    finally:
        try:
            lock.release()
        except redis.exceptions.LockError:
            # Lock expired or already released — safe to ignore.
            pass

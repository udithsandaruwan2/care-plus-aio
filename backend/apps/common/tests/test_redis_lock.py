"""Unit smoke for Redis lock helper (Step 71 / Step 51)."""

from django.test import TestCase, tag

from apps.common.redis_lock import redis_client, redis_lock


@tag("load")
class RedisLockHelperTests(TestCase):
    def test_lock_roundtrip(self):
        client = redis_client()
        client.ping()
        key = "test:step71:lock"
        with redis_lock(key, timeout=5, blocking_timeout=2):
            # Nested acquire on same key should fail quickly if we used a second client
            # with short blocking — here we just assert the critical section runs.
            self.assertTrue(True)
        # Lock released — can re-acquire.
        with redis_lock(key, timeout=5, blocking_timeout=2):
            self.assertTrue(True)

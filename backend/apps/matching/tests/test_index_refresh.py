"""Step 89 — automatic FAISS refresh / stale no-op."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.accounts.models import Role
from apps.matching.faiss_index import (
    artifact_index_version,
    clear_index_dirty,
    expected_index_version,
    is_index_dirty,
    mark_index_dirty,
    rebuild_index_if_stale,
    refresh_caregiver_embedding,
    reset_cache,
)
from apps.matching.index_refresh import embed_fingerprint, maybe_enqueue_embedding_refresh
from apps.matching.models import CaregiverProfile

User = get_user_model()


@override_settings(
    EMBEDDING_BACKEND="hash",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class IndexRefreshTests(TestCase):
    def setUp(self):
        cache.clear()
        clear_index_dirty()
        reset_cache()
        self.user = User.objects.create_user(
            email="idx.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        self.profile = CaregiverProfile.objects.create(
            user=self.user,
            display_name="Index Tester",
            location=Point(79.86, 6.93, srid=4326),
            specialties=["Diabetes"],
            languages=["English"],
            care_levels=["intermediate"],
            is_active=True,
            is_available=True,
            is_approved=True,
        )

    def test_refresh_updates_embedding_and_version(self):
        first = refresh_caregiver_embedding(self.profile.pk)
        self.assertTrue(first["ok"])
        self.profile.refresh_from_db()
        self.assertEqual(len(self.profile.embedding), 768)

        self.profile.specialties = ["Hypertension"]
        self.profile.save(update_fields=["specialties", "updated_at"])
        second = refresh_caregiver_embedding(self.profile.pk)
        self.assertTrue(second["ok"])
        self.assertEqual(second["action"], "upsert")
        self.profile.refresh_from_db()
        # Hash embedder is deterministic on text — specialty change must change vector.
        self.assertTrue(any(x != 0 for x in self.profile.embedding))

    def test_rebuild_if_stale_noops_when_unchanged(self):
        refresh_caregiver_embedding(self.profile.pk)
        clear_index_dirty()
        reset_cache()
        out = rebuild_index_if_stale(force=False)
        self.assertFalse(out["rebuilt"])
        self.assertEqual(out["reason"], "unchanged")
        self.assertEqual(out["version"], expected_index_version())
        self.assertEqual(out["version"], artifact_index_version())

    def test_dirty_flag_forces_rebuild(self):
        refresh_caregiver_embedding(self.profile.pk)
        mark_index_dirty()
        self.assertTrue(is_index_dirty())
        out = rebuild_index_if_stale(force=False)
        self.assertTrue(out["rebuilt"])
        self.assertEqual(out["reason"], "dirty")
        self.assertFalse(is_index_dirty())

    def test_maybe_enqueue_skips_when_fingerprint_unchanged(self):
        before = embed_fingerprint(self.profile)
        # No specialty change.
        queued = maybe_enqueue_embedding_refresh(before, self.profile)
        self.assertFalse(queued)
        self.profile.specialties = ["Stroke"]
        self.profile.save(update_fields=["specialties"])
        self.profile.refresh_from_db()
        queued = maybe_enqueue_embedding_refresh(before, self.profile)
        self.assertTrue(queued)

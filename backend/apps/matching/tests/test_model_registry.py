"""Step 88 — ModelVersion registry."""

from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Role
from apps.matching.model_registry import active_model, register_model_version, resolve_model_version
from apps.matching.models import ModelKind, ModelVersion, create_match_run

User = get_user_model()


class ModelRegistryTests(TestCase):
    def test_register_activates_exactly_one_per_kind(self):
        a = register_model_version(
            kind=ModelKind.CF,
            version="20260101000000",
            rows_trained_on=10,
            metrics={"ndcg": 0.1},
            artifact_path="/tmp/v1",
        )
        b = register_model_version(
            kind=ModelKind.CF,
            version="20260102000000",
            rows_trained_on=20,
            metrics={"ndcg": 0.2},
            artifact_path="/tmp/v2",
        )
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertFalse(a.is_active)
        self.assertTrue(b.is_active)
        self.assertEqual(active_model(ModelKind.CF).pk, b.pk)
        self.assertEqual(
            ModelVersion.objects.filter(kind=ModelKind.CF, is_active=True).count(), 1
        )

    def test_kinds_activate_independently(self):
        register_model_version(kind=ModelKind.CF, version="cf1", rows_trained_on=1)
        register_model_version(kind=ModelKind.FAISS, version="hash:1:abc", rows_trained_on=5)
        self.assertTrue(active_model(ModelKind.CF).is_active)
        self.assertTrue(active_model(ModelKind.FAISS).is_active)

    def test_match_run_resolves_model_fks(self):
        cf = register_model_version(kind=ModelKind.CF, version="cf-resolve", rows_trained_on=3)
        faiss = register_model_version(
            kind=ModelKind.FAISS, version="hash:2:deadbeef", rows_trained_on=2
        )
        user = User.objects.create_user(
            email="mv.patient@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        run = create_match_run(
            user=user,
            query="need nurse",
            cf_version="cf-resolve",
            index_version="hash:2:deadbeef",
        )
        self.assertEqual(run.cf_model_id, cf.pk)
        self.assertEqual(run.faiss_model_id, faiss.pk)
        self.assertEqual(resolve_model_version(ModelKind.CF, "cf-resolve").pk, cf.pk)

    def test_register_parses_iso_trained_at(self):
        row = register_model_version(
            kind=ModelKind.SLOT_CLASSIFIER,
            version="slot-v1",
            trained_at="2026-08-20T12:00:00+00:00",
            activate=False,
        )
        self.assertFalse(row.is_active)
        self.assertEqual(row.trained_at, datetime(2026, 8, 20, 12, 0, tzinfo=UTC))

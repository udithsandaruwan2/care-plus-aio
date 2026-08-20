"""Step 90 — Replay evaluation harness metrics + eval_ranking command."""

from __future__ import annotations

import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.matching.cf_eval import (
    catalogue_coverage,
    evaluate_ranking,
    exposure_gini,
    holdout_bounds,
    precision_at_k,
    recall_at_k,
    relevance_for_run,
)
from apps.matching.cf_model import StubCFModel, reset_cf_cache
from apps.matching.engine import match_run_provenance, run_match
from apps.matching.faiss_index import reset_cache
from apps.matching.interactions import log_interaction
from apps.matching.models import (
    CaregiverProfile,
    InteractionKind,
    MatchResult,
    MatchRun,
    PatientProfile,
    create_match_run,
)

User = get_user_model()


class MetricUnitTests(SimpleTestCase):
    def test_precision_at_k(self):
        labels = {1: 5.0, 2: 0.0, 3: 5.0}
        self.assertAlmostEqual(precision_at_k(labels, [1, 2, 3], 2), 0.5)
        self.assertAlmostEqual(precision_at_k(labels, [1, 3, 2], 2), 1.0)
        self.assertEqual(precision_at_k(labels, [], 5), 0.0)

    def test_recall_at_k(self):
        labels = {1: 5.0, 3: 5.0}
        self.assertAlmostEqual(recall_at_k(labels, [1, 2, 4], 3), 0.5)
        self.assertAlmostEqual(recall_at_k(labels, [1, 3], 10), 1.0)

    def test_exposure_gini_equal_and_skewed(self):
        self.assertAlmostEqual(exposure_gini({1: 5, 2: 5, 3: 5}), 0.0, places=6)
        skewed = exposure_gini({1: 100, 2: 1, 3: 1})
        self.assertGreater(skewed, 0.5)

    def test_catalogue_coverage(self):
        self.assertAlmostEqual(catalogue_coverage([1, 1, 2], 4), 0.5)
        self.assertEqual(catalogue_coverage([], 10), 0.0)

    def test_holdout_bounds_are_causal_window(self):
        end = timezone.now()
        start, end2 = holdout_bounds(days=7, end=end)
        self.assertEqual(end2, end)
        self.assertAlmostEqual((end2 - start).total_seconds(), 7 * 86400, delta=1)


class RankingEvalIntegrationTests(TestCase):
    def setUp(self):
        reset_cache()
        reset_cf_cache()
        self.patient = User.objects.create_user(
            email="eval.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(
            user=self.patient,
            display_name="Eval Patient",
            location=Point(79.8612, 6.9271, srid=4326),
        )
        self.preferred = self._cg(
            "eval.pref@example.com",
            "Preferred",
            specialties=["diabetes"],
            lon=79.87,
            lat=6.94,
            trust=0.7,
        )
        self.alt = self._cg(
            "eval.alt@example.com",
            "Alt",
            specialties=["wound care"],
            lon=79.86,
            lat=6.93,
            trust=0.95,
        )

    def _cg(self, email, name, *, specialties, lon, lat, trust):
        user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
        return CaregiverProfile.objects.create(
            user=user,
            display_name=name,
            location=Point(lon, lat, srid=4326),
            certifications=["First Aid"],
            specialties=specialties,
            languages=["Sinhala"],
            care_levels=["intermediate"],
            trust_score=trust,
            bio=name,
            is_active=True,
            is_approved=True,
            is_available=True,
        )

    def _persist_match(self, tmp: str):
        with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash", CF_ENABLED=False):
            reset_cache()
            reset_cf_cache()
            call_command("build_caregiver_index", verbosity=0)
            out = run_match(
                condition="diabetes",
                language="Sinhala",
                care_level="intermediate",
                query="need diabetes caregiver",
                patient_id=self.patient.pk,
                longitude=79.86,
                latitude=6.93,
                top_k=5,
            )
            run = create_match_run(
                user=self.patient,
                query=out.query,
                condition="diabetes",
                language="Sinhala",
                care_level="intermediate",
                emergency=out.emergency,
                weights=list(out.weights),
                source="test",
                **match_run_provenance(out),
            )
            for rank, hit in enumerate(out.results, start=1):
                MatchResult.objects.create(
                    run=run,
                    caregiver_id=hit.caregiver_id,
                    rank=rank,
                    score=hit.score,
                    cbf=hit.cbf,
                    cf=hit.cf,
                    geo=hit.geo,
                    trust=hit.trust,
                    explanation=hit.explanation,
                    distance_m=hit.distance_m,
                )
            return run

    def test_relevance_uses_post_run_accepts(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._persist_match(tmp)
            log_interaction(self.patient, self.preferred, InteractionKind.ACCEPT)
            labels = relevance_for_run(run)
            self.assertIn(self.preferred.id, labels)
            self.assertGreater(labels[self.preferred.id], 0)

    def test_evaluate_ranking_and_command_are_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._persist_match(tmp)
            log_interaction(self.patient, self.preferred, InteractionKind.ACCEPT)

            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash", CF_ENABLED=False):
                reset_cache()
                a = evaluate_ranking(days=30, cf_model=StubCFModel())
                b = evaluate_ranking(days=30, cf_model=StubCFModel())

            self.assertGreaterEqual(a.n_runs, 1)
            self.assertGreaterEqual(a.n_labelled, 1)
            self.assertEqual(a.ndcg_at_5, b.ndcg_at_5)
            self.assertEqual(a.map_score, b.map_score)
            self.assertEqual(a.recall_at_10, b.recall_at_10)
            self.assertEqual(a.precision_at_5, b.precision_at_5)
            self.assertEqual(a.catalogue_coverage, b.catalogue_coverage)
            self.assertEqual(a.exposure_gini, b.exposure_gini)

            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash", CF_ENABLED=False):
                reset_cache()
                call_command("eval_ranking", "--days", "30", verbosity=0)

    def test_old_runs_outside_holdout_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._persist_match(tmp)
            MatchRun.objects.filter(pk=run.pk).update(
                created_at=timezone.now() - timedelta(days=60)
            )
            log_interaction(self.patient, self.preferred, InteractionKind.ACCEPT)
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash", CF_ENABLED=False):
                reset_cache()
                report = evaluate_ranking(days=7, cf_model=StubCFModel())
            self.assertEqual(report.n_runs, 0)
            self.assertEqual(report.n_labelled, 0)

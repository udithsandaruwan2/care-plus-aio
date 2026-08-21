"""Step 101 — learned fusion weights by segment."""

from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

import numpy as np
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.ahp import FACTORS, get_ahp_weights
from apps.matching.i18n import format_match_explanation
from apps.matching.models import (
    CaregiverProfile,
    Interaction,
    InteractionKind,
    MatchResult,
    PatientProfile,
    create_match_run,
)
from apps.matching.weights_train import (
    SegmentExample,
    fit_weights,
    get_fusion_weights,
    infer_geo_segment,
    reset_learned_weights_cache,
    train_fusion_weights,
    train_segment,
)

User = get_user_model()


class GeoSegmentTests(TestCase):
    def test_urban_rural_inference(self):
        self.assertEqual(infer_geo_segment("Colombo"), "urban")
        self.assertEqual(infer_geo_segment("Kandy"), "rural")
        self.assertIsNone(infer_geo_segment(""))
        self.assertIsNone(infer_geo_segment(None))


class LearnedWeightsUnitTests(TestCase):
    def test_sparse_segment_falls_back_to_ahp(self):
        prior = np.asarray(get_ahp_weights(), dtype=np.float64)
        fit = train_segment("routine_urban", [], force=False)
        self.assertEqual(fit.source, "ahp")
        self.assertEqual(fit.reason, "sparse")
        self.assertEqual(list(fit.vector), list(prior))

    def test_learned_beats_ahp_on_geo_labelled_holdout(self):
        # Synthetic: accepts always have high geo; AHP is CBF-heavy so learning
        # geo should improve NDCG on geo-labelled ranking.
        rng = np.random.default_rng(42)
        examples: list[SegmentExample] = []
        now = timezone.now()
        for i in range(24):
            # Four candidates: varying factors; caregiver 0 has high geo.
            feats = np.array(
                [
                    [0.2, 0.2, 0.95, 0.2],
                    [0.9, 0.2, 0.1, 0.2],
                    [0.5, 0.5, 0.2, 0.5],
                    [0.3, 0.8, 0.15, 0.4],
                ],
                dtype=np.float64,
            )
            feats += rng.normal(0, 0.01, size=feats.shape)
            examples.append(
                SegmentExample(
                    run_id=i + 1,
                    caregiver_ids=[10, 11, 12, 13],
                    features=feats,
                    labels={10: 5.0},  # geo-strong caregiver accepted
                    created_at=now - timedelta(hours=24 - i),
                )
            )

        prior = np.asarray(get_ahp_weights(), dtype=np.float64)
        with self.settings(WEIGHTS_MIN_SEGMENT_LABELS=8, WEIGHTS_PROMOTE_MARGIN=0.01):
            fit = train_segment("routine_urban", examples, force=False)
        self.assertEqual(fit.source, "learned")
        self.assertTrue(fit.promoted)
        self.assertGreaterEqual(fit.ndcg_learned, fit.ndcg_ahp + 0.01)

        # XAI still names a dominant factor under learned weights.
        row = np.array([0.2, 0.2, 0.95, 0.2])
        W = np.asarray(fit.vector)
        contributor = int(np.argmax(row * W))
        explanation = format_match_explanation(contributor, "en")
        self.assertIn("Matched because:", explanation)
        self.assertEqual(FACTORS[contributor], "geo")

    def test_fit_weights_increases_geo_mass(self):
        prior = np.asarray([0.5, 0.1, 0.2, 0.2], dtype=np.float64)
        examples = []
        now = timezone.now()
        for i in range(12):
            feats = np.array(
                [
                    [0.1, 0.1, 0.99, 0.1],
                    [0.99, 0.1, 0.05, 0.1],
                ],
                dtype=np.float64,
            )
            examples.append(
                SegmentExample(
                    run_id=i,
                    caregiver_ids=[1, 2],
                    features=feats,
                    labels={1: 5.0},
                    created_at=now,
                )
            )
        learned = fit_weights(examples, prior, epochs=60, lr=0.4)
        self.assertGreater(learned[2], prior[2])
        self.assertAlmostEqual(sum(learned), 1.0, places=5)


@override_settings(WEIGHTS_MIN_SEGMENT_LABELS=8, WEIGHTS_GATED_PROMOTION=True)
class LearnedWeightsPersistTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.weights_dir = Path(self.tmp.name) / "fusion"
        self.patient = User.objects.create_user(
            email="w.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(
            user=self.patient,
            display_name="Weights Patient",
            city="Colombo",
            location=Point(79.86, 6.93, srid=4326),
        )
        self.cgs = []
        for i in range(4):
            u = User.objects.create_user(
                email=f"w.cg{i}@example.com", password="pw-strong-123", role=Role.CAREGIVER
            )
            self.cgs.append(
                CaregiverProfile.objects.create(
                    user=u,
                    display_name=f"W CG {i}",
                    location=Point(79.86, 6.93, srid=4326),
                    specialties=["diabetes"],
                    languages=["English"],
                    care_levels=["intermediate"],
                    trust_score=0.8,
                    is_active=True,
                    is_approved=True,
                )
            )

    def _seed_labelled_runs(self, n: int = 16):
        now = timezone.now()
        for i in range(n):
            run = create_match_run(
                user=self.patient,
                condition="diabetes",
                language="English",
                care_level="intermediate",
                emergency=False,
                weights=list(get_ahp_weights()),
                weights_source="ahp",
                filters={"city": "Colombo", "top_k": 4},
                latency_ms=1,
                source="test",
            )
            # Backdate for ordered holdout split.
            MatchResult.objects.filter(run=run).delete()
            from apps.matching.models import MatchRun

            MatchRun.objects.filter(pk=run.pk).update(created_at=now - timedelta(hours=n - i))
            run.refresh_from_db()
            feats = [
                (0.2, 0.2, 0.95, 0.2),
                (0.9, 0.2, 0.1, 0.2),
                (0.4, 0.4, 0.3, 0.4),
                (0.3, 0.7, 0.2, 0.3),
            ]
            for rank, (cg, f) in enumerate(zip(self.cgs, feats), start=1):
                MatchResult.objects.create(
                    run=run,
                    caregiver=cg,
                    rank=rank,
                    score=sum(f) / 4,
                    cbf=f[0],
                    cf=f[1],
                    geo=f[2],
                    trust=f[3],
                    explanation="test",
                )
            # Accept the geo-strong caregiver after the run.
            ix = Interaction.objects.create(
                patient=self.patient,
                caregiver=self.cgs[0],
                kind=InteractionKind.ACCEPT,
                weight=5.0,
            )
            Interaction.objects.filter(pk=ix.pk).update(
                created_at=run.created_at + timedelta(minutes=1)
            )

    def test_train_promotes_routine_urban_and_loads(self):
        self._seed_labelled_runs(16)
        with self.settings(
            WEIGHTS_ARTIFACT_DIR=str(self.weights_dir),
            WEIGHTS_MIN_SEGMENT_LABELS=8,
            WEIGHTS_PROMOTE_MARGIN=0.01,
        ):
            reset_learned_weights_cache()
            summary = train_fusion_weights(force=False)
            self.assertGreaterEqual(summary["learned_count"], 1)
            self.assertEqual(
                summary["segments"]["routine_urban"]["source"],
                "learned",
            )
            # Unknown / sparse emergency_rural stays AHP.
            self.assertEqual(summary["segments"]["emergency_rural"]["source"], "ahp")

            vec, src = get_fusion_weights(emergency=False, city="Colombo", refresh=True)
            self.assertTrue(src.startswith("learned:"))
            self.assertAlmostEqual(sum(vec), 1.0, places=5)

            # Sparse city → still resolves rural/urban; empty city falls back.
            _, src_empty = get_fusion_weights(emergency=False, city="", refresh=True)
            self.assertIn(src_empty, {"ahp", "ahp_emergency"})


class WeightsApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="w.api@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        self.url = reverse("v1:match_ahp_weights")

    def test_weights_endpoint_reports_active_source(self):
        self.client.force_authenticate(self.user)
        res = self.client.get(self.url, {"city": "Colombo"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("consistency_ratio", res.data)
        self.assertLess(res.data["consistency_ratio"], 0.1)
        self.assertIn("active_source", res.data)
        self.assertIn("active_vector", res.data)
        self.assertEqual(len(res.data["active_vector"]), 4)
        self.assertAlmostEqual(sum(res.data["active_vector"]), 1.0, places=5)
        self.assertEqual(res.data.get("consistency_ratio_source"), "ahp")

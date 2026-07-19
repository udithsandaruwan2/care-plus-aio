"""Step 19 — VEHMF fusion engine + /api/v1/match/."""

import tempfile

import numpy as np
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope, Role
from apps.matching.engine import _normalize, run_match
from apps.matching.faiss_index import build_index, reset_cache
from apps.matching.models import CaregiverProfile, MatchRun

User = get_user_model()


class FusionMathTests(SimpleTestCase):
    def test_normalize_minmax(self):
        out = _normalize(np.array([2.0, 4.0, 6.0], dtype=np.float32))
        self.assertAlmostEqual(float(out[0]), 0.0, places=5)
        self.assertAlmostEqual(float(out[2]), 1.0, places=5)

    def test_normalize_constant_is_zero(self):
        out = _normalize(np.array([3.0, 3.0, 3.0], dtype=np.float32))
        self.assertTrue(np.allclose(out, 0.0))

    def test_fusion_prefers_high_weighted_factor(self):
        # Artificial: CBF dominates when α=1.
        W = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        matrix = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.1, 1.0, 1.0, 1.0],
            ],
            dtype=np.float32,
        )
        final = matrix @ W
        self.assertGreater(final[0], final[1])


class VehmfEngineTests(TestCase):
    def setUp(self):
        reset_cache()
        self.cg_diabetes = self._cg(
            "vehmf.cg.d@example.com",
            "Diabetes Near",
            specialties=["diabetes"],
            languages=["Sinhala"],
            care_levels=["intermediate"],
            lon=79.86,
            lat=6.93,
            trust=0.95,
        )
        self.cg_far = self._cg(
            "vehmf.cg.f@example.com",
            "Wound Far",
            specialties=["wound care"],
            languages=["Tamil"],
            care_levels=["basic"],
            lon=81.2,
            lat=8.5,
            trust=0.6,
        )

    def _cg(self, email, name, *, specialties, languages, care_levels, lon, lat, trust):
        user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
        return CaregiverProfile.objects.create(
            user=user,
            display_name=name,
            location=Point(lon, lat, srid=4326),
            certifications=["First Aid"],
            specialties=specialties,
            languages=languages,
            care_levels=care_levels,
            trust_score=trust,
            bio=name,
        )

    def test_run_match_ranks_diabetes_near_colombo(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                build_index(persist=True)
                out = run_match(
                    condition="diabetes",
                    language="Sinhala",
                    care_level="intermediate",
                    query="Colombo",
                    longitude=79.86,
                    latitude=6.93,
                    top_k=5,
                )
                self.assertGreaterEqual(len(out.results), 1)
                self.assertEqual(out.results[0].caregiver_id, self.cg_diabetes.id)
                self.assertIn("Matched because:", out.results[0].explanation)
                self.assertAlmostEqual(sum(out.weights), 1.0, places=5)


class MatchApiTests(APITestCase):
    def setUp(self):
        reset_cache()
        self.patient = User.objects.create_user(
            email="vehmf.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        ConsentLog.objects.create(user=self.patient, scope=ConsentScope.AI_PROCESSING, granted=True)
        cg = User.objects.create_user(
            email="vehmf.api.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        CaregiverProfile.objects.create(
            user=cg,
            display_name="API Diabetes CG",
            location=Point(79.86, 6.93, srid=4326),
            certifications=["Diabetes Educator (basic)"],
            specialties=["diabetes"],
            languages=["Sinhala", "English"],
            care_levels=["intermediate"],
            trust_score=0.9,
            bio="near Colombo",
        )
        self.url = reverse("v1:match")

    def test_requires_consent(self):
        resp = self.client.post(self.url, {"condition": "diabetes"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_match_persists_run_and_returns_breakdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                call_command("build_caregiver_index", verbosity=0)
                self.client.force_authenticate(self.patient)
                resp = self.client.post(
                    self.url,
                    {
                        "condition": "diabetes",
                        "language": "Sinhala",
                        "care_level": "intermediate",
                        "longitude": 79.86,
                        "latitude": 6.93,
                        "k": 5,
                    },
                    format="json",
                )
                self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
                self.assertIn("request_id", resp.data)
                self.assertIn("latency_ms", resp.data)
                self.assertLess(resp.data["latency_ms"], 800)
                self.assertGreaterEqual(len(resp.data["results"]), 1)
                top = resp.data["results"][0]
                self.assertIn("breakdown", top)
                self.assertIn("explanation", top)
                self.assertTrue(MatchRun.objects.filter(pk=resp.data["request_id"]).exists())
                self.assertEqual(
                    MatchRun.objects.get(pk=resp.data["request_id"]).results.count(),
                    len(resp.data["results"]),
                )

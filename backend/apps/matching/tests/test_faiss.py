"""Step 17 — embeddings + FAISS IndexFlatIP."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope, Role
from apps.matching.embeddings import HashEmbedder, intent_to_text, profile_to_text
from apps.matching.faiss_index import build_index, reset_cache
from apps.matching.models import EMBEDDING_DIM, CaregiverProfile

User = get_user_model()


class HashEmbedderTests(TestCase):
    def test_l2_normalized_and_dim(self):
        emb = HashEmbedder()
        mat = emb.embed(["diabetes Sinhala intermediate", "unrelated gardening tips"])
        self.assertEqual(mat.shape, (2, EMBEDDING_DIM))
        norms = (mat**2).sum(axis=1) ** 0.5
        self.assertTrue(all(abs(n - 1.0) < 1e-5 for n in norms))

    def test_shared_tokens_score_higher(self):
        emb = HashEmbedder()
        q, a, b = emb.embed(
            [
                "diabetes sinhala intermediate",
                "diabetes educator sinhala intermediate care",
                "wound care tamil basic only",
            ]
        )
        self.assertGreater(float(q @ a), float(q @ b))


class FaissIndexTests(TestCase):
    def setUp(self):
        reset_cache()
        self.diabetes = self._mk(
            "seed.cg.faiss.0@careplus.local",
            "Diabetes CG",
            specialties=["diabetes"],
            languages=["Sinhala", "English"],
            care_levels=["intermediate"],
            lon=79.86,
            lat=6.93,
        )
        self.wound = self._mk(
            "seed.cg.faiss.1@careplus.local",
            "Wound CG",
            specialties=["wound care"],
            languages=["Tamil"],
            care_levels=["basic"],
            lon=80.63,
            lat=7.29,
        )

    def _mk(self, email, name, *, specialties, languages, care_levels, lon, lat):
        user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
        return CaregiverProfile.objects.create(
            user=user,
            display_name=name,
            location=Point(lon, lat, srid=4326),
            certifications=["First Aid"],
            specialties=specialties,
            languages=languages,
            care_levels=care_levels,
            trust_score=0.8,
            bio=f"{name} near test city",
        )

    @override_settings(EMBEDDING_BACKEND="hash", FAISS_ARTIFACT_DIR="")
    def test_build_persists_embeddings_and_ranks_diabetes(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                built = build_index(persist=True)
                self.assertEqual(built.size, 2)
                self.diabetes.refresh_from_db()
                self.assertEqual(len(self.diabetes.embedding), EMBEDDING_DIM)

                emb = HashEmbedder()
                q = emb.embed(
                    [
                        intent_to_text(
                            condition="diabetes",
                            language="Sinhala",
                            care_level="intermediate",
                            extra="Colombo",
                        )
                    ]
                )[0]
                hits = built.search(q, k=2)
                self.assertEqual(hits[0][0], self.diabetes.id)
                self.assertTrue((Path(tmp) / "caregivers.faiss").exists())
                self.assertTrue((Path(tmp) / "caregivers.ids.json").exists())

    def test_profile_text_includes_specialty(self):
        text = profile_to_text(self.diabetes)
        self.assertIn("diabetes", text)
        self.assertIn("sinhala", text)


class CbfPreviewApiTests(APITestCase):
    def setUp(self):
        reset_cache()
        self.patient = User.objects.create_user(
            email="cbf.patient@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        ConsentLog.objects.create(user=self.patient, scope=ConsentScope.AI_PROCESSING, granted=True)
        cg_user = User.objects.create_user(
            email="cbf.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        CaregiverProfile.objects.create(
            user=cg_user,
            display_name="Diabetes Expert",
            location=Point(79.86, 6.93, srid=4326),
            certifications=["Diabetes Educator (basic)"],
            specialties=["diabetes"],
            languages=["Sinhala", "English"],
            care_levels=["intermediate", "advanced"],
            trust_score=0.95,
            bio="Community caregiver based near Colombo.",
        )
        self.url = reverse("v1:match_cbf_preview")

    def test_requires_auth_and_consent(self):
        resp = self.client.post(self.url, {"condition": "diabetes"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(EMBEDDING_BACKEND="hash")
    def test_diabetes_query_returns_ranked_hit(self):
        import tempfile

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
                        "query": "Colombo",
                        "k": 5,
                    },
                    format="json",
                )
                self.assertEqual(resp.status_code, status.HTTP_200_OK)
                self.assertGreaterEqual(len(resp.data["results"]), 1)
                top = resp.data["results"][0]
                self.assertIn("diabetes", [s.lower() for s in top["specialties"]])

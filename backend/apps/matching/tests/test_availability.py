"""Step 20e — soft presence: unavailable caregivers hidden from match top-N."""

import tempfile

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope, Role
from apps.matching.engine import run_match
from apps.matching.faiss_index import build_index, reset_cache
from apps.matching.models import CaregiverProfile

User = get_user_model()


class AvailabilityMatchTests(TestCase):
    def setUp(self):
        reset_cache()
        self.available = self._cg(
            "avail.cg@example.com",
            "Available Diabetes",
            specialties=["diabetes"],
            available=True,
            trust=0.95,
        )
        self.unavailable = self._cg(
            "unavail.cg@example.com",
            "Unavailable Diabetes",
            specialties=["diabetes"],
            available=False,
            trust=0.99,
        )

    def _cg(self, email, name, *, specialties, available, trust):
        user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
        return CaregiverProfile.objects.create(
            user=user,
            display_name=name,
            location=Point(79.86, 6.93, srid=4326),
            certifications=["First Aid"],
            specialties=specialties,
            languages=["Sinhala", "English"],
            care_levels=["intermediate"],
            trust_score=trust,
            bio=name,
            is_active=True,
            is_approved=True,
            is_available=available,
        )

    def test_unavailable_excluded_from_match_top_n(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                build_index(persist=True)
                out = run_match(
                    condition="diabetes",
                    language="Sinhala",
                    care_level="intermediate",
                    longitude=79.86,
                    latitude=6.93,
                    top_k=10,
                )
                ids = {r.caregiver_id for r in out.results}
                self.assertIn(self.available.id, ids)
                self.assertNotIn(self.unavailable.id, ids)


class CaregiverMeApiTests(APITestCase):
    def setUp(self):
        self.caregiver = User.objects.create_user(
            email="me.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        self.profile = CaregiverProfile.objects.create(
            user=self.caregiver,
            display_name="Me CG",
            location=Point(79.86, 6.93, srid=4326),
            certifications=["First Aid"],
            specialties=["diabetes"],
            languages=["English"],
            care_levels=["basic"],
            trust_score=0.8,
            is_active=True,
            is_approved=True,
            is_available=True,
        )
        self.patient = User.objects.create_user(
            email="me.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        self.url = reverse("v1:caregiver_me")

    def test_patient_forbidden(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_and_patch_availability(self):
        self.client.force_authenticate(self.caregiver)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_available"])
        self.assertEqual(resp.data["display_name"], "Me CG")

        resp = self.client.patch(self.url, {"is_available": False}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_available"])
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_available)

        resp = self.client.patch(self.url, {"is_available": True}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_available"])

    def test_match_api_omits_unavailable(self):
        ConsentLog.objects.create(user=self.patient, scope=ConsentScope.AI_PROCESSING, granted=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                call_command("build_caregiver_index", verbosity=0)
                self.client.force_authenticate(self.patient)
                resp = self.client.post(
                    reverse("v1:match"),
                    {"condition": "diabetes", "language": "English", "k": 5},
                    format="json",
                )
                self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
                ids = {r["caregiver_id"] for r in resp.data["results"]}
                self.assertIn(self.profile.id, ids)

                self.profile.is_available = False
                self.profile.save(update_fields=["is_available"])
                resp = self.client.post(
                    reverse("v1:match"),
                    {"condition": "diabetes", "language": "English", "k": 5},
                    format="json",
                )
                self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
                ids = {r["caregiver_id"] for r in resp.data["results"]}
                self.assertNotIn(self.profile.id, ids)

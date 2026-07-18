"""Step 16 acceptance: domain profiles + Sri Lanka seed geometries."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile, PatientProfile

User = get_user_model()


class ProfileModelTests(TestCase):
    def test_caregiver_point_is_valid_wgs84(self):
        user = User.objects.create_user(
            email="cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        # Colombo
        profile = CaregiverProfile.objects.create(
            user=user,
            display_name="Test CG",
            location=Point(79.8612, 6.9271, srid=4326),
            certifications=["First Aid"],
            languages=["Sinhala", "English"],
            specialties=["diabetes"],
            care_levels=["basic", "intermediate"],
            trust_score=0.88,
        )
        profile.refresh_from_db()
        self.assertEqual(profile.location.srid, 4326)
        self.assertTrue(profile.location.valid)
        self.assertAlmostEqual(profile.location.x, 79.8612, places=4)
        self.assertAlmostEqual(profile.location.y, 6.9271, places=4)
        # Sri Lanka rough bbox sanity.
        self.assertTrue(79.5 < profile.location.x < 82.0)
        self.assertTrue(5.5 < profile.location.y < 10.0)

    def test_patient_profile_optional_location(self):
        user = User.objects.create_user(
            email="pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        profile = PatientProfile.objects.create(
            user=user,
            display_name="Test PT",
            preferred_language="Tamil",
            conditions=["hypertension"],
            care_level="basic",
        )
        self.assertIsNone(profile.location)


class SeedProfilesCommandTests(TestCase):
    def test_seed_loads_n_caregivers_with_valid_geometries(self):
        call_command("seed_profiles", caregivers=12, patients=3, verbosity=0)
        qs = CaregiverProfile.objects.filter(user__email__startswith="seed.cg.")
        self.assertEqual(qs.count(), 12)
        for cg in qs:
            self.assertIsNotNone(cg.location)
            self.assertTrue(cg.location.valid)
            self.assertEqual(cg.location.srid, 4326)
            self.assertTrue(79.0 < cg.location.x < 82.5)
            self.assertTrue(5.5 < cg.location.y < 10.2)
            self.assertGreaterEqual(cg.trust_score, 0.0)
            self.assertLessEqual(cg.trust_score, 1.0)
            self.assertTrue(cg.languages)
            self.assertTrue(cg.certifications)

        self.assertEqual(
            PatientProfile.objects.filter(user__email__startswith="seed.pt.").count(),
            3,
        )

    def test_seed_is_idempotent(self):
        call_command("seed_profiles", caregivers=5, patients=2, verbosity=0)
        call_command("seed_profiles", caregivers=5, patients=2, verbosity=0)
        self.assertEqual(
            CaregiverProfile.objects.filter(user__email__startswith="seed.cg.").count(),
            5,
        )


class CaregiverListApiTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="viewer@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        cg_user = User.objects.create_user(
            email="listed@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        CaregiverProfile.objects.create(
            user=cg_user,
            display_name="Listed CG",
            location=Point(80.6337, 7.2906, srid=4326),
            certifications=["CPR Certified"],
            languages=["Sinhala"],
            specialties=["elderly care"],
            care_levels=["basic"],
            trust_score=0.9,
        )
        self.url = reverse("v1:caregiver_list")

    def test_list_requires_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_returns_active_caregivers(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)
        row = next(r for r in resp.data if r["display_name"] == "Listed CG")
        self.assertAlmostEqual(row["longitude"], 80.6337, places=3)
        self.assertAlmostEqual(row["latitude"], 7.2906, places=3)
        self.assertEqual(row["trust_score"], 0.9)

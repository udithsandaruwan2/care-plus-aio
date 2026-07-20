"""Step 22b — patient onboarding profile + completion gate."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import PatientProfile
from apps.matching.patient_profile import patient_profile_completion
from apps.vocab.models import ConditionTerm

User = get_user_model()


class ProfileCompletionTests(TestCase):
    def test_empty_profile_is_below_threshold(self):
        user = User.objects.create_user(
            email="empty.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        profile = PatientProfile.objects.create(user=user)
        completion = patient_profile_completion(profile)
        self.assertLess(completion.percent, 80)
        self.assertFalse(completion.can_request_care)
        self.assertIn("display_name", completion.missing_fields)

    def test_complete_profile_meets_threshold(self):
        user = User.objects.create_user(
            email="full.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        profile = PatientProfile.objects.create(
            user=user,
            display_name="Kamal Perera",
            city="Colombo",
            location=Point(79.8612, 6.9271, srid=4326),
            preferred_language="Sinhala",
            languages=["Sinhala", "English"],
            care_level="intermediate",
            conditions=["diabetes"],
            height_cm=172,
            weight_kg=70.5,
            blood_type="O+",
            emergency_contact_name="Nimali Perera",
            emergency_contact_phone="+94771234567",
        )
        completion = patient_profile_completion(profile)
        self.assertGreaterEqual(completion.percent, 80)
        self.assertTrue(completion.can_request_care)


class PatientMeApiTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="onboard.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        ConditionTerm.objects.create(slug="diabetes", canonical_en="Diabetes", active=True)
        self.url = reverse("v1:patient_me")

    def test_get_creates_profile_and_returns_completion(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("completion_percent", resp.data)
        self.assertFalse(resp.data["can_request_care"])
        self.assertTrue(PatientProfile.objects.filter(user=self.patient).exists())

    def test_patch_validates_vocab_conditions(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.patch(
            self.url,
            {"conditions": ["not-a-real-slug"]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_updates_profile_fields(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.patch(
            self.url,
            {
                "display_name": "Anjali S.",
                "city": "Kandy",
                "longitude": 80.6337,
                "latitude": 7.2906,
                "preferred_language": "Tamil",
                "languages": ["Tamil", "English"],
                "care_level": "basic",
                "conditions": ["diabetes"],
                "height_cm": 160,
                "weight_kg": 55,
                "blood_type": "A+",
                "medications": ["metformin"],
                "allergies": ["peanuts"],
                "emergency_contact_name": "Ravi S.",
                "emergency_contact_phone": "+94770000000",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["display_name"], "Anjali S.")
        self.assertTrue(resp.data["can_request_care"])
        self.assertGreaterEqual(resp.data["completion_percent"], 80)

    @override_settings(PATIENT_PROFILE_MIN_COMPLETION=95)
    def test_completion_threshold_is_configurable(self):
        user = User.objects.create_user(
            email="cfg.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        profile = PatientProfile.objects.create(
            user=user,
            display_name="Test",
            city="Colombo",
            location=Point(79.86, 6.92, srid=4326),
            preferred_language="English",
            languages=["English"],
            care_level="basic",
            conditions=["diabetes"],
            height_cm=170,
            weight_kg=70,
            blood_type="O+",
            emergency_contact_name="EC",
            # phone missing → below 100%
        )
        completion = patient_profile_completion(profile)
        self.assertGreaterEqual(completion.percent, 80)
        self.assertFalse(completion.can_request_care)

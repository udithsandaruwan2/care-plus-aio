"""Step 22c — caregiver onboarding profile + match eligibility gate."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.caregiver_profile import caregiver_profile_completion
from apps.matching.models import CaregiverProfile
from apps.vocab.models import ConditionTerm

User = get_user_model()


def _complete_caregiver_kwargs():
    return {
        "display_name": "Nimali Fernando",
        "nic_id": "199012345678",
        "city": "Colombo",
        "location": Point(79.8612, 6.9271, srid=4326),
        "languages": ["Sinhala", "English"],
        "specialties": ["diabetes"],
        "care_levels": ["intermediate"],
        "certifications": ["First Aid (Red Cross)", "CPR Certified"],
        "years_experience": 5,
        "service_radius_km": 30.0,
        "bio": "Experienced community caregiver in Colombo.",
        "certification_docs": [{"name": "First Aid", "status": "pending"}],
    }


class CaregiverProfileCompletionTests(TestCase):
    def setUp(self):
        ConditionTerm.objects.create(slug="diabetes", canonical_en="Diabetes", active=True)

    def test_empty_profile_is_below_threshold(self):
        user = User.objects.create_user(
            email="empty.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        profile = CaregiverProfile.objects.create(
            user=user,
            display_name="New CG",
            location=Point(79.86, 6.92, srid=4326),
        )
        completion = caregiver_profile_completion(profile)
        self.assertLess(completion.percent, 80)
        self.assertFalse(completion.can_request_care)
        self.assertIn("nic_id", completion.missing_fields)

    def test_complete_profile_meets_threshold_when_approved(self):
        user = User.objects.create_user(
            email="full.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        profile = CaregiverProfile.objects.create(
            user=user,
            is_active=True,
            is_approved=True,
            **_complete_caregiver_kwargs(),
        )
        completion = caregiver_profile_completion(profile)
        self.assertGreaterEqual(completion.percent, 80)
        self.assertTrue(completion.can_request_care)


class CaregiverMeApiTests(APITestCase):
    def setUp(self):
        self.caregiver = User.objects.create_user(
            email="onboard.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        ConditionTerm.objects.create(slug="diabetes", canonical_en="Diabetes", active=True)
        self.url = reverse("v1:caregiver_me")

    def test_get_creates_profile_and_returns_completion(self):
        self.client.force_authenticate(self.caregiver)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("completion_percent", resp.data)
        self.assertFalse(resp.data["is_match_eligible"])
        self.assertFalse(resp.data["onboarding_complete"])
        self.assertTrue(CaregiverProfile.objects.filter(user=self.caregiver).exists())

    def test_patch_validates_vocab_specialties(self):
        self.client.force_authenticate(self.caregiver)
        resp = self.client.patch(
            self.url,
            {"specialties": ["not-a-real-slug"]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(CAREGIVER_AUTO_APPROVE=True)
    def test_patch_completes_onboarding_and_activates(self):
        self.client.force_authenticate(self.caregiver)
        payload = _complete_caregiver_kwargs()
        payload["longitude"] = payload.pop("location").x
        payload["latitude"] = 6.9271
        resp = self.client.patch(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["onboarding_complete"])
        self.assertTrue(resp.data["is_match_eligible"])
        self.assertTrue(resp.data["is_approved"])
        self.assertTrue(resp.data["is_active"])
        profile = CaregiverProfile.objects.get(user=self.caregiver)
        self.assertTrue(profile.is_active)
        self.assertTrue(profile.is_approved)

    @override_settings(CAREGIVER_AUTO_APPROVE=False)
    def test_manual_approval_required_when_auto_approve_off(self):
        self.client.force_authenticate(self.caregiver)
        payload = _complete_caregiver_kwargs()
        payload["longitude"] = payload.pop("location").x
        payload["latitude"] = 6.9271
        resp = self.client.patch(self.url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["onboarding_complete"])
        self.assertFalse(resp.data["is_match_eligible"])
        self.assertFalse(resp.data["is_approved"])


class InactiveCaregiverMatchTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="match.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        cg_user = User.objects.create_user(
            email="inactive.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        self.inactive = CaregiverProfile.objects.create(
            user=cg_user,
            display_name="Inactive CG",
            location=Point(79.86, 6.93, srid=4326),
            certifications=["First Aid"],
            specialties=["diabetes"],
            languages=["English"],
            care_levels=["basic"],
            trust_score=0.9,
            is_active=False,
            is_approved=False,
        )

    def test_inactive_caregiver_not_in_browse_list(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(reverse("v1:caregiver_list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {r["id"] for r in resp.data["results"]}
        self.assertNotIn(self.inactive.id, ids)

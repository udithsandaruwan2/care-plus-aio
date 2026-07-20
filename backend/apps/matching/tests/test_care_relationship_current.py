"""Step 26 — current active care relationship on home dashboards."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import (
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    PatientProfile,
)

User = get_user_model()


def _patient(email="pt.cur@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Current",
        city="Colombo",
        location=Point(79.86, 6.92, srid=4326),
        preferred_language="English",
        languages=["English"],
        care_level="basic",
        conditions=["dengue"],
        height_cm=170,
        weight_kg=70,
        blood_type="O+",
        emergency_contact_name="EC",
        emergency_contact_phone="+94770000000",
    )
    return user


def _caregiver(email="cg.cur@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Current",
        location=Point(79.86, 6.93, srid=4326),
        languages=["English"],
        care_levels=["basic"],
        trust_score=0.9,
        is_active=True,
        is_approved=True,
        is_available=False,
    )
    return user, profile


class CareRelationshipCurrentApiTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ACTIVE,
        )
        self.url = reverse("v1:care_relationship_current")

    def test_patient_sees_current_caregiver(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], self.rel.pk)
        self.assertEqual(resp.data["caregiver_name"], "CG Current")
        self.assertEqual(resp.data["status"], "active")

    def test_caregiver_sees_current_patient(self):
        self.client.force_authenticate(self.cg_user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["patient_email"], self.patient.email)

    def test_returns_null_when_no_active_link(self):
        self.rel.status = CareRelationshipStatus.ENDED
        self.rel.save(update_fields=["status"])
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data)

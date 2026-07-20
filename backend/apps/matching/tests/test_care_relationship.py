"""Step 25 — CareRelationship activate/end lifecycle."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditAction, AuditLog, Role
from apps.matching.care_relationships import sync_caregiver_availability
from apps.matching.models import (
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
    PatientProfile,
)

User = get_user_model()


def _patient(email="pt.rel@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Rel",
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


def _caregiver(email="cg.rel@example.com", *, available=True):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Rel",
        location=Point(79.86, 6.93, srid=4326),
        certifications=["First Aid"],
        specialties=["dengue"],
        languages=["English"],
        care_levels=["basic"],
        trust_score=0.9,
        is_active=True,
        is_approved=True,
        is_available=available,
    )
    return user, profile


class CareRelationshipLifecycleTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.PENDING_PAYMENT,
        )
        self.activate_url = reverse(
            "v1:care_relationship_action", kwargs={"pk": self.rel.pk}
        )
        self.current_url = reverse("v1:care_relationship_current")

    def test_activate_marks_caregiver_unavailable(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.patch(self.activate_url, {"action": "activate"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["status"], "active")

        self.caregiver.refresh_from_db()
        self.assertFalse(self.caregiver.is_available)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.ACTIVATE_CARE_RELATIONSHIP,
            ).exists()
        )

    def test_end_relationship_frees_caregiver_availability(self):
        self.rel.status = CareRelationshipStatus.ACTIVE
        self.rel.save(update_fields=["status"])
        sync_caregiver_availability(self.caregiver)
        self.caregiver.refresh_from_db()
        self.assertFalse(self.caregiver.is_available)

        self.client.force_authenticate(self.cg_user)
        resp = self.client.patch(
            self.activate_url,
            {"action": "end", "reason": "Patient recovered"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["status"], "ended")
        self.assertEqual(resp.data["end_reason"], "Patient recovered")

        self.caregiver.refresh_from_db()
        self.assertTrue(self.caregiver.is_available)
        self.rel.refresh_from_db()
        self.assertEqual(self.rel.status, CareRelationshipStatus.ENDED)
        self.assertIsNotNone(self.rel.ended_at)

    @override_settings(ONE_PRIMARY_CAREGIVER=True)
    def test_only_one_active_primary_per_patient(self):
        _, cg2 = _caregiver("cg2.rel@example.com")
        rel2 = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=cg2,
            status=CareRelationshipStatus.PENDING_PAYMENT,
        )
        self.rel.status = CareRelationshipStatus.ACTIVE
        self.rel.save(update_fields=["status"])

        self.client.force_authenticate(self.patient)
        url = reverse("v1:care_relationship_action", kwargs={"pk": rel2.pk})
        resp = self.client.patch(url, {"action": "activate"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_current_endpoint_returns_active_primary(self):
        self.rel.status = CareRelationshipStatus.ACTIVE
        self.rel.save(update_fields=["status"])
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.current_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["id"], self.rel.pk)

    def test_history_list_retains_ended_relationships(self):
        self.rel.status = CareRelationshipStatus.ENDED
        self.rel.save(update_fields=["status"])
        self.client.force_authenticate(self.patient)
        resp = self.client.get(reverse("v1:care_relationship_list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["status"], "ended")

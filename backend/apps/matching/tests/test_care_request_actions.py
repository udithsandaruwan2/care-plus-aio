"""Step 24 — caregiver accept/reject + provisional CareRelationship."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditAction, AuditLog, Role
from apps.matching.models import (
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
    Interaction,
    InteractionKind,
    PatientProfile,
)

User = get_user_model()


def _patient(email="pt.act@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Act",
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


def _caregiver(email="cg.act@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Act",
        location=Point(79.86, 6.93, srid=4326),
        certifications=["First Aid"],
        specialties=["dengue"],
        languages=["English"],
        care_levels=["basic"],
        trust_score=0.9,
        is_active=True,
        is_approved=True,
        is_available=True,
    )
    return user, profile


class CareRequestActionTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.create_url = reverse("v1:care_request_list")
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            self.create_url,
            {"caregiver_id": self.caregiver.pk, "message": "Need help"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.req_id = resp.data["id"]
        self.action_url = reverse("v1:care_request_action", kwargs={"pk": self.req_id})

    def test_caregiver_accepts_creates_provisional_relationship(self):
        self.client.force_authenticate(self.cg_user)
        resp = self.client.patch(self.action_url, {"action": "accept"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "accepted")
        self.assertIsNotNone(resp.data.get("relationship_id"))

        req = CareRequest.objects.get(pk=self.req_id)
        self.assertEqual(req.status, CareRequestStatus.ACCEPTED)
        rel = CareRelationship.objects.get(pk=resp.data["relationship_id"])
        self.assertEqual(rel.status, CareRelationshipStatus.PENDING_PAYMENT)
        self.assertEqual(rel.patient_id, self.patient.pk)
        self.assertEqual(rel.caregiver_id, self.caregiver.pk)

        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.cg_user,
                action=AuditAction.ACCEPT_CARE_REQUEST,
            ).exists()
        )
        self.assertTrue(
            Interaction.objects.filter(
                patient=self.patient,
                caregiver=self.caregiver,
                kind=InteractionKind.ACCEPT,
            ).exists()
        )

    def test_caregiver_rejects_request(self):
        self.client.force_authenticate(self.cg_user)
        resp = self.client.patch(
            self.action_url,
            {"action": "reject", "reason": "Fully booked this week"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "rejected")
        self.assertFalse(CareRelationship.objects.filter(care_request_id=self.req_id).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.cg_user,
                action=AuditAction.REJECT_CARE_REQUEST,
            ).exists()
        )

    def test_patient_cannot_accept(self):
        resp = self.client.patch(self.action_url, {"action": "accept"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_caregiver_cannot_cancel(self):
        self.client.force_authenticate(self.cg_user)
        resp = self.client.patch(self.action_url, {"action": "cancel"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_accept_twice(self):
        self.client.force_authenticate(self.cg_user)
        resp1 = self.client.patch(self.action_url, {"action": "accept"}, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        resp2 = self.client.patch(self.action_url, {"action": "accept"}, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

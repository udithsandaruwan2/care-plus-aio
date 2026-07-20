"""Step 23 — CareRequest model + API."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditAction, AuditLog, Role
from apps.matching.care_requests import expire_stale_care_requests
from apps.matching.models import (
    CaregiverProfile,
    CareRequest,
    CareRequestStatus,
    Interaction,
    InteractionKind,
    PatientProfile,
)

User = get_user_model()


def _patient(email="pt.cr@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient CR",
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
        emergency_contact_phone="+94770000000",
    )
    return user


def _caregiver(email="cg.cr@example.com", *, available=True):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG CR",
        location=Point(79.86, 6.93, srid=4326),
        certifications=["First Aid"],
        specialties=["diabetes"],
        languages=["English"],
        care_levels=["basic"],
        trust_score=0.9,
        is_active=True,
        is_approved=True,
        is_available=available,
    )
    return user, profile


class CareRequestApiTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.list_url = reverse("v1:care_request_list")

    def test_patient_creates_pending_request(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            self.list_url,
            {
                "caregiver_id": self.caregiver.pk,
                "message": "Need help with diabetes care.",
                "match_snapshot": {"rank": 1, "score": 0.91},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "pending")
        self.assertEqual(resp.data["caregiver_id"], self.caregiver.pk)
        self.assertEqual(resp.data["match_snapshot"]["score"], 0.91)
        self.assertTrue(CareRequest.objects.filter(patient=self.patient).exists())
        self.assertTrue(
            Interaction.objects.filter(
                patient=self.patient,
                caregiver=self.caregiver,
                kind=InteractionKind.REQUEST,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.CREATE_CARE_REQUEST,
            ).exists()
        )

    def test_duplicate_active_request_blocked(self):
        self.client.force_authenticate(self.patient)
        payload = {"caregiver_id": self.caregiver.pk}
        resp1 = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        resp2 = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_incomplete_patient_profile_forbidden(self):
        user = User.objects.create_user(
            email="incomplete.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(user=user)
        self.client.force_authenticate(user)
        resp = self.client.post(
            self.list_url, {"caregiver_id": self.caregiver.pk}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unavailable_caregiver_rejected(self):
        _, unavailable = _caregiver("unavail.cg@example.com", available=False)
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            self.list_url, {"caregiver_id": unavailable.pk}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_caregiver_sees_inbox(self):
        self.client.force_authenticate(self.patient)
        self.client.post(self.list_url, {"caregiver_id": self.caregiver.pk}, format="json")
        self.client.force_authenticate(self.cg_user)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["status"], "pending")

    def test_patient_can_cancel_pending(self):
        self.client.force_authenticate(self.patient)
        created = self.client.post(
            self.list_url, {"caregiver_id": self.caregiver.pk}, format="json"
        )
        req_id = created.data["id"]
        url = reverse("v1:care_request_action", kwargs={"pk": req_id})
        resp = self.client.patch(url, {"action": "cancel"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "cancelled")
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.CANCEL_CARE_REQUEST,
            ).exists()
        )

    def test_caregiver_cannot_create_request(self):
        self.client.force_authenticate(self.cg_user)
        resp = self.client.post(
            self.list_url, {"caregiver_id": self.caregiver.pk}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class CareRequestExpiryTests(APITestCase):
    def test_expire_stale_pending_requests(self):
        patient = _patient("exp.pt@example.com")
        _, caregiver = _caregiver("exp.cg@example.com")
        req = CareRequest.objects.create(
            patient=patient,
            caregiver=caregiver,
            status=CareRequestStatus.PENDING,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        count = expire_stale_care_requests()
        self.assertEqual(count, 1)
        req.refresh_from_db()
        self.assertEqual(req.status, CareRequestStatus.EXPIRED)
        self.assertIsNotNone(req.responded_at)

    @override_settings(CARE_REQUEST_TTL_HOURS=48)
    def test_create_sets_expiry_from_settings(self):
        patient = _patient("ttl.pt@example.com")
        _, caregiver = _caregiver("ttl.cg@example.com")
        self.client.force_authenticate(patient)
        before = timezone.now()
        resp = self.client.post(
            reverse("v1:care_request_list"),
            {"caregiver_id": caregiver.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        req = CareRequest.objects.get(pk=resp.data["id"])
        self.assertGreater(req.expires_at, before + timedelta(hours=47))

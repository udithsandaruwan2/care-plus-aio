"""Step 56 — admin analytics API."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import (
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
    CaregiverProfile,
    create_match_run,
)

User = get_user_model()


class AdminAnalyticsApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin.analytics@example.com",
            password="pw-strong-123",
            role=Role.ADMIN,
        )
        self.auditor = User.objects.create_user(
            email="auditor.analytics@example.com",
            password="pw-strong-123",
            role=Role.AUDITOR,
        )
        self.patient = User.objects.create_user(
            email="patient.analytics@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )
        self.cg_user = User.objects.create_user(
            email="cg.analytics@example.com",
            password="pw-strong-123",
            role=Role.CAREGIVER,
        )
        self.cg = CaregiverProfile.objects.create(
            user=self.cg_user,
            display_name="Analytics CG",
            location=Point(79.86, 6.93, srid=4326),
            is_active=True,
            is_approved=True,
            is_available=True,
        )
        expires = timezone.now() + timedelta(days=2)
        CareRequest.objects.create(
            patient=self.patient,
            caregiver=self.cg,
            status=CareRequestStatus.PENDING,
            message="hi",
            expires_at=expires,
        )
        CareRequest.objects.create(
            patient=self.patient,
            caregiver=self.cg,
            status=CareRequestStatus.ACCEPTED,
            message="ok",
            expires_at=expires,
        )
        CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.cg,
            status=CareRelationshipStatus.ACTIVE,
        )
        for ms in (100, 200, 400):
            create_match_run(
                user=self.patient,
                query="dengue",
                weights=[0.4, 0.2, 0.2, 0.2],
                latency_ms=ms,
            )
        self.url = reverse("v1:admin_analytics")

    def test_patient_forbidden(self):
        self.client.force_authenticate(self.patient)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_analytics_payload(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get(self.url, {"window_days": 30})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        by_status = {row["key"]: row["count"] for row in res.data["requests_by_status"]}
        self.assertEqual(by_status["pending"], 1)
        self.assertEqual(by_status["accepted"], 1)

        roles = {row["key"]: row["count"] for row in res.data["roles"]}
        self.assertGreaterEqual(roles["patient"], 1)
        self.assertGreaterEqual(roles["caregiver"], 1)
        self.assertGreaterEqual(roles["admin"], 1)

        self.assertEqual(res.data["relationships"]["active"], 1)
        latency = res.data["match_latency"]
        self.assertEqual(latency["sample_size"], 3)
        self.assertEqual(latency["p50_ms"], 200)
        self.assertEqual(latency["p95_ms"], 380)

    def test_auditor_can_read(self):
        self.client.force_authenticate(self.auditor)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

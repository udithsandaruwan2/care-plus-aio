"""Step 45 — health metric ingest + window aggregates."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile, CareRelationship, CareRelationshipStatus, PatientProfile

from ..models import HealthMetric

User = get_user_model()


def _patient(email="pt.hm@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient HM",
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


def _caregiver(email="cg.hm@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG HM",
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


class HealthMetricApiTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.other_patient = _patient("pt.other.hm@example.com")
        self.cg_user, self.caregiver = _caregiver()
        CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ACTIVE,
            is_primary=True,
        )
        self.ingest_url = reverse("v1:health_metric_ingest")
        self.window_url = reverse("v1:health_metric_window")

    def test_patient_ingests_own_metric(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            self.ingest_url,
            {"kind": "heart_rate", "value": 82, "unit": "bpm", "source": "sim"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["patient"], self.patient.pk)
        self.assertEqual(HealthMetric.objects.count(), 1)

    def test_patient_cannot_ingest_for_other_patient(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            self.ingest_url,
            {"patient_id": self.other_patient.pk, "kind": "heart_rate", "value": 82},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_window_aggregates_for_patient(self):
        now = timezone.now()
        HealthMetric.objects.create(
            patient=self.patient, kind="heart_rate", value=80, unit="bpm", source="sim", recorded_at=now
        )
        HealthMetric.objects.create(
            patient=self.patient,
            kind="heart_rate",
            value=100,
            unit="bpm",
            source="sim",
            recorded_at=now + timedelta(minutes=1),
        )
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.window_url, {"kind": "heart_rate", "hours": 24})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["count"], 2)
        self.assertEqual(resp.data["min"], 80.0)
        self.assertEqual(resp.data["max"], 100.0)
        self.assertEqual(resp.data["avg"], 90.0)
        self.assertEqual(resp.data["latest"]["value"], 100.0)
        self.assertGreaterEqual(len(resp.data["series"]), 1)

    def test_active_caregiver_can_read_linked_patient_metrics(self):
        HealthMetric.objects.create(
            patient=self.patient,
            kind="spo2",
            value=97,
            unit="percent",
            source="sim",
            recorded_at=timezone.now(),
        )
        self.client.force_authenticate(self.cg_user)
        resp = self.client.get(
            self.window_url,
            {"kind": "spo2", "hours": 24, "patient_id": self.patient.pk},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["count"], 1)


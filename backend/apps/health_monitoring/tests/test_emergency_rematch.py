"""Step 47 emergency re-match flow tests."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile, PatientProfile

from ..models import HealthEvent, HealthMetric
from ..tasks import detect_health_anomalies

User = get_user_model()


def _patient(email="pt.emergency@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Emergency",
        city="Colombo",
        location=Point(79.86, 6.92, srid=4326),
        preferred_language="English",
        languages=["English"],
        care_level="advanced",
        conditions=["diabetes"],
        height_cm=170,
        weight_kg=70,
        blood_type="O+",
        emergency_contact_name="EC",
        emergency_contact_phone="+94770000000",
    )
    return user


def _caregiver(email: str, *, advanced: bool, certs: list[str], offset_y: float):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    return CaregiverProfile.objects.create(
        user=user,
        display_name=email.split("@")[0],
        location=Point(79.86, 6.92 + offset_y, srid=4326),
        certifications=certs,
        specialties=["diabetes"],
        languages=["English"],
        care_levels=["advanced"] if advanced else ["basic"],
        trust_score=0.8,
        is_active=True,
        is_approved=True,
        is_available=True,
    )


class EmergencyRematchTests(TestCase):
    def setUp(self):
        self.patient = _patient()
        _caregiver("cg-basic@example.com", advanced=False, certs=["BLS"], offset_y=0.001)
        self.cg_advanced = _caregiver(
            "cg-advanced@example.com",
            advanced=True,
            certs=["ALS", "RN"],
            offset_y=0.002,
        )
        self.now = timezone.now()

    def _glucose(self, value: float, minutes_ago: int):
        HealthMetric.objects.create(
            patient=self.patient,
            kind="blood_glucose",
            value=value,
            unit="mg/dL",
            source="sim",
            recorded_at=self.now - timedelta(minutes=minutes_ago),
        )

    @patch("apps.matching.emergency.notify_health_critical_mobile")
    @patch("apps.matching.emergency.push_match_results")
    def test_health_critical_event_triggers_emergency_ws_push(self, push_mock, mobile_mock):
        self._glucose(215, 7)
        self._glucose(205, 4)
        self._glucose(210, 1)
        out = detect_health_anomalies()
        self.assertEqual(out["created"], 1)
        self.assertEqual(out["dispatched"], 1)
        event = HealthEvent.objects.get()
        self.assertEqual(event.event_type, "health_critical")
        self.assertIsNotNone(event.handled_at)
        self.assertIsNotNone(event.rematch_run_id)
        push_mock.assert_called_once()
        args, _kwargs = push_mock.call_args
        self.assertEqual(args[0], self.patient.pk)
        payload = args[1]
        self.assertTrue(payload["emergency"])
        self.assertEqual(payload["results"][0]["caregiver_id"], self.cg_advanced.pk)
        self.assertEqual(payload["emergency_context"]["event_id"], event.pk)
        mobile_mock.assert_called_once()


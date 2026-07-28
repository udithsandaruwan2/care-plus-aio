"""Step 46 anomaly daemon tests."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.matching.models import PatientProfile

from ..models import HealthEvent, HealthMetric
from ..services import detect_glucose_anomalies

User = get_user_model()


def _patient(email="pt.anomaly@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Anomaly",
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


class AnomalyDaemonTests(TestCase):
    def setUp(self):
        self.patient = _patient()
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

    def test_hyperglycemia_trend_emits_health_critical(self):
        self._glucose(205, 8)
        self._glucose(198, 5)
        self._glucose(212, 2)
        events = detect_glucose_anomalies(now=self.now)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e.event_type, "health_critical")
        self.assertEqual(e.rule_key, "hyperglycemia_trend")
        self.assertEqual(e.kind, "blood_glucose")

    def test_hypoglycemia_trend_emits_health_critical(self):
        self._glucose(62, 9)
        self._glucose(65, 4)
        self._glucose(59, 1)
        events = detect_glucose_anomalies(now=self.now)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].rule_key, "hypoglycemia_trend")

    def test_mixed_readings_do_not_emit(self):
        self._glucose(95, 7)
        self._glucose(210, 4)
        self._glucose(88, 1)
        events = detect_glucose_anomalies(now=self.now)
        self.assertEqual(events, [])
        self.assertEqual(HealthEvent.objects.count(), 0)

    def test_cooldown_suppresses_duplicate_events(self):
        self._glucose(220, 7)
        self._glucose(215, 4)
        self._glucose(210, 1)
        first = detect_glucose_anomalies(now=self.now, cooldown_minutes=60)
        second = detect_glucose_anomalies(now=self.now + timedelta(minutes=2), cooldown_minutes=60)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(HealthEvent.objects.count(), 1)


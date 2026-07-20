"""Step 28 — care-request mid-TTL reminders and expiry notices."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Role
from apps.matching.care_request_lifecycle import (
    expire_stale_care_requests_with_notice,
    send_pending_care_request_reminders,
)
from apps.matching.models import (
    CaregiverProfile,
    CareRequest,
    CareRequestStatus,
    PatientProfile,
)
from apps.matching.tasks import expire_care_requests, remind_care_requests

User = get_user_model()


def _patient(email="pt.ttl@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient TTL",
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


def _caregiver(email="cg.ttl@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG TTL",
        location=Point(79.86, 6.93, srid=4326),
        languages=["English"],
        care_levels=["basic"],
        trust_score=0.9,
        is_active=True,
        is_approved=True,
        is_available=True,
    )
    return user, profile


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CARE_REQUEST_NOTIFY_EMAIL_ENABLED=True,
    CARE_REQUEST_TTL_HOURS=48,
)
class CareRequestReminderTests(TestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        now = timezone.now()
        # Created 25h ago, expires in 23h → past N/2 (24h) for 48h TTL.
        self.req = CareRequest.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRequestStatus.PENDING,
            expires_at=now + timedelta(hours=23),
        )
        CareRequest.objects.filter(pk=self.req.pk).update(created_at=now - timedelta(hours=25))
        self.req.refresh_from_db()

    def test_mid_ttl_reminder_sends_once(self):
        count = send_pending_care_request_reminders()
        self.assertEqual(count, 1)
        self.req.refresh_from_db()
        self.assertIsNotNone(self.req.reminder_sent_at)
        self.assertEqual(len(mail.outbox), 2)  # patient + caregiver

        mail.outbox.clear()
        count2 = send_pending_care_request_reminders()
        self.assertEqual(count2, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_celery_remind_task(self):
        result = remind_care_requests()
        self.assertEqual(result["reminded"], 1)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CARE_REQUEST_NOTIFY_EMAIL_ENABLED=True,
)
class CareRequestExpiryNoticeTests(TestCase):
    def setUp(self):
        self.patient = _patient("pt.exp2@example.com")
        self.cg_user, self.caregiver = _caregiver("cg.exp2@example.com")
        self.req = CareRequest.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRequestStatus.PENDING,
            expires_at=timezone.now() - timedelta(hours=1),
        )

    def test_expiry_notifies_and_marks_expired(self):
        count = expire_stale_care_requests_with_notice()
        self.assertEqual(count, 1)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, CareRequestStatus.EXPIRED)
        self.assertEqual(len(mail.outbox), 2)

    def test_celery_expire_task(self):
        result = expire_care_requests()
        self.assertEqual(result["expired"], 1)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, CareRequestStatus.EXPIRED)

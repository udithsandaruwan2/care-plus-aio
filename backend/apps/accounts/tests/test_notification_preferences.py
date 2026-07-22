"""Step 39 — notification preference API tests."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import NotificationPreference

User = get_user_model()


class NotificationPreferenceApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="prefs@example.com", password="pw-strong-123")
        self.url = reverse("v1:notification_preferences")
        self.client.force_authenticate(user=self.user)

    def test_get_returns_defaults(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("events", res.data)
        self.assertIn("channels", res.data)
        keys = {e["key"] for e in res.data["events"]}
        self.assertIn("marketing_newsletter", keys)
        self.assertIn("security_login_alert", keys)
        security = next(e for e in res.data["events"] if e["key"] == "security_login_alert")
        self.assertTrue(security["locked"])

    def test_disable_marketing_email(self):
        res = self.client.patch(
            self.url,
            {"email": {"marketing_newsletter": False, "marketing_promotions": False}},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        newsletter = next(e for e in res.data["events"] if e["key"] == "marketing_newsletter")
        self.assertFalse(newsletter["email"])
        pref = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(pref.channels["email"]["marketing_newsletter"])

    def test_cannot_disable_security_alerts(self):
        res = self.client.patch(
            self.url,
            {"email": {"security_login_alert": False}},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be disabled", res.data["detail"].lower())

    def test_is_notification_enabled_respects_preferences(self):
        from apps.accounts.notification_preferences import is_notification_enabled

        NotificationPreference.objects.create(
            user=self.user,
            channels={"email": {"marketing_newsletter": False}},
        )
        self.assertFalse(
            is_notification_enabled(self.user, channel="email", event_key="marketing_newsletter")
        )
        self.assertTrue(
            is_notification_enabled(self.user, channel="email", event_key="security_login_alert")
        )

    @patch("apps.matching.care_request_lifecycle.send_mail")
    def test_reminder_email_skipped_when_disabled(self, send_mail_mock):
        from apps.matching.care_request_lifecycle import notify_care_request_reminder
        from apps.matching.models import CareRequest, CaregiverProfile, CareRequestStatus
        from django.contrib.gis.geos import Point
        from django.utils import timezone
        from datetime import timedelta

        cg_user = User.objects.create_user(
            email="cg.prefs@example.com", password="pw-strong-123", role="caregiver"
        )
        caregiver = CaregiverProfile.objects.create(
            user=cg_user,
            display_name="CG Prefs",
            location=Point(79.86, 6.93, srid=4326),
            certifications=[],
            specialties=[],
            languages=["English"],
            care_levels=["basic"],
            trust_score=0.9,
            is_active=True,
            is_approved=True,
            is_available=True,
        )
        NotificationPreference.objects.create(
            user=self.user,
            channels={"email": {"care_request_reminder": False}},
        )
        req = CareRequest.objects.create(
            patient=self.user,
            caregiver=caregiver,
            status=CareRequestStatus.PENDING,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        notify_care_request_reminder(req)
        patient_calls = [c for c in send_mail_mock.call_args_list if self.user.email in c[0][3]]
        self.assertEqual(len(patient_calls), 0)

"""Step 41 — Web Push subscription API tests."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PushSubscription, Role
from apps.matching.models import CaregiverProfile, PatientProfile

User = get_user_model()


class WebPushApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="push@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        self.client.force_authenticate(user=self.user)
        self.vapid_url = reverse("v1:vapid_public_key")
        self.sub_url = reverse("v1:push_subscriptions")

    def test_vapid_key_when_configured(self):
        with override_settings(VAPID_PUBLIC_KEY="BPublicKey", VAPID_PRIVATE_KEY="PrivateKey"):
            res = self.client.get(self.vapid_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["configured"])
        self.assertEqual(res.data["public_key"], "BPublicKey")

    def test_subscribe_and_unsubscribe(self):
        payload = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint-1",
            "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
            "user_agent": "TestBrowser",
        }
        res = self.client.post(self.sub_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 1)

        res = self.client.post(self.sub_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 1)

        res = self.client.delete(
            self.sub_url, {"endpoint": payload["endpoint"]}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["deleted"], 1)
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 0)

    @override_settings(
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
        WEB_PUSH_ENABLED=True,
        VAPID_PUBLIC_KEY="BPublic",
        VAPID_PRIVATE_KEY="Private",
    )
    @patch("apps.accounts.webpush.send_web_push")
    def test_care_request_triggers_push_when_subscribed(self, send_push_mock):
        send_push_mock.return_value = True
        PushSubscription.objects.create(
            user=self.user,
            endpoint="https://fcm.googleapis.com/fcm/send/cg-endpoint",
            p256dh="p256",
            auth="auth",
        )
        patient = User.objects.create_user(
            email="pt.push@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(
            user=patient,
            display_name="Push Patient",
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
        caregiver = CaregiverProfile.objects.create(
            user=self.user,
            display_name="CG Push",
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
        from apps.matching.care_requests import create_care_request

        create_care_request(patient=patient, caregiver=caregiver, message="Need care")
        self.assertTrue(send_push_mock.called)
        payload = send_push_mock.call_args.kwargs["payload"]
        self.assertEqual(payload["title"], "New care request")

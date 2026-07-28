"""Step 49 — mobile push token API + health critical dispatch."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import MobilePushDevice, Role
from apps.accounts.notifications.push_dispatch import notify_health_critical_mobile

User = get_user_model()


class MobilePushApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="mobile.push@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse("v1:mobile_push_devices")

    def test_register_and_remove_mobile_device_token(self):
        payload = {"token": "fcm-token-123", "platform": "fcm", "device_id": "device-A"}
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(MobilePushDevice.objects.filter(user=self.user).count(), 1)

        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(MobilePushDevice.objects.filter(user=self.user).count(), 1)

        res = self.client.delete(self.url, {"token": payload["token"]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["deleted"], 1)
        self.assertEqual(MobilePushDevice.objects.filter(user=self.user).count(), 0)

    @patch("apps.accounts.notifications.tasks.send_mobile_push_notification.delay")
    @patch("apps.accounts.mobile_push.mobile_push_configured")
    def test_notify_health_critical_mobile_queues_task(self, configured_mock, delay_mock):
        configured_mock.return_value = True
        MobilePushDevice.objects.create(user=self.user, token="fcm-token-xyz", platform="fcm")
        ok = notify_health_critical_mobile(user=self.user, event_id=77, caregiver_id=9, match_run_id=88)
        self.assertTrue(ok)
        delay_mock.assert_called_once()
        kwargs = delay_mock.call_args.kwargs
        self.assertEqual(kwargs["user_id"], self.user.pk)
        self.assertEqual(kwargs["event_key"], "health_critical")


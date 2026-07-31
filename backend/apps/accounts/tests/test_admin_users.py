"""Step 54 — admin/auditor user directory + admin disable account."""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role

User = get_user_model()


class AdminUserApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin.users@example.com",
            password="pw-strong-123",
            role=Role.ADMIN,
        )
        self.auditor = User.objects.create_user(
            email="auditor.users@example.com",
            password="pw-strong-123",
            role=Role.AUDITOR,
        )
        self.patient = User.objects.create_user(
            email="patient.users@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )
        self.caregiver = User.objects.create_user(
            email="caregiver.users@example.com",
            password="pw-strong-123",
            role=Role.CAREGIVER,
        )
        self.list_url = reverse("v1:admin_user_list")

    def test_patient_forbidden(self):
        self.client.force_authenticate(self.patient)
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_lists_and_filters_by_role(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get(self.list_url, {"role": "patient"})
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        emails = [row["email"] for row in res.data["results"]]
        self.assertIn(self.patient.email, emails)
        self.assertNotIn(self.caregiver.email, emails)

    def test_auditor_can_list_but_not_disable(self):
        self.client.force_authenticate(self.auditor)
        listed = self.client.get(self.list_url)
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)

        detail = reverse("v1:admin_user_detail", kwargs={"pk": self.patient.pk})
        patched = self.client.patch(detail, {"is_active": False}, format="json")
        self.assertEqual(patched.status_code, status.HTTP_403_FORBIDDEN)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_active)

    def test_admin_disables_and_reenables(self):
        self.client.force_authenticate(self.admin)
        detail = reverse("v1:admin_user_detail", kwargs={"pk": self.patient.pk})
        disabled = self.client.patch(detail, {"is_active": False}, format="json")
        self.assertEqual(disabled.status_code, status.HTTP_200_OK, disabled.data)
        self.assertFalse(disabled.data["is_active"])
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_active)

        enabled = self.client.patch(detail, {"is_active": True}, format="json")
        self.assertEqual(enabled.status_code, status.HTTP_200_OK, enabled.data)
        self.assertTrue(enabled.data["is_active"])

    def test_admin_cannot_disable_self(self):
        self.client.force_authenticate(self.admin)
        detail = reverse("v1:admin_user_detail", kwargs={"pk": self.admin.pk})
        res = self.client.patch(detail, {"is_active": False}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

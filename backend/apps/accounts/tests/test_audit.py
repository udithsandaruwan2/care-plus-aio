"""Step 8 acceptance: immutable audit trail.

Viewing patient health writes exactly one append-only audit row. Updates and
deletes are rejected by the ORM and by a Postgres trigger.
"""

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditAction, AuditLog, Role

User = get_user_model()


class AuditTrailApiTests(APITestCase):
    def setUp(self):
        self.caregiver = User.objects.create_user(
            email="care@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        self.patient = User.objects.create_user(
            email="patient@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        self.auditor = User.objects.create_user(
            email="auditor@example.com", password="pw-strong-123", role=Role.AUDITOR
        )
        self.demo_url = reverse("v1:audit_demo_view_health")
        self.list_url = reverse("v1:audit_list")

    def test_view_health_writes_exactly_one_audit_row(self):
        self.client.force_authenticate(self.caregiver)
        before = AuditLog.objects.count()

        resp = self.client.get(self.demo_url, {"patient_id": self.patient.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.assertEqual(AuditLog.objects.count(), before + 1)
        row = AuditLog.objects.latest("ts")
        self.assertEqual(row.action, AuditAction.VIEW_HEALTH)
        self.assertEqual(row.actor_id, self.caregiver.pk)
        self.assertEqual(row.target_type, "patient")
        self.assertEqual(row.target_id, str(self.patient.pk))

    def test_second_view_appends_another_row(self):
        self.client.force_authenticate(self.caregiver)
        self.client.get(self.demo_url, {"patient_id": self.patient.pk})
        self.client.get(self.demo_url, {"patient_id": self.patient.pk})
        self.assertEqual(
            AuditLog.objects.filter(
                actor=self.caregiver, action=AuditAction.VIEW_HEALTH
            ).count(),
            2,
        )

    def test_audit_list_requires_admin_or_auditor(self):
        self.client.force_authenticate(self.caregiver)
        denied = self.client.get(self.list_url)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.auditor)
        allowed = self.client.get(self.list_url)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_orm_rejects_update_and_delete(self):
        row = AuditLog.objects.create(
            actor=self.caregiver,
            action=AuditAction.VIEW_HEALTH,
            target_type="patient",
            target_id="1",
        )
        with self.assertRaises(ValueError):
            row.action = AuditAction.LOGIN
            row.save()
        with self.assertRaises(ValueError):
            row.delete()


class AuditLogImmutabilityDbTests(TestCase):
    """Postgres trigger blocks UPDATE/DELETE even via QuerySet (bypasses ORM)."""

    def setUp(self):
        self.user = User.objects.create_user(email="u@example.com", password="pw-strong-123")
        self.row = AuditLog.objects.create(
            actor=self.user,
            action=AuditAction.VIEW_HEALTH,
            target_type="patient",
            target_id="99",
        )

    def test_sql_update_blocked(self):
        if connection.vendor != "postgresql":
            self.skipTest("immutability trigger is Postgres-only")
        with self.assertRaises(Exception):
            with transaction.atomic():
                AuditLog.objects.filter(pk=self.row.pk).update(action=AuditAction.LOGIN)

    def test_sql_delete_blocked(self):
        if connection.vendor != "postgresql":
            self.skipTest("immutability trigger is Postgres-only")
        with self.assertRaises(Exception):
            with transaction.atomic():
                AuditLog.objects.filter(pk=self.row.pk).delete()
        self.assertTrue(AuditLog.objects.filter(pk=self.row.pk).exists())

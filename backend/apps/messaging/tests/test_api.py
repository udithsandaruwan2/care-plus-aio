"""Step 38 — messaging REST API tests."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import (
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    PatientProfile,
)
from apps.messaging.models import Message, MessageThread

User = get_user_model()


def _patient(email="pt.msg@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Msg",
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


def _caregiver(email="cg.msg@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Msg",
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


class MessagingApiTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ACTIVE,
            is_primary=True,
        )
        self.thread = MessageThread.objects.create(relationship=self.rel)
        self.current_url = reverse("v1:message_thread_current")
        self.messages_url = reverse("v1:message_list_create", kwargs={"pk": self.thread.pk})
        self.read_url = reverse("v1:message_read", kwargs={"pk": self.thread.pk})

    def test_current_thread_for_patient(self):
        self.client.force_authenticate(user=self.patient)
        res = self.client.get(self.current_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], self.thread.pk)
        self.assertEqual(res.data["partner_label"], "CG Msg")

    def test_patient_sends_and_caregiver_lists(self):
        self.client.force_authenticate(user=self.patient)
        res = self.client.post(self.messages_url, {"body": "Hello caregiver"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["is_mine"])

        self.client.force_authenticate(user=self.cg_user)
        res = self.client.get(self.messages_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["body"], "Hello caregiver")
        self.assertFalse(res.data[0]["is_mine"])

    def test_read_receipt(self):
        msg = Message.objects.create(
            thread=self.thread, sender=self.patient, body="Please confirm visit"
        )
        self.client.force_authenticate(user=self.cg_user)
        res = self.client.post(
            self.read_url, {"last_read_message_id": msg.pk}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.read_at)

    def test_ended_relationship_denied(self):
        self.rel.status = CareRelationshipStatus.ENDED
        self.rel.save(update_fields=["status"])
        self.client.force_authenticate(user=self.patient)
        res = self.client.post(self.messages_url, {"body": "Too late"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_poll_after_id(self):
        m1 = Message.objects.create(thread=self.thread, sender=self.patient, body="One")
        m2 = Message.objects.create(thread=self.thread, sender=self.cg_user, body="Two")
        self.client.force_authenticate(user=self.patient)
        res = self.client.get(f"{self.messages_url}?after_id={m1.pk}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["id"], m2.pk)

    def test_outsider_denied(self):
        outsider = User.objects.create_user(
            email="out.msg@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        self.client.force_authenticate(user=outsider)
        res = self.client.get(self.messages_url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

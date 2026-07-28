"""Step 50 — caregiver weekly availability slots API."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile, PatientProfile

User = get_user_model()


def _caregiver(email="cg.slot@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Slot",
        location=Point(79.86, 6.93, srid=4326),
        certifications=["First Aid"],
        specialties=["diabetes"],
        languages=["English"],
        care_levels=["basic", "advanced"],
        trust_score=0.9,
        is_active=True,
        is_approved=True,
        is_available=True,
    )
    return user, profile


def _patient(email="pt.slot@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="PT Slot",
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


class ScheduleApiTests(APITestCase):
    def setUp(self):
        self.cg_user, self.cg_profile = _caregiver()
        self.pt_user = _patient()
        self.cg_slots_url = reverse("v1:caregiver_availability_slot_list")
        self.public_slots_url = reverse(
            "v1:caregiver_availability_public_list",
            kwargs={"pk": self.cg_profile.pk},
        )

    def test_caregiver_can_publish_weekly_slots(self):
        self.client.force_authenticate(self.cg_user)
        res = self.client.post(
            self.cg_slots_url,
            {
                "weekday": 0,
                "start_time": "09:00:00",
                "end_time": "12:00:00",
                "timezone": "Asia/Colombo",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data["weekday"], 0)
        self.assertEqual(res.data["timezone"], "Asia/Colombo")

        res = self.client.get(self.cg_slots_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

    def test_patient_sees_free_slots_for_caregiver(self):
        self.client.force_authenticate(self.cg_user)
        self.client.post(
            self.cg_slots_url,
            {
                "weekday": 2,
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "timezone": "Asia/Colombo",
            },
            format="json",
        )
        self.client.force_authenticate(self.pt_user)
        res = self.client.get(self.public_slots_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["weekday"], 2)

    def test_patient_cannot_publish_slots(self):
        self.client.force_authenticate(self.pt_user)
        res = self.client.post(
            self.cg_slots_url,
            {"weekday": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


"""Step 51 — Redlock-protected shift booking API."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase, APITransactionTestCase

from apps.accounts.models import Role
from apps.matching.models import (
    CaregiverAvailabilitySlot,
    CaregiverProfile,
    PatientProfile,
    Shift,
    ShiftStatus,
)

User = get_user_model()
COLOMBO = ZoneInfo("Asia/Colombo")


def _next_monday_at(hour: int, minute: int = 0) -> datetime:
    now = timezone.now().astimezone(COLOMBO)
    days_ahead = (0 - now.weekday()) % 7
    if days_ahead == 0 and (now.hour, now.minute) >= (hour, minute):
        days_ahead = 7
    day = (now + timedelta(days=days_ahead)).date()
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=COLOMBO)


def _caregiver(email="cg.shift@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Shift",
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


def _patient(email="pt.shift@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="PT Shift",
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


class ShiftBookingApiTests(APITestCase):
    def setUp(self):
        self.cg_user, self.cg_profile = _caregiver()
        self.pt_user = _patient()
        self.pt2 = _patient(email="pt2.shift@example.com")
        self.slot = CaregiverAvailabilitySlot.objects.create(
            caregiver=self.cg_profile,
            weekday=0,
            start_time="09:00:00",
            end_time="12:00:00",
            timezone="Asia/Colombo",
            is_active=True,
        )
        self.list_url = reverse("v1:shift_list")
        self.starts = _next_monday_at(9, 0)
        self.ends = self.starts + timedelta(hours=2)

    def _payload(self, **overrides):
        data = {
            "caregiver_id": self.cg_profile.pk,
            "starts_at": self.starts.isoformat(),
            "ends_at": self.ends.isoformat(),
            "availability_slot_id": self.slot.pk,
            "timezone": "Asia/Colombo",
            "notes": "Morning visit",
        }
        data.update(overrides)
        return data

    def test_patient_can_book_shift(self):
        self.client.force_authenticate(self.pt_user)
        res = self.client.post(self.list_url, self._payload(), format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data["status"], ShiftStatus.BOOKED)
        self.assertEqual(res.data["caregiver"], self.cg_profile.pk)
        self.assertEqual(Shift.objects.filter(status=ShiftStatus.BOOKED).count(), 1)

        listed = self.client.get(self.list_url)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data), 1)

    def test_overlap_rejected(self):
        self.client.force_authenticate(self.pt_user)
        first = self.client.post(self.list_url, self._payload(), format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)

        self.client.force_authenticate(self.pt2)
        second = self.client.post(
            self.list_url,
            self._payload(
                starts_at=(self.starts + timedelta(hours=1)).isoformat(),
                ends_at=(self.ends + timedelta(hours=1)).isoformat(),
            ),
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST, second.data)
        self.assertEqual(Shift.objects.filter(status=ShiftStatus.BOOKED).count(), 1)

    def test_cancel_shift(self):
        self.client.force_authenticate(self.pt_user)
        booked = self.client.post(self.list_url, self._payload(), format="json")
        self.assertEqual(booked.status_code, status.HTTP_201_CREATED, booked.data)
        detail = reverse("v1:shift_detail", kwargs={"pk": booked.data["id"]})
        cancelled = self.client.delete(detail)
        self.assertEqual(cancelled.status_code, status.HTTP_200_OK, cancelled.data)
        self.assertEqual(cancelled.data["status"], ShiftStatus.CANCELLED)

        # Slot frees after cancel — second patient can book same window.
        self.client.force_authenticate(self.pt2)
        again = self.client.post(self.list_url, self._payload(notes="retry"), format="json")
        self.assertEqual(again.status_code, status.HTTP_201_CREATED, again.data)


class ConcurrentShiftBookingTests(APITransactionTestCase):
    """TransactionTestCase so worker threads can see committed setUp rows."""

    def setUp(self):
        self.cg_user, self.cg_profile = _caregiver(email="cg.concurrent@example.com")
        self.pt_user = _patient(email="pt.concurrent@example.com")
        self.pt2 = _patient(email="pt2.concurrent@example.com")
        self.slot = CaregiverAvailabilitySlot.objects.create(
            caregiver=self.cg_profile,
            weekday=0,
            start_time="09:00:00",
            end_time="12:00:00",
            timezone="Asia/Colombo",
            is_active=True,
        )
        self.list_url = reverse("v1:shift_list")
        self.starts = _next_monday_at(10, 0)
        self.ends = self.starts + timedelta(hours=1)

    def test_concurrent_book_exactly_one_success(self):
        starts = self.starts.isoformat()
        ends = self.ends.isoformat()
        caregiver_id = self.cg_profile.pk
        slot_id = self.slot.pk
        patients = [self.pt_user, self.pt2]
        list_url = self.list_url

        def attempt(user):
            client = APIClient()
            client.force_authenticate(user)
            try:
                res = client.post(
                    list_url,
                    {
                        "caregiver_id": caregiver_id,
                        "starts_at": starts,
                        "ends_at": ends,
                        "availability_slot_id": slot_id,
                        "timezone": "Asia/Colombo",
                    },
                    format="json",
                )
                return res.status_code
            finally:
                connection.close()

        codes = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt, u) for u in patients]
            for fut in as_completed(futures):
                codes.append(fut.result())

        self.assertEqual(codes.count(status.HTTP_201_CREATED), 1, codes)
        self.assertEqual(
            codes.count(status.HTTP_400_BAD_REQUEST)
            + codes.count(status.HTTP_409_CONFLICT)
            + codes.count(status.HTTP_503_SERVICE_UNAVAILABLE),
            1,
            codes,
        )
        self.assertEqual(Shift.objects.filter(status=ShiftStatus.BOOKED).count(), 1)

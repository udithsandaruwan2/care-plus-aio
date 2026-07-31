"""Step 53 — shift conflict returns VEHMF next-best caregiver offer."""

import tempfile
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.matching.faiss_index import build_index, reset_cache
from apps.matching.models import CaregiverAvailabilitySlot, CaregiverProfile, MatchRun, Shift, ShiftStatus
from apps.matching.tests.test_shift_booking import (
    _caregiver,
    _next_monday_at,
    _patient,
)


class ShiftConflictFallbackTests(APITestCase):
    def setUp(self):
        reset_cache()
        self.cg1_user, self.cg1 = _caregiver(email="cg1.fallback@example.com")
        self.cg1.display_name = "Primary Booked"
        self.cg1.specialties = ["diabetes"]
        self.cg1.languages = ["English"]
        self.cg1.care_levels = ["basic", "advanced"]
        self.cg1.trust_score = 0.95
        self.cg1.location = Point(79.86, 6.93, srid=4326)
        self.cg1.save()

        self.cg2_user, self.cg2 = _caregiver(email="cg2.fallback@example.com")
        self.cg2.display_name = "Next Best Alt"
        self.cg2.specialties = ["diabetes"]
        self.cg2.languages = ["English"]
        self.cg2.care_levels = ["basic", "advanced"]
        self.cg2.trust_score = 0.85
        self.cg2.location = Point(79.87, 6.94, srid=4326)
        self.cg2.save()

        self.pt1 = _patient(email="pt1.fallback@example.com")
        self.pt2 = _patient(email="pt2.fallback@example.com")

        self.slot1 = CaregiverAvailabilitySlot.objects.create(
            caregiver=self.cg1,
            weekday=0,
            start_time="09:00:00",
            end_time="12:00:00",
            timezone="Asia/Colombo",
            is_active=True,
        )
        self.slot2 = CaregiverAvailabilitySlot.objects.create(
            caregiver=self.cg2,
            weekday=0,
            start_time="09:00:00",
            end_time="12:00:00",
            timezone="Asia/Colombo",
            is_active=True,
        )
        self.list_url = reverse("v1:shift_list")
        self.starts = _next_monday_at(9, 0)
        self.ends = self.starts + timedelta(hours=2)

    def _payload(self, caregiver: CaregiverProfile, slot: CaregiverAvailabilitySlot, **overrides):
        data = {
            "caregiver_id": caregiver.pk,
            "starts_at": self.starts.isoformat(),
            "ends_at": self.ends.isoformat(),
            "availability_slot_id": slot.pk,
            "timezone": "Asia/Colombo",
        }
        data.update(overrides)
        return data

    def test_loser_offered_next_best_caregiver(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash", CF_ENABLED=False):
                reset_cache()
                build_index(persist=True)

                self.client.force_authenticate(self.pt1)
                first = self.client.post(
                    self.list_url,
                    self._payload(self.cg1, self.slot1),
                    format="json",
                )
                self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)

                self.client.force_authenticate(self.pt2)
                second = self.client.post(
                    self.list_url,
                    self._payload(self.cg1, self.slot1),
                    format="json",
                )
                self.assertEqual(second.status_code, status.HTTP_409_CONFLICT, second.data)
                self.assertTrue(second.data.get("conflict"))
                self.assertEqual(second.data.get("code"), "shift_overlap")
                fallback = second.data.get("fallback")
                self.assertIsNotNone(fallback, second.data)
                self.assertEqual(fallback["caregiver_id"], self.cg2.pk)
                self.assertEqual(fallback["availability_slot_id"], self.slot2.pk)
                self.assertEqual(fallback["display_name"], "Next Best Alt")
                self.assertTrue(MatchRun.objects.filter(pk=fallback["match_run_id"]).exists())
                self.assertEqual(Shift.objects.filter(status=ShiftStatus.BOOKED).count(), 1)

                # Loser can book the offered caregiver for the same window.
                book_alt = self.client.post(
                    self.list_url,
                    self._payload(
                        self.cg2,
                        self.slot2,
                        notes="accepted fallback",
                    ),
                    format="json",
                )
                self.assertEqual(book_alt.status_code, status.HTTP_201_CREATED, book_alt.data)
                self.assertEqual(book_alt.data["caregiver"], self.cg2.pk)
                self.assertEqual(Shift.objects.filter(status=ShiftStatus.BOOKED).count(), 2)

    def test_overlap_without_alt_still_409(self):
        CaregiverAvailabilitySlot.objects.filter(caregiver=self.cg2).delete()
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash", CF_ENABLED=False):
                reset_cache()
                build_index(persist=True)

                self.client.force_authenticate(self.pt1)
                first = self.client.post(
                    self.list_url,
                    self._payload(self.cg1, self.slot1),
                    format="json",
                )
                self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)

                self.client.force_authenticate(self.pt2)
                second = self.client.post(
                    self.list_url,
                    self._payload(self.cg1, self.slot1),
                    format="json",
                )
                self.assertEqual(second.status_code, status.HTTP_409_CONFLICT, second.data)
                self.assertTrue(second.data.get("conflict"))
                self.assertIsNone(second.data.get("fallback"))

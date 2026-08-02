"""Step 71 — match p95 latency + Redlock concurrency acceptance tests."""

from __future__ import annotations

import os
import statistics
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.db import connection
from django.test import tag
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase, APITransactionTestCase

from apps.accounts.models import ConsentLog, ConsentScope, Role
from apps.matching.faiss_index import reset_cache
from apps.matching.models import (
    CaregiverAvailabilitySlot,
    CaregiverProfile,
    PatientProfile,
    Shift,
    ShiftStatus,
)

User = get_user_model()
COLOMBO = ZoneInfo("Asia/Colombo")

# Architecture / Step 19 budget; overridable for slow environments.
MATCH_P95_MS = int(os.environ.get("MATCH_P95_MS", "800"))
MATCH_SAMPLES = int(os.environ.get("MATCH_SAMPLES", "25"))
BOOK_CONCURRENCY = int(os.environ.get("BOOK_CONCURRENCY", "8"))


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def _next_monday_at(hour: int, minute: int = 0) -> datetime:
    now = timezone.now().astimezone(COLOMBO)
    days_ahead = (0 - now.weekday()) % 7
    if days_ahead == 0 and (now.hour, now.minute) >= (hour, minute):
        days_ahead = 7
    day = (now + timedelta(days=days_ahead)).date()
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=COLOMBO)


@tag("load")
class MatchP95LatencyTests(APITestCase):
    """Server-reported match latency p95 must stay under the architecture budget."""

    def setUp(self):
        reset_cache()
        self.patient = User.objects.create_user(
            email="load.pt@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )
        ConsentLog.objects.create(
            user=self.patient, scope=ConsentScope.AI_PROCESSING, granted=True
        )
        for i in range(5):
            cg = User.objects.create_user(
                email=f"load.cg{i}@example.com",
                password="pw-strong-123",
                role=Role.CAREGIVER,
            )
            CaregiverProfile.objects.create(
                user=cg,
                display_name=f"Load CG {i}",
                location=Point(79.86 + i * 0.01, 6.93, srid=4326),
                certifications=["First Aid"],
                specialties=["diabetes" if i % 2 == 0 else "wound care"],
                languages=["Sinhala", "English"],
                care_levels=["intermediate", "basic"],
                trust_score=0.7 + i * 0.05,
                bio=f"seed caregiver {i}",
                is_active=True,
                is_approved=True,
                is_available=True,
            )
        self.url = reverse("v1:match")

    def test_match_latency_p95_under_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                call_command("build_caregiver_index", verbosity=0)
                self.client.force_authenticate(self.patient)
                samples: list[float] = []
                for _ in range(MATCH_SAMPLES):
                    resp = self.client.post(
                        self.url,
                        {
                            "condition": "diabetes",
                            "language": "Sinhala",
                            "care_level": "intermediate",
                            "longitude": 79.86,
                            "latitude": 6.93,
                            "k": 5,
                        },
                        format="json",
                    )
                    self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
                    samples.append(float(resp.data["latency_ms"]))

                samples.sort()
                p95 = _percentile(samples, 95)
                self.assertLessEqual(
                    p95,
                    MATCH_P95_MS,
                    msg=(
                        f"match p95={p95:.1f}ms exceeds {MATCH_P95_MS}ms "
                        f"(n={len(samples)}, mean={statistics.mean(samples):.1f}, "
                        f"max={samples[-1]:.1f})"
                    ),
                )


@tag("load")
class RedlockHighConcurrencyTests(APITransactionTestCase):
    """N concurrent bookings for the same window → exactly one BOOKED shift."""

    def setUp(self):
        self.cg_user = User.objects.create_user(
            email="load.cg.lock@example.com",
            password="pw-strong-123",
            role=Role.CAREGIVER,
        )
        self.cg_profile = CaregiverProfile.objects.create(
            user=self.cg_user,
            display_name="Load Lock CG",
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
        self.slot = CaregiverAvailabilitySlot.objects.create(
            caregiver=self.cg_profile,
            weekday=0,
            start_time="09:00:00",
            end_time="17:00:00",
            timezone="Asia/Colombo",
            is_active=True,
        )
        self.patients = []
        for i in range(BOOK_CONCURRENCY):
            user = User.objects.create_user(
                email=f"load.pt{i}@example.com",
                password="pw-strong-123",
                role=Role.PATIENT,
            )
            PatientProfile.objects.create(
                user=user,
                display_name=f"Load PT {i}",
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
            self.patients.append(user)
        self.list_url = reverse("v1:shift_list")
        self.starts = _next_monday_at(10, 0)
        self.ends = self.starts + timedelta(hours=1)

    def test_eight_way_concurrent_book_exactly_one_success(self):
        starts = self.starts.isoformat()
        ends = self.ends.isoformat()
        caregiver_id = self.cg_profile.pk
        slot_id = self.slot.pk
        list_url = self.list_url
        patients = list(self.patients)

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

        codes: list[int] = []
        with ThreadPoolExecutor(max_workers=len(patients)) as pool:
            futures = [pool.submit(attempt, u) for u in patients]
            for fut in as_completed(futures):
                codes.append(fut.result())

        self.assertEqual(codes.count(status.HTTP_201_CREATED), 1, codes)
        losers = (
            codes.count(status.HTTP_400_BAD_REQUEST)
            + codes.count(status.HTTP_409_CONFLICT)
            + codes.count(status.HTTP_503_SERVICE_UNAVAILABLE)
        )
        self.assertEqual(losers, len(patients) - 1, codes)
        self.assertEqual(Shift.objects.filter(status=ShiftStatus.BOOKED).count(), 1)

"""Step 76 — COMPLETE / RATE / REJECT interaction logging + idempotent backfill."""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.db.models import Count
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.care_relationships import end_relationship
from apps.matching.care_requests import reject_care_request
from apps.matching.cf_model import reset_cf_cache
from apps.matching.cf_train import train_cf_als
from apps.matching.interactions import (
    backfill_outcome_interactions,
    complete_outcome_key,
    log_interaction,
)
from apps.matching.models import (
    INTERACTION_WEIGHTS,
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
    Interaction,
    InteractionKind,
    PatientProfile,
    Review,
    ReviewStatus,
)

User = get_user_model()


def _patient(email="pt.out@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Out",
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


def _caregiver(email="cg.out@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Out",
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


def _pending_request(patient, caregiver, *, message="Need help"):
    from datetime import timedelta

    from django.utils import timezone

    return CareRequest.objects.create(
        patient=patient,
        caregiver=caregiver,
        status=CareRequestStatus.PENDING,
        message=message,
        expires_at=timezone.now() + timedelta(hours=72),
    )


class OutcomeInteractionLiveTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()

    def test_reject_care_request_logs_negative_reject(self):
        req = _pending_request(self.patient, self.caregiver)
        reject_care_request(req, caregiver_user=self.cg_user, reason="Booked")
        row = Interaction.objects.get(kind=InteractionKind.REJECT)
        self.assertEqual(row.patient_id, self.patient.pk)
        self.assertEqual(row.caregiver_id, self.caregiver.pk)
        self.assertEqual(row.weight, INTERACTION_WEIGHTS[InteractionKind.REJECT])
        self.assertEqual(row.metadata["care_request_id"], req.pk)
        self.assertTrue(row.metadata["outcome_key"].startswith("reject:"))

    def test_end_active_relationship_logs_complete(self):
        rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ACTIVE,
        )
        end_relationship(rel, actor=self.patient, reason="Done")
        row = Interaction.objects.get(kind=InteractionKind.COMPLETE)
        self.assertEqual(row.weight, 8.0)
        self.assertEqual(row.metadata["relationship_id"], rel.pk)
        self.assertEqual(row.metadata["outcome_key"], complete_outcome_key(rel.pk))

    def test_end_pending_payment_does_not_log_complete(self):
        rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.PENDING_PAYMENT,
        )
        end_relationship(rel, actor=self.patient, reason="Never paid")
        self.assertFalse(Interaction.objects.filter(kind=InteractionKind.COMPLETE).exists())

    def test_review_submission_logs_rate_times_stars(self):
        rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ENDED,
        )
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            reverse("v1:review_list"),
            {"relationship_id": rel.pk, "rating": 5, "comment": "Great"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        row = Interaction.objects.get(kind=InteractionKind.RATE)
        self.assertEqual(row.weight, 5.0)
        self.assertEqual(row.rating, 5)
        self.assertEqual(row.metadata["review_id"], resp.data["id"])


class OutcomeBackfillTests(TestCase):
    def setUp(self):
        self.patient = _patient("pt.bf@example.com")
        self.cg_user, self.caregiver = _caregiver("cg.bf@example.com")

    def test_backfill_is_idempotent_and_covers_orm_rows(self):
        rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ENDED,
        )
        review = Review.objects.create(
            relationship=rel,
            patient=self.patient,
            caregiver=self.caregiver,
            rating=4,
            comment="Backfill me",
            status=ReviewStatus.APPROVED,
        )
        req = _pending_request(self.patient, self.caregiver, message="Nope")
        req.status = CareRequestStatus.REJECTED
        req.save(update_fields=["status"])

        first = backfill_outcome_interactions()
        self.assertEqual(first, {"complete": 1, "rate": 1, "reject": 1})
        second = backfill_outcome_interactions()
        self.assertEqual(second, {"complete": 0, "rate": 0, "reject": 0})
        self.assertEqual(Interaction.objects.filter(kind=InteractionKind.COMPLETE).count(), 1)
        self.assertEqual(Interaction.objects.filter(kind=InteractionKind.RATE).count(), 1)
        self.assertEqual(Interaction.objects.filter(kind=InteractionKind.REJECT).count(), 1)
        rate = Interaction.objects.get(kind=InteractionKind.RATE)
        self.assertEqual(rate.weight, 4.0)
        self.assertEqual(rate.metadata["review_id"], review.pk)

    def test_backfill_command_and_all_kinds_on_seeded_funnel(self):
        log_interaction(self.patient, self.caregiver, InteractionKind.VIEW)
        log_interaction(self.patient, self.caregiver, InteractionKind.REQUEST)
        log_interaction(self.patient, self.caregiver, InteractionKind.ACCEPT)

        rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ACTIVE,
        )
        end_relationship(rel, actor=self.patient, reason="Finished")
        Review.objects.create(
            relationship=rel,
            patient=self.patient,
            caregiver=self.caregiver,
            rating=5,
            status=ReviewStatus.PENDING,
        )
        req = _pending_request(self.patient, self.caregiver)
        reject_care_request(req, caregiver_user=self.cg_user)

        call_command("backfill_interactions", verbosity=0)
        kinds = {
            row["kind"]
            for row in Interaction.objects.values("kind").annotate(n=Count("id"))
        }
        self.assertEqual(
            kinds,
            {
                InteractionKind.VIEW,
                InteractionKind.REQUEST,
                InteractionKind.ACCEPT,
                InteractionKind.COMPLETE,
                InteractionKind.RATE,
                InteractionKind.REJECT,
            },
        )

        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(CF_ARTIFACT_DIR=str(Path(tmp) / "cf")):
                reset_cf_cache()
                meta = train_cf_als(factors=8, iterations=5)
                self.assertGreaterEqual(meta["n_interactions"], 6)
                self.assertTrue(
                    Interaction.objects.filter(kind=InteractionKind.COMPLETE).exists()
                )

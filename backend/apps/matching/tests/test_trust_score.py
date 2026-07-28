"""Step 43 — caregiver trust score recompute jobs."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.matching.models import (
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
    PatientProfile,
    Review,
    ReviewStatus,
)
from apps.matching.tasks import recompute_all_caregiver_trust, recompute_caregiver_trust

User = get_user_model()


def _patient(email="pt.trust@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Trust",
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


def _caregiver(email="cg.trust@example.com", *, trust=0.3):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Trust",
        location=Point(79.86, 6.93, srid=4326),
        certifications=["First Aid"],
        specialties=["dengue"],
        languages=["English"],
        care_levels=["basic"],
        trust_score=trust,
        is_active=True,
        is_approved=True,
        is_available=True,
    )
    return user, profile


class TrustScoreTaskTests(TestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ENDED,
            is_primary=True,
        )
        Review.objects.create(
            relationship=self.rel,
            patient=self.patient,
            caregiver=self.caregiver,
            rating=5,
            comment="Excellent",
            status=ReviewStatus.APPROVED,
        )
        req = CareRequest.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRequestStatus.ACCEPTED,
            expires_at=timezone.now() + timedelta(hours=12),
            responded_at=timezone.now() + timedelta(hours=1),
        )
        CareRequest.objects.filter(pk=req.pk).update(created_at=timezone.now())

    def test_recompute_single_caregiver_trust(self):
        before = self.caregiver.trust_score
        out = recompute_caregiver_trust(self.caregiver.pk)
        self.caregiver.refresh_from_db()
        self.assertEqual(out["caregiver_id"], self.caregiver.pk)
        self.assertGreater(self.caregiver.trust_score, before)
        self.assertGreaterEqual(self.caregiver.trust_score, 0.0)
        self.assertLessEqual(self.caregiver.trust_score, 1.0)

    def test_recompute_all_caregiver_trust(self):
        _, cg2 = _caregiver("cg2.trust@example.com", trust=0.6)
        result = recompute_all_caregiver_trust()
        self.assertGreaterEqual(result["updated"], 2)
        cg2.refresh_from_db()
        self.assertGreaterEqual(cg2.trust_score, 0.0)

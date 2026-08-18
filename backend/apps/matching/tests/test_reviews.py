"""Step 42 — Review model, creation rules, and moderation."""

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
    Interaction,
    InteractionKind,
    PatientProfile,
    Review,
    ReviewStatus,
)

User = get_user_model()


def _patient(email="pt.review@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Review",
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


def _caregiver(email="cg.review@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Review",
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


class ReviewApiTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.other_patient = _patient(email="other.review@example.com")
        self.cg_user, self.caregiver = _caregiver()
        self.admin = User.objects.create_user(
            email="admin.review@example.com",
            password="pw-strong-123",
            role=Role.ADMIN,
        )
        self.rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ENDED,
            is_primary=True,
        )
        self.review_list_url = reverse("v1:review_list")
        self.review_moderate_url = lambda pk: reverse("v1:review_moderate", kwargs={"pk": pk})

    def test_patient_can_create_pending_review_after_relationship_ended(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            self.review_list_url,
            {"relationship_id": self.rel.pk, "rating": 5, "comment": "Great support."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["status"], ReviewStatus.PENDING)
        self.assertEqual(Review.objects.count(), 1)
        self.assertTrue(
            Interaction.objects.filter(
                patient=self.patient,
                caregiver=self.caregiver,
                kind=InteractionKind.RATE,
                weight=5.0,
            ).exists()
        )

    def test_cannot_create_review_before_relationship_ended(self):
        self.rel.status = CareRelationshipStatus.ACTIVE
        self.rel.save(update_fields=["status"])
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            self.review_list_url,
            {"relationship_id": self.rel.pk, "rating": 4, "comment": "Soon"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patient_can_only_review_own_relationship(self):
        self.client.force_authenticate(self.other_patient)
        resp = self.client.post(
            self.review_list_url,
            {"relationship_id": self.rel.pk, "rating": 4},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_approves_review_and_detail_shows_it(self):
        self.caregiver.trust_score = 0.2
        self.caregiver.save(update_fields=["trust_score"])
        review = Review.objects.create(
            relationship=self.rel,
            patient=self.patient,
            caregiver=self.caregiver,
            rating=5,
            comment="Excellent care",
        )
        self.client.force_authenticate(self.admin)
        mod = self.client.patch(
            self.review_moderate_url(review.pk),
            {"status": ReviewStatus.APPROVED},
            format="json",
        )
        self.assertEqual(mod.status_code, status.HTTP_200_OK, mod.data)
        review.refresh_from_db()
        self.assertEqual(review.status, ReviewStatus.APPROVED)
        self.assertEqual(review.moderator_id, self.admin.pk)
        self.caregiver.refresh_from_db()
        self.assertGreater(self.caregiver.trust_score, 0.2)

        self.client.force_authenticate(self.patient)
        detail = self.client.get(reverse("v1:caregiver_detail", kwargs={"pk": self.caregiver.pk}))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["review_count"], 1)
        self.assertEqual(detail.data["review_average"], 5.0)
        self.assertEqual(len(detail.data["reviews_teaser"]), 1)
        self.assertEqual(detail.data["reviews_teaser"][0]["rating"], 5)

    def test_pending_review_hidden_from_public_detail(self):
        Review.objects.create(
            relationship=self.rel,
            patient=self.patient,
            caregiver=self.caregiver,
            rating=2,
            comment="Pending moderation",
            status=ReviewStatus.PENDING,
        )
        self.client.force_authenticate(self.patient)
        detail = self.client.get(reverse("v1:caregiver_detail", kwargs={"pk": self.caregiver.pk}))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["review_count"], 0)
        self.assertIsNone(detail.data["review_average"])
        self.assertEqual(detail.data["reviews_teaser"], [])

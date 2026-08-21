"""Directory card payload: age, experience, verification, and ratings."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import (
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    Review,
    ReviewStatus,
)
from apps.matching.seed_avatars import avatar_png, initials

User = get_user_model()


class CaregiverCardPayloadTests(APITestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="card.cg@example.com",
            password="pw-strong-123",
            role=Role.CAREGIVER,
        )
        self.caregiver = CaregiverProfile.objects.create(
            user=user,
            display_name="Nimali Fernando",
            location=Point(79.86, 6.93, srid=4326),
            city="Colombo",
            certifications=["First Aid"],
            specialties=["diabetes"],
            languages=["English"],
            care_levels=["basic"],
            trust_score=0.88,
            date_of_birth=timezone.localdate() - timedelta(days=40 * 365 + 10),
            years_experience=7,
            is_approved=True,
            is_active=True,
            is_available=True,
        )
        self.patient = User.objects.create_user(
            email="card.pt@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )

    def _approved_review(self, rating: int):
        relationship = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ENDED,
        )
        return Review.objects.create(
            relationship=relationship,
            patient=self.patient,
            caregiver=self.caregiver,
            rating=rating,
            comment="Kind and reliable.",
            status=ReviewStatus.APPROVED,
        )

    def test_list_exposes_card_fields(self):
        res = self.client.get(reverse("v1:caregiver_list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        row = next(r for r in res.data["results"] if r["id"] == self.caregiver.pk)
        self.assertEqual(row["age"], 40)
        self.assertEqual(row["years_experience"], 7)
        self.assertTrue(row["is_verified"])
        self.assertEqual(row["review_count"], 0)
        self.assertIsNone(row["review_average"])

    def test_list_reports_approved_review_rating(self):
        self._approved_review(4)
        res = self.client.get(reverse("v1:caregiver_list"))
        row = next(r for r in res.data["results"] if r["id"] == self.caregiver.pk)
        self.assertEqual(row["review_count"], 1)
        self.assertEqual(row["review_average"], 4.0)

    def test_detail_keeps_card_fields_and_teaser(self):
        self._approved_review(5)
        res = self.client.get(reverse("v1:caregiver_detail", kwargs={"pk": self.caregiver.pk}))
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["age"], 40)
        self.assertTrue(res.data["is_verified"])
        self.assertEqual(res.data["review_count"], 1)
        self.assertEqual(res.data["review_average"], 5.0)
        self.assertEqual(len(res.data["reviews_teaser"]), 1)

    def test_age_is_null_when_birthday_missing(self):
        self.caregiver.date_of_birth = None
        self.caregiver.save(update_fields=["date_of_birth"])
        res = self.client.get(reverse("v1:caregiver_detail", kwargs={"pk": self.caregiver.pk}))
        self.assertIsNone(res.data["age"])


class SeedAvatarTests(APITestCase):
    def test_initials_from_full_name(self):
        self.assertEqual(initials("Nimali Fernando"), "NF")
        self.assertEqual(initials("Lakmali"), "LA")
        self.assertEqual(initials(""), "CP")

    def test_avatar_is_deterministic_png(self):
        first = avatar_png("Nimali Fernando", salt="7")
        second = avatar_png("Nimali Fernando", salt="7")
        other = avatar_png("Ishara Mendis", salt="7")
        self.assertTrue(first.startswith(b"\x89PNG"))
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

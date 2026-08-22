"""Half-created caregiver rows must stay out of browse, detail, and matching."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.caregiver_profile import listable_caregivers
from apps.matching.models import CaregiverProfile

User = get_user_model()


def make_caregiver(email, name, **extra):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    fields = {
        "display_name": name,
        "location": Point(79.86, 6.93, srid=4326),
        "city": "Colombo",
        "certifications": ["First Aid"],
        "specialties": ["diabetes"],
        "languages": ["English"],
        "care_levels": ["basic"],
        "bio": f"{name} supports daily care.",
        "years_experience": 6,
        "trust_score": 0.8,
        "is_active": True,
        "is_approved": True,
        "is_available": True,
    }
    fields.update(extra)
    return CaregiverProfile.objects.create(user=user, **fields)


class ListableCaregiverTests(APITestCase):
    def setUp(self):
        self.complete = make_caregiver("real.cg@example.com", "Nimali Perera")
        self.no_specialties = make_caregiver("blank.cg@example.com", "CG", specialties=[])
        self.placeholder_name = make_caregiver("dbg.cg@example.com", "X")
        self.initials_name = make_caregiver("init.cg@example.com", "CG")

    def test_queryset_helper_keeps_only_complete_rows(self):
        ids = set(listable_caregivers().values_list("id", flat=True))
        self.assertEqual(ids, {self.complete.id})

    def test_browse_hides_incomplete_rows(self):
        res = self.client.get(reverse("v1:caregiver_list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        names = {row["display_name"] for row in res.data["results"]}
        self.assertEqual(names, {"Nimali Perera"})

    def test_detail_404s_for_incomplete_rows(self):
        res = self.client.get(
            reverse("v1:caregiver_detail", kwargs={"pk": self.no_specialties.pk})
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_whitespace_only_name_is_not_listable(self):
        blank = make_caregiver("blank.name@example.com", "   ")
        self.assertNotIn(blank.id, set(listable_caregivers().values_list("id", flat=True)))

    def test_two_letter_placeholder_is_not_listable(self):
        self.assertNotIn(
            self.initials_name.id, set(listable_caregivers().values_list("id", flat=True))
        )
        res = self.client.get(reverse("v1:caregiver_list"))
        names = {row["display_name"] for row in res.data["results"]}
        self.assertNotIn("CG", names)
        self.assertNotIn("X", names)

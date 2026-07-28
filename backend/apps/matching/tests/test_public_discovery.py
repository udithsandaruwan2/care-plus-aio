"""Public frontend support: caregiver browse/detail availability without login."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile

User = get_user_model()


class PublicDiscoveryTests(APITestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="public.cg@example.com",
            password="pw-strong-123",
            role=Role.CAREGIVER,
        )
        self.cg = CaregiverProfile.objects.create(
            user=user,
            display_name="Public Caregiver",
            location=Point(79.86, 6.93, srid=4326),
            city="Colombo",
            certifications=["First Aid"],
            specialties=["diabetes"],
            languages=["English"],
            care_levels=["basic"],
            trust_score=0.88,
            is_active=True,
            is_available=True,
        )

    def test_unauth_can_list_caregivers(self):
        res = self.client.get(reverse("v1:caregiver_list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertGreaterEqual(res.data["count"], 1)

    def test_unauth_can_view_caregiver_detail(self):
        res = self.client.get(reverse("v1:caregiver_detail", kwargs={"pk": self.cg.pk}))
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["id"], self.cg.pk)


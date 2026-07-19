"""Step 20b — caregiver search / filter / geo browse API."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile

User = get_user_model()


class CaregiverSearchApiTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="searcher@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        self.url = reverse("v1:caregiver_list")

        self.colombo = self._cg(
            "cg.cmb@example.com",
            "Colombo Diabetes CG",
            city="Colombo",
            lon=79.8612,
            lat=6.9271,
            languages=["Sinhala", "English"],
            specialties=["diabetes", "hypertension"],
            care_levels=["intermediate"],
            available=True,
        )
        self.jaffna = self._cg(
            "cg.jfn@example.com",
            "Jaffna Tamil CG",
            city="Jaffna",
            lon=80.0255,
            lat=9.6615,
            languages=["Tamil", "English"],
            specialties=["elderly care"],
            care_levels=["basic"],
            available=True,
        )
        self.offline = self._cg(
            "cg.off@example.com",
            "Unavailable CG",
            city="Kandy",
            lon=80.6337,
            lat=7.2906,
            languages=["Sinhala"],
            specialties=["diabetes"],
            care_levels=["basic"],
            available=False,
        )
        inactive_user = User.objects.create_user(
            email="cg.dead@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        CaregiverProfile.objects.create(
            user=inactive_user,
            display_name="Inactive CG",
            location=Point(79.86, 6.93, srid=4326),
            city="Colombo",
            languages=["Sinhala"],
            specialties=["diabetes"],
            care_levels=["basic"],
            is_active=False,
            is_available=True,
        )

    def _cg(self, email, name, *, city, lon, lat, languages, specialties, care_levels, available):
        user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
        return CaregiverProfile.objects.create(
            user=user,
            display_name=name,
            location=Point(lon, lat, srid=4326),
            city=city,
            languages=languages,
            specialties=specialties,
            care_levels=care_levels,
            trust_score=0.8,
            is_active=True,
            is_available=available,
        )

    def _names(self, resp):
        return {row["display_name"] for row in resp.data["results"]}

    def test_paginated_list_excludes_inactive(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)
        self.assertIn("count", resp.data)
        names = self._names(resp)
        self.assertIn("Colombo Diabetes CG", names)
        self.assertNotIn("Inactive CG", names)

    def test_filter_language_and_specialty_combine(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(
            self.url, {"language": "Sinhala", "specialty": "diabetes", "available": "true"}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = self._names(resp)
        self.assertEqual(names, {"Colombo Diabetes CG"})

    def test_filter_city(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.url, {"city": "Jaffna"})
        self.assertEqual(self._names(resp), {"Jaffna Tamil CG"})

    def test_near_colombo_excludes_jaffna(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.url, {"near": "79.8612,6.9271", "radius_km": "30"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = self._names(resp)
        self.assertIn("Colombo Diabetes CG", names)
        self.assertNotIn("Jaffna Tamil CG", names)

    def test_q_search(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.url, {"q": "Tamil"})
        self.assertIn("Jaffna Tamil CG", self._names(resp))

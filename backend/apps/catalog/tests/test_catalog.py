"""Step 29 — care package / add-on catalog."""

from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import AddOn, CareLevel, CarePackage


class CatalogSeedTests(TestCase):
    def test_seed_catalog_creates_lkr_packages(self):
        call_command("seed_catalog")
        self.assertEqual(CarePackage.objects.filter(is_active=True).count(), 3)
        self.assertEqual(AddOn.objects.filter(is_active=True).count(), 4)
        basic = CarePackage.objects.get(slug="basic-home-care")
        self.assertEqual(basic.care_level, CareLevel.BASIC)
        self.assertEqual(basic.price_lkr, Decimal("8500.00"))

        # Idempotent
        call_command("seed_catalog")
        self.assertEqual(CarePackage.objects.count(), 3)


class CatalogApiTests(APITestCase):
    def setUp(self):
        call_command("seed_catalog")
        self.packages_url = reverse("v1:catalog_packages")
        self.addons_url = reverse("v1:catalog_addons")

    def test_list_packages_public(self):
        resp = self.client.get(self.packages_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 3)
        self.assertIn("price_lkr", resp.data[0])

    def test_filter_packages_by_care_level(self):
        resp = self.client.get(self.packages_url, {"care_level": "advanced"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["slug"], "advanced-clinical")

    def test_list_addons_and_filter_category(self):
        resp = self.client.get(self.addons_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 4)

        resp = self.client.get(self.addons_url, {"category": "food"})
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["slug"], "meal-support")

    def test_inactive_packages_hidden(self):
        CarePackage.objects.filter(slug="basic-home-care").update(is_active=False)
        resp = self.client.get(self.packages_url)
        self.assertEqual(len(resp.data), 2)

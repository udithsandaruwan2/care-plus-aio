"""Step 55 — admin vocab + catalog CRUD APIs."""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.catalog.models import AddOn, CarePackage
from apps.vocab.models import ConditionTerm

User = get_user_model()


class AdminVocabCatalogApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin.catalog@example.com",
            password="pw-strong-123",
            role=Role.ADMIN,
        )
        self.auditor = User.objects.create_user(
            email="auditor.catalog@example.com",
            password="pw-strong-123",
            role=Role.AUDITOR,
        )
        self.patient = User.objects.create_user(
            email="patient.catalog@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )
        self.cond_url = reverse("v1:admin_vocab_conditions")
        self.pkg_url = reverse("v1:admin_catalog_packages")
        self.addon_url = reverse("v1:admin_catalog_addons")

    def test_patient_forbidden(self):
        self.client.force_authenticate(self.patient)
        self.assertEqual(self.client.get(self.cond_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(self.pkg_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(self.addon_url).status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_crud_condition(self):
        self.client.force_authenticate(self.admin)
        created = self.client.post(
            self.cond_url,
            {
                "slug": "dengue-fever",
                "canonical_en": "Dengue fever",
                "synonyms": {"en": ["dengue"], "si": ["ඩෙංගු"]},
                "active": True,
                "version": 1,
                "notes": "test",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        detail = reverse("v1:admin_vocab_condition_detail", kwargs={"slug": "dengue-fever"})
        patched = self.client.patch(detail, {"active": False}, format="json")
        self.assertEqual(patched.status_code, status.HTTP_200_OK, patched.data)
        self.assertFalse(patched.data["active"])
        deleted = self.client.delete(detail)
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ConditionTerm.objects.filter(slug="dengue-fever").exists())

    def test_auditor_read_only_packages(self):
        CarePackage.objects.create(
            slug="basic-week",
            name="Basic week",
            care_level="basic",
            price_lkr="15000.00",
            default_days=7,
            is_active=True,
        )
        self.client.force_authenticate(self.auditor)
        listed = self.client.get(self.pkg_url)
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)
        self.assertEqual(len(listed.data), 1)

        blocked = self.client.post(
            self.pkg_url,
            {
                "slug": "new-pkg",
                "name": "New",
                "care_level": "basic",
                "price_lkr": "1000.00",
                "default_days": 3,
                "is_active": True,
                "sort_order": 1,
            },
            format="json",
        )
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_crud_package_and_addon(self):
        self.client.force_authenticate(self.admin)
        pkg = self.client.post(
            self.pkg_url,
            {
                "slug": "adv-week",
                "name": "Advanced week",
                "description": "Full support",
                "care_level": "advanced",
                "price_lkr": "45000.00",
                "default_days": 7,
                "is_active": True,
                "sort_order": 2,
            },
            format="json",
        )
        self.assertEqual(pkg.status_code, status.HTTP_201_CREATED, pkg.data)
        pkg_id = pkg.data["id"]
        pkg_detail = reverse("v1:admin_catalog_package_detail", kwargs={"pk": pkg_id})
        self.assertEqual(
            self.client.patch(pkg_detail, {"price_lkr": "46000.00"}, format="json").status_code,
            status.HTTP_200_OK,
        )

        addon = self.client.post(
            self.addon_url,
            {
                "slug": "hospital-run",
                "name": "Hospital run",
                "category": "hospital",
                "price_lkr": "2500.00",
                "is_active": True,
                "sort_order": 1,
            },
            format="json",
        )
        self.assertEqual(addon.status_code, status.HTTP_201_CREATED, addon.data)
        addon_detail = reverse("v1:admin_catalog_addon_detail", kwargs={"pk": addon.data["id"]})
        self.assertEqual(self.client.delete(addon_detail).status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AddOn.objects.filter(slug="hospital-run").exists())
        self.assertEqual(self.client.delete(pkg_detail).status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CarePackage.objects.filter(pk=pkg_id).exists())

"""Step 30 — checkout creates priced Order in awaiting_payment."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditAction, AuditLog, Role
from apps.catalog.models import AddOn, CarePackage, Order, OrderLineItem, OrderStatus
from apps.matching.models import (
    CaregiverProfile,
    CareRequest,
    CareRequestStatus,
    PatientProfile,
)

User = get_user_model()


def _patient(email="pt.checkout@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Checkout",
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


def _caregiver(email="cg.checkout@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Checkout",
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


def _package(**overrides):
    defaults = {
        "slug": "basic-home-care",
        "name": "Basic Home Care",
        "description": "Daily support",
        "care_level": "basic",
        "price_lkr": Decimal("8500.00"),
        "default_days": 7,
        "is_active": True,
        "sort_order": 1,
    }
    defaults.update(overrides)
    return CarePackage.objects.create(**defaults)


def _addon(**overrides):
    defaults = {
        "slug": "hospital-escort",
        "name": "Hospital escort",
        "description": "Clinic visit support",
        "category": "hospital",
        "price_lkr": Decimal("3500.00"),
        "is_active": True,
        "sort_order": 1,
    }
    defaults.update(overrides)
    return AddOn.objects.create(**defaults)


class CheckoutOrderTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.package = _package()
        self.addon = _addon()
        self.other_addon = _addon(
            slug="meal-support",
            name="Meal support",
            category="food",
            price_lkr=Decimal("2500.00"),
            sort_order=2,
        )

        self.client.force_authenticate(self.patient)
        create_resp = self.client.post(
            reverse("v1:care_request_list"),
            {"caregiver_id": self.caregiver.pk, "message": "Need help"},
            format="json",
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        self.req_id = create_resp.data["id"]

        self.client.force_authenticate(self.cg_user)
        accept_resp = self.client.patch(
            reverse("v1:care_request_action", kwargs={"pk": self.req_id}),
            {"action": "accept"},
            format="json",
        )
        self.assertEqual(accept_resp.status_code, status.HTTP_200_OK)

        self.checkout_url = reverse("v1:checkout_create")
        self.client.force_authenticate(self.patient)

    def test_checkout_creates_priced_order_awaiting_payment(self):
        resp = self.client.post(
            self.checkout_url,
            {
                "care_request_id": self.req_id,
                "package_id": self.package.pk,
                "addon_ids": [self.addon.pk, self.other_addon.pk],
                "days": 10,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["status"], OrderStatus.AWAITING_PAYMENT)
        self.assertEqual(resp.data["days"], 10)
        self.assertEqual(resp.data["currency"], "LKR")
        self.assertEqual(resp.data["care_request_id"], self.req_id)

        # 8500 * 10 + 3500 + 2500 = 91000
        self.assertEqual(Decimal(str(resp.data["total_lkr"])), Decimal("91000.00"))
        self.assertEqual(len(resp.data["lines"]), 3)

        order = Order.objects.get(pk=resp.data["id"])
        self.assertEqual(order.status, OrderStatus.AWAITING_PAYMENT)
        self.assertEqual(OrderLineItem.objects.filter(order=order).count(), 3)

        package_line = order.lines.get(kind="package")
        self.assertEqual(package_line.quantity, 10)
        self.assertEqual(package_line.unit_price_lkr, Decimal("8500.00"))
        self.assertEqual(package_line.line_total_lkr, Decimal("85000.00"))

        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.CREATE_ORDER,
                target_id=str(order.pk),
            ).exists()
        )

        detail = self.client.get(reverse("v1:order_detail", kwargs={"pk": order.pk}))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["id"], order.pk)
        self.assertEqual(len(detail.data["lines"]), 3)

    def test_checkout_defaults_days_from_package(self):
        resp = self.client.post(
            self.checkout_url,
            {
                "care_request_id": self.req_id,
                "package_id": self.package.pk,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["days"], 7)
        self.assertEqual(Decimal(str(resp.data["total_lkr"])), Decimal("59500.00"))

    def test_rejects_pending_care_request(self):
        pending = CareRequest.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRequestStatus.PENDING,
            expires_at=CareRequest.objects.get(pk=self.req_id).expires_at,
        )
        resp = self.client.post(
            self.checkout_url,
            {"care_request_id": pending.pk, "package_id": self.package.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_wrong_patient(self):
        other = _patient(email="other.checkout@example.com")
        self.client.force_authenticate(other)
        resp = self.client.post(
            self.checkout_url,
            {"care_request_id": self.req_id, "package_id": self.package.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_inactive_package(self):
        self.package.is_active = False
        self.package.save(update_fields=["is_active"])
        resp = self.client.post(
            self.checkout_url,
            {"care_request_id": self.req_id, "package_id": self.package.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_duplicate_open_order(self):
        first = self.client.post(
            self.checkout_url,
            {"care_request_id": self.req_id, "package_id": self.package.pk, "days": 5},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        second = self.client.post(
            self.checkout_url,
            {"care_request_id": self.req_id, "package_id": self.package.pk, "days": 3},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_price_snapshot_survives_catalog_change(self):
        resp = self.client.post(
            self.checkout_url,
            {
                "care_request_id": self.req_id,
                "package_id": self.package.pk,
                "addon_ids": [self.addon.pk],
                "days": 2,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        order_id = resp.data["id"]
        original_total = Decimal(str(resp.data["total_lkr"]))

        self.package.price_lkr = Decimal("99999.00")
        self.package.save(update_fields=["price_lkr"])
        self.addon.price_lkr = Decimal("1.00")
        self.addon.save(update_fields=["price_lkr"])

        detail = self.client.get(reverse("v1:order_detail", kwargs={"pk": order_id}))
        self.assertEqual(Decimal(str(detail.data["total_lkr"])), original_total)
        package_line = next(line for line in detail.data["lines"] if line["kind"] == "package")
        self.assertEqual(Decimal(str(package_line["unit_price_lkr"])), Decimal("8500.00"))

    def test_caregiver_cannot_checkout(self):
        self.client.force_authenticate(self.cg_user)
        resp = self.client.post(
            self.checkout_url,
            {"care_request_id": self.req_id, "package_id": self.package.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

"""Step 31 — PaymentIntent mock confirm + PayHere webhook signature."""

from decimal import Decimal
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditAction, AuditLog, Role
from apps.catalog.models import (
    CarePackage,
    Order,
    OrderStatus,
    PaymentIntent,
    PaymentIntentStatus,
    PaymentProviderName,
)
from apps.catalog.payments.providers.payhere import payhere_md5sig
from apps.matching.models import CaregiverProfile, PatientProfile

User = get_user_model()


def _patient(email="pt.pay@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Pay",
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


def _caregiver(email="cg.pay@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Pay",
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


class PaymentIntentFlowTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.package = CarePackage.objects.create(
            slug="basic-home-care",
            name="Basic Home Care",
            care_level="basic",
            price_lkr=Decimal("8500.00"),
            default_days=7,
            is_active=True,
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
        accept = self.client.patch(
            reverse("v1:care_request_action", kwargs={"pk": self.req_id}),
            {"action": "accept"},
            format="json",
        )
        self.assertEqual(accept.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(self.patient)
        checkout = self.client.post(
            reverse("v1:checkout_create"),
            {"care_request_id": self.req_id, "package_id": self.package.pk, "days": 2},
            format="json",
        )
        self.assertEqual(checkout.status_code, status.HTTP_201_CREATED, checkout.data)
        self.order_id = checkout.data["id"]
        self.intent_url = reverse("v1:payment_intent", kwargs={"pk": self.order_id})

    @override_settings(PAYMENT_PROVIDER="mock", MOCK_PAYMENT_CONFIRM_ENABLED=True)
    def test_mock_pay_succeeds_only_via_explicit_confirm(self):
        create = self.client.post(self.intent_url, {}, format="json")
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        self.assertEqual(create.data["status"], PaymentIntentStatus.REQUIRES_PAYMENT)
        self.assertEqual(create.data["provider"], PaymentProviderName.MOCK)

        order = Order.objects.get(pk=self.order_id)
        self.assertEqual(order.status, OrderStatus.AWAITING_PAYMENT)

        provider_intent_id = create.data["provider_intent_id"]
        confirm_url = reverse(
            "v1:mock_payment_confirm",
            kwargs={"provider_intent_id": provider_intent_id},
        )
        confirm = self.client.post(confirm_url, {}, format="json")
        self.assertEqual(confirm.status_code, status.HTTP_200_OK, confirm.data)
        self.assertEqual(confirm.data["status"], PaymentIntentStatus.SUCCEEDED)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PAID)

        from apps.matching.models import CareRelationship, CareRelationshipStatus

        rel = CareRelationship.objects.get(care_request_id=self.req_id)
        self.assertEqual(rel.status, CareRelationshipStatus.ACTIVE)
        self.caregiver.refresh_from_db()
        self.assertFalse(self.caregiver.is_available)

        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.CONFIRM_PAYMENT,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.ACTIVATE_CARE_RELATIONSHIP,
            ).exists()
        )

        # Creating intent again on paid order fails.
        again = self.client.post(self.intent_url, {}, format="json")
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(PAYMENT_PROVIDER="mock", MOCK_PAYMENT_CONFIRM_ENABLED=False)
    def test_mock_confirm_disabled_returns_403(self):
        create = self.client.post(self.intent_url, {}, format="json")
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        confirm_url = reverse(
            "v1:mock_payment_confirm",
            kwargs={"provider_intent_id": create.data["provider_intent_id"]},
        )
        confirm = self.client.post(confirm_url, {}, format="json")
        self.assertEqual(confirm.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Order.objects.get(pk=self.order_id).status, OrderStatus.AWAITING_PAYMENT)

    @override_settings(PAYMENT_PROVIDER="mock", MOCK_PAYMENT_CONFIRM_ENABLED=True)
    def test_reuses_open_payment_intent(self):
        first = self.client.post(self.intent_url, {}, format="json")
        second = self.client.post(self.intent_url, {}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(PaymentIntent.objects.filter(order_id=self.order_id).count(), 1)


@override_settings(
    PAYMENT_PROVIDER="payhere",
    PAYHERE_MERCHANT_ID="1211149",
    PAYHERE_MERCHANT_SECRET="secret_abc",
    PAYHERE_SANDBOX=True,
)
class PayHereWebhookTests(APITestCase):
    def setUp(self):
        self.patient = _patient(email="pt.ph@example.com")
        self.cg_user, self.caregiver = _caregiver(email="cg.ph@example.com")
        self.package = CarePackage.objects.create(
            slug="basic-home-care-ph",
            name="Basic Home Care",
            care_level="basic",
            price_lkr=Decimal("8500.00"),
            default_days=7,
            is_active=True,
        )

        self.client.force_authenticate(self.patient)
        create_resp = self.client.post(
            reverse("v1:care_request_list"),
            {"caregiver_id": self.caregiver.pk},
            format="json",
        )
        self.req_id = create_resp.data["id"]
        self.client.force_authenticate(self.cg_user)
        self.client.patch(
            reverse("v1:care_request_action", kwargs={"pk": self.req_id}),
            {"action": "accept"},
            format="json",
        )
        self.client.force_authenticate(self.patient)
        checkout = self.client.post(
            reverse("v1:checkout_create"),
            {"care_request_id": self.req_id, "package_id": self.package.pk, "days": 1},
            format="json",
        )
        self.order_id = checkout.data["id"]
        intent = self.client.post(
            reverse("v1:payment_intent", kwargs={"pk": self.order_id}),
            {},
            format="json",
        )
        self.assertEqual(intent.status_code, status.HTTP_201_CREATED, intent.data)
        self.provider_intent_id = intent.data["provider_intent_id"]
        self.amount = f"{Decimal(intent.data['amount_lkr']):.2f}"
        self.webhook_url = reverse("v1:payhere_webhook")

    def _payload(self, *, status_code="2", tamper_sig=False):
        data = {
            "merchant_id": "1211149",
            "order_id": self.provider_intent_id,
            "payhere_amount": self.amount,
            "payhere_currency": "LKR",
            "status_code": status_code,
            "status_message": "Successfully completed" if status_code == "2" else "Failed",
        }
        sig = payhere_md5sig(
            merchant_id=data["merchant_id"],
            order_id=data["order_id"],
            amount=data["payhere_amount"],
            currency=data["payhere_currency"],
            status_code=data["status_code"],
            merchant_secret="secret_abc",
        )
        data["md5sig"] = "DEADBEEF" if tamper_sig else sig
        return urlencode(data)

    def test_valid_webhook_signature_marks_paid(self):
        resp = self.client.post(
            self.webhook_url,
            data=self._payload(status_code="2"),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["status"], PaymentIntentStatus.SUCCEEDED)
        self.assertEqual(Order.objects.get(pk=self.order_id).status, OrderStatus.PAID)
        self.assertTrue(
            AuditLog.objects.filter(action=AuditAction.PAYMENT_WEBHOOK).exists()
        )
        from apps.matching.models import CareRelationship, CareRelationshipStatus

        rel = CareRelationship.objects.get(care_request_id=self.req_id)
        self.assertEqual(rel.status, CareRelationshipStatus.ACTIVE)
        self.caregiver.refresh_from_db()
        self.assertFalse(self.caregiver.is_available)

    def test_tampered_webhook_signature_rejected(self):
        resp = self.client.post(
            self.webhook_url,
            data=self._payload(status_code="2", tamper_sig=True),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Order.objects.get(pk=self.order_id).status, OrderStatus.AWAITING_PAYMENT)

    def test_failed_status_marks_intent_failed_not_order_paid(self):
        resp = self.client.post(
            self.webhook_url,
            data=self._payload(status_code="0"),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["status"], PaymentIntentStatus.FAILED)
        self.assertEqual(Order.objects.get(pk=self.order_id).status, OrderStatus.AWAITING_PAYMENT)

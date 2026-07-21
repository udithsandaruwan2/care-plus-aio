"""Step 33 — payment receipt email with LKR breakdown + audit."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditAction, AuditLog, Role
from apps.catalog.models import CarePackage, Order
from apps.matching.models import CaregiverProfile, PatientProfile

User = get_user_model()


def _patient(email="pt.receipt@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Receipt",
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


def _caregiver(email="cg.receipt@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Receipt",
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


@override_settings(
    PAYMENT_PROVIDER="mock",
    MOCK_PAYMENT_CONFIRM_ENABLED=True,
    RECEIPT_EMAIL_ENABLED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ReceiptEmailTests(APITestCase):
    def setUp(self):
        mail.outbox.clear()
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.package = CarePackage.objects.create(
            slug="basic-home-care-rcpt",
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
            {
                "care_request_id": self.req_id,
                "package_id": self.package.pk,
                "days": 2,
            },
            format="json",
        )
        self.assertEqual(checkout.status_code, status.HTTP_201_CREATED, checkout.data)
        self.order_id = checkout.data["id"]
        intent = self.client.post(
            reverse("v1:payment_intent", kwargs={"pk": self.order_id}),
            {},
            format="json",
        )
        self.provider_intent_id = intent.data["provider_intent_id"]

    def test_mock_pay_sends_receipt_with_lkr_breakdown_and_audit(self):
        confirm = self.client.post(
            reverse(
                "v1:mock_payment_confirm",
                kwargs={"provider_intent_id": self.provider_intent_id},
            ),
            {},
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK, confirm.data)

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, [self.patient.email])
        self.assertIn(f"Order #{self.order_id}", msg.body)
        self.assertIn("Basic Home Care", msg.body)
        self.assertIn("LKR", msg.body)
        self.assertIn("17,000.00", msg.body)  # 8500 × 2

        order = Order.objects.get(pk=self.order_id)
        self.assertTrue(order.receipt_email_sent)
        self.assertIsNotNone(order.receipt_sent_at)

        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.RECEIPT_SENT,
                target_id=str(self.order_id),
            ).exists()
        )

        # Idempotent — re-confirm does not duplicate email.
        mail.outbox.clear()
        again = self.client.post(
            reverse(
                "v1:mock_payment_confirm",
                kwargs={"provider_intent_id": self.provider_intent_id},
            ),
            {},
            format="json",
        )
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_html_receipt_endpoint(self):
        self.client.post(
            reverse(
                "v1:mock_payment_confirm",
                kwargs={"provider_intent_id": self.provider_intent_id},
            ),
            {},
            format="json",
        )
        resp = self.client.get(reverse("v1:order_receipt", kwargs={"pk": self.order_id}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", resp["Content-Type"])
        body = resp.content.decode()
        self.assertIn("Basic Home Care", body)
        self.assertIn("LKR", body)
        self.assertIn(f"Order #{self.order_id}", body)

    @override_settings(RECEIPT_EMAIL_ENABLED=False)
    def test_receipt_disabled_skips_email(self):
        mail.outbox.clear()
        confirm = self.client.post(
            reverse(
                "v1:mock_payment_confirm",
                kwargs={"provider_intent_id": self.provider_intent_id},
            ),
            {},
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK, confirm.data)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(Order.objects.get(pk=self.order_id).receipt_email_sent)
        self.assertFalse(
            AuditLog.objects.filter(action=AuditAction.RECEIPT_SENT).exists()
        )

"""Step 95 — idempotent care-request create / message send / payment confirm."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.catalog.models import (
    Order,
    OrderStatus,
    PaymentIntent,
    PaymentIntentStatus,
    PaymentProviderName,
)
from apps.common.idempotency import IdempotencyRecord, IdempotencyScope
from apps.matching.models import (
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    PatientProfile,
)
from apps.messaging.models import Message, MessageThread

User = get_user_model()


def _patient(email="pt.idem@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient Idem",
        city="Colombo",
        location=Point(79.86, 6.92, srid=4326),
        preferred_language="English",
        languages=["English"],
        care_level="basic",
        conditions=["diabetes"],
        height_cm=170,
        weight_kg=70,
        blood_type="O+",
        emergency_contact_name="EC",
        emergency_contact_phone="+94770000001",
    )
    return user


def _caregiver(email="cg.idem@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG Idem",
        location=Point(79.86, 6.93, srid=4326),
        certifications=["First Aid"],
        specialties=["diabetes"],
        languages=["English"],
        care_levels=["basic"],
        trust_score=0.9,
        is_active=True,
        is_approved=True,
        is_available=True,
    )
    return user, profile


class CareRequestIdempotencyTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.url = reverse("v1:care_request_list")

    def test_same_idempotency_key_returns_original(self):
        self.client.force_authenticate(self.patient)
        payload = {
            "caregiver_id": self.caregiver.pk,
            "message": "Need help",
            "idempotency_key": "cr-key-1",
        }
        r1 = self.client.post(self.url, payload, format="json")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = self.client.post(
            self.url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="cr-key-1",
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r1.data["id"], r2.data["id"])
        self.assertEqual(CareRequest.objects.filter(patient=self.patient).count(), 1)
        self.assertEqual(
            IdempotencyRecord.objects.filter(
                user=self.patient,
                scope=IdempotencyScope.CARE_REQUEST_CREATE,
                key="cr-key-1",
            ).count(),
            1,
        )


class MessageIdempotencyTests(APITestCase):
    def setUp(self):
        self.patient = _patient("pt.msg.idem@example.com")
        self.cg_user, self.caregiver = _caregiver("cg.msg.idem@example.com")
        rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ACTIVE,
            is_primary=True,
        )
        self.thread = MessageThread.objects.create(relationship=rel)
        self.url = reverse("v1:message_list_create", kwargs={"pk": self.thread.pk})

    def test_message_replay_same_key(self):
        self.client.force_authenticate(self.patient)
        payload = {"body": "Hello from outbox", "idempotency_key": "msg-key-1"}
        r1 = self.client.post(self.url, payload, format="json")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = self.client.post(self.url, payload, format="json")
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r1.data["id"], r2.data["id"])
        self.assertEqual(Message.objects.filter(thread=self.thread).count(), 1)


class PaymentConfirmIdempotencyTests(APITestCase):
    def setUp(self):
        from decimal import Decimal
        from datetime import timedelta

        from django.utils import timezone

        from apps.matching.models import CareRequest, CareRequestStatus

        self.patient = _patient("pt.pay.idem@example.com")
        self.cg_user, self.caregiver = _caregiver("cg.pay.idem@example.com")
        cr = CareRequest.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRequestStatus.ACCEPTED,
            message="",
            expires_at=timezone.now() + timedelta(hours=24),
            responded_at=timezone.now(),
        )
        self.order = Order.objects.create(
            care_request=cr,
            patient=self.patient,
            status=OrderStatus.AWAITING_PAYMENT,
            days=2,
            currency="LKR",
            subtotal_lkr=Decimal("10000.00"),
            total_lkr=Decimal("10000.00"),
        )
        self.intent = PaymentIntent.objects.create(
            order=self.order,
            patient=self.patient,
            provider=PaymentProviderName.MOCK,
            provider_intent_id="mock_idem_1",
            status=PaymentIntentStatus.REQUIRES_PAYMENT,
            amount_lkr=Decimal("10000.00"),
            currency="LKR",
            idempotency_key="order-pay-idem-1",
        )
        self.url = reverse(
            "v1:mock_payment_confirm",
            kwargs={"provider_intent_id": self.intent.provider_intent_id},
        )

    def test_confirm_replay_same_header_key(self):
        self.client.force_authenticate(self.patient)
        r1 = self.client.post(self.url, {}, format="json", HTTP_IDEMPOTENCY_KEY="pay-key-1")
        self.assertEqual(r1.status_code, status.HTTP_200_OK, r1.data)
        self.assertEqual(r1.data["status"], "succeeded")
        r2 = self.client.post(self.url, {}, format="json", HTTP_IDEMPOTENCY_KEY="pay-key-1")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data["id"], r2.data["id"])
        self.assertEqual(
            IdempotencyRecord.objects.filter(
                user=self.patient,
                scope=IdempotencyScope.PAYMENT_CONFIRM,
                key="pay-key-1",
            ).count(),
            1,
        )

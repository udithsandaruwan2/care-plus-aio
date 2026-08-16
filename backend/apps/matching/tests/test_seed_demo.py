"""Showcase seed covers every live product situation."""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import Role
from apps.catalog.models import CarePackage, Order, OrderStatus, PaymentIntent, PaymentIntentStatus
from apps.health_monitoring.models import HealthEvent, HealthMetric
from apps.leads.models import Lead, LeadStatus
from apps.matching.demo_seed import DEMO_PASSWORD
from apps.matching.models import (
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
    Review,
    ReviewStatus,
    Shift,
)
from apps.matching.patient_profile import patient_profile_completion
from apps.medical_records.models import MedicalRecord
from apps.messaging.models import Message

User = get_user_model()


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    NOTIFICATION_EMAIL_ENABLED=False,
    LEAD_ACK_EMAIL_ENABLED=False,
    MOCK_PAYMENT_CONFIRM_ENABLED=True,
)
class SeedDemoCommandTests(TestCase):
    def test_seed_demo_covers_core_situations(self):
        call_command("seed_demo", caregivers=12, patients=4, verbosity=0)

        patient = User.objects.get(email="demo.patient@careplus.local")
        self.assertTrue(patient.check_password(DEMO_PASSWORD))
        self.assertTrue(patient_profile_completion(patient.patient_profile).can_request_care)

        self.assertTrue(User.objects.filter(email="demo.admin@careplus.local", role=Role.ADMIN).exists())
        self.assertTrue(User.objects.filter(email="demo.caregiver@careplus.local", role=Role.CAREGIVER).exists())

        self.assertTrue(
            CareRelationship.objects.filter(
                patient=patient, status=CareRelationshipStatus.ACTIVE
            ).exists()
        )
        self.assertTrue(
            CareRequest.objects.filter(patient=patient, status=CareRequestStatus.PENDING).exists()
        )
        self.assertTrue(
            CareRequest.objects.filter(patient=patient, status=CareRequestStatus.REJECTED).exists()
        )
        self.assertTrue(
            CareRequest.objects.filter(patient=patient, status=CareRequestStatus.CANCELLED).exists()
        )
        self.assertTrue(
            CareRequest.objects.filter(patient=patient, status=CareRequestStatus.EXPIRED).exists()
        )
        self.assertGreaterEqual(Message.objects.filter(thread__relationship__patient=patient).count(), 2)
        self.assertGreaterEqual(MedicalRecord.objects.filter(patient=patient).count(), 1)
        self.assertTrue(HealthMetric.objects.filter(patient=patient).exists())
        self.assertTrue(HealthEvent.objects.filter(patient=patient).exists())
        self.assertTrue(Shift.objects.filter(patient=patient).exists())

        pay = User.objects.get(email="demo.pay@careplus.local")
        self.assertTrue(
            Order.objects.filter(patient=pay, status=OrderStatus.AWAITING_PAYMENT).exists()
        )
        failed = User.objects.get(email="demo.failed@careplus.local")
        self.assertTrue(
            PaymentIntent.objects.filter(
                patient=failed, status=PaymentIntentStatus.FAILED
            ).exists()
        )

        alumni = User.objects.get(email="demo.alumni@careplus.local")
        self.assertTrue(
            Review.objects.filter(patient=alumni, status=ReviewStatus.APPROVED).exists()
        )
        self.assertTrue(
            Review.objects.filter(patient=alumni, status=ReviewStatus.PENDING).exists()
        )

        onboarding = User.objects.get(email="demo.onboarding@careplus.local")
        self.assertFalse(patient_profile_completion(onboarding.patient_profile).can_request_care)

        self.assertTrue(Lead.objects.filter(status=LeadStatus.NEW).exists())
        self.assertTrue(Lead.objects.filter(status=LeadStatus.CONTACTED).exists())
        self.assertTrue(Lead.objects.filter(status=LeadStatus.CLOSED).exists())
        self.assertGreaterEqual(CarePackage.objects.filter(is_active=True).count(), 6)

    def test_seed_demo_is_idempotent(self):
        call_command("seed_demo", caregivers=12, patients=4, verbosity=0)
        n_requests = CareRequest.objects.count()
        call_command("seed_demo", caregivers=12, patients=4, verbosity=0)
        self.assertEqual(CareRequest.objects.count(), n_requests)
        self.assertTrue(User.objects.get(email="demo.patient@careplus.local").check_password(DEMO_PASSWORD))

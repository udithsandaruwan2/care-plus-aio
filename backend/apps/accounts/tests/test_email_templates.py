"""Step 40 — localized email templates and Celery delivery."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core import mail
from django.test import TestCase, override_settings

from apps.accounts.notifications.copy import supported_template_keys
from apps.accounts.notifications.render import render_notification_email
from apps.accounts.notifications.tasks import send_notification_email
from apps.accounts.models import Role
from apps.matching.models import CaregiverProfile, CareRequest, CareRequestStatus, PatientProfile

User = get_user_model()


class EmailTemplateRenderTests(TestCase):
    def test_all_templates_render_en_si_ta(self):
        context = {
            "caregiver_name": "Anjali",
            "patient_label": "Patient One",
            "patient_name": "Patient One",
            "message": "Need help",
            "request_id": 42,
            "expires_at": "2026-07-22",
            "checkout_url": "http://localhost:5173/requests/42/checkout",
            "amount_lkr": "LKR 5,000.00",
            "user_name": "Sam",
            "alert_title": "Payment failed",
            "detail": "Card declined",
        }
        template_contexts = {
            "care_request_received": context,
            "care_request_accepted": context,
            "payment_due": context,
            "anomaly_alert": context,
        }
        for key in supported_template_keys():
            for lang in ("English", "Sinhala", "Tamil"):
                subject, body = render_notification_email(
                    key,
                    language=lang,
                    context=template_contexts[key],
                )
                self.assertTrue(subject.strip(), f"{key}/{lang} subject empty")
                self.assertTrue(body.strip(), f"{key}/{lang} body empty")
                self.assertNotIn("{", subject)
                self.assertNotIn("{", body)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class NotificationEmailTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="tpl@example.com", password="pw-strong-123", role=Role.PATIENT
        )

    def test_celery_task_sends_rendered_email(self):
        result = send_notification_email(
            user_id=self.user.pk,
            event_key="care_request_accepted",
            template_key="care_request_accepted",
            context={
                "patient_name": "Pat",
                "caregiver_name": "CG",
                "checkout_url": "http://localhost/requests/1/checkout",
            },
            language="Tamil",
        )
        self.assertTrue(result["sent"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Care Plus", mail.outbox[0].subject)
        self.assertIn("CG", mail.outbox[0].body)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class CareRequestEmailDispatchTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="pt.tpl@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(
            user=self.patient,
            display_name="Patient Template",
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
            emergency_contact_phone="+94770000000",
        )
        self.cg_user = User.objects.create_user(
            email="cg.tpl@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        self.caregiver = CaregiverProfile.objects.create(
            user=self.cg_user,
            display_name="CG Template",
            location=Point(79.86, 6.93, srid=4326),
            certifications=[],
            specialties=[],
            languages=["English"],
            care_levels=["basic"],
            trust_score=0.9,
            is_active=True,
            is_approved=True,
            is_available=True,
        )

    def test_create_care_request_queues_received_email(self):
        from apps.matching.care_requests import create_care_request

        mail.outbox.clear()
        create_care_request(patient=self.patient, caregiver=self.caregiver, message="Hello")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.cg_user.email])

    def test_accept_care_request_queues_patient_emails(self):
        from apps.matching.care_requests import accept_care_request, create_care_request

        req = create_care_request(patient=self.patient, caregiver=self.caregiver)
        mail.outbox.clear()
        accept_care_request(req, caregiver_user=self.cg_user)
        patient_mail = [m for m in mail.outbox if self.patient.email in m.to]
        self.assertEqual(len(patient_mail), 2)
        subjects = " ".join(m.subject for m in patient_mail)
        self.assertIn("accepted", subjects.lower())

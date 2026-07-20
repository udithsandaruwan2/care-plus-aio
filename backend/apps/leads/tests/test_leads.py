"""Step 27 — marketing lead appointments."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.leads.models import Lead, LeadStatus
from apps.leads.services import mark_lead_contacted

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    LEAD_ACK_EMAIL_ENABLED=True,
)
class LeadPublicCreateTests(APITestCase):
    def setUp(self):
        self.url = reverse("v1:lead_list")

    def test_public_can_submit_lead(self):
        resp = self.client.post(
            self.url,
            {
                "name": "Amaya Perera",
                "email": "amaya@example.com",
                "phone": "+94771234567",
                "message": "Need dengue home care info",
                "city": "Colombo",
                "preferred_language": "Sinhala",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "new")
        self.assertTrue(Lead.objects.filter(email="amaya@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Amaya", mail.outbox[0].body)
        lead = Lead.objects.get(email="amaya@example.com")
        self.assertTrue(lead.ack_email_sent)

    def test_rejects_blank_name(self):
        resp = self.client.post(
            self.url,
            {"name": " ", "email": "x@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    LEAD_ACK_EMAIL_ENABLED=False,
)
class LeadAdminQueueTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin.lead@example.com",
            password="pw-strong-123",
            role=Role.ADMIN,
        )
        self.patient = User.objects.create_user(
            email="pt.lead@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )
        self.lead = Lead.objects.create(
            name="Kasun",
            email="kasun@example.com",
            message="Interested in Care Plus",
        )
        self.list_url = reverse("v1:lead_list")
        self.contact_url = reverse("v1:lead_contact", kwargs={"pk": self.lead.pk})

    def test_admin_lists_leads(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_patient_cannot_list_leads(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_marks_contacted(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            self.contact_url,
            {"action": "contact", "notes": "Called back"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["status"], "contacted")
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, LeadStatus.CONTACTED)
        self.assertEqual(self.lead.admin_notes, "Called back")
        self.assertEqual(self.lead.contacted_by_id, self.admin.pk)

    def test_patient_cannot_mark_contacted(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.patch(
            self.contact_url, {"action": "contact"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_mark_closed_lead_fails(self):
        self.lead.status = LeadStatus.CLOSED
        self.lead.save(update_fields=["status"])
        with self.assertRaises(Exception):
            mark_lead_contacted(self.lead, actor=self.admin)

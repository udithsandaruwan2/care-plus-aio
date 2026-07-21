"""Step 35 — medical record upload, list, signed download APIs."""

import tempfile

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditAction, AuditLog, Role
from apps.matching.models import (
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    PatientProfile,
)
from apps.medical_records.attachments import build_signed_download_token
from apps.medical_records.models import MedicalRecord, MedicalRecordAttachment
from apps.vocab.models import ConditionTerm

User = get_user_model()


def _patient(email="pt.mr.api@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient API",
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


def _caregiver(email="cg.mr.api@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG API",
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


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MedicalRecordApiTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.cg_user, self.caregiver = _caregiver()
        self.condition = ConditionTerm.objects.create(
            slug="dengue",
            canonical_en="Dengue fever",
            synonyms={"en": ["dengue"]},
            active=True,
        )
        CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ACTIVE,
            is_primary=True,
        )
        self.list_url = reverse("v1:medical_record_list")
        self.client.force_authenticate(self.patient)

    def test_patient_multipart_create_with_attachment(self):
        pdf = SimpleUploadedFile(
            "report.pdf",
            b"%PDF-1.4 test content",
            content_type="application/pdf",
        )
        resp = self.client.post(
            self.list_url,
            {
                "condition_slug": "dengue",
                "title": "Lab report",
                "description": "Initial labs",
                "sensitive_notes": "Platelet count low",
                "file": pdf,
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["title"], "Lab report")
        self.assertEqual(resp.data["sensitive_notes"], "Platelet count low")
        self.assertEqual(len(resp.data["attachments"]), 1)
        self.assertEqual(resp.data["attachments"][0]["content_type"], "application/pdf")

    def test_patient_lists_own_records(self):
        MedicalRecord.objects.create(
            patient=self.patient,
            condition=self.condition,
            title="Note A",
        )
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data if isinstance(resp.data, list) else resp.data.get("results", resp.data)
        self.assertEqual(len(results), 1)

    def test_caregiver_lists_active_patient_records(self):
        MedicalRecord.objects.create(
            patient=self.patient,
            condition=self.condition,
            title="Shared note",
        )
        self.client.force_authenticate(self.cg_user)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data if isinstance(resp.data, list) else resp.data.get("results", resp.data)
        self.assertEqual(len(results), 1)

    def test_detail_read_audits_view_health(self):
        record = MedicalRecord.objects.create(
            patient=self.patient,
            condition=self.condition,
            title="Private",
        )
        record.sensitive_notes = "Secret"
        record.save()
        AuditLog.objects.filter(action=AuditAction.VIEW_HEALTH).delete()
        url = reverse("v1:medical_record_detail", kwargs={"pk": record.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["sensitive_notes"], "Secret")
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.VIEW_HEALTH,
                target_id=str(record.pk),
            ).exists()
        )

    def test_rejects_disallowed_mime(self):
        exe = SimpleUploadedFile("bad.exe", b"MZ", content_type="application/x-msdownload")
        record = MedicalRecord.objects.create(
            patient=self.patient,
            condition=self.condition,
            title="Doc",
        )
        url = reverse("v1:medical_record_attachment_upload", kwargs={"pk": record.pk})
        resp = self.client.post(url, {"file": exe}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(MEDICAL_RECORD_MAX_UPLOAD_BYTES=10)
    def test_rejects_oversized_file(self):
        big = SimpleUploadedFile("big.pdf", b"x" * 20, content_type="application/pdf")
        record = MedicalRecord.objects.create(
            patient=self.patient,
            condition=self.condition,
            title="Doc",
        )
        url = reverse("v1:medical_record_attachment_upload", kwargs={"pk": record.pk})
        resp = self.client.post(url, {"file": big}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signed_download_url_and_download(self):
        record = MedicalRecord.objects.create(
            patient=self.patient,
            condition=self.condition,
            title="With file",
        )
        pdf = SimpleUploadedFile("labs.pdf", b"%PDF-1.4 labs", content_type="application/pdf")
        upload_url = reverse("v1:medical_record_attachment_upload", kwargs={"pk": record.pk})
        up = self.client.post(upload_url, {"file": pdf}, format="multipart")
        self.assertEqual(up.status_code, status.HTTP_201_CREATED, up.data)
        attachment_id = up.data["id"]

        sign_url = reverse(
            "v1:medical_record_attachment_download_url",
            kwargs={"pk": attachment_id},
        )
        sign = self.client.post(sign_url, {}, format="json")
        self.assertEqual(sign.status_code, status.HTTP_200_OK, sign.data)
        self.assertIn("url", sign.data)
        self.assertIn("token=", sign.data["url"])

        token = sign.data["url"].split("token=", 1)[1]
        download_url = reverse("v1:medical_record_attachment_download")
        self.client.logout()
        dl = self.client.get(download_url, {"token": token})
        self.assertEqual(dl.status_code, status.HTTP_200_OK)
        body = b"".join(dl.streaming_content)
        self.assertIn(b"%PDF", body)

    def test_invalid_download_token_rejected(self):
        download_url = reverse("v1:medical_record_attachment_download")
        resp = self.client.get(download_url, {"token": "not-valid"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

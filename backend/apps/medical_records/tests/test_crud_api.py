"""Step 37 — medical record update and soft-delete API tests."""

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
from apps.medical_records.models import MedicalRecord
from apps.vocab.models import ConditionTerm

User = get_user_model()


def _patient(email="pt.mr.crud@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient CRUD",
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


def _caregiver(email="cg.mr.crud@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG CRUD",
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
class MedicalRecordCrudApiTests(APITestCase):
    def setUp(self):
        self.patient = _patient()
        self.other_patient = _patient(email="other.mr.crud@example.com")
        self.cg_user, self.caregiver = _caregiver()
        self.condition = ConditionTerm.objects.create(
            slug="dengue",
            canonical_en="Dengue fever",
            synonyms={"en": ["dengue"]},
            active=True,
        )
        self.diabetes = ConditionTerm.objects.create(
            slug="diabetes",
            canonical_en="Diabetes",
            synonyms={"en": ["diabetes"]},
            active=True,
        )
        CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ACTIVE,
            is_primary=True,
        )
        self.record = MedicalRecord.objects.create(
            patient=self.patient,
            condition=self.condition,
            title="Initial visit",
            description="Baseline notes",
        )
        self.record.sensitive_notes = "Private detail"
        self.record.save()

    def test_patient_updates_record(self):
        self.client.force_authenticate(user=self.patient)
        url = reverse("v1:medical_record_detail", kwargs={"pk": self.record.pk})
        res = self.client.patch(
            url,
            {"title": "Updated visit", "description": "New notes", "sensitive_notes": "Updated private"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["title"], "Updated visit")
        self.assertEqual(res.data["sensitive_notes"], "Updated private")
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.UPDATE_MEDICAL_RECORD,
                target_id=str(self.record.pk),
            ).exists()
        )

    def test_caregiver_cannot_update(self):
        self.client.force_authenticate(user=self.cg_user)
        url = reverse("v1:medical_record_detail", kwargs={"pk": self.record.pk})
        res = self.client.patch(url, {"title": "Hacked"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_soft_deletes_record(self):
        self.client.force_authenticate(user=self.patient)
        url = reverse("v1:medical_record_detail", kwargs={"pk": self.record.pk})
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.record.refresh_from_db()
        self.assertIsNotNone(self.record.deleted_at)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.DELETE_MEDICAL_RECORD,
                target_id=str(self.record.pk),
            ).exists()
        )

    def test_deleted_record_hidden_from_list(self):
        self.record.deleted_at = self.record.updated_at
        self.record.save(update_fields=["deleted_at"])
        self.client.force_authenticate(user=self.patient)
        res = self.client.get(reverse("v1:medical_record_list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    def test_caregiver_cannot_see_deleted_record(self):
        self.record.deleted_at = self.record.updated_at
        self.record.save(update_fields=["deleted_at"])
        self.client.force_authenticate(user=self.cg_user)
        url = reverse("v1:medical_record_detail", kwargs={"pk": self.record.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_audits_create_action(self):
        AuditLog.objects.filter(action=AuditAction.CREATE_MEDICAL_RECORD).delete()
        self.client.force_authenticate(user=self.patient)
        res = self.client.post(
            reverse("v1:medical_record_list"),
            {
                "condition_slug": "diabetes",
                "title": "New record",
                "description": "Desc",
            },
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.CREATE_MEDICAL_RECORD,
                target_id=str(res.data["id"]),
            ).count(),
            1,
        )

    def test_other_patient_cannot_delete(self):
        self.client.force_authenticate(user=self.other_patient)
        url = reverse("v1:medical_record_detail", kwargs={"pk": self.record.pk})
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_upload_rejected_for_deleted_record(self):
        self.record.deleted_at = self.record.updated_at
        self.record.save(update_fields=["deleted_at"])
        self.client.force_authenticate(user=self.patient)
        url = reverse("v1:medical_record_attachment_upload", kwargs={"pk": self.record.pk})
        upload = SimpleUploadedFile("lab.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        res = self.client.post(url, {"file": upload}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

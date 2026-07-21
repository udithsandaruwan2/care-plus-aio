"""MedicalRecord encryption and access control (Step 34)."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import AuditAction, AuditLog, Role
from apps.matching.models import (
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    PatientProfile,
)
from apps.medical_records.access import can_read_medical_record, read_medical_record
from apps.medical_records.models import MedicalRecord
from apps.vocab.models import ConditionTerm

User = get_user_model()


def _patient(email="pt.mr@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.PATIENT)
    PatientProfile.objects.create(
        user=user,
        display_name="Patient MR",
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


def _caregiver(email="cg.mr@example.com"):
    user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
    profile = CaregiverProfile.objects.create(
        user=user,
        display_name="CG MR",
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


def _condition():
    return ConditionTerm.objects.create(
        slug="dengue",
        canonical_en="Dengue fever",
        synonyms={"en": ["dengue"]},
        active=True,
    )


def _record(patient, condition, notes="Private clinical detail"):
    rec = MedicalRecord.objects.create(
        patient=patient,
        condition=condition,
        title="Follow-up notes",
        description="Routine check",
    )
    rec.sensitive_notes = notes
    rec.save()
    return rec


@override_settings(FIELD_ENCRYPTION_KEY="")
class MedicalRecordEncryptionTests(TestCase):
    def setUp(self):
        self.patient = _patient()
        self.condition = _condition()

    def test_sensitive_notes_encrypted_at_rest(self):
        rec = _record(self.patient, self.condition, notes="Secret diagnosis detail")
        stored = MedicalRecord.objects.get(pk=rec.pk)
        self.assertNotEqual(stored.sensitive_notes_ciphertext, "Secret diagnosis detail")
        self.assertTrue(len(stored.sensitive_notes_ciphertext) > 0)

    def test_sensitive_notes_roundtrip(self):
        rec = _record(self.patient, self.condition, notes="Allergic to penicillin")
        fresh = MedicalRecord.objects.get(pk=rec.pk)
        self.assertEqual(fresh.sensitive_notes, "Allergic to penicillin")


class MedicalRecordAccessTests(TestCase):
    def setUp(self):
        self.patient = _patient()
        self.other_patient = _patient(email="other.mr@example.com")
        self.cg_user, self.caregiver = _caregiver()
        self.other_cg_user, _ = _caregiver(email="other.cg@example.com")
        self.admin = User.objects.create_user(
            email="admin.mr@example.com",
            password="pw-strong-123",
            role=Role.ADMIN,
        )
        self.auditor = User.objects.create_user(
            email="auditor.mr@example.com",
            password="pw-strong-123",
            role=Role.AUDITOR,
        )
        self.condition = _condition()
        self.record = _record(self.patient, self.condition)
        self.rel = CareRelationship.objects.create(
            patient=self.patient,
            caregiver=self.caregiver,
            status=CareRelationshipStatus.ACTIVE,
            is_primary=True,
        )

    def test_patient_can_read_own_record(self):
        self.assertTrue(can_read_medical_record(self.patient, self.record))

    def test_active_caregiver_can_read(self):
        self.assertTrue(can_read_medical_record(self.cg_user, self.record))

    def test_ended_caregiver_denied(self):
        self.rel.status = CareRelationshipStatus.ENDED
        self.rel.save(update_fields=["status"])
        self.assertFalse(can_read_medical_record(self.cg_user, self.record))

    def test_unlinked_caregiver_denied(self):
        self.assertFalse(can_read_medical_record(self.other_cg_user, self.record))

    def test_other_patient_denied(self):
        self.assertFalse(can_read_medical_record(self.other_patient, self.record))

    def test_admin_and_auditor_can_read(self):
        self.assertTrue(can_read_medical_record(self.admin, self.record))
        self.assertTrue(can_read_medical_record(self.auditor, self.record))

    def test_read_writes_view_health_audit(self):
        AuditLog.objects.filter(action=AuditAction.VIEW_HEALTH).delete()
        read_medical_record(user=self.patient, record=self.record)
        self.assertEqual(
            AuditLog.objects.filter(
                actor=self.patient,
                action=AuditAction.VIEW_HEALTH,
                target_type="medical_record",
                target_id=str(self.record.pk),
            ).count(),
            1,
        )

    def test_denied_read_raises_permission_denied(self):
        with self.assertRaises(PermissionDenied):
            read_medical_record(user=self.other_patient, record=self.record)

"""Step 69 — privacy export + right-to-erasure + FAISS eviction.
Step 105 — export completeness registry + streaming JSON.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditAction, AuditLog, ConsentLog, ConsentScope, Role
from apps.accounts.privacy import (
    EXPORT_NESTED_MODELS,
    EXPORT_USER_MODELS,
    build_user_export,
    export_coverage_gaps,
)
from apps.matching.faiss_index import build_index, load_index
from apps.matching.models import CaregiverProfile, MatchResult, create_match_run
from apps.voice.models import create_voice_intent

User = get_user_model()


def _json_body(res) -> dict:
    """Parse JSON from DRF Response or StreamingHttpResponse."""
    if hasattr(res, "data") and isinstance(res.data, dict):
        return res.data
    if getattr(res, "streaming", False):
        raw = b"".join(res.streaming_content)
        return json.loads(raw.decode("utf-8"))
    return json.loads(res.content.decode("utf-8"))


@override_settings(EMBEDDING_BACKEND="hash", FIELD_ENCRYPTION_KEY="")
class PrivacyExportEraseTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="privacy.pt@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )
        self.caregiver_user = User.objects.create_user(
            email="privacy.cg@example.com",
            password="pw-strong-123",
            role=Role.CAREGIVER,
        )
        self.cg = CaregiverProfile.objects.create(
            user=self.caregiver_user,
            display_name="Privacy CG",
            location=Point(79.86, 6.93, srid=4326),
            certifications=["First Aid"],
            specialties=["diabetes"],
            languages=["English"],
            care_levels=["basic"],
            trust_score=0.9,
            is_active=True,
            is_approved=True,
            is_available=True,
            bio="Sensitive bio",
            nic_id="123456789V",
        )
        build_index(persist=True)
        self.export_url = reverse("v1:privacy_export")
        self.erase_url = reverse("v1:privacy_erase")

    def test_export_json_includes_voice_intent(self):
        create_voice_intent(
            user=self.patient,
            raw_text="I have dengue",
            condition="dengue",
            language="English",
            languages=["English"],
            care_level="basic",
            urgency="routine",
            source="stub",
        )
        self.client.force_authenticate(self.patient)
        res = self.client.get(self.export_url, {"export_format": "json"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = _json_body(res)
        self.assertEqual(data["user"]["email"], self.patient.email)
        self.assertEqual(len(data["voice_intents"]), 1)
        self.assertEqual(data["voice_intents"][0]["condition"], "dengue")
        self.assertEqual(data["schema_version"], 2)
        self.assertTrue(
            AuditLog.objects.filter(actor=self.patient, action=AuditAction.EXPORT_DATA).exists()
        )

    def test_export_json_includes_match_result_scores(self):
        run = create_match_run(
            user=self.patient,
            query="diabetes nearby",
            condition="diabetes",
            language="English",
            care_level="basic",
            weights=[0.4, 0.2, 0.2, 0.2],
            source="test",
        )
        MatchResult.objects.create(
            run=run,
            caregiver=self.cg,
            rank=1,
            score=0.91,
            cbf=0.8,
            cf=0.1,
            geo=0.7,
            trust=0.9,
            explanation="Matched because: strong medical/skill match",
            distance_m=1200,
        )
        self.client.force_authenticate(self.patient)
        res = self.client.get(self.export_url, {"export_format": "json"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = _json_body(res)
        self.assertEqual(len(data["match_runs"]), 1)
        row = data["match_runs"][0]
        self.assertEqual(row["weights"], [0.4, 0.2, 0.2, 0.2])
        self.assertEqual(len(row["results"]), 1)
        self.assertEqual(row["results"][0]["cbf"], 0.8)
        self.assertEqual(row["results"][0]["caregiver_id"], self.cg.pk)

    def test_export_includes_consents_and_audit(self):
        ConsentLog.objects.create(
            user=self.patient, scope=ConsentScope.AI_PROCESSING, granted=True
        )
        self.client.force_authenticate(self.patient)
        res = self.client.get(self.export_url, {"export_format": "json"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = _json_body(res)
        self.assertTrue(any(c["scope"] == ConsentScope.AI_PROCESSING for c in data["consents"]))
        self.assertTrue(
            any(a["action"] == AuditAction.EXPORT_DATA for a in data["audit_logs"])
        )
        for key in EXPORT_USER_MODELS.values():
            self.assertIn(key, data, msg=f"missing export key {key}")

    def test_export_pdf(self):
        self.client.force_authenticate(self.patient)
        res = self.client.get(self.export_url, {"export_format": "pdf"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF"))

    def test_erase_requires_confirm_and_password(self):
        self.client.force_authenticate(self.patient)
        res = self.client.post(self.erase_url, {"password": "pw-strong-123"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self.client.post(
            self.erase_url,
            {"password": "wrong", "confirm": "erase"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_erase_patient_wipes_phi_and_deactivates(self):
        create_voice_intent(
            user=self.patient,
            raw_text="secret transcript",
            condition="asthma",
            language="English",
            languages=["English"],
            care_level="basic",
            urgency="routine",
            source="stub",
        )
        self.client.force_authenticate(self.patient)
        res = self.client.post(
            self.erase_url,
            {"password": "pw-strong-123", "confirm": "erase"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertTrue(res.data["erased"])

        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_active)
        self.assertIsNotNone(self.patient.erased_at)
        self.assertTrue(self.patient.email.startswith("erased+"))
        self.assertEqual(self.patient.voice_intents.count(), 0)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.patient, action=AuditAction.REQUEST_ERASURE
            ).exists()
        )

        token_url = reverse("v1:token_obtain_pair")
        self.client.force_authenticate(user=None)
        login = self.client.post(
            token_url,
            {"email": "privacy.pt@example.com", "password": "pw-strong-123"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_erase_caregiver_rebuilds_faiss_without_them(self):
        before = load_index()
        self.assertIn(self.cg.pk, before.caregiver_ids)

        self.client.force_authenticate(self.caregiver_user)
        res = self.client.post(
            self.erase_url,
            {"password": "pw-strong-123", "confirm": "erase"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertTrue(res.data["faiss_rebuilt"])

        self.cg.refresh_from_db()
        self.assertFalse(self.cg.is_active)
        self.assertEqual(self.cg.display_name, "Erased")
        self.assertEqual(self.cg.nic_id, "")
        self.assertEqual(self.cg.embedding, [])

        after = load_index()
        self.assertNotIn(self.cg.pk, after.caregiver_ids)

    def test_admin_cannot_self_erase(self):
        admin = User.objects.create_user(
            email="privacy.admin@example.com",
            password="pw-strong-123",
            role=Role.ADMIN,
        )
        self.client.force_authenticate(admin)
        res = self.client.post(
            self.erase_url,
            {"password": "pw-strong-123", "confirm": "erase"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class ExportCompletenessTests(APITestCase):
    def test_registry_covers_every_user_linked_model(self):
        gaps = export_coverage_gaps()
        self.assertFalse(
            gaps,
            msg=(
                "New user-linked model(s) missing from EXPORT_USER_MODELS / "
                f"EXPORT_MODEL_EXCLUSIONS: {sorted(gaps)}"
            ),
        )

    def test_nested_models_documented(self):
        self.assertEqual(EXPORT_NESTED_MODELS["matching.MatchResult"], "match_runs")
        self.assertEqual(
            EXPORT_NESTED_MODELS["medical_records.MedicalRecordAttachment"],
            "medical_records",
        )

    def test_seeded_patient_export_has_registry_keys_and_results(self):
        patient = User.objects.create_user(
            email="complete.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        ConsentLog.objects.create(user=patient, scope=ConsentScope.AI_PROCESSING, granted=True)
        cg_user = User.objects.create_user(
            email="complete.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        cg = CaregiverProfile.objects.create(
            user=cg_user,
            display_name="Complete CG",
            location=Point(79.86, 6.93, srid=4326),
            specialties=["diabetes"],
            languages=["English"],
            care_levels=["basic"],
            trust_score=0.8,
            is_active=True,
            is_approved=True,
        )
        run = create_match_run(
            user=patient,
            query="diabetes",
            condition="diabetes",
            weights=[0.4, 0.2, 0.2, 0.2],
            source="test",
        )
        MatchResult.objects.create(
            run=run,
            caregiver=cg,
            rank=1,
            score=0.9,
            cbf=0.9,
            cf=0.5,
            geo=0.5,
            trust=0.8,
            explanation="skills",
        )
        payload = build_user_export(patient)
        for key in EXPORT_USER_MODELS.values():
            self.assertIn(key, payload)
        self.assertEqual(payload["schema_version"], 2)
        self.assertTrue(payload["consents"])
        self.assertTrue(payload["match_runs"])
        self.assertTrue(payload["match_runs"][0]["results"])
        self.assertEqual(payload["match_runs"][0]["weights"], [0.4, 0.2, 0.2, 0.2])
        self.assertTrue(
            any(a["action"] == AuditAction.RUN_MATCH for a in payload["audit_logs"])
        )


@override_settings(FIELD_ENCRYPTION_KEY="")
class PurgeErasedAccountsTests(APITestCase):
    def test_purge_skips_recent(self):
        from apps.accounts.privacy import purge_erased_accounts

        user = User.objects.create_user(
            email="purge.me@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )
        user.erased_at = timezone.now()
        user.is_active = False
        user.save(update_fields=["erased_at", "is_active"])
        out = purge_erased_accounts(older_than_days=30)
        self.assertEqual(out["users"], 0)

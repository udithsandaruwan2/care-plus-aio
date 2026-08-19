"""Step 69 — privacy export + right-to-erasure + FAISS eviction."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditAction, AuditLog, Role
from apps.matching.faiss_index import build_index, load_index
from apps.matching.models import CaregiverProfile
from apps.voice.models import create_voice_intent

User = get_user_model()


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
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["user"]["email"], self.patient.email)
        self.assertEqual(len(res.data["voice_intents"]), 1)
        self.assertEqual(res.data["voice_intents"][0]["condition"], "dengue")
        self.assertTrue(
            AuditLog.objects.filter(actor=self.patient, action=AuditAction.EXPORT_DATA).exists()
        )

    def test_export_json_includes_match_result_scores(self):
        from apps.matching.models import MatchResult, create_match_run

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
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(len(res.data["match_runs"]), 1)
        row = res.data["match_runs"][0]
        self.assertEqual(row["weights"], [0.4, 0.2, 0.2, 0.2])
        self.assertEqual(len(row["results"]), 1)
        self.assertEqual(row["results"][0]["cbf"], 0.8)
        self.assertEqual(row["results"][0]["caregiver_id"], self.cg.pk)

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

        # Login with old credentials must fail.
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

"""Step 104 — patient match history list + soft-delete."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AuditAction, AuditLog, Role
from apps.accounts.privacy import build_user_export
from apps.matching.models import CaregiverProfile, MatchResult, create_match_run
from apps.voice.models import create_voice_intent

User = get_user_model()


class MatchHistoryApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.patient = User.objects.create_user(
            email="hist.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        self.other = User.objects.create_user(
            email="hist.other@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        cg_user = User.objects.create_user(
            email="hist.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        self.cg = CaregiverProfile.objects.create(
            user=cg_user,
            display_name="History CG",
            location=Point(79.86, 6.93, srid=4326),
            specialties=["diabetes"],
            languages=["Sinhala"],
            care_levels=["intermediate"],
            trust_score=0.9,
            is_active=True,
            is_approved=True,
            is_available=True,
        )
        intent = create_voice_intent(
            user=self.patient,
            raw_text="I need diabetes care",
            condition="diabetes",
            language="Sinhala",
            languages=["Sinhala"],
            care_level="intermediate",
            urgency="routine",
            source="stub",
        )
        self.run = create_match_run(
            user=self.patient,
            query="diabetes care",
            condition="diabetes",
            language="Sinhala",
            care_level="intermediate",
            weights=[0.4, 0.2, 0.2, 0.2],
            voice_intent=intent,
            source="test",
        )
        MatchResult.objects.create(
            run=self.run,
            caregiver=self.cg,
            rank=1,
            score=0.91,
            cbf=0.9,
            cf=0.5,
            geo=0.5,
            trust=0.9,
            explanation="Matched because specialties align with diabetes.",
        )
        # Other patient's run must never leak.
        create_match_run(
            user=self.other,
            query="secret",
            condition="wound",
            weights=[0.4, 0.2, 0.2, 0.2],
            source="test",
        )

    def test_list_includes_results_and_understood(self):
        self.client.force_authenticate(self.patient)
        res = self.client.get("/api/v1/match/history/")
        self.assertEqual(res.status_code, 200)
        rows = res.data["results"]
        self.assertEqual(len(rows), 1)
        entry = rows[0]
        self.assertEqual(entry["id"], self.run.pk)
        self.assertEqual(entry["query"], "diabetes care")
        self.assertEqual(entry["understood"]["condition"], "diabetes")
        self.assertEqual(len(entry["results"]), 1)
        self.assertIn("diabetes", entry["results"][0]["explanation"])

    def test_voice_history_alias(self):
        self.client.force_authenticate(self.patient)
        res = self.client.get("/api/v1/voice/history/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["results"]), 1)

    def test_delete_removes_from_api_and_export_keeps_audit(self):
        self.client.force_authenticate(self.patient)
        del_res = self.client.delete(f"/api/v1/match/history/{self.run.pk}/")
        self.assertEqual(del_res.status_code, 204)

        list_res = self.client.get("/api/v1/match/history/")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(list_res.data["results"], [])

        export = build_user_export(self.patient)
        self.assertFalse(any(r["id"] == self.run.pk for r in export["match_runs"]))

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.RUN_MATCH, target_id=str(self.run.pk)
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.DELETE_MATCH_HISTORY, target_id=str(self.run.pk)
            ).exists()
        )

        # Query text scrubbed on the row.
        self.run.refresh_from_db()
        self.assertIsNotNone(self.run.deleted_at)
        self.assertEqual(self.run.query, "")

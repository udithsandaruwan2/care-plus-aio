"""Step 79 — MatchRun provenance + replay_match."""

import tempfile

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import Role
from apps.matching.faiss_index import reset_cache
from apps.matching.models import CaregiverProfile, MatchResult
from apps.matching.replay import replay_match_run

User = get_user_model()


class MatchReplayTests(TestCase):
    def setUp(self):
        reset_cache()
        self.patient = User.objects.create_user(
            email="replay.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        cg_user = User.objects.create_user(
            email="replay.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        self.cg = CaregiverProfile.objects.create(
            user=cg_user,
            display_name="Replay CG",
            location=Point(79.86, 6.93, srid=4326),
            certifications=["First Aid"],
            specialties=["diabetes"],
            languages=["Sinhala"],
            care_levels=["intermediate"],
            trust_score=0.9,
            bio="Colombo",
            is_active=True,
            is_approved=True,
            is_available=True,
        )

    def _run_api_match(self, tmp):
        from apps.matching.engine import match_run_provenance, run_match
        from apps.matching.models import create_match_run

        with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
            reset_cache()
            call_command("build_caregiver_index", verbosity=0)
            out = run_match(
                condition="diabetes",
                language="Sinhala",
                care_level="intermediate",
                query="need diabetes caregiver",
                patient_id=self.patient.pk,
                longitude=79.86,
                latitude=6.93,
                top_k=5,
            )
            run = create_match_run(
                user=self.patient,
                query=out.query,
                condition="diabetes",
                language="Sinhala",
                care_level="intermediate",
                emergency=out.emergency,
                weights=list(out.weights),
                source="test",
                **match_run_provenance(out),
            )
            for rank, hit in enumerate(out.results, start=1):
                MatchResult.objects.create(
                    run=run,
                    caregiver_id=hit.caregiver_id,
                    rank=rank,
                    score=hit.score,
                    cbf=hit.cbf,
                    cf=hit.cf,
                    geo=hit.geo,
                    trust=hit.trust,
                    explanation=hit.explanation,
                    distance_m=hit.distance_m,
                )
            return run

    def test_replay_matches_when_artifacts_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run_api_match(tmp)
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                report = replay_match_run(run)
            self.assertTrue(report["ok"], report)
            self.assertTrue(report["ranking_match"])
            self.assertTrue(report["artifacts_match"])
            self.assertEqual(report["stored_ids"], report["replayed_ids"])
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                call_command("replay_match", str(run.pk), verbosity=0)

    def test_replay_reports_mismatch_when_index_membership_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run_api_match(tmp)
            other_user = User.objects.create_user(
                email="replay.cg2@example.com", password="pw-strong-123", role=Role.CAREGIVER
            )
            CaregiverProfile.objects.create(
                user=other_user,
                display_name="Second CG",
                location=Point(79.87, 6.94, srid=4326),
                certifications=["First Aid"],
                specialties=["wound care"],
                languages=["English"],
                care_levels=["basic"],
                trust_score=0.5,
                bio="far",
                is_active=True,
                is_approved=True,
                is_available=True,
            )
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                call_command("build_caregiver_index", verbosity=0)
                report = replay_match_run(run)
            self.assertFalse(report["artifacts_match"])
            self.assertFalse(report["ok"])
            self.assertTrue(any("artifacts_changed" in r for r in report["reasons"]))
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                with self.assertRaises(CommandError):
                    call_command("replay_match", str(run.pk), verbosity=0)

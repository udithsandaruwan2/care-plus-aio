"""Step 21 acceptance: interaction log + offline ALS CF training."""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Role
from apps.matching.cf_model import load_cf_model, reset_cf_cache
from apps.matching.cf_train import patient_cf_scores, train_cf_als
from apps.matching.interactions import log_interaction, record_match_interactions
from apps.matching.models import CaregiverProfile, Interaction, InteractionKind, PatientProfile

User = get_user_model()


class InteractionLogTests(TestCase):
    def setUp(self):
        self.patient_user = User.objects.create_user(
            email="cf.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(
            user=self.patient_user,
            display_name="CF Patient",
            location=Point(79.8612, 6.9271, srid=4326),
        )
        self.caregivers = []
        for i in range(5):
            cg_user = User.objects.create_user(
                email=f"cf.cg{i}@example.com",
                password="pw-strong-123",
                role=Role.CAREGIVER,
            )
            self.caregivers.append(
                CaregiverProfile.objects.create(
                    user=cg_user,
                    display_name=f"CG {i}",
                    location=Point(79.86 + i * 0.01, 6.92, srid=4326),
                    specialties=["diabetes"],
                    languages=["English"],
                    trust_score=0.7,
                )
            )

    def test_log_interaction_and_match_views(self):
        log_interaction(
            self.patient_user,
            self.caregivers[0],
            InteractionKind.REQUEST,
        )
        n = record_match_interactions(
            self.patient_user,
            [c.id for c in self.caregivers[:3]],
            source="test",
        )
        self.assertEqual(n, 3)
        self.assertEqual(Interaction.objects.filter(patient=self.patient_user).count(), 4)

    def test_seed_and_train_produces_per_user_scores(self):
        call_command("seed_profiles", caregivers=8, patients=2, verbosity=0)
        call_command("seed_interactions", flush=True, views_per_patient=6, verbosity=0)
        self.assertGreaterEqual(Interaction.objects.count(), 5)

        with tempfile.TemporaryDirectory() as tmp:
            artifact_root = Path(tmp) / "cf"
            with self.settings(CF_ARTIFACT_DIR=str(artifact_root)):
                reset_cf_cache()
                meta = train_cf_als(factors=8, iterations=10)
                self.assertGreaterEqual(meta["n_interactions"], 5)
                self.assertTrue((artifact_root / "current.json").exists())

                model = load_cf_model(force=True)
                self.assertIsNotNone(model)
                patient_id = meta["patient_ids"][0]
                scores = patient_cf_scores(patient_id, top_k=3)
                self.assertGreaterEqual(len(scores), 1)
                self.assertIn("cf_score", scores[0])
                self.assertGreaterEqual(scores[0]["cf_score"], 0.0)
                self.assertLessEqual(scores[0]["cf_score"], 1.0)

                predicted = model.predict(patient_id, meta["caregiver_ids"][:3])
                self.assertEqual(predicted.shape[0], 3)

    def test_train_cf_command(self):
        call_command("seed_profiles", caregivers=6, patients=2, verbosity=0)
        call_command("seed_interactions", flush=True, verbosity=0)
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(CF_ARTIFACT_DIR=str(Path(tmp) / "cf")):
                reset_cf_cache()
                call_command("train_cf", verbosity=0)
                self.assertIsNotNone(load_cf_model(force=True))

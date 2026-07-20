"""Step 22 — CF blended into VEHMF fusion + offline NDCG/MAP checks."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import Role
from apps.matching.cf_eval import average_precision, ndcg_at_k
from apps.matching.cf_model import StubCFModel, reset_cf_cache
from apps.matching.engine import VEHMFEngine, _effective_weights, run_match
from apps.matching.faiss_index import build_index, reset_cache
from apps.matching.interactions import log_interaction
from apps.matching.models import CaregiverProfile, InteractionKind, PatientProfile

User = get_user_model()


class _PreferredCF:
    """Deterministic CF that strongly prefers one caregiver id."""

    def __init__(self, patient_id: int, preferred_id: int):
        self.patient_id = patient_id
        self.preferred_id = preferred_id
        self.version = "test"

    def predict(self, patient_id: int | None, caregiver_ids):
        if patient_id != self.patient_id:
            return np.full(len(caregiver_ids), 0.5, dtype=np.float32)
        return np.array(
            [1.0 if cid == self.preferred_id else 0.0 for cid in caregiver_ids],
            dtype=np.float32,
        )


class EffectiveWeightsTests(SimpleTestCase):
    def test_disabling_cf_zeroes_beta_and_redistributes(self):
        W = np.array([0.48, 0.07, 0.20, 0.25], dtype=np.float32)
        out = _effective_weights(W, cf_active=False)
        self.assertAlmostEqual(float(out[1]), 0.0, places=6)
        self.assertAlmostEqual(float(out.sum()), 1.0, places=5)
        self.assertGreater(float(out[0]), 0.48)

    def test_active_cf_keeps_weights(self):
        W = np.array([0.48, 0.07, 0.20, 0.25], dtype=np.float32)
        out = _effective_weights(W, cf_active=True)
        self.assertTrue(np.allclose(out, W))


class CfBlendEngineTests(TestCase):
    def setUp(self):
        reset_cache()
        reset_cf_cache()
        self.patient = User.objects.create_user(
            email="blend.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(
            user=self.patient,
            display_name="Blend Patient",
            location=Point(79.8612, 6.9271, srid=4326),
        )
        self.preferred = self._cg(
            "blend.pref@example.com",
            "Preferred CG",
            specialties=["diabetes"],
            languages=["Sinhala"],
            lon=79.87,
            lat=6.94,
            trust=0.7,
        )
        self.alt = self._cg(
            "blend.alt@example.com",
            "Alt CG",
            specialties=["wound care"],
            languages=["Tamil"],
            lon=79.86,
            lat=6.93,
            trust=0.95,
        )

    def _cg(self, email, name, *, specialties, languages, lon, lat, trust):
        user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
        return CaregiverProfile.objects.create(
            user=user,
            display_name=name,
            location=Point(lon, lat, srid=4326),
            certifications=["First Aid"],
            specialties=specialties,
            languages=languages,
            care_levels=["intermediate"],
            trust_score=trust,
            bio=name,
            is_active=True,
            is_approved=True,
        )

    def test_cf_bias_can_promote_preferred_caregiver(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash", CF_ENABLED=True):
                reset_cache()
                build_index(persist=True)
                cf = _PreferredCF(self.patient.pk, self.preferred.id)
                # Heavy β so CF can overturn a stronger CBF match on the alternate caregiver.
                biased_engine = VEHMFEngine(
                    cf_model=cf,
                    ahp_weights=(0.15, 0.65, 0.10, 0.10),
                )
                neutral_engine = VEHMFEngine(
                    cf_model=StubCFModel(),
                    ahp_weights=(0.15, 0.65, 0.10, 0.10),
                )
                kwargs = dict(
                    condition="wound care",
                    language="Sinhala",
                    care_level="intermediate",
                    query="Colombo wound",
                    patient_id=self.patient.pk,
                    longitude=79.86,
                    latitude=6.93,
                    top_k=2,
                )
                biased = run_match(**kwargs, engine=biased_engine)
                neutral = run_match(**kwargs, engine=neutral_engine)
                self.assertEqual(biased.results[0].caregiver_id, self.preferred.id)
                self.assertEqual(neutral.results[0].caregiver_id, self.alt.id)

    def test_cf_disabled_zeros_beta_weight(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash", CF_ENABLED=False):
                reset_cache()
                build_index(persist=True)
                out = run_match(
                    condition="diabetes",
                    language="Sinhala",
                    care_level="intermediate",
                    query="Colombo",
                    patient_id=self.patient.pk,
                    longitude=79.86,
                    latitude=6.93,
                    top_k=2,
                )
                self.assertFalse(out.cf_enabled)
                self.assertAlmostEqual(out.weights[1], 0.0, places=6)

    def test_trained_cf_improves_ndcg_over_cbf_only(self):
        for _ in range(6):
            log_interaction(self.patient, self.preferred, InteractionKind.VIEW)
        log_interaction(self.patient, self.preferred, InteractionKind.REQUEST)
        log_interaction(self.patient, self.preferred, InteractionKind.ACCEPT)
        log_interaction(self.patient, self.preferred, InteractionKind.COMPLETE)
        log_interaction(self.patient, self.preferred, InteractionKind.RATE, rating=5)
        log_interaction(self.patient, self.alt, InteractionKind.VIEW)

        relevance = {self.preferred.id: 5.0, self.alt.id: 1.0}

        with tempfile.TemporaryDirectory() as tmp:
            artifact_root = Path(tmp) / "cf"
            with self.settings(
                FAISS_ARTIFACT_DIR=tmp,
                CF_ARTIFACT_DIR=str(artifact_root),
                EMBEDDING_BACKEND="hash",
                CF_ENABLED=True,
            ):
                reset_cache()
                reset_cf_cache()
                build_index(persist=True)
                call_command("train_cf", verbosity=0)

                with_cf = run_match(
                    condition="diabetes",
                    language="Sinhala",
                    care_level="intermediate",
                    query="Colombo care",
                    patient_id=self.patient.pk,
                    longitude=79.86,
                    latitude=6.93,
                    top_k=2,
                )
                self.assertTrue(with_cf.cf_enabled)

                with self.settings(CF_ENABLED=False):
                    without_cf = run_match(
                        condition="diabetes",
                        language="Sinhala",
                        care_level="intermediate",
                        query="Colombo care",
                        patient_id=self.patient.pk,
                        longitude=79.86,
                        latitude=6.93,
                        top_k=2,
                        engine=VEHMFEngine(),
                    )
                self.assertFalse(without_cf.cf_enabled)

                ranked_with = [r.caregiver_id for r in with_cf.results]
                ranked_without = [r.caregiver_id for r in without_cf.results]
                ndcg_with = ndcg_at_k(relevance, ranked_with, k=2)
                ndcg_without = ndcg_at_k(relevance, ranked_without, k=2)
                map_with = average_precision(relevance, ranked_with)
                map_without = average_precision(relevance, ranked_without)

                self.assertGreaterEqual(ndcg_with, ndcg_without)
                self.assertGreaterEqual(map_with, map_without)
                self.assertEqual(ranked_with[0], self.preferred.id)

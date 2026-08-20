"""Step 92 — REJECT / VIEW-only negatives in confidence-weighted CF training."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import Role
from apps.matching.cf_eval import ndcg_at_k, recall_at_k
from apps.matching.cf_model import load_cf_model, load_cf_model_from_dir, reset_cf_cache
from apps.matching.cf_train import (
    build_confidence_observations,
    classify_pair_signals,
    train_cf_als,
)
from apps.matching.interactions import log_interaction
from apps.matching.models import CaregiverProfile, InteractionKind, PatientProfile

User = get_user_model()


class ClassifyPairSignalTests(SimpleTestCase):
    def test_reject_outranks_view(self):
        rows = [
            (1, 10, InteractionKind.VIEW, 1.0),
            (1, 10, InteractionKind.REJECT, -1.0),
            (1, 11, InteractionKind.ACCEPT, 5.0),
            (1, 12, InteractionKind.VIEW, 1.0),
        ]
        signals = classify_pair_signals(rows)
        self.assertEqual(signals[(1, 10)][0], "hard_negative")
        self.assertEqual(signals[(1, 11)][0], "positive")
        self.assertEqual(signals[(1, 12)][0], "weak_negative")

    def test_observations_emit_pref_zero_for_negatives(self):
        signals = {
            (1, 10): ("positive", 5.0),
            (1, 11): ("hard_negative", 1.0),
            (1, 12): ("weak_negative", 1.0),
        }
        obs, counts = build_confidence_observations(
            signals,
            patient_to_idx={1: 0},
            caregiver_to_idx={10: 0, 11: 1, 12: 2},
            use_negatives=True,
        )
        prefs = {(i, p) for _, i, _, p in obs}
        self.assertIn((0, 1.0), prefs)
        self.assertIn((1, 0.0), prefs)
        self.assertIn((2, 0.0), prefs)
        self.assertEqual(counts["hard_negative"], 1)
        self.assertEqual(counts["weak_negative"], 1)


class NegativeSignalTrainingTests(TestCase):
    def setUp(self):
        reset_cf_cache()
        self.patients = []
        for i in range(3):
            u = User.objects.create_user(
                email=f"neg.pt{i}@example.com", password="pw-strong-123", role=Role.PATIENT
            )
            PatientProfile.objects.create(
                user=u,
                display_name=f"Patient {i}",
                location=Point(79.86, 6.93, srid=4326),
            )
            self.patients.append(u)
        self.good = []
        self.bad = []
        for i in range(3):
            gu = User.objects.create_user(
                email=f"neg.good{i}@example.com",
                password="pw-strong-123",
                role=Role.CAREGIVER,
            )
            self.good.append(
                CaregiverProfile.objects.create(
                    user=gu,
                    display_name=f"Good {i}",
                    location=Point(79.86 + i * 0.01, 6.93, srid=4326),
                    specialties=["diabetes"],
                    languages=["English"],
                    trust_score=0.8,
                    is_active=True,
                    is_approved=True,
                )
            )
            bu = User.objects.create_user(
                email=f"neg.bad{i}@example.com",
                password="pw-strong-123",
                role=Role.CAREGIVER,
            )
            self.bad.append(
                CaregiverProfile.objects.create(
                    user=bu,
                    display_name=f"Bad {i}",
                    location=Point(79.90 + i * 0.01, 6.94, srid=4326),
                    specialties=["diabetes"],
                    languages=["English"],
                    trust_score=0.8,
                    is_active=True,
                    is_approved=True,
                )
            )

        # Shared pattern: each patient accepts goods, rejects bads, views another bad.
        for pt in self.patients:
            for cg in self.good:
                log_interaction(pt, cg, InteractionKind.VIEW)
                log_interaction(pt, cg, InteractionKind.REQUEST)
                log_interaction(pt, cg, InteractionKind.ACCEPT)
            for cg in self.bad[:2]:
                log_interaction(pt, cg, InteractionKind.VIEW)
                log_interaction(pt, cg, InteractionKind.REQUEST)
                log_interaction(pt, cg, InteractionKind.REJECT)
            # Shown but ignored → weak negative
            log_interaction(pt, self.bad[2], InteractionKind.VIEW)

    def _rank_ids(self, model, patient_id: int) -> list[int]:
        ids = list(model.caregiver_ids)
        scores = model.predict(patient_id, ids)
        return [cid for cid, _ in sorted(zip(ids, scores, strict=True), key=lambda r: -r[1])]

    def test_negatives_objective_beats_legacy_on_ndcg_and_recall(self):
        relevance = {cg.id: 5.0 for cg in self.good}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cf"
            with self.settings(
                CF_ARTIFACT_DIR=str(root),
                CF_GATED_PROMOTION=False,
                CF_USE_NEGATIVES=True,
            ):
                reset_cf_cache()
                legacy = train_cf_als(
                    factors=8, iterations=12, force=True, use_negatives=False
                )
                time.sleep(1.1)
                modern = train_cf_als(
                    factors=8, iterations=12, force=True, use_negatives=True
                )

            legacy_model = load_cf_model_from_dir(root / f"v{legacy['version']}")
            modern_model = load_cf_model_from_dir(root / f"v{modern['version']}")
            self.assertIsNotNone(legacy_model)
            self.assertIsNotNone(modern_model)
            self.assertEqual(modern.get("objective"), "confidence_wals_negatives")
            self.assertGreater(modern["signal_counts"]["hard_negative"], 0)
            self.assertGreater(modern["signal_counts"]["weak_negative"], 0)

            ndcg_legacy = []
            ndcg_modern = []
            recall_legacy = []
            recall_modern = []
            for pt in self.patients:
                ranked_l = self._rank_ids(legacy_model, pt.pk)
                ranked_m = self._rank_ids(modern_model, pt.pk)
                ndcg_legacy.append(ndcg_at_k(relevance, ranked_l, 5))
                ndcg_modern.append(ndcg_at_k(relevance, ranked_m, 5))
                recall_legacy.append(recall_at_k(relevance, ranked_l, 10))
                recall_modern.append(recall_at_k(relevance, ranked_m, 10))
                # Rejected caregivers should not outrank accepted ones under negatives.
                good_best = min(ranked_m.index(cg.id) for cg in self.good)
                bad_best = min(ranked_m.index(cg.id) for cg in self.bad[:2])
                self.assertLess(good_best, bad_best)

            mean_ndcg_l = sum(ndcg_legacy) / len(ndcg_legacy)
            mean_ndcg_m = sum(ndcg_modern) / len(ndcg_modern)
            mean_rec_l = sum(recall_legacy) / len(recall_legacy)
            mean_rec_m = sum(recall_modern) / len(recall_modern)
            self.assertGreaterEqual(mean_ndcg_m, mean_ndcg_l)
            self.assertGreaterEqual(mean_rec_m, mean_rec_l)
            # Persist comparison numbers for the PR / ops note.
            (root / "step92_metrics.json").write_text(
                __import__("json").dumps(
                    {
                        "legacy_ndcg_at_5": mean_ndcg_l,
                        "negatives_ndcg_at_5": mean_ndcg_m,
                        "legacy_recall_at_10": mean_rec_l,
                        "negatives_recall_at_10": mean_rec_m,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

    def test_train_with_negatives_writes_active_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(
                CF_ARTIFACT_DIR=str(Path(tmp) / "cf"),
                CF_GATED_PROMOTION=False,
                CF_USE_NEGATIVES=True,
            ):
                reset_cf_cache()
                meta = train_cf_als(factors=8, iterations=8, force=True)
                model = load_cf_model(force=True)
            self.assertTrue(meta["promoted"])
            self.assertIsNotNone(model)
            self.assertEqual(meta["objective"], "confidence_wals_negatives")

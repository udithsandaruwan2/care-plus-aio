"""Step 91 — gated CF model promotion against holdout metrics."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import Role
from apps.matching.cf_eval import RankingEvalReport
from apps.matching.cf_model import load_cf_model, reset_cf_cache
from apps.matching.cf_train import (
    promote_cf_version,
    should_promote,
    train_cf_als,
)
from apps.matching.interactions import log_interaction
from apps.matching.models import CaregiverProfile, InteractionKind, ModelKind, ModelVersion, PatientProfile

User = get_user_model()


def _fake_report(*, ndcg: float, labelled: int = 1) -> RankingEvalReport:
    from django.utils import timezone

    now = timezone.now()
    return RankingEvalReport(
        n_runs=labelled,
        n_labelled=labelled,
        ndcg_at_5=ndcg,
        map_score=ndcg,
        recall_at_10=ndcg,
        precision_at_5=ndcg,
        catalogue_coverage=0.5,
        exposure_gini=0.1,
        holdout_start=now,
        holdout_end=now,
        cf_version="test",
        per_run=(),
    )


class ShouldPromoteTests(SimpleTestCase):
    def test_requires_margin(self):
        self.assertFalse(should_promote(candidate_score=0.50, incumbent_score=0.50, margin=0.01))
        self.assertTrue(should_promote(candidate_score=0.52, incumbent_score=0.50, margin=0.01))


class GatedPromotionTests(TestCase):
    def setUp(self):
        reset_cf_cache()
        self.patient = User.objects.create_user(
            email="gate.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(
            user=self.patient,
            display_name="Gate Patient",
            location=Point(79.86, 6.93, srid=4326),
        )
        self.caregivers = []
        for i in range(5):
            u = User.objects.create_user(
                email=f"gate.cg{i}@example.com",
                password="pw-strong-123",
                role=Role.CAREGIVER,
            )
            self.caregivers.append(
                CaregiverProfile.objects.create(
                    user=u,
                    display_name=f"CG {i}",
                    location=Point(79.86 + i * 0.01, 6.92, srid=4326),
                    specialties=["diabetes"],
                    languages=["English"],
                    trust_score=0.7,
                    is_active=True,
                    is_approved=True,
                )
            )
        for cg in self.caregivers:
            log_interaction(self.patient, cg, InteractionKind.VIEW)
            log_interaction(self.patient, cg, InteractionKind.REQUEST)

    def test_cold_start_promotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cf"
            with self.settings(CF_ARTIFACT_DIR=str(root), CF_GATED_PROMOTION=True):
                reset_cf_cache()
                meta = train_cf_als(factors=8, iterations=5)
                self.assertTrue(meta["promoted"])
                self.assertEqual(meta["reason"], "cold_start")
                self.assertTrue((root / "current.json").exists())
                active = ModelVersion.objects.get(kind=ModelKind.CF, is_active=True)
                self.assertEqual(active.version, meta["version"])

    def test_shuffled_candidate_rejected_keeps_incumbent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cf"
            with self.settings(
                CF_ARTIFACT_DIR=str(root),
                CF_GATED_PROMOTION=True,
                CF_PROMOTE_MARGIN=0.01,
            ):
                reset_cf_cache()
                first = train_cf_als(factors=8, iterations=5, force=True)
                incumbent = first["version"]
                self.assertTrue((root / "current.json").exists())

                def _eval(*, days, cf_model):
                    # Incumbent looks strong; shuffled candidate looks weak.
                    if getattr(cf_model, "version", None) == incumbent:
                        return _fake_report(ndcg=0.80)
                    return _fake_report(ndcg=0.10)

                with patch("apps.matching.cf_eval.evaluate_ranking", side_effect=_eval):
                    # Distinct version timestamp
                    time.sleep(1.1)
                    second = train_cf_als(
                        factors=8,
                        iterations=5,
                        shuffle_interactions=True,
                    )

                self.assertFalse(second["promoted"])
                self.assertEqual(second["reason"], "holdout_loss")
                pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
                self.assertEqual(pointer["version"], incumbent)
                active = ModelVersion.objects.get(kind=ModelKind.CF, is_active=True)
                self.assertEqual(active.version, incumbent)
                candidate = ModelVersion.objects.get(
                    kind=ModelKind.CF, version=second["version"]
                )
                self.assertFalse(candidate.is_active)
                self.assertIn("holdout", candidate.metrics)

    def test_improvement_is_promoted_and_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cf"
            with self.settings(
                CF_ARTIFACT_DIR=str(root),
                CF_GATED_PROMOTION=True,
                CF_PROMOTE_MARGIN=0.01,
            ):
                reset_cf_cache()
                first = train_cf_als(factors=8, iterations=5, force=True)
                incumbent = first["version"]

                def _eval(*, days, cf_model):
                    if getattr(cf_model, "version", None) == incumbent:
                        return _fake_report(ndcg=0.40)
                    return _fake_report(ndcg=0.70)

                with patch("apps.matching.cf_eval.evaluate_ranking", side_effect=_eval):
                    time.sleep(1.1)
                    second = train_cf_als(factors=8, iterations=5)

                self.assertTrue(second["promoted"])
                self.assertEqual(second["reason"], "holdout_win")
                pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
                self.assertEqual(pointer["version"], second["version"])
                active = ModelVersion.objects.get(kind=ModelKind.CF, is_active=True)
                self.assertEqual(active.version, second["version"])
                self.assertEqual(active.metrics.get("promotion_reason"), "holdout_win")

    def test_promote_model_force_escape_hatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cf"
            with self.settings(CF_ARTIFACT_DIR=str(root), CF_GATED_PROMOTION=True):
                reset_cf_cache()
                first = train_cf_als(factors=8, iterations=5, force=True)
                time.sleep(1.1)
                with patch(
                    "apps.matching.cf_eval.evaluate_ranking",
                    return_value=_fake_report(ndcg=0.0),
                ):
                    rejected = train_cf_als(factors=8, iterations=5, shuffle_interactions=True)
                self.assertFalse(rejected["promoted"])
                call_command("promote_model", rejected["version"], "--force", verbosity=0)
                model = load_cf_model(force=True)
                self.assertIsNotNone(model)
                self.assertEqual(model.version, rejected["version"])
                active = ModelVersion.objects.get(kind=ModelKind.CF, is_active=True)
                self.assertEqual(active.version, rejected["version"])

    def test_promote_cf_version_without_force_respects_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cf"
            with self.settings(
                CF_ARTIFACT_DIR=str(root),
                CF_GATED_PROMOTION=True,
                CF_PROMOTE_MARGIN=0.05,
            ):
                reset_cf_cache()
                first = train_cf_als(factors=8, iterations=5, force=True)
                time.sleep(1.1)
                with patch(
                    "apps.matching.cf_eval.evaluate_ranking",
                    return_value=_fake_report(ndcg=0.0),
                ):
                    candidate = train_cf_als(factors=8, iterations=5)
                self.assertFalse(candidate["promoted"])

                def _eval(*, days, cf_model):
                    if getattr(cf_model, "version", None) == first["version"]:
                        return _fake_report(ndcg=0.90)
                    return _fake_report(ndcg=0.10)

                with patch("apps.matching.cf_eval.evaluate_ranking", side_effect=_eval):
                    result = promote_cf_version(candidate["version"], force=False)
                self.assertFalse(result["promoted"])
                pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
                self.assertEqual(pointer["version"], first["version"])

"""Step 100 — epsilon-greedy exploration slot."""

from __future__ import annotations

import random
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope, Role
from apps.matching.engine import RankedMatch
from apps.matching.exploration import (
    apply_exploration_slot,
    exposure_counts_from_rankings,
)
from apps.matching.faiss_index import reset_cache
from apps.matching.models import CaregiverProfile, MatchResult, PatientProfile, create_match_run

User = get_user_model()


def _hit(cid: int, score: float) -> RankedMatch:
    return RankedMatch(
        caregiver_id=cid,
        score=score,
        cbf=score,
        cf=0.5,
        geo=0.5,
        trust=0.5,
        explanation="test",
        distance_m=None,
    )


class ExplorationUnitTests(TestCase):
    def test_epsilon_zero_keeps_greedy(self):
        greedy = [_hit(1, 0.9), _hit(2, 0.8), _hit(3, 0.7)]
        remainder = [_hit(10, 0.1), _hit(11, 0.05)]
        out, explored = apply_exploration_slot(
            greedy, remainder, emergency=False, epsilon=0.0, rng=random.Random(1)
        )
        self.assertFalse(explored)
        self.assertEqual([r.caregiver_id for r in out], [1, 2, 3])
        self.assertTrue(all(not r.was_exploratory for r in out))

    def test_epsilon_one_replaces_last_slot(self):
        greedy = [_hit(1, 0.9), _hit(2, 0.8), _hit(3, 0.7)]
        remainder = [_hit(10, 0.1)]
        out, explored = apply_exploration_slot(
            greedy, remainder, emergency=False, epsilon=1.0, rng=random.Random(0)
        )
        self.assertTrue(explored)
        self.assertEqual([r.caregiver_id for r in out], [1, 2, 10])
        self.assertTrue(out[-1].was_exploratory)
        self.assertFalse(out[0].was_exploratory)

    def test_emergency_never_explores(self):
        greedy = [_hit(1, 0.9), _hit(2, 0.8)]
        remainder = [_hit(10, 0.1)]
        out, explored = apply_exploration_slot(
            greedy, remainder, emergency=True, epsilon=1.0, rng=random.Random(0)
        )
        self.assertFalse(explored)
        self.assertEqual([r.caregiver_id for r in out], [1, 2])

    def test_simulated_exposure_gini_falls(self):
        # Strong head + long-tail remainder — greedy always shows 1..5.
        greedy = [_hit(i, 1.0 - i * 0.05) for i in range(1, 6)]
        remainder = [_hit(i, 0.1 - (i - 10) * 0.01) for i in range(10, 30)]
        catalogue = list(range(1, 6)) + list(range(10, 30))
        top_k_ids = [r.caregiver_id for r in greedy]

        greedy_runs = [top_k_ids for _ in range(200)]
        explore_runs = []
        for seed in range(200):
            out, _ = apply_exploration_slot(
                greedy,
                remainder,
                emergency=False,
                epsilon=1.0,
                rng=random.Random(seed),
            )
            explore_runs.append([r.caregiver_id for r in out])

        def gini_over_catalogue(runs: list[list[int]]) -> float:
            counts = exposure_counts_from_rankings(runs)
            # Include zeros so monopoly-on-head scores higher than long-tail spread.
            values = [float(counts.get(cid, 0)) for cid in catalogue]
            n = len(values)
            ordered = sorted(values)
            total = sum(ordered)
            if total <= 0:
                return 0.0
            weighted = sum((i + 1) * x for i, x in enumerate(ordered))
            return (2.0 * weighted) / (n * total) - (n + 1) / n

        g_greedy = gini_over_catalogue(greedy_runs)
        g_explore = gini_over_catalogue(explore_runs)
        self.assertGreater(g_greedy, g_explore)
        explore_ids = {cid for run in explore_runs for cid in run}
        self.assertTrue(any(cid >= 10 for cid in explore_ids))


class ExplorationPersistTests(APITestCase):
    def setUp(self):
        reset_cache()
        self.patient = User.objects.create_user(
            email="explore.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        ConsentLog.objects.create(user=self.patient, scope=ConsentScope.AI_PROCESSING, granted=True)
        PatientProfile.objects.create(
            user=self.patient,
            display_name="Explore Patient",
            location=Point(79.86, 6.93, srid=4326),
        )
        self.caregivers = []
        for i in range(8):
            u = User.objects.create_user(
                email=f"explore.cg{i}@example.com",
                password="pw-strong-123",
                role=Role.CAREGIVER,
            )
            self.caregivers.append(
                CaregiverProfile.objects.create(
                    user=u,
                    display_name=f"Explore CG {i}",
                    location=Point(79.86 + i * 0.01, 6.93, srid=4326),
                    specialties=["diabetes"] if i < 4 else ["wound care"],
                    languages=["English"],
                    care_levels=["intermediate"],
                    trust_score=0.9 - i * 0.05,
                    is_active=True,
                    is_approved=True,
                    is_available=True,
                    bio=f"caregiver {i}",
                )
            )
        self.url = reverse("v1:match")

    @override_settings(MATCH_EXPLORATION_EPSILON=1.0, EMBEDDING_BACKEND="hash")
    def test_match_api_flags_exploratory_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                call_command("build_caregiver_index", verbosity=0)
                self.client.force_authenticate(self.patient)
                res = self.client.post(
                    self.url,
                    {
                        "condition": "diabetes",
                        "language": "English",
                        "care_level": "intermediate",
                        "k": 3,
                        "emergency": False,
                        "longitude": 79.86,
                        "latitude": 6.93,
                    },
                    format="json",
                )
                self.assertEqual(res.status_code, status.HTTP_201_CREATED)
                results = res.data["results"]
                self.assertGreaterEqual(len(results), 1)
                self.assertTrue(any(r.get("was_exploratory") for r in results))
                self.assertTrue(
                    MatchResult.objects.filter(
                        run_id=res.data["request_id"], was_exploratory=True
                    ).exists()
                )
                from apps.matching.models import MatchRun

                run = MatchRun.objects.get(pk=res.data["request_id"])
                self.assertTrue(run.filters.get("explored"))

    @override_settings(MATCH_EXPLORATION_EPSILON=1.0, EMBEDDING_BACKEND="hash")
    def test_emergency_match_never_exploratory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                call_command("build_caregiver_index", verbosity=0)
                self.client.force_authenticate(self.patient)
                res = self.client.post(
                    self.url,
                    {
                        "condition": "diabetes",
                        "language": "English",
                        "care_level": "intermediate",
                        "k": 3,
                        "emergency": True,
                        "longitude": 79.86,
                        "latitude": 6.93,
                    },
                    format="json",
                )
                self.assertEqual(res.status_code, status.HTTP_201_CREATED)
                self.assertTrue(all(not r.get("was_exploratory") for r in res.data["results"]))
                self.assertFalse(
                    MatchResult.objects.filter(
                        run_id=res.data["request_id"], was_exploratory=True
                    ).exists()
                )

    def test_create_match_result_default_flag(self):
        run = create_match_run(user=self.patient, emergency=False, source="test")
        MatchResult.objects.create(
            run=run,
            caregiver=self.caregivers[0],
            rank=1,
            score=0.5,
            cbf=0.5,
            cf=0.5,
            geo=0.5,
            trust=0.5,
            explanation="x",
        )
        self.assertFalse(MatchResult.objects.get(run=run).was_exploratory)

"""Step 103 — ranking guardrails (approval, MMR, exposure caps, fairness report)."""

from __future__ import annotations

import tempfile

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import Role
from apps.matching.engine import RankedMatch, run_match
from apps.matching.fairness import (
    build_fairness_report,
    diversity_stats,
    filter_overexposed,
    mmr_rerank,
)
from apps.matching.faiss_index import build_index, reset_cache
from apps.matching.models import CaregiverProfile, MatchResult, create_match_run

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
    )


class MmrUnitTests(TestCase):
    def setUp(self):
        self.profiles = {}
        specs = [
            ("a", ["Sinhala"], ["diabetes"]),
            ("b", ["Sinhala"], ["diabetes"]),
            ("c", ["Sinhala"], ["diabetes"]),
            ("d", ["Tamil"], ["wound care"]),
            ("e", ["English"], ["dementia"]),
        ]
        self.keys = {}
        for key, langs, specs_ in specs:
            u = User.objects.create_user(
                email=f"mmr{key}@example.com", password="pw-strong-123", role=Role.CAREGIVER
            )
            p = CaregiverProfile.objects.create(
                user=u,
                display_name=f"MMR {key}",
                location=Point(79.86, 6.93, srid=4326),
                specialties=specs_,
                languages=langs,
                care_levels=["intermediate"],
                trust_score=0.8,
                is_active=True,
                is_approved=True,
                is_available=True,
            )
            self.keys[key] = p.id
            self.profiles[p.id] = p

    def test_mmr_improves_language_specialty_diversity(self):
        # Greedy order is three near-identical diabetes/Sinhala profiles first.
        a, b, c, d, e = (self.keys[k] for k in "abcde")
        # Near-tied scores so diversity can beat the third clone at λ=0.55.
        candidates = [
            _hit(a, 0.90),
            _hit(b, 0.89),
            _hit(c, 0.88),
            _hit(d, 0.85),
            _hit(e, 0.84),
        ]
        greedy = candidates[:3]
        mmr = mmr_rerank(candidates, self.profiles, k=3, lambda_=0.55)
        g_stats = diversity_stats(greedy, self.profiles)
        m_stats = diversity_stats(mmr, self.profiles)
        self.assertGreater(m_stats["unique_languages"], g_stats["unique_languages"])
        self.assertGreater(m_stats["unique_specialties"], g_stats["unique_specialties"])
        mmr_ids = [h.caregiver_id for h in mmr]
        self.assertTrue(d in mmr_ids or e in mmr_ids)
        self.assertNotEqual(set(mmr_ids), {a, b, c})


class ExposureCapTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="cap.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        self.cgs = []
        for i in range(3):
            u = User.objects.create_user(
                email=f"cap.cg{i}@example.com", password="pw-strong-123", role=Role.CAREGIVER
            )
            self.cgs.append(
                CaregiverProfile.objects.create(
                    user=u,
                    display_name=f"Cap CG {i}",
                    location=Point(79.86, 6.93, srid=4326),
                    specialties=["diabetes"],
                    languages=["English"],
                    care_levels=["intermediate"],
                    trust_score=0.8,
                    is_active=True,
                    is_approved=True,
                    is_available=True,
                )
            )

    def test_filter_overexposed_drops_capped(self):
        for i in range(3):
            run = create_match_run(user=self.patient, source="test")
            MatchResult.objects.create(
                run=run,
                caregiver=self.cgs[0],
                rank=1,
                score=0.9,
                cbf=0.9,
                cf=0.5,
                geo=0.5,
                trust=0.5,
                explanation="x",
            )
        candidates = [_hit(self.cgs[0].id, 0.9), _hit(self.cgs[1].id, 0.8)]
        with self.settings(MATCH_EXPOSURE_CAP=3, MATCH_EXPOSURE_WINDOW_HOURS=24):
            kept, dropped = filter_overexposed(candidates, emergency=False)
        self.assertIn(self.cgs[0].id, dropped)
        self.assertEqual([c.caregiver_id for c in kept], [self.cgs[1].id])

    def test_emergency_bypasses_cap(self):
        for i in range(5):
            run = create_match_run(user=self.patient, source="test", emergency=True)
            MatchResult.objects.create(
                run=run,
                caregiver=self.cgs[0],
                rank=1,
                score=0.9,
                cbf=0.9,
                cf=0.5,
                geo=0.5,
                trust=0.5,
                explanation="x",
            )
        candidates = [_hit(self.cgs[0].id, 0.9)]
        with self.settings(MATCH_EXPOSURE_CAP=1):
            kept, dropped = filter_overexposed(candidates, emergency=True)
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, [])


@override_settings(EMBEDDING_BACKEND="hash", MATCH_MMR_LAMBDA=0.55, MATCH_EXPOSURE_CAP=0)
class ApprovalFilterTests(TestCase):
    def setUp(self):
        reset_cache()
        self.approved = self._cg("ok@example.com", "Approved CG", approved=True, specs=["diabetes"])
        self.unapproved = self._cg(
            "no@example.com", "Pending CG", approved=False, specs=["diabetes"]
        )

    def _cg(self, email, name, *, approved, specs):
        u = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
        return CaregiverProfile.objects.create(
            user=u,
            display_name=name,
            location=Point(79.86, 6.93, srid=4326),
            specialties=specs,
            languages=["Sinhala", "English"],
            care_levels=["intermediate"],
            trust_score=0.95 if approved else 0.99,
            bio=name,
            is_active=True,
            is_approved=approved,
            is_available=True,
        )

    def test_unapproved_never_in_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                build_index(persist=True)
                out = run_match(
                    condition="diabetes",
                    language="Sinhala",
                    care_level="intermediate",
                    longitude=79.86,
                    latitude=6.93,
                    top_k=5,
                )
                ids = [r.caregiver_id for r in out.results]
                self.assertIn(self.approved.id, ids)
                self.assertNotIn(self.unapproved.id, ids)


class FairnessReportTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="fair.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        u = User.objects.create_user(
            email="fair.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        self.cg = CaregiverProfile.objects.create(
            user=u,
            display_name="Fair CG",
            city="Colombo",
            location=Point(79.86, 6.93, srid=4326),
            specialties=["diabetes"],
            languages=["Sinhala"],
            care_levels=["intermediate"],
            trust_score=0.8,
            is_active=True,
            is_approved=True,
        )
        run = create_match_run(user=self.patient, source="test")
        MatchResult.objects.create(
            run=run,
            caregiver=self.cg,
            rank=1,
            score=0.9,
            cbf=0.9,
            cf=0.5,
            geo=0.5,
            trust=0.5,
            explanation="x",
        )

    def test_build_and_command(self):
        report = build_fairness_report(days=14)
        self.assertGreaterEqual(report["n_impressions"], 1)
        self.assertTrue(any(r["city"] == "Colombo" for r in report["by_city"]))
        self.assertTrue(any(r["language"] == "Sinhala" for r in report["by_language"]))
        call_command("fairness_report", days=14, verbosity=0)

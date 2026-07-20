"""Step 15i — refine phrase → filter deltas + hard filters in VEHMF."""

import tempfile

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import Role
from apps.matching.engine import run_match
from apps.matching.faiss_index import build_index, reset_cache
from apps.matching.models import CaregiverProfile
from apps.voice.refine import apply_deltas_to_intent, parse_refine_deltas
from apps.voice.router import classify_turn

User = get_user_model()

COMPLETE = {
    "condition": "diabetes",
    "language": "Sinhala",
    "care_level": "intermediate",
}


class ParseRefineDeltasTests(SimpleTestCase):
    def test_tamil_within_5_km(self):
        d = parse_refine_deltas("only Tamil speakers within 5 km")
        self.assertEqual(d.language, "Tamil")
        self.assertEqual(d.max_distance_km, 5.0)
        self.assertTrue(d.applied())

    def test_closer_defaults_radius(self):
        d = parse_refine_deltas("someone closer please")
        self.assertTrue(d.prefer_closer)
        self.assertEqual(d.max_distance_km, 15.0)

    def test_specialty_and_care(self):
        d = parse_refine_deltas("advanced wound care only")
        self.assertEqual(d.care_level, "advanced")
        self.assertEqual(d.specialty, "wound care")

    def test_apply_sets_hard_flags(self):
        intent = apply_deltas_to_intent(COMPLETE, parse_refine_deltas("Tamil only"))
        self.assertEqual(intent["language"], "Tamil")
        self.assertTrue(intent["_hard_language"])


class RefineRouteTests(SimpleTestCase):
    def test_tamil_within_routes_refine(self):
        d = classify_turn(
            "only Tamil speakers within 5 km",
            COMPLETE,
            has_prior_match=True,
        )
        self.assertEqual(d.route, "REFINE")


class RefineEngineFilterTests(TestCase):
    def setUp(self):
        reset_cache()
        self.tamil_near = self._cg(
            "ref.ta.near@example.com",
            "Tamil Near",
            languages=["Tamil", "English"],
            specialties=["diabetes"],
            lon=79.861,
            lat=6.927,
        )
        self.sinhala_far = self._cg(
            "ref.si.far@example.com",
            "Sinhala Far",
            languages=["Sinhala"],
            specialties=["diabetes"],
            lon=81.0,
            lat=8.0,
        )

    def _cg(self, email, name, *, languages, specialties, lon, lat):
        user = User.objects.create_user(email=email, password="pw-strong-123", role=Role.CAREGIVER)
        return CaregiverProfile.objects.create(
            user=user,
            display_name=name,
            location=Point(lon, lat, srid=4326),
            certifications=["First Aid"],
            specialties=specialties,
            languages=languages,
            care_levels=["intermediate"],
            trust_score=0.9,
            bio=name,
            is_active=True,
            is_approved=True,
            is_available=True,
        )

    def test_hard_language_and_distance_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp, EMBEDDING_BACKEND="hash"):
                reset_cache()
                build_index(persist=True)
                out = run_match(
                    condition="diabetes",
                    language="Tamil",
                    care_level="intermediate",
                    longitude=79.86,
                    latitude=6.93,
                    top_k=10,
                    max_distance_km=10,
                    hard_filter_language=True,
                )
                ids = {r.caregiver_id for r in out.results}
                self.assertIn(self.tamil_near.id, ids)
                self.assertNotIn(self.sinhala_far.id, ids)
                for hit in out.results:
                    if hit.distance_m is not None:
                        self.assertLessEqual(hit.distance_m, 10_000)

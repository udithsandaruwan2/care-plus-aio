"""Step 18 — AHP weight solver + consistency checks."""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.ahp import (
    DEFAULT_EMERGENCY,
    DEFAULT_PAIRWISE,
    AhpError,
    get_ahp_weights,
    normalize_weights,
    reset_ahp_cache,
    solve_ahp,
    write_config,
)

User = get_user_model()


class AhpSolverTests(SimpleTestCase):
    def test_weights_sum_to_one_and_cr_ok(self):
        result = solve_ahp(DEFAULT_PAIRWISE)
        self.assertAlmostEqual(sum(result.weights), 1.0, places=6)
        self.assertLess(result.consistency_ratio, 0.1)
        self.assertTrue(result.is_consistent)
        # Clinical CBF should dominate the default survey.
        self.assertEqual(result.weights.index(max(result.weights)), 0)

    def test_rejects_inconsistent_matrix(self):
        bad = [
            [1, 9, 9, 9],
            [1 / 9, 1, 9, 1 / 9],
            [1 / 9, 1 / 9, 1, 9],
            [1 / 9, 9, 1 / 9, 1],
        ]
        with self.assertRaises(AhpError):
            solve_ahp(bad)

    def test_normalize_and_emergency_defaults(self):
        w = normalize_weights([2, 2, 2, 2])
        self.assertTrue(all(abs(x - 0.25) < 1e-9 for x in w))
        e = normalize_weights(DEFAULT_EMERGENCY)
        self.assertAlmostEqual(sum(e), 1.0, places=9)
        self.assertAlmostEqual(e[0], 0.80, places=5)


class AhpConfigTests(TestCase):
    def test_write_and_load_config(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ahp_weights.json"
            with self.settings(
                AHP_WEIGHTS_PATH=str(path), AHP_WEIGHTS="", AHP_EMERGENCY_WEIGHTS=""
            ):
                reset_ahp_cache()
                write_config(path)
                self.assertTrue(path.exists())
                normal = get_ahp_weights(refresh=True)
                emergency = get_ahp_weights(emergency=True, refresh=True)
                self.assertAlmostEqual(sum(normal), 1.0, places=6)
                self.assertAlmostEqual(sum(emergency), 1.0, places=6)
                self.assertAlmostEqual(emergency[0], 0.80, places=5)

    def test_env_override(self):
        with self.settings(AHP_WEIGHTS="0.5,0.1,0.2,0.2", AHP_EMERGENCY_WEIGHTS="0.7,0.1,0.1,0.1"):
            reset_ahp_cache()
            normal = get_ahp_weights(refresh=True)
            emergency = get_ahp_weights(emergency=True, refresh=True)
            for got, want in zip(normal, (0.5, 0.1, 0.2, 0.2), strict=True):
                self.assertAlmostEqual(got, want, places=9)
            for got, want in zip(emergency, (0.7, 0.1, 0.1, 0.1), strict=True):
                self.assertAlmostEqual(got, want, places=9)


class AhpApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ahp@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        self.url = reverse("v1:match_ahp_weights")

    def test_requires_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_weights(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ahp.json"
            write_config(path)
            with self.settings(
                AHP_WEIGHTS_PATH=str(path), AHP_WEIGHTS="", AHP_EMERGENCY_WEIGHTS=""
            ):
                reset_ahp_cache()
                self.client.force_authenticate(self.user)
                resp = self.client.get(self.url)
                self.assertEqual(resp.status_code, status.HTTP_200_OK)
                self.assertAlmostEqual(sum(resp.data["vector"]), 1.0, places=5)
                self.assertLess(resp.data["consistency_ratio"], 0.1)
                self.assertEqual(len(resp.data["emergency_vector"]), 4)

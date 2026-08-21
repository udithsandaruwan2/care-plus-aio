"""Step 102 — online A/B weight variants."""

from __future__ import annotations

import json
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.analytics import build_weight_ab_comparison
from apps.matching.experiments import (
    active_variants,
    assign_variant,
    load_ab_config,
    resolve_ab_weights,
    stopping_rule_status,
)
from apps.matching.models import (
    CareRequest,
    CareRequestStatus,
    CaregiverProfile,
    MatchRun,
    PatientProfile,
    create_match_run,
)

User = get_user_model()


def _write_config(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


class AssignmentTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg_path = Path(self.tmp.name) / "weight_ab.json"
        self.doc = {
            "experiment_id": "test_ab",
            "salt": "test-salt",
            "min_runs_per_variant": 10,
            "min_days": 7,
            "variants": [
                {"id": "control", "traffic": 50, "active": True, "weights": None},
                {"id": "geo_tilt", "traffic": 50, "active": True, "weights": [0.35, 0.1, 0.35, 0.2]},
            ],
        }
        _write_config(self.cfg_path, self.doc)

    def test_assignment_stable_across_calls(self):
        with self.settings(WEIGHT_AB_CONFIG_PATH=str(self.cfg_path), WEIGHT_AB_ENABLED=True):
            a = assign_variant(42)
            b = assign_variant(42)
            self.assertEqual(a, b)
            self.assertIn(a, {"control", "geo_tilt"})

    def test_retired_variant_excluded_from_new_traffic(self):
        self.doc["variants"][1]["active"] = False
        _write_config(self.cfg_path, self.doc)
        with self.settings(WEIGHT_AB_CONFIG_PATH=str(self.cfg_path), WEIGHT_AB_ENABLED=True):
            arms = active_variants(load_ab_config())
            self.assertEqual([a["id"] for a in arms], ["control"])
            for uid in range(1, 40):
                self.assertEqual(assign_variant(uid), "control")

    def test_resolve_records_variant_and_override(self):
        with self.settings(WEIGHT_AB_CONFIG_PATH=str(self.cfg_path), WEIGHT_AB_ENABLED=True):
            # Find a user that hashes to geo_tilt.
            chosen = None
            for uid in range(1, 500):
                if assign_variant(uid) == "geo_tilt":
                    chosen = uid
                    break
            self.assertIsNotNone(chosen)
            res = resolve_ab_weights(chosen, emergency=False, city="Colombo")
            self.assertEqual(res.variant, "geo_tilt")
            self.assertEqual(res.weights_source, "ab:geo_tilt")
            self.assertAlmostEqual(sum(res.weights), 1.0, places=5)
            self.assertGreater(res.weights[2], 0.3)  # geo tilt

    def test_disabled_experiment_empty_variant(self):
        with self.settings(WEIGHT_AB_CONFIG_PATH=str(self.cfg_path), WEIGHT_AB_ENABLED=False):
            res = resolve_ab_weights(7, emergency=False)
            self.assertEqual(res.variant, "")


class WeightAbAnalyticsTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg_path = Path(self.tmp.name) / "weight_ab.json"
        _write_config(
            self.cfg_path,
            {
                "experiment_id": "test_ab",
                "salt": "test-salt",
                "min_runs_per_variant": 5,
                "min_days": 3,
                "variants": [
                    {"id": "control", "traffic": 50, "active": True, "weights": None},
                    {"id": "geo_tilt", "traffic": 50, "active": True, "weights": [0.35, 0.1, 0.35, 0.2]},
                ],
            },
        )
        self.patient = User.objects.create_user(
            email="ab.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(
            user=self.patient,
            display_name="AB Patient",
            city="Colombo",
            location=Point(79.86, 6.93, srid=4326),
        )
        cg_user = User.objects.create_user(
            email="ab.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        self.cg = CaregiverProfile.objects.create(
            user=cg_user,
            display_name="AB CG",
            location=Point(79.86, 6.93, srid=4326),
            specialties=["diabetes"],
            languages=["English"],
            care_levels=["intermediate"],
            trust_score=0.9,
            is_active=True,
            is_approved=True,
        )

    def test_comparison_and_stopping_rule(self):
        with self.settings(WEIGHT_AB_CONFIG_PATH=str(self.cfg_path)):
            now = timezone.now()
            for i, variant in enumerate(["control", "control", "geo_tilt"]):
                run = create_match_run(
                    user=self.patient,
                    emergency=False,
                    weights=[0.4, 0.2, 0.2, 0.2],
                    weights_source=f"ab:{variant}",
                    variant=variant,
                    source="test",
                )
                run_created = now - timedelta(hours=i + 1)
                MatchRun.objects.filter(pk=run.pk).update(created_at=run_created)
                run.refresh_from_db()
                if variant == "control":
                    cr = CareRequest.objects.create(
                        patient=self.patient,
                        caregiver=self.cg,
                        match_run=run,
                        status=CareRequestStatus.ACCEPTED,
                        message="ok",
                        expires_at=run_created + timedelta(days=3),
                    )
                    CareRequest.objects.filter(pk=cr.pk).update(
                        created_at=run_created,
                        responded_at=run_created + timedelta(minutes=12),
                    )

            payload = build_weight_ab_comparison(window_days=30)
            self.assertEqual(payload["experiment_id"], "test_ab")
            by_v = {r["variant"]: r for r in payload["variants"]}
            self.assertEqual(by_v["control"]["n_runs"], 2)
            self.assertEqual(by_v["control"]["n_accepts"], 2)
            self.assertEqual(by_v["control"]["accept_rate"], 1.0)
            self.assertEqual(by_v["geo_tilt"]["n_runs"], 1)
            self.assertFalse(payload["stopping_rule"]["ready"])
            self.assertTrue(any("n_runs" in r for r in payload["stopping_rule"]["reasons"]))

            ready = stopping_rule_status(
                [
                    {"variant": "control", "n_runs": 5},
                    {"variant": "geo_tilt", "n_runs": 5},
                ],
                window_days=14,
                config=load_ab_config(),
            )
            self.assertTrue(ready["ready"])


class WeightAbApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="ab.admin@example.com", password="pw-strong-123", role=Role.ADMIN
        )

    def test_analytics_includes_weight_ab(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get(reverse("v1:admin_analytics"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("weight_ab", res.data)
        self.assertIn("stopping_rule", res.data["weight_ab"])
        self.assertIn("variants", res.data["weight_ab"])

"""Step 96 — offline slot classifier beats rule stub on hand holdout."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from django.test import TestCase, override_settings

from apps.matching.models import ModelKind, ModelVersion
from apps.voice.extraction import extract_stub
from apps.voice.slots import (
    evaluate_on_rows,
    evaluate_stub_on_rows,
    extract_with_classifier,
    load_hand_holdout,
    load_slot_classifier,
    train_slot_classifier,
)


class SlotClassifierTests(TestCase):
    def test_train_beats_stub_on_hand_holdout_and_is_fast(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(
                SLOT_ARTIFACT_DIR=tmp,
                SLOT_GATED_PROMOTION=True,
                SLOT_PROMOTE_MARGIN=0.02,
            ):
                meta = train_slot_classifier(force=False, include_voice_intents=False)
                holdout = load_hand_holdout()
                self.assertGreaterEqual(len(holdout), 20)

                clf_metrics = (meta.get("metrics") or {}).get("holdout") or {}
                stub_metrics = (meta.get("metrics") or {}).get("stub_holdout") or {}
                clf_cond = float((clf_metrics.get("per_slot") or {}).get("condition") or 0)
                stub_cond = float((stub_metrics.get("per_slot") or {}).get("condition") or 0)
                clf_exact = float(clf_metrics.get("exact_match") or 0)
                stub_exact = float(stub_metrics.get("exact_match") or 0)

                self.assertGreater(
                    clf_cond,
                    stub_cond,
                    msg=f"condition clf={clf_cond} stub={stub_cond}",
                )
                self.assertGreaterEqual(clf_cond, 0.65)
                self.assertGreaterEqual(clf_exact, stub_exact)
                self.assertTrue((meta.get("promotion") or {}).get("promoted"))

                active = ModelVersion.objects.filter(
                    kind=ModelKind.SLOT_CLASSIFIER, is_active=True
                ).first()
                self.assertIsNotNone(active)
                self.assertEqual(active.version, meta["version"])
                self.assertTrue((Path(tmp) / "current.json").is_file())

                clf = load_slot_classifier(force=True)
                self.assertIsNotNone(clf)
                # Lean CPU: p95 under 50 ms on holdout sample.
                report = evaluate_on_rows(clf, holdout)
                self.assertLess(report["latency_ms_p95"], 50.0)

                # Spot-check a paraphrase the stub typically misses.
                sample = "insulin shots every morning and evening"
                stub = extract_stub(sample)
                got = extract_with_classifier(sample, classifier=clf)
                self.assertIsNotNone(got)
                self.assertEqual(got["condition"], "diabetes")
                self.assertNotEqual(stub.get("condition") or "", "diabetes")

    def test_single_utterance_under_50ms(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(SLOT_ARTIFACT_DIR=tmp, SLOT_GATED_PROMOTION=False):
                train_slot_classifier(force=True, include_voice_intents=False)
                clf = load_slot_classifier(force=True)
                self.assertIsNotNone(clf)
                # Warm-up
                clf.predict_one("hello")
                times = []
                for _ in range(20):
                    t0 = time.perf_counter()
                    clf.predict_one("glucose keeps swinging wildly this week")
                    times.append((time.perf_counter() - t0) * 1000.0)
                times.sort()
                self.assertLess(times[len(times) // 2], 50.0)

    def test_stub_baseline_below_classifier_on_holdout(self):
        holdout = load_hand_holdout()
        stub = evaluate_stub_on_rows(holdout)
        self.assertLess(stub["per_slot"]["condition"], 0.55)

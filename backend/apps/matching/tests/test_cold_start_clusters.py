"""Step 99 — cold-start clustering + CF seed + intent vocab suggestions."""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.matching.cf_eval import ndcg_at_k
from apps.matching.cf_model import AlsCFModel, load_cf_model, reset_cf_cache
from apps.matching.cf_train import train_cf_als
from apps.matching.clustering import (
    build_cf_cold_start_vectors,
    build_and_persist_all,
    cluster_caregiver_embeddings,
    cluster_intent_embeddings,
    suggest_vocab_from_intent_clusters,
)
from apps.matching.embeddings import get_embedder, profile_to_text
from apps.matching.models import CaregiverProfile, PatientProfile, create_match_run
from apps.vocab.models import ConditionTerm
from apps.vocab.resolver import resolve_condition

User = get_user_model()


class ColdStartClusterTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cf_dir = Path(self.tmp.name) / "cf"
        self.cluster_dir = Path(self.tmp.name) / "clusters"

        self.patient_user = User.objects.create_user(
            email="cold.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        PatientProfile.objects.create(
            user=self.patient_user,
            display_name="Cold Patient",
            location=Point(79.86, 6.93, srid=4326),
        )

        self.trained_cgs = []
        for i, specs in enumerate(
            [
                ["diabetes", "hypertension"],
                ["diabetes"],
                ["wound care"],
                ["wound care", "elderly care"],
                ["dementia"],
                ["asthma"],
            ]
        ):
            u = User.objects.create_user(
                email=f"cold.cg{i}@example.com",
                password="pw-strong-123",
                role=Role.CAREGIVER,
            )
            cg = CaregiverProfile.objects.create(
                user=u,
                display_name=f"Trained CG {i}",
                location=Point(79.86 + i * 0.01, 6.93, srid=4326),
                specialties=specs,
                languages=["Sinhala", "English"],
                care_levels=["intermediate"],
                trust_score=0.8,
                is_active=True,
                is_approved=True,
                bio=f"{specs[0]} specialist",
            )
            vec = get_embedder().embed([profile_to_text(cg)])[0]
            cg.embedding = vec.tolist()
            cg.save(update_fields=["embedding"])
            self.trained_cgs.append(cg)

        # Seed interactions so ALS includes trained caregivers only.
        from apps.matching.interactions import log_interaction
        from apps.matching.models import InteractionKind

        for cg in self.trained_cgs:
            log_interaction(self.patient_user, cg, InteractionKind.VIEW)
            log_interaction(self.patient_user, cg, InteractionKind.REQUEST)

    def _train(self) -> AlsCFModel:
        with self.settings(
            CF_ARTIFACT_DIR=str(self.cf_dir),
            CLUSTER_ARTIFACT_DIR=str(self.cluster_dir),
            CF_GATED_PROMOTION=False,
        ):
            reset_cf_cache()
            train_cf_als(factors=8, iterations=12, force=True)
            model = load_cf_model(force=True)
            assert model is not None
            return model

    def test_new_caregiver_gets_nonzero_cf_before_interactions(self):
        model = self._train()
        # Brand-new caregiver matching diabetes cluster, zero interactions.
        u = User.objects.create_user(
            email="cold.new@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        newbie = CaregiverProfile.objects.create(
            user=u,
            display_name="New Diabetes CG",
            location=Point(79.87, 6.94, srid=4326),
            specialties=["diabetes"],
            languages=["Sinhala"],
            care_levels=["intermediate"],
            trust_score=0.75,
            is_active=True,
            is_approved=True,
            bio="diabetes educator",
        )
        vec = get_embedder().embed([profile_to_text(newbie)])[0]
        newbie.embedding = vec.tolist()
        newbie.save(update_fields=["embedding"])

        self.assertNotIn(newbie.id, model.caregiver_ids)
        raw_before = model.raw_scores(self.patient_user.id, [newbie.id])[0]
        self.assertEqual(float(raw_before), 0.0)

        with self.settings(CLUSTER_ARTIFACT_DIR=str(self.cluster_dir)):
            clusters = cluster_caregiver_embeddings(k=3)
            cold = build_cf_cold_start_vectors(model, clusters)
            seeded = model.with_cold_start(cold)

        self.assertIn(newbie.id, cold)
        raw_after = seeded.raw_scores(self.patient_user.id, [newbie.id])[0]
        self.assertNotEqual(float(raw_after), 0.0)

        # Against a pool of trained + new, seeded CF should not pin the new CG at 0.
        pool = [c.id for c in self.trained_cgs] + [newbie.id]
        scores = seeded.predict(self.patient_user.id, pool)
        new_idx = pool.index(newbie.id)
        self.assertGreater(float(scores[new_idx]), 0.0)

    def test_ndcg_does_not_regress_for_known_caregivers(self):
        model = self._train()
        with self.settings(CLUSTER_ARTIFACT_DIR=str(self.cluster_dir)):
            clusters = cluster_caregiver_embeddings(k=3)
            cold = build_cf_cold_start_vectors(model, clusters)
            seeded = model.with_cold_start(cold)

        # Synthetic graded relevance over trained caregivers only.
        relevance = {c.id: float(6 - i) for i, c in enumerate(self.trained_cgs)}
        ids = [c.id for c in self.trained_cgs]
        base_raw = model.raw_scores(self.patient_user.id, ids)
        seed_raw = seeded.raw_scores(self.patient_user.id, ids)
        ranked_base_ids = [cid for cid, _ in sorted(zip(ids, base_raw), key=lambda t: t[1], reverse=True)]
        ranked_seed_ids = [cid for cid, _ in sorted(zip(ids, seed_raw), key=lambda t: t[1], reverse=True)]
        # Trained factors unchanged → identical ranking among known items.
        self.assertEqual(ranked_base_ids, ranked_seed_ids)
        n_base = ndcg_at_k(relevance, ranked_base_ids, 5)
        n_seed = ndcg_at_k(relevance, ranked_seed_ids, 5)
        self.assertEqual(n_base, n_seed)

    def test_intent_clusters_surface_novel_vocab(self):
        # Novel demand phrase not covered by seed vocab.
        novel = "chemotherapy companion support"
        self.assertEqual(resolve_condition(novel), ("", ""))

        for i in range(6):
            create_match_run(
                user=self.patient_user,
                condition=novel if i < 4 else "diabetes",
                language="English",
                care_level="intermediate",
                query=f"need help with {novel}" if i < 4 else "diabetes check",
                emergency=False,
                weights_source="test",
                index_version="test",
                latency_ms=1,
            )
            create_match_run(
                user=self.patient_user,
                condition="wound care",
                language="English",
                care_level="basic",
                query="wound dressing",
                emergency=False,
                weights_source="test",
                index_version="test",
                latency_ms=1,
            )
        with self.settings(
            CF_ARTIFACT_DIR=str(self.cf_dir),
            CLUSTER_ARTIFACT_DIR=str(self.cluster_dir),
            CF_GATED_PROMOTION=False,
        ):
            reset_cf_cache()
            train_cf_als(factors=8, iterations=8, force=True)
            summary = build_and_persist_all(caregiver_k=3, intent_k=3, create_vocab_drafts=True)

        self.assertGreaterEqual(summary["intent_clusters"], 1)
        self.assertGreaterEqual(summary["vocab_novel"], 1)
        assignment = cluster_intent_embeddings(k=3)
        suggestions = suggest_vocab_from_intent_clusters(assignment)
        novel_rows = [s for s in suggestions if not s["already_in_vocab"]]
        self.assertGreaterEqual(len(novel_rows), 1)
        self.assertTrue(
            ConditionTerm.objects.filter(notes="step99-intent-cluster", active=False).exists()
        )


class AdminClusterApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin.clusters@example.com",
            password="pw-strong-123",
            role=Role.ADMIN,
        )
        self.client.force_authenticate(user=self.admin)

    def test_admin_clusters_endpoint(self):
        url = reverse("v1:admin_clusters")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("caregiver", res.data)
        self.assertIn("intent", res.data)
        self.assertIn("cold_start_seeded", res.data)

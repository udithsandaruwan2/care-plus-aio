"""Step 15b — canonical medical vocabulary."""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.vocab.models import ConditionTerm
from apps.vocab.resolver import clear_resolver_cache, resolve_condition
from apps.vocab.seed_data import SEED_CONDITIONS
from apps.voice.backends import extract_intent

User = get_user_model()


class VocabSeedTests(TestCase):
    def test_seed_has_at_least_30(self):
        self.assertGreaterEqual(len(SEED_CONDITIONS), 30)

    def test_seed_command_creates_active_terms(self):
        call_command("seed_vocab")
        clear_resolver_cache()
        self.assertGreaterEqual(ConditionTerm.objects.filter(active=True).count(), 30)

    def test_dengue_sinhala_resolves(self):
        call_command("seed_vocab")
        clear_resolver_cache()
        slug, canonical = resolve_condition("මට ඩෙංගු තියෙනවා")
        self.assertEqual(slug, "dengue")
        self.assertEqual(canonical, "Dengue")

    def test_unknown_returns_empty(self):
        call_command("seed_vocab")
        clear_resolver_cache()
        slug, canonical = resolve_condition("xyzzy not a real illness")
        self.assertEqual(slug, "")
        self.assertEqual(canonical, "")


@override_settings(VOICE_INTENT_BACKEND="stub")
class VocabWiredExtractorTests(TestCase):
    def setUp(self):
        call_command("seed_vocab")
        clear_resolver_cache()

    def test_stub_maps_dengue_sinhala_to_slug(self):
        out = extract_intent("මට ඩෙංගු තියෙනවා මට ඉක්මනින් එයා එක ඕනේ")
        self.assertEqual(out["condition"], "dengue")

    def test_sugar_problem_maps_to_diabetes(self):
        out = extract_intent("I have a sugar problem and need Sinhala care")
        self.assertEqual(out["condition"], "diabetes")


class VocabApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="vocab@example.com", password="pw-strong-123")
        call_command("seed_vocab")
        clear_resolver_cache()
        self.url = reverse("v1:vocab_conditions")

    def test_requires_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lists_at_least_30(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data["count"], 30)
        slugs = {row["slug"] for row in resp.data["results"]}
        self.assertIn("dengue", slugs)
        self.assertIn("diabetes", slugs)

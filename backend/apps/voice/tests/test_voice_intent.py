"""Step 14 acceptance: voice → structured intent (consent-gated).

Uses the deterministic stub extractor (no external calls). A Sinhala sentence
must yield {condition, language, care_level} and persist a VoiceIntent row,
and the AI-consent gate must block callers without consent.
"""

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope
from apps.voice.backends import extract_intent
from apps.voice.extraction import detect_language, detect_languages
from apps.voice.models import VoiceIntent

User = get_user_model()

SINHALA = "මට දියවැඩියාව තියෙනවා, සිංහල කතා කරන කෙනෙක් ඕන."


@override_settings(VOICE_INTENT_BACKEND="stub")
class VoiceIntentApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="p@example.com", password="pw-strong-123")
        self.url = reverse("v1:voice_intent")

    def _consent(self, granted=True):
        ConsentLog.objects.create(user=self.user, scope=ConsentScope.AI_PROCESSING, granted=granted)

    def test_requires_authentication(self):
        resp = self.client.post(self.url, {"text": SINHALA}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blocked_without_consent(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.url, {"text": SINHALA}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS)

    def test_sinhala_intent_extracted_and_persisted(self):
        self.client.force_authenticate(self.user)
        self._consent()
        resp = self.client.post(self.url, {"text": SINHALA}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["condition"], "diabetes")
        self.assertEqual(resp.data["language"], "Sinhala")
        self.assertIn("Sinhala", resp.data["languages"])
        self.assertEqual(resp.data["care_level"], "intermediate")
        self.assertEqual(resp.data["source"], "stub")

        row = VoiceIntent.objects.get(pk=resp.data["id"])
        self.assertEqual(row.user, self.user)
        self.assertEqual(row.condition, "diabetes")

    def test_language_hint_overrides_detection(self):
        self.client.force_authenticate(self.user)
        self._consent()
        resp = self.client.post(
            self.url, {"text": "I have asthma", "language": "English"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["language"], "English")
        self.assertEqual(resp.data["condition"], "asthma")


@override_settings(VOICE_INTENT_BACKEND="stub")
class ExtractorUnitTests(APITestCase):
    def test_tamil_script_detected(self):
        out = extract_intent("எனக்கு நீரிழிவு உள்ளது")
        self.assertEqual(out["language"], "Tamil")
        self.assertEqual(out["condition"], "diabetes")

    def test_urgency_and_advanced_level(self):
        out = extract_intent("emergency: need advanced cardiac care now")
        self.assertEqual(out["condition"], "cardiac")
        self.assertEqual(out["care_level"], "advanced")
        self.assertEqual(out["urgency"], "urgent")
        self.assertEqual(out["language"], "English")

    def test_sinhala_dengue_and_soon_urgency(self):
        out = extract_intent("මට ඩෙංගු තියෙනවා මට ඉක්මනින් එයා එක ඕනේ")
        self.assertEqual(out["condition"], "dengue")
        self.assertEqual(out["language"], "Sinhala")
        self.assertEqual(out["urgency"], "urgent")

    def test_singlish_mixed_languages(self):
        out = extract_intent("මට diabetes caregiver ඕනේ Sinhala speaking")
        self.assertEqual(out["condition"], "diabetes")
        self.assertEqual(out["language"], "Sinhala")
        self.assertEqual(out["languages"], ["Sinhala", "English"])

    def test_tanglish_mixed_languages(self):
        langs = detect_languages("எனக்கு diabetes care வேண்டும் please")
        self.assertEqual(langs, ["Tamil", "English"])
        self.assertEqual(detect_language("எனக்கு diabetes care வேண்டும் please"), "Tamil")

"""Dialogue turn routing (text-only; no live Gemini in unit tests)."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope
from apps.voice.dialogue import _route, process_turn

User = get_user_model()


class RouteUnitTests(TestCase):
    def test_greeting_is_chat(self):
        self.assertEqual(_route("hello there", {}, False), "CHAT")

    def test_care_need_clarify_when_incomplete(self):
        self.assertEqual(
            _route("I need a caregiver for diabetes", {"condition": "Diabetes"}, False),
            "CLARIFY",
        )

    def test_complete_intent_is_match(self):
        intent = {
            "condition": "Diabetes",
            "language": "Sinhala",
            "care_level": "intermediate",
        }
        self.assertEqual(_route("find me someone", intent, False), "MATCH")


@override_settings(VOICE_INTENT_BACKEND="stub", ASR_BACKEND="client", DIALOGUE_CHAT_BACKEND="stub")
class VoiceTurnApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="turn@example.com", password="pw-strong-123")
        ConsentLog.objects.create(
            user=self.user, scope=ConsentScope.AI_PROCESSING, granted=True
        )
        self.url = reverse("v1:voice_turn")

    def test_chat_turn_returns_reply(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.url, {"text": "hello"}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["route"], "CHAT")
        self.assertTrue(resp.data["reply"])
        self.assertEqual(resp.data["asr_source"], "client")

    def test_process_turn_empty(self):
        out = process_turn(user=self.user, client_text="")
        self.assertEqual(out["route"], "CHAT")
        self.assertIn("catch", out["reply"].lower())

"""Natural-conversation router fixtures (Step 15f)."""

from django.test import SimpleTestCase

from apps.voice.router import classify_turn


COMPLETE = {
    "condition": "diabetes",
    "language": "Sinhala",
    "care_level": "basic",
}


class RouterFixtureTests(SimpleTestCase):
    def test_thanks_after_match_is_chat_not_match(self):
        d = classify_turn("thank you", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "thanks")

    def test_sinhala_thanks_after_match(self):
        d = classify_turn("ස්තූතියි", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "thanks")

    def test_tamil_thanks_after_match(self):
        d = classify_turn("நன்றி", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "thanks")

    def test_ok_after_match_does_not_rematch(self):
        d = classify_turn("ok", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "affirm")

    def test_goodbye_clears_match(self):
        d = classify_turn("goodbye", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "CHAT")
        self.assertTrue(d.clear_match)

    def test_refine_closer_after_match(self):
        d = classify_turn("someone closer please", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "REFINE")

    def test_about_match_why_number_one(self):
        d = classify_turn(
            "why is number one ranked high?",
            COMPLETE,
            has_prior_match=True,
            has_history_match=True,
        )
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "about_match")

    def test_about_match_works_with_history_only(self):
        d = classify_turn(
            "why is number one ranked high?",
            COMPLETE,
            has_prior_match=False,
            has_history_match=True,
        )
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "about_match")

    def test_history_only_does_not_force_post_match_default(self):
        d = classify_turn(
            "hmm interesting",
            COMPLETE,
            has_prior_match=False,
            has_history_match=True,
        )
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "general")

    def test_request_action(self):
        d = classify_turn("request the first one", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "ACTION")

    def test_complete_intent_without_seek_is_chat(self):
        d = classify_turn("how are you?", COMPLETE, has_prior_match=False)
        self.assertEqual(d.route, "CHAT")
        self.assertNotEqual(d.situation, "match")

    def test_explicit_match_seek(self):
        d = classify_turn(
            "I need a caregiver for diabetes",
            {"condition": "diabetes", "language": "English", "care_level": "basic"},
            has_prior_match=False,
        )
        self.assertEqual(d.route, "MATCH")

    def test_greeting_is_chat(self):
        d = classify_turn("hello there", {}, has_prior_match=False)
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "greeting")

    def test_emergency(self):
        d = classify_turn("this is an emergency", COMPLETE, has_prior_match=False)
        self.assertEqual(d.route, "EMERGENCY")

    def test_incomplete_care_seek_clarifies(self):
        d = classify_turn(
            "find me a caregiver",
            {"condition": "diabetes"},
            has_prior_match=False,
        )
        self.assertEqual(d.route, "CLARIFY")

    def test_post_match_default_chat(self):
        d = classify_turn("hmm interesting", COMPLETE, has_prior_match=True)
        self.assertEqual(d.route, "CHAT")
        self.assertEqual(d.situation, "post_match_chat")

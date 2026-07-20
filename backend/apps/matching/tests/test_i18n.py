"""Tests for localized VEHMF copy (Sinhala / Tamil / English)."""

from django.test import SimpleTestCase

from apps.matching.i18n import localize_explanation, match_spoken_reply


class MatchI18nTests(SimpleTestCase):
    def test_sinhala_match_reply_is_fully_localized(self):
        results = [
            {
                "display_name": "Lakmali Herath",
                "score": 0.65,
                "explanation": "Matched because: strong medical/skill match.",
            }
        ]
        reply = match_spoken_reply(results, "si-LK")
        self.assertIn("Lakmali Herath", reply)
        self.assertIn("ගැලපෙන්නේ මෙම නිසාවෙන්", reply)
        self.assertNotIn("Matched because", reply)
        self.assertNotIn("score", reply.lower())

    def test_localize_explanation_tamil(self):
        out = localize_explanation(
            "Matched because: very close / short travel time.",
            "Tamil",
        )
        self.assertIn("பொருந்துவதற்கான காரணம்", out)
        self.assertNotIn("Matched because", out)

    def test_english_unchanged(self):
        en = "Matched because: strong medical/skill match."
        self.assertEqual(localize_explanation(en, "en-US"), en)

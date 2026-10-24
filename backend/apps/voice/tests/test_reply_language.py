"""A Tamil or Sinhala utterance is answered in that language."""

from __future__ import annotations

import unittest

from apps.voice.dialogue import reply_language_for_utterance
from apps.voice.extraction import detect_languages, spoken_reply_bcp47


class ReplyLanguageTests(unittest.TestCase):
    def test_tamil_script_wins_over_the_english_picker(self) -> None:
        self.assertEqual(
            reply_language_for_utterance("எனக்கு ஒரு caregiver வேண்டும்", "en-US"),
            "ta-LK",
        )

    def test_sinhala_script_wins_over_the_english_picker(self) -> None:
        self.assertEqual(
            reply_language_for_utterance("මට උපකාරකයෙක් ඕන", "en-US"),
            "si-LK",
        )

    def test_mixed_greeting_follows_sinhala(self) -> None:
        self.assertEqual(spoken_reply_bcp47("Hi, කොහොමද?"), "si-LK")
        self.assertEqual(
            reply_language_for_utterance("Hi, කොහොමද?", "en-US"),
            "si-LK",
        )

    def test_romanized_captions_follow_spoken_language(self) -> None:
        self.assertEqual(spoken_reply_bcp47("ayubowan kohomada"), "si-LK")
        self.assertEqual(spoken_reply_bcp47("mata caregiver kenek onee"), "si-LK")
        self.assertEqual(spoken_reply_bcp47("vanakkam enakku vendum"), "ta-LK")

    def test_clear_english_is_english_even_if_picker_is_sinhala(self) -> None:
        self.assertEqual(reply_language_for_utterance("hello", "si-LK"), "en-US")
        self.assertEqual(
            reply_language_for_utterance("I need a caregiver", "si-LK"),
            "en-US",
        )

    def test_short_followup_keeps_prior_sinhala(self) -> None:
        self.assertEqual(
            reply_language_for_utterance("hari", "en-US", prior_reply_lang="si-LK"),
            "si-LK",
        )

    def test_latin_text_keeps_the_picker_when_unclear(self) -> None:
        self.assertEqual(reply_language_for_utterance("hmm", "ta-LK"), "ta-LK")

    def test_detect_languages_includes_romanized_sinhala(self) -> None:
        langs = detect_languages("mata diabetes kenek onee")
        self.assertIn("Sinhala", langs)

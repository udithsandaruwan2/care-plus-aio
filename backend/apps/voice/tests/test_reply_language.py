"""A Tamil or Sinhala utterance is answered in that language."""

from __future__ import annotations

import unittest

from apps.voice.dialogue import reply_language_for_utterance


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

    def test_latin_text_keeps_the_picker(self) -> None:
        self.assertEqual(reply_language_for_utterance("I need a caregiver", "en-US"), "en-US")
        self.assertEqual(reply_language_for_utterance("I need a caregiver", "ta-LK"), "ta-LK")

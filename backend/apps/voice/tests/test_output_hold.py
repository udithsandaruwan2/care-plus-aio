"""Barge-in holds playback until the interrupted model turn actually ends."""

from django.test import SimpleTestCase

from apps.voice.output_hold import apply_output_hold


class OutputHoldTests(SimpleTestCase):
    def test_barge_keeps_the_old_reply_quiet_until_the_turn_ends(self):
        holding, release = apply_output_hold(
            holding=True, interrupted=False, turn_complete=False
        )
        self.assertTrue(holding)
        self.assertFalse(release)

        holding, release = apply_output_hold(
            holding=True, interrupted=True, turn_complete=False
        )
        self.assertFalse(holding)
        self.assertTrue(release)

    def test_a_normal_turn_end_does_not_toggle_playback(self):
        holding, release = apply_output_hold(
            holding=False, interrupted=False, turn_complete=True
        )
        self.assertFalse(holding)
        self.assertFalse(release)
